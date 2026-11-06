"""维护者案例复核：案例列表、knowledge.json 片段导出与合并。"""

import json
import re
import sqlite3
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from blueprints.admin import _admin_denied, _audit
from common import _fingerprint, normalize_version
from db import DB_PATH
from knowledge_merge import (
    KnowledgeError,
    export_fragment,
    load_knowledge,
    merge_cases,
    preview_case,
)
from settings import ADMIN_PAGE_SIZE_MAX

bp = Blueprint('cases', __name__)

SIGNATURE_RE = re.compile(r'^[0-9A-F]{12}$')
CASE_FIELDS = (
    'signature, map_hash, map_name, fingerprint, game_version, module, '
    'relative_offset, cause, source, confidence, annotator, occurrence, '
    'first_seen, last_seen, updated_at, merged_at, merged_key')


def _fetch_cases(signatures):
    placeholders = ','.join('?' for _ in signatures)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            f"SELECT {CASE_FIELDS} FROM knowledge_cases "
            f"WHERE signature IN ({placeholders}) ORDER BY updated_at DESC",
            signatures).fetchall()
    finally:
        conn.close()


def _like(value):
    return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def _mark_merged(signature, timestamp, key):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE knowledge_cases SET merged_at = ?, merged_key = ? "
            "WHERE signature = ?", (timestamp, key, signature))
        conn.commit()
    finally:
        conn.close()


@bp.route('/api/admin/cases', methods=['GET'])
def admin_case_list():
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
    raw_hash = (request.args.get('map_hash') or '').strip()
    if raw_hash:
        where.append("lower(map_hash) = ?")
        params.append(raw_hash.lower())
    map_name = (request.args.get('map') or '').strip()
    if map_name:
        where.append("map_name = ?")
        params.append(map_name)
    fingerprint = _fingerprint(request.args.get('fingerprint'))
    if fingerprint:
        where.append("fingerprint = ?")
        params.append(fingerprint)
    module = (request.args.get('module') or '').strip()
    if module:
        where.append("lower(module) = lower(?)")
        params.append(module)
    version = (request.args.get('version') or '').strip()
    if version:
        where.append("game_version = ?")
        params.append(normalize_version(version) or version)
    source = (request.args.get('source') or '').strip()
    if source:
        where.append("source = ?")
        params.append(source)
    merged = (request.args.get('merged') or '').strip()
    if merged == '0':
        where.append("merged_at IS NULL")
    elif merged == '1':
        where.append("merged_at IS NOT NULL")
    keyword = (request.args.get('q') or '').strip()
    if keyword:
        pattern = _like(keyword)
        where.append("(cause LIKE ? ESCAPE '\\' OR annotator LIKE ? ESCAPE '\\' "
                     "OR map_name LIKE ? ESCAPE '\\' OR signature LIKE ? ESCAPE '\\' "
                     "OR module LIKE ? ESCAPE '\\' OR relative_offset LIKE ? ESCAPE '\\')")
        params.extend([pattern] * 6)

    where_clause = " WHERE " + " AND ".join(where) if where else ""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_cases{where_clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {CASE_FIELDS} FROM knowledge_cases{where_clause} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]).fetchall()
    finally:
        conn.close()

    kb_error = None
    try:
        kb = load_knowledge()
    except KnowledgeError as exc:
        kb = {}
        kb_error = str(exc)

    items = []
    for row in rows:
        case = dict(row)
        if kb_error:
            case['merge'] = {'mergeable': False, 'reason': kb_error}
        else:
            case['merge'] = preview_case(case, kb)
        items.append(case)
    return jsonify({"total": total, "cases": items, "kb_error": kb_error})


@bp.route('/api/admin/cases/<signature>/export', methods=['GET'])
def admin_case_export(signature):
    denied = _admin_denied()
    if denied:
        return denied

    sig = (signature or '').strip().upper()
    if not SIGNATURE_RE.fullmatch(sig):
        return jsonify({"error": "not found", "message": "案例不存在"}), 404
    rows = _fetch_cases([sig])
    if not rows:
        return jsonify({"error": "not found", "message": "案例不存在"}), 404

    case = dict(rows[0])
    try:
        fragment, skipped = export_fragment([case])
    except KnowledgeError as exc:
        return jsonify({"error": "knowledge_error", "message": str(exc)}), 500
    if not fragment['modules']:
        reason = skipped[0]['reason'] if skipped else '案例无法合并'
        return jsonify({"error": "invalid_case", "message": reason}), 400

    module_key, versions = next(iter(fragment['modules'].items()))
    version, offsets = next(iter(versions.items()))
    target = f"{module_key}/{version}/{next(iter(offsets))}"
    _audit('export_case', sig, target)
    body = json.dumps(fragment, ensure_ascii=False, indent=2) + '\n'
    return Response(body, mimetype='application/json', headers={
        'Content-Disposition': f'attachment; filename="knowledge-case-{sig}.json"',
    })


@bp.route('/api/admin/cases/merge', methods=['POST'])
def admin_case_merge():
    denied = _admin_denied()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    raw = data.get('signatures')
    if not isinstance(raw, list) or not raw:
        return jsonify({"error": "invalid", "message": "请选择要合并的案例"}), 400
    signatures = []
    for value in raw:
        sig = str(value or '').strip().upper()
        if not SIGNATURE_RE.fullmatch(sig):
            return jsonify({"error": "invalid", "message": "案例签名格式无效"}), 400
        if sig not in signatures:
            signatures.append(sig)
    if len(signatures) > ADMIN_PAGE_SIZE_MAX:
        return jsonify({"error": "too_many",
                        "message": f"单次最多合并 {ADMIN_PAGE_SIZE_MAX} 条"}), 400

    overwrite = bool(data.get('overwrite'))
    dry_run = bool(data.get('dry_run'))
    rows = _fetch_cases(signatures)
    cases = [dict(row) for row in rows]
    found = {case['signature'] for case in cases}
    missing = [sig for sig in signatures if sig not in found]

    try:
        results, changed = merge_cases(cases, overwrite=overwrite, dry_run=dry_run)
    except KnowledgeError as exc:
        return jsonify({"error": "knowledge_error", "message": str(exc)}), 500
    results.extend({'signature': sig, 'status': 'not_found',
                    'reason': '案例不存在'} for sig in missing)

    merged = 0
    if changed and not dry_run:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for item in results:
            if item.get('status') == 'merged':
                _mark_merged(item['signature'], now, item['merged_key'])
                _audit('merge_case', item['signature'], item['merged_key'])
                merged += 1

    counts = {}
    for item in results:
        counts[item['status']] = counts.get(item['status'], 0) + 1
    return jsonify({
        "dry_run": dry_run,
        "changed": changed,
        "counts": counts,
        "results": results,
    })
