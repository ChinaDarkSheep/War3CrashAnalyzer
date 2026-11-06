"""维护者管理端：令牌保护的列表 / 详情 / 预览 / 下载 / 删除 / 补跑入库。"""

import hmac
import io
import os
import re
import shutil
import sqlite3
import zipfile
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, send_file

from common import (
    _clean_map_field, _map_display_name, _map_hash_from_name, _map_key,
    _module, _parse_json, _preferred_map_name, _resolve_map_identity)
from db import DB_PATH
from diagnosis import _ingest_crash_records
from download_store import DownloadConfigError, get_download, save_download
from settings import (
    ADMIN_PAGE_SIZE_MAX,
    ADMIN_PREVIEW_BYTES,
    ADMIN_TOKEN,
    FEEDBACK_NOTE_MAX,
    FEEDBACK_STATUSES,
    RAW_RETENTION_DAYS,
    UPLOAD_ROOT,
)
from upload_store import (
    UploadError,
    _client_ip_hash,
    _decode_bytes,
    _ext_of,
    _parse_crash_zone,
    _parse_kk_zone,
    _public_upload,
    _representative_index,
    _upload_map_hash,
    _walk_files,
)

bp = Blueprint('admin', __name__)


def _admin_denied():
    if not ADMIN_TOKEN:
        return jsonify({
            "error": "admin_disabled",
            "message": "服务端未设置 WAR3_ADMIN_TOKEN，管理端已禁用",
        }), 503
    provided = (request.headers.get("X-Admin-Token") or "").strip()
    if not hmac.compare_digest(provided, ADMIN_TOKEN):
        return jsonify({"error": "forbidden", "message": "管理令牌无效"}), 403
    return None


def _audit(action, code, detail=''):
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO admin_audit (created_at, action, code, detail, ip_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), action, code,
                 (detail or '')[:500], _client_ip_hash()))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        print(f"[!] 管理操作审计写入失败: {exc}")


def _admin_upload(row):
    data = _public_upload(row)
    data.update({
        'ip_hash': row['ip_hash'],
        'raw_deleted_at': row['raw_deleted_at'],
    })
    return data


def _admin_upload_row(code):
    if not re.fullmatch(r'\d{6}', code or ''):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM raw_uploads WHERE code = ?", (code,)).fetchone()
    finally:
        conn.close()


_OVERVIEW_DAYS = (7, 30, 90)


def _rate(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _overview_issues(summary, quality):
    """把数据质量问题翻译成维护者能直接行动的提示。"""
    if not summary['reports']:
        return [{
            'level': 'info',
            'title': '范围内暂无入库崩溃',
            'detail': '换一个时间范围，或确认客户端上报与网页上传是否正常。',
        }]

    issues = []
    if quality['missing_identity']:
        issues.append({
            'level': 'warn',
            'title': f"{quality['missing_identity']} 条崩溃缺少地图身份",
            'detail': '没有地图哈希也没有可用地图名，这些日志只计入总览与实时诊断流，无法进入地图看板。',
        })
    if quality['md5_names']:
        issues.append({
            'level': 'info',
            'title': f"{quality['md5_names']} 条崩溃仍使用 MD5 文件名",
            'detail': '客户端未读到真实地图名时先用 MD5 文件名占位，出现友好地图名后会自动替换。',
        })
    if quality['missing_fingerprint']:
        issues.append({
            'level': 'warn',
            'title': f"{quality['missing_fingerprint']} 条崩溃没有栈指纹",
            'detail': '缺少指纹的崩溃无法参与聚合排行，需检查调用栈解析与日志完整性。',
        })
    author_rate = summary['author_rate']
    if author_rate is not None and author_rate < 0.5:
        issues.append({
            'level': 'warn',
            'title': f"地图作者填写率仅 {int(author_rate * 100)}%",
            'detail': '作者信息依赖客户端读取本地 w3x；玩家未选择地图或使用旧客户端时可能缺失。',
        })
    if summary['pending_feedback']:
        issues.append({
            'level': 'info',
            'title': f"{summary['pending_feedback']} 个上传待反馈",
            'detail': '在「上传管理」标记复核进度，提交者可通过上传码看到反馈。',
        })
    if not issues:
        issues.append({
            'level': 'ok',
            'title': '数据质量正常',
            'detail': '地图身份、作者、指纹与反馈队列均无待处理项。',
        })
    return issues


@bp.route('/api/admin/overview', methods=['GET'])
def admin_overview():
    """维护者运营总览：上传量、入库率、数据质量、趋势与聚合 Top。"""
    denied = _admin_denied()
    if denied:
        return denied

    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    if days not in _OVERVIEW_DAYS:
        days = 30
    since = f'-{days} days'

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        upload_row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(CASE WHEN has_crash = 1 THEN 1 ELSE 0 END), 0) AS crash_uploads, "
            "COALESCE(SUM(CASE WHEN has_kk = 1 THEN 1 ELSE 0 END), 0) AS kk_uploads, "
            "COALESCE(SUM(CASE WHEN COALESCE(report_count, 0) > 0 THEN 1 ELSE 0 END), 0) AS ingested, "
            "COALESCE(SUM(CASE WHEN raw_deleted_at IS NULL THEN 1 ELSE 0 END), 0) AS raw_available "
            "FROM raw_uploads "
            "WHERE date(created_at) >= date('now', 'localtime', ?)", (since,)).fetchone()

        feedback_counts = {key: 0 for key in FEEDBACK_STATUSES}
        for row in conn.execute(
                "SELECT COALESCE(feedback_status, 'pending') AS status, "
                "COUNT(*) AS count FROM raw_uploads "
                "WHERE date(created_at) >= date('now', 'localtime', ?) "
                "GROUP BY status", (since,)).fetchall():
            status = row['status'] if row['status'] in feedback_counts else 'pending'
            feedback_counts[status] += row['count']

        report_rows = conn.execute(
            "SELECT map_name, map_hash, map_author, fingerprint, upload_code, "
            "attribution, game_version FROM crash_reports "
            "WHERE date(timestamp) >= date('now', 'localtime', ?)",
            (since,)).fetchall()
        total_reports = len(report_rows)
        with_identity = with_author = with_fingerprint = uploaded = 0
        missing_identity = md5_names = missing_names = 0
        attributions = {}
        versions = {}
        for row in report_rows:
            map_name = row['map_name']
            map_hash = ((row['map_hash'] or '').strip().lower()
                        or _map_hash_from_name(map_name))
            clean_name = _clean_map_field(map_name)
            if map_hash or clean_name:
                with_identity += 1
            else:
                missing_identity += 1
            if _map_hash_from_name(map_name):
                md5_names += 1
            if not clean_name:
                missing_names += 1
            if _clean_map_field(row['map_author'], strip_path=False):
                with_author += 1
            if (row['fingerprint'] or '').strip():
                with_fingerprint += 1
            if (row['upload_code'] or '').strip():
                uploaded += 1
            attribution = (row['attribution'] or '').strip() or '未判定'
            attributions[attribution] = attributions.get(attribution, 0) + 1
            version = (row['game_version'] or '').strip() or '未知版本'
            versions[version] = versions.get(version, 0) + 1

        summary = {
            'uploads': upload_row['total'],
            'crash_uploads': upload_row['crash_uploads'],
            'kk_uploads': upload_row['kk_uploads'],
            'ingested_uploads': upload_row['ingested'],
            'ingest_rate': _rate(upload_row['ingested'],
                                 upload_row['crash_uploads']),
            'reports': total_reports,
            'identity_rate': _rate(with_identity, total_reports),
            'author_rate': _rate(with_author, total_reports),
            'fingerprint_rate': _rate(with_fingerprint, total_reports),
            'uploaded_reports': uploaded,
            'pending_feedback': feedback_counts['pending'],
            'raw_available': upload_row['raw_available'],
            'retention_days': RAW_RETENTION_DAYS,
        }
        quality = {
            'missing_identity': missing_identity,
            'missing_names': missing_names,
            'md5_names': md5_names,
            'missing_author': total_reports - with_author,
            'missing_fingerprint': total_reports - with_fingerprint,
        }

        upload_days = {row['day']: row['count'] for row in conn.execute(
            "SELECT date(created_at) AS day, COUNT(*) AS count FROM raw_uploads "
            "WHERE date(created_at) >= date('now', 'localtime', ?) "
            "GROUP BY day", (since,)).fetchall()}
        report_days = {row['day']: row['count'] for row in conn.execute(
            "SELECT date(timestamp) AS day, COUNT(*) AS count FROM crash_reports "
            "WHERE date(timestamp) >= date('now', 'localtime', ?) "
            "GROUP BY day", (since,)).fetchall()}
        today = date.today()
        trend = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            trend.append({
                'day': day,
                'uploads': upload_days.get(day, 0),
                'reports': report_days.get(day, 0),
            })

        aggregate_rows = conn.execute(
            "SELECT map_key, map_hash, map_name, map_author, fingerprint, module, "
            "relative_offset, attribution, game_version, occurrence, annotation, "
            "last_seen FROM crash_aggregates "
            "WHERE date(last_seen) >= date('now', 'localtime', ?) "
            "ORDER BY occurrence DESC, last_seen DESC", (since,)).fetchall()
    finally:
        conn.close()

    map_groups = {}
    fingerprint_groups = {}
    for row in aggregate_rows:
        key = row['map_key']
        entry = map_groups.get(key)
        if entry is None:
            entry = {
                'map_key': key,
                'map_hash': (row['map_hash'] or '').lower() or None,
                'map_name': None,
                'map_author': None,
                'occurrence': 0,
                'fingerprint_count': 0,
                'annotation_count': 0,
                'versions': [],
                'last_seen': None,
                'top': None,
            }
            map_groups[key] = entry
        entry['map_hash'] = (entry['map_hash']
                             or (row['map_hash'] or '').lower() or None)
        entry['map_name'] = _preferred_map_name(entry['map_name'], row['map_name'])
        entry['map_author'] = entry['map_author'] or _clean_map_field(
            row['map_author'], 80, strip_path=False)
        entry['occurrence'] += row['occurrence']
        entry['fingerprint_count'] += 1
        if row['annotation']:
            entry['annotation_count'] += 1
        version = row['game_version']
        if version and version not in entry['versions']:
            entry['versions'].append(version)
        if entry['top'] is None:
            entry['top'] = row
        entry['last_seen'] = max(entry['last_seen'] or '',
                                 row['last_seen'] or '') or None

        fingerprint = row['fingerprint']
        fp_entry = fingerprint_groups.get(fingerprint)
        if fp_entry is None:
            fp_entry = {
                'fingerprint': fingerprint,
                'occurrence': 0,
                'map_keys': set(),
                'module': None,
                'relative_offset': None,
                'attribution': None,
                'last_seen': None,
                'sample_map_key': key,
            }
            fingerprint_groups[fingerprint] = fp_entry
        fp_entry['occurrence'] += row['occurrence']
        fp_entry['map_keys'].add(key)
        fp_entry['module'] = fp_entry['module'] or row['module']
        fp_entry['relative_offset'] = (fp_entry['relative_offset']
                                       or row['relative_offset'])
        fp_entry['attribution'] = fp_entry['attribution'] or row['attribution']
        fp_entry['last_seen'] = max(fp_entry['last_seen'] or '',
                                    row['last_seen'] or '') or None

    top_maps = sorted(map_groups.values(),
                      key=lambda item: item['occurrence'], reverse=True)[:8]
    for item in top_maps:
        item['map_name'] = _map_display_name(item['map_name'], item['map_hash'])
        top = item.pop('top')
        item['top_fingerprint'] = None
        if top is not None:
            item['top_fingerprint'] = {
                'fingerprint': top['fingerprint'],
                'module': _module(top['module']),
                'relative_offset': top['relative_offset'],
                'attribution': top['attribution'],
                'occurrence': top['occurrence'],
            }

    top_fingerprints = sorted(
        fingerprint_groups.values(),
        key=lambda item: (item['occurrence'], len(item['map_keys'])),
        reverse=True)[:10]
    for item in top_fingerprints:
        item['map_count'] = len(item.pop('map_keys'))
        sample = map_groups.get(item.pop('sample_map_key'))
        item['sample_map_name'] = (
            _map_display_name(sample['map_name'], sample['map_hash'])
            if sample else None)
        item['module'] = _module(item['module'])

    return jsonify({
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'range': {
            'days': days,
            'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
            'until': datetime.now().strftime('%Y-%m-%d'),
        },
        'summary': summary,
        'quality': quality,
        'issues': _overview_issues(summary, quality),
        'feedback': [
            {'status': key, 'label': label, 'count': feedback_counts[key]}
            for key, label in FEEDBACK_STATUSES.items()
        ],
        'trend': trend,
        'top_maps': top_maps,
        'top_fingerprints': top_fingerprints,
        'attributions': [
            {'attribution': key, 'count': value}
            for key, value in sorted(attributions.items(),
                                     key=lambda item: item[1], reverse=True)
        ],
        'versions': [
            {'version': key, 'count': value}
            for key, value in sorted(versions.items(),
                                     key=lambda item: item[1], reverse=True)
        ],
    })


def _upload_storage_root(code):
    return os.path.join(UPLOAD_ROOT, code)


def _upload_file_path(code, rel):
    """把管理端传入的相对路径限制在上传目录内，拒绝穿越与绝对路径。"""
    if not re.fullmatch(r'\d{6}', code or '') or not rel:
        return None
    root = os.path.abspath(_upload_storage_root(code))
    target = os.path.abspath(os.path.join(
        root, *rel.replace('\\', '/').split('/')))
    if not target.startswith(root + os.sep):
        return None
    return target if os.path.isfile(target) else None


@bp.route('/api/admin/uploads', methods=['GET'])
def admin_upload_list():
    denied = _admin_denied()
    if denied:
        return denied

    try:
        limit = int(request.args.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    limit = min(ADMIN_PAGE_SIZE_MAX, max(1, limit))
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    where = []
    params = []
    keyword = (request.args.get('q') or '').strip()
    if keyword:
        like = f"%{keyword}%"
        where.append("(code LIKE ? OR map_name LIKE ? OR map_hash LIKE ? "
                     "OR crash_module LIKE ? OR relative_offset LIKE ? "
                     "OR analysis LIKE ? OR fingerprint LIKE ?)")
        params.extend([like] * 7)
    version = (request.args.get('version') or '').strip()
    if version:
        where.append("game_version = ?")
        params.append(version)
    attribution = (request.args.get('attribution') or '').strip()
    if attribution:
        where.append("attribution = ?")
        params.append(attribution)
    feedback = (request.args.get('feedback') or '').strip()
    if feedback in FEEDBACK_STATUSES:
        where.append("COALESCE(feedback_status, 'pending') = ?")
        params.append(feedback)
    has_kk = request.args.get('has_kk')
    if has_kk in ('0', '1'):
        where.append("has_kk = ?")
        params.append(int(has_kk))
    raw = request.args.get('raw')
    if raw == '1':
        where.append("raw_deleted_at IS NULL")
    elif raw == '0':
        where.append("raw_deleted_at IS NOT NULL")
    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM raw_uploads{where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM raw_uploads{where_sql} "
            "ORDER BY created_at DESC, code DESC LIMIT ? OFFSET ?",
            params + [limit, offset]).fetchall()
    finally:
        conn.close()
    return jsonify({
        'total': total,
        'limit': limit,
        'offset': offset,
        'items': [_admin_upload(row) for row in rows],
    })


@bp.route('/api/admin/uploads/<code>', methods=['GET'])
def admin_upload_detail(code):
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404

    files = []
    if not row['raw_deleted_at']:
        root = _upload_storage_root(row['code'])
        if os.path.isdir(root):
            for rel, full in _walk_files(root):
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = None
                files.append({'path': rel, 'size': size})

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        reports = conn.execute(
            "SELECT id, map_name, map_author, map_hash, game_version, module, "
            "relative_offset, attribution, confidence, fingerprint, timestamp, "
            "analysis_result, stack "
            "FROM crash_reports WHERE upload_code = ? ORDER BY id",
            (row['code'],)).fetchall()
        audits = conn.execute(
            "SELECT created_at, action, detail FROM admin_audit "
            "WHERE code = ? ORDER BY id DESC LIMIT 40",
            (row['code'],)).fetchall()
    finally:
        conn.close()

    return jsonify({
        'upload': _admin_upload(row),
        'files': files,
        'reports': [dict(report) for report in reports],
        'audits': [dict(item) for item in audits],
    })


@bp.route('/api/admin/uploads/<code>/preview', methods=['GET'])
def admin_upload_preview(code):
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404
    if row['raw_deleted_at']:
        return jsonify({"error": "expired", "message": "原始文件已到期删除"}), 410

    rel = (request.args.get('path') or '').strip()
    path = _upload_file_path(row['code'], rel)
    if not path:
        return jsonify({"error": "not_found", "message": "文件不存在"}), 404
    if _ext_of(path) in ('.dmp', '.mdmp', '.bin'):
        return jsonify({"error": "binary", "message": "二进制文件不支持在线预览，请直接下载"}), 415

    size = os.path.getsize(path)
    with open(path, 'rb') as handle:
        data = handle.read(ADMIN_PREVIEW_BYTES + 1)
    truncated = len(data) > ADMIN_PREVIEW_BYTES
    _audit('preview', row['code'], rel)
    return jsonify({
        'path': rel,
        'size': size,
        'truncated': truncated,
        'text': _decode_bytes(data[:ADMIN_PREVIEW_BYTES]),
    })


@bp.route('/api/admin/uploads/<code>/file', methods=['GET'])
def admin_upload_file(code):
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404
    if row['raw_deleted_at']:
        return jsonify({"error": "expired", "message": "原始文件已到期删除"}), 410

    rel = (request.args.get('path') or '').strip()
    path = _upload_file_path(row['code'], rel)
    if not path:
        return jsonify({"error": "not_found", "message": "文件不存在"}), 404

    _audit('download_file', row['code'], rel)
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


@bp.route('/api/admin/uploads/<code>/archive', methods=['GET'])
def admin_upload_archive(code):
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404
    if row['raw_deleted_at']:
        return jsonify({"error": "expired", "message": "原始文件已到期删除"}), 410

    root = _upload_storage_root(row['code'])
    if not os.path.isdir(root):
        return jsonify({"error": "expired", "message": "原始文件不存在"}), 410
    entries = _walk_files(root)
    if not entries:
        return jsonify({"error": "empty", "message": "该上传没有原始文件"}), 410

    # 单次上传上限 50 MB，直接在内存里打包，避免临时文件在 Windows 上被占用无法删除
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED,
                             allowZip64=True) as archive:
            for rel, full in entries:
                archive.write(full, arcname=rel)
    except Exception as exc:
        print(f"[!] 打包上传文件失败: {exc}")
        return jsonify({"error": "archive_failed", "message": "打包失败"}), 500
    buffer.seek(0)

    _audit('download_archive', row['code'], f'{len(entries)} files')
    return send_file(
        buffer, as_attachment=True, mimetype='application/zip',
        download_name=f'war3-upload-{row["code"]}.zip')


@bp.route('/api/admin/uploads/<code>/feedback', methods=['POST'])
def admin_upload_feedback(code):
    """维护者反馈：状态与备注会随上传码公开给提交者。"""
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "invalid_body",
            "message": "请求体必须是 JSON 对象",
        }), 400
    status = (data.get('status') or '').strip()
    note = (data.get('note') or '').strip()
    if status not in FEEDBACK_STATUSES:
        return jsonify({
            "error": "invalid_status",
            "message": "反馈状态无效",
            "allowed": list(FEEDBACK_STATUSES),
        }), 400
    if len(note) > FEEDBACK_NOTE_MAX:
        return jsonify({
            "error": "note_too_long",
            "message": f"反馈备注不能超过 {FEEDBACK_NOTE_MAX} 字",
        }), 400

    feedback_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE raw_uploads SET feedback_status = ?, feedback_note = ?, "
            "feedback_at = ? WHERE code = ?",
            (status, note or None, feedback_at, row['code']))
        conn.commit()
    finally:
        conn.close()

    label = FEEDBACK_STATUSES[status]
    _audit('feedback', row['code'], f"{label}: {note[:200]}")
    return jsonify({
        'status': 'ok',
        'code': row['code'],
        'feedback': {
            'status': status,
            'label': label,
            'note': note,
            'updated_at': feedback_at,
        },
    })


@bp.route('/api/admin/download', methods=['GET'])
def admin_download_get():
    denied = _admin_denied()
    if denied:
        return denied
    return jsonify(get_download())


@bp.route('/api/admin/download', methods=['POST'])
def admin_download_save():
    """更新客户端下载入口；链接留空即下线。"""
    denied = _admin_denied()
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "invalid_body",
            "message": "请求体必须是 JSON 对象",
        }), 400
    try:
        payload = save_download(
            version=data.get('version'),
            url=data.get('url'),
            extract_code=data.get('extract_code'),
            note=data.get('note'))
    except DownloadConfigError as exc:
        return jsonify({"error": exc.code, "message": exc.message}), 400

    if payload['configured']:
        detail = f"{payload['version']}: {payload['url']}" \
            if payload['version'] else payload['url']
    else:
        detail = '已下线下载入口'
    _audit('download_update', None, detail)
    return jsonify({'status': 'ok', 'download': payload})


@bp.route('/api/admin/uploads/<code>/delete', methods=['POST'])
def admin_upload_delete(code):
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404

    already_deleted = bool(row['raw_deleted_at'])
    deleted_at = row['raw_deleted_at']
    if not already_deleted:
        deleted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        shutil.rmtree(_upload_storage_root(row['code']), ignore_errors=True)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE raw_uploads SET raw_deleted_at = ? WHERE code = ?",
                (deleted_at, row['code']))
            conn.commit()
        finally:
            conn.close()
        _audit('delete_raw', row['code'], 'raw files removed')

    return jsonify({
        'status': 'deleted',
        'code': row['code'],
        'already_deleted': already_deleted,
        'raw_deleted_at': deleted_at,
    })


@bp.route('/api/admin/uploads/<code>/reingest', methods=['POST'])
def admin_upload_reingest(code):
    """补跑入库：用于 P2.7 之前的上传或入库失败的历史记录。"""
    denied = _admin_denied()
    if denied:
        return denied
    row = _admin_upload_row(code)
    if row is None:
        return jsonify({"error": "not_found", "message": "上传码不存在"}), 404
    if row['raw_deleted_at']:
        return jsonify({"error": "expired", "message": "原始文件已到期删除"}), 410

    root = _upload_storage_root(row['code'])
    crash_dir = os.path.join(root, 'crash')
    kk_dir = os.path.join(root, 'kk')
    try:
        crash_records = _parse_crash_zone(crash_dir) if os.path.isdir(crash_dir) else []
        kk_info = _parse_kk_zone(kk_dir) if os.path.isdir(kk_dir) else None
    except UploadError as exc:
        return jsonify({"error": "invalid", "message": exc.message}), 400
    if not crash_records:
        return jsonify({
            "error": "no_crash",
            "message": "该上传没有可入库的崩溃日志（仅平台日志）",
        }), 400

    representative_index = _representative_index(crash_records)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    summary = _parse_json(row['summary']) or {}
    map_meta = summary.get('map_meta') if isinstance(summary, dict) else None
    if not isinstance(map_meta, dict):
        map_meta = {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        outcome = _ingest_crash_records(
            conn, crash_records, row['code'], kk_info, timestamp,
            representative_index, map_meta)
        diagnosis = outcome.get('representative')
        if diagnosis:
            map_name, map_author = _resolve_map_identity(
                row['map_name'], (kk_info or {}).get('map_name'),
                map_meta.get('name'), map_meta.get('author'),
                (kk_info or {}).get('map_hash'))
            if not map_name:
                map_name = diagnosis.get('map_name')
            conn.execute('''UPDATE raw_uploads SET
                            fingerprint = COALESCE(?, fingerprint),
                            attribution = COALESCE(?, attribution),
                            confidence = COALESCE(?, confidence),
                            report_count = ?,
                            game_version = COALESCE(game_version, ?),
                            map_name = COALESCE(?, map_name),
                            map_author = COALESCE(map_author, ?),
                            map_hash = COALESCE(map_hash, ?),
                            crash_module = COALESCE(crash_module, ?),
                            relative_offset = COALESCE(relative_offset, ?),
                            analysis = COALESCE(analysis, ?)
                            WHERE code = ?''',
                         (diagnosis.get('fingerprint'),
                          diagnosis.get('attribution'),
                          diagnosis.get('confidence'),
                          outcome['inserted'] + outcome['duplicates'],
                          diagnosis.get('version'),
                          map_name,
                          map_author,
                          _upload_map_hash(map_name or row['map_name'], kk_info, True,
                                           crash_name=row['map_name']),
                          diagnosis.get('module'),
                          diagnosis.get('relative_offset'),
                          diagnosis.get('analysis'),
                          row['code']))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[!] 补跑入库失败: {exc}")
        return jsonify({"error": "server_error", "message": "入库失败"}), 500
    finally:
        conn.close()

    _audit('reingest', row['code'],
           f"inserted={outcome['inserted']} duplicates={outcome['duplicates']}")
    return jsonify({
        'status': 'ok',
        'inserted': outcome['inserted'],
        'duplicates': outcome['duplicates'],
    })
