"""维护者管理端：令牌保护的列表 / 详情 / 预览 / 下载 / 删除 / 补跑入库。"""

import hmac
import io
import os
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from db import DB_PATH
from diagnosis import _ingest_crash_records
from settings import (
    ADMIN_PAGE_SIZE_MAX,
    ADMIN_PREVIEW_BYTES,
    ADMIN_TOKEN,
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
            "SELECT id, map_name, map_hash, game_version, module, relative_offset, "
            "attribution, confidence, fingerprint, timestamp, analysis_result, stack "
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        outcome = _ingest_crash_records(
            conn, crash_records, row['code'], kk_info, timestamp,
            representative_index)
        diagnosis = outcome.get('representative')
        if diagnosis:
            conn.execute('''UPDATE raw_uploads SET
                            fingerprint = COALESCE(?, fingerprint),
                            attribution = COALESCE(?, attribution),
                            confidence = COALESCE(?, confidence),
                            report_count = ?,
                            game_version = COALESCE(game_version, ?),
                            map_name = COALESCE(map_name, ?),
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
                          diagnosis.get('map_name'),
                          _upload_map_hash(
                              diagnosis.get('map_name') or row['map_name'],
                              kk_info, True),
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
