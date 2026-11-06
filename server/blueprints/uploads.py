"""玩家兜底上传：/api/upload 与上传码查询。"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from common import _module_from_analysis
from db import DB_PATH
from diagnosis import _ingest_crash_records
from settings import RAW_RETENTION_DAYS, UPLOAD_RATE_PER_HOUR, UPLOAD_ROOT
from upload_store import (
    UploadError,
    _client_ip_hash,
    _new_upload_code,
    _parse_crash_zone,
    _parse_kk_zone,
    _public_upload,
    _rate_limited,
    _representative_index,
    _request_zone_items,
    _tree_digest,
    _upload_map_hash,
    _write_zone,
    cleanup_expired_uploads,
)

bp = Blueprint('uploads', __name__)


def upload_too_large(_):
    return jsonify({
        "error": "too_large",
        "message": "单次上传上限为 50 MB，请只保留崩溃发生前后的日志",
    }), 413


@bp.route('/api/upload', methods=['POST'])
def upload_logs():
    """接收崩溃文件夹与 KK 会话日志，返回 6 位上传码；原始文件不进公开接口。"""
    cleanup_expired_uploads()
    ip_hash = _client_ip_hash()
    if _rate_limited('upload:' + ip_hash, UPLOAD_RATE_PER_HOUR):
        return jsonify({
            "error": "rate_limited",
            "message": "上传过于频繁，请一小时后再试或把上传码发给维护者",
        }), 429

    try:
        crash_items = _request_zone_items('crash')
        kk_items = _request_zone_items('kk')
    except UploadError as exc:
        return jsonify({"error": "invalid", "message": exc.message}), exc.status
    if not crash_items and not kk_items:
        return jsonify({"error": "empty", "message": "请至少选择一个崩溃记录文件夹或平台日志文件夹"}), 400

    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_ROOT, 'tmp'), exist_ok=True)
    temp_root = tempfile.mkdtemp(prefix='upload-', dir=os.path.join(UPLOAD_ROOT, 'tmp'))
    state = {'total_bytes': 0, 'file_count': 0}
    try:
        if crash_items:
            _write_zone('crash', crash_items, os.path.join(temp_root, 'crash'), state)
        if kk_items:
            _write_zone('kk', kk_items, os.path.join(temp_root, 'kk'), state)

        crash_records = _parse_crash_zone(os.path.join(temp_root, 'crash')) if crash_items else []
        kk_info = _parse_kk_zone(os.path.join(temp_root, 'kk')) if kk_items else None

        content_hash, stored_files = _tree_digest(temp_root)
        if stored_files == 0:
            raise UploadError("上传的文件均为空或类型不受支持")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            duplicate = conn.execute(
                "SELECT * FROM raw_uploads WHERE content_hash = ? "
                "AND raw_deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
                (content_hash,)).fetchone()
            if duplicate is not None:
                shutil.rmtree(temp_root, ignore_errors=True)
                payload = _public_upload(duplicate)
                payload.update({"status": "duplicate", "duplicate": True})
                return jsonify(payload)

            representative_index = _representative_index(crash_records)
            representative = (crash_records[representative_index]
                              if representative_index >= 0 else {})
            version = representative.get('game_version') or (kk_info or {}).get('game_version')
            map_name = representative.get('map_name')
            if not map_name or map_name == 'Unknown':
                map_name = (kk_info or {}).get('map_name')
            map_hash = _upload_map_hash(
                map_name, kk_info,
                allow_unknown=sum(1 for record in crash_records
                                  if record.get('text')) == 1)
            relative_offset = representative.get('relative_offset')
            analysis = representative.get('analysis')
            crash_module = _module_from_analysis(analysis)

            summary = {
                'crash': {
                    'records': len(crash_records),
                    'files': sum(record['files'] for record in crash_records),
                    'dmps': sum(record['dmps'] for record in crash_records),
                    'with_offset': sum(1 for record in crash_records
                                       if record['relative_offset']),
                } if crash_records else None,
                'kk': {
                    'files': kk_info['files'],
                    'session': kk_info['session'],
                    'map_path_found': bool(kk_info['map_path']),
                } if kk_info else None,
                'stored_files': stored_files,
            }

            created = datetime.now()
            expires = created + timedelta(days=RAW_RETENTION_DAYS)
            created_text = created.strftime('%Y-%m-%d %H:%M:%S')
            expires_text = expires.strftime('%Y-%m-%d %H:%M:%S')

            for _ in range(10):
                code = _new_upload_code(conn)
                final_root = os.path.join(UPLOAD_ROOT, code)
                if os.path.exists(final_root):
                    continue
                os.rename(temp_root, final_root)
                break
            else:
                raise UploadError("上传码生成失败，请稍后重试", 503)
            try:
                conn.execute('''INSERT INTO raw_uploads
                                (code, created_at, expires_at, content_hash, ip_hash,
                                 file_count, total_bytes, has_crash, has_kk,
                                 game_version, map_name, map_hash, crash_module,
                                 relative_offset, analysis, kk_session, summary,
                                 raw_deleted_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)''',
                             (code, created_text, expires_text, content_hash, ip_hash,
                              stored_files, state['total_bytes'], int(bool(crash_records)),
                              int(bool(kk_info)), version, map_name, map_hash,
                              crash_module, relative_offset, analysis,
                              (kk_info or {}).get('session'),
                              json.dumps(summary, ensure_ascii=False)))
            except Exception:
                shutil.rmtree(final_root, ignore_errors=True)
                raise

            # 入库失败不影响用户拿到上传码：原始文件已保留，可由维护者补跑
            try:
                conn.execute('SAVEPOINT ingest')
                outcome = _ingest_crash_records(
                    conn, crash_records, code, kk_info, created_text,
                    representative_index)
                if summary.get('crash') is not None:
                    summary['crash']['with_offset'] = outcome['with_offset']
                    conn.execute(
                        "UPDATE raw_uploads SET summary = ? WHERE code = ?",
                        (json.dumps(summary, ensure_ascii=False), code))
                diagnosis = outcome.get('representative')
                if diagnosis:
                    diagnosed_map = diagnosis.get('map_name')
                    if not diagnosed_map or diagnosed_map == 'Unknown':
                        diagnosed_map = None
                    conn.execute('''UPDATE raw_uploads SET
                                    game_version = COALESCE(?, game_version),
                                    map_name = COALESCE(?, map_name),
                                    map_hash = COALESCE(?, map_hash),
                                    crash_module = COALESCE(?, crash_module),
                                    relative_offset = COALESCE(?, relative_offset),
                                    analysis = COALESCE(?, analysis),
                                    fingerprint = ?, attribution = ?,
                                    confidence = ?, report_count = ?
                                    WHERE code = ?''',
                                 (diagnosis.get('version'),
                                  diagnosed_map,
                                  map_hash,
                                  diagnosis.get('module'),
                                  diagnosis.get('relative_offset'),
                                  diagnosis.get('analysis'),
                                  diagnosis.get('fingerprint'),
                                  diagnosis.get('attribution'),
                                  diagnosis.get('confidence'),
                                  outcome['inserted'] + outcome['duplicates'],
                                  code))
                conn.execute('RELEASE ingest')
            except Exception as exc:
                print(f"[!] 上传日志入库失败（原始文件已保留）: {exc}")
                try:
                    conn.execute('ROLLBACK TO ingest')
                    conn.execute('RELEASE ingest')
                except sqlite3.Error:
                    pass
            conn.commit()
            row = conn.execute("SELECT * FROM raw_uploads WHERE code = ?", (code,)).fetchone()
        finally:
            conn.close()
    except UploadError as exc:
        shutil.rmtree(temp_root, ignore_errors=True)
        return jsonify({"error": "invalid", "message": exc.message}), exc.status
    except Exception as exc:
        shutil.rmtree(temp_root, ignore_errors=True)
        print(f"[!] 上传处理失败: {exc}")
        return jsonify({"error": "server_error", "message": "服务器处理上传失败"}), 500

    payload = _public_upload(row)
    payload.update({"status": "success", "duplicate": False})
    return jsonify(payload)


@bp.route('/api/upload/<code>', methods=['GET'])
def upload_status(code):
    code = (code or '').strip()
    if not re.fullmatch(r'\d{6}', code):
        return jsonify({"error": "invalid code"}), 404
    ip_hash = _client_ip_hash()
    if _rate_limited('status:' + ip_hash, 240):
        return jsonify({"error": "rate_limited", "message": "查询过于频繁"}), 429

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM raw_uploads WHERE code = ?", (code,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "not found", "message": "上传码不存在或已过期"}), 404
    return jsonify(_public_upload(row))
