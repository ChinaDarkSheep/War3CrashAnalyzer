"""聚合排行、作者标注与案例缓存。"""

import hmac
import os
import re
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from common import (
    _aggregate_identity, _clean_map_field, _fingerprint, _map_display_name,
    _map_hash, _module, _parse_json, _preferred_map_name, _public_map_name,
    _public_text, _text)
from db import DB_PATH

bp = Blueprint('aggregates', __name__)

ANNOTATION_SOURCES = {"作者确认", "维护者确认", "社区反馈"}

_MAP_KEY_MD5 = re.compile(r'^md5:[0-9a-f]{32}$')
_MAP_KEY_NAME = re.compile(r'^name:\S[\s\S]{0,499}$')



def _annotation_denied():
    """标注写入需要服务端配置的令牌；未配置时整体禁用，避免公开写接口。"""
    expected = os.environ.get("WAR3_ANNOTATION_TOKEN", "").strip()
    if not expected:
        return jsonify({
            "error": "annotation disabled",
            "message": "服务端未设置 WAR3_ANNOTATION_TOKEN，作者标注已禁用",
        }), 503
    provided = (request.headers.get("X-Annotation-Token") or "").strip()
    if not hmac.compare_digest(provided, expected):
        return jsonify({
            "error": "forbidden",
            "message": "标注令牌无效",
        }), 403
    return None


@bp.route('/api/aggregates', methods=['GET'])
def get_aggregates():
    """按地图身份 + 栈指纹聚合的排行；map_hash 精确优先，旧数据可按地图名查。"""
    raw_hash = (request.args.get('map_hash') or '').strip()
    map_hash = _map_hash(raw_hash) if raw_hash else None
    if raw_hash and not map_hash:
        return jsonify({"total": 0, "aggregates": []})
    map_name = (request.args.get('map') or '').strip()
    fingerprint = _fingerprint(request.args.get('fingerprint'))
    try:
        limit = max(1, min(200, int(request.args.get('limit', 50))))
    except (TypeError, ValueError):
        limit = 50

    where_clauses = []
    params = []
    if map_hash:
        where_clauses.append("map_hash = ?")
        params.append(map_hash)
    if map_name:
        where_clauses.append("map_name = ?")
        params.append(map_name)
    if fingerprint:
        where_clauses.append("fingerprint = ?")
        params.append(fingerprint)
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM crash_aggregates{where_clause}", params)
    total = c.fetchone()[0]
    c.execute(f"SELECT signature, map_key, map_hash, map_name, map_author, "
              f"fingerprint, game_version, module, relative_offset, attribution, "
              f"occurrence, annotation, first_seen, last_seen, last_report_id "
              f"FROM crash_aggregates{where_clause} "
              f"ORDER BY occurrence DESC, last_seen DESC LIMIT ?",
              params + [limit])
    aggregates = []
    for row in c.fetchall():
        item = dict(row)
        item['module'] = _module(item.get('module'))
        item['map_name'] = _public_map_name(item.get('map_name'))
        item['map_author'] = _clean_map_field(
            item.get('map_author'), 80, strip_path=False)
        aggregates.append(item)
    conn.close()
    return jsonify({"total": total, "aggregates": aggregates})


@bp.route('/api/aggregate/<signature>', methods=['GET'])
def get_aggregate_detail(signature):
    """作者查询：聚合详情、30 天趋势与脱敏样本（不含原始日志与本机信息）。"""
    signature = (signature or '').strip().upper()
    if not re.fullmatch(r"[0-9A-F]{12}", signature):
        return jsonify({"error": "invalid signature"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT signature, map_key, map_hash, map_name, map_author, "
              "fingerprint, game_version, module, relative_offset, attribution, "
              "occurrence, annotation, annotation_source, annotation_confidence, "
              "annotator, annotated_at, first_seen, last_seen, last_report_id "
              "FROM crash_aggregates WHERE signature = ?", (signature,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404

    aggregate = dict(row)
    where, params = _aggregate_identity(aggregate)
    aggregate['module'] = _module(aggregate.get('module'))
    aggregate['map_name'] = _public_map_name(aggregate.get('map_name'))
    aggregate['map_author'] = _clean_map_field(
        aggregate.get('map_author'), 80, strip_path=False)

    c.execute(f"SELECT COUNT(*) FROM crash_reports WHERE {where}", params)
    sample_total = c.fetchone()[0]

    c.execute(f"SELECT map_name, map_author, timestamp, game_version, attribution, "
              f"confidence, module, relative_offset, crash_address, analysis_result, "
              f"stack, fingerprint_frames, dmp_info FROM crash_reports WHERE {where} "
              f"ORDER BY timestamp DESC LIMIT 20", params)
    samples = []
    for item in c.fetchall():
        sample = dict(item)
        sample["stack"] = _parse_json(sample.pop("stack", None)) or []
        sample["fingerprint_frames"] = _parse_json(
            sample.pop("fingerprint_frames", None)) or []
        sample["dmp"] = _parse_json(sample.pop("dmp_info", None))
        sample["module"] = _module(sample.get("module"))
        sample["map_name"] = _public_map_name(sample.get("map_name"))
        sample["map_author"] = _clean_map_field(
            sample.get("map_author"), 80, strip_path=False)
        sample["analysis_result"] = _public_text(sample.get("analysis_result"))
        for frame in sample["stack"]:
            if isinstance(frame, dict):
                frame["module"] = _module(frame.get("module"))
        samples.append(sample)

    c.execute(f"SELECT date(timestamp) AS day, COUNT(*) AS count "
              f"FROM crash_reports WHERE {where} GROUP BY day", params)
    counts = {item["day"]: item["count"] for item in c.fetchall() if item["day"]}
    today = datetime.now().date()
    trend = []
    for offset in range(29, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        trend.append({"day": day, "count": counts.get(day, 0)})

    conn.close()
    return jsonify({
        "aggregate": aggregate,
        "trend": trend,
        "samples": samples,
        "sample_total": sample_total,
    })


@bp.route('/api/maps', methods=['GET'])
def get_maps():
    """地图维度总览：同一地图（哈希或名称）合并所有指纹。"""
    q = _text(request.args.get('q'), 120)
    version = _text(request.args.get('version'), 40)
    try:
        days = int(request.args.get('days', 0))
    except (TypeError, ValueError):
        days = 0
    days = days if 0 < days <= 3650 else 0
    try:
        limit = max(1, min(100, int(request.args.get('limit', 30))))
    except (TypeError, ValueError):
        limit = 30
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    where_clauses = []
    params = []
    if q:
        where_clauses.append("(map_name LIKE ? OR map_author LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if version:
        where_clauses.append("game_version = ?")
        params.append(version)
    if days:
        where_clauses.append("date(last_seen) >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    sorts = {
        "occurrence": "occurrence DESC, last_seen DESC",
        "fingerprints": "fingerprint_count DESC, occurrence DESC",
        "recent": "last_seen DESC, occurrence DESC",
        "name": "name_hint ASC",
    }
    order_by = sorts.get((request.args.get('sort') or '').strip(), sorts["occurrence"])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(f"SELECT COUNT(DISTINCT map_key) AS map_count, "
              f"COALESCE(SUM(occurrence), 0) AS total_occurrence, "
              f"COALESCE(SUM(CASE WHEN map_author IS NOT NULL "
              f"AND trim(map_author) <> '' THEN occurrence ELSE 0 END), 0) AS author_occurrence, "
              f"COALESCE(SUM(CASE WHEN date(last_seen) >= date('now', 'localtime', '-7 days') "
              f"THEN occurrence ELSE 0 END), 0) AS recent_occurrence "
              f"FROM crash_aggregates{where_clause}", params)
    summary_row = c.fetchone()
    summary = {
        "map_count": summary_row["map_count"],
        "total_occurrence": summary_row["total_occurrence"],
        "author_occurrence": summary_row["author_occurrence"],
        "recent_occurrence": summary_row["recent_occurrence"],
    }

    c.execute(f"SELECT map_key, MAX(map_hash) AS map_hash, MIN(map_name) AS name_hint, "
              f"COUNT(*) AS fingerprint_count, SUM(occurrence) AS occurrence, "
              f"MIN(first_seen) AS first_seen, MAX(last_seen) AS last_seen "
              f"FROM crash_aggregates{where_clause} GROUP BY map_key "
              f"ORDER BY {order_by} LIMIT ? OFFSET ?", params + [limit, offset])
    groups = [dict(row) for row in c.fetchall()]

    c.execute("SELECT DISTINCT game_version FROM crash_aggregates "
              "WHERE game_version IS NOT NULL AND game_version <> '' "
              "ORDER BY game_version")
    versions = [row["game_version"] for row in c.fetchall()]

    maps = []
    if groups:
        keys = [item["map_key"] for item in groups]
        placeholders = ", ".join("?" for _ in keys)
        c.execute(f"SELECT signature, map_key, map_hash, map_name, map_author, "
                  f"fingerprint, game_version, module, relative_offset, attribution, "
                  f"occurrence, annotation, last_seen FROM crash_aggregates "
                  f"WHERE map_key IN ({placeholders}) "
                  f"ORDER BY occurrence DESC, last_seen DESC", keys)
        details = {}
        for row in c.fetchall():
            details.setdefault(row["map_key"], []).append(dict(row))
        for group in groups:
            rows = details.get(group["map_key"], [])
            map_name = None
            map_author = None
            map_versions = []
            annotation_count = 0
            for row in rows:
                map_name = _preferred_map_name(map_name, row.get("map_name"))
                map_author = map_author or _clean_map_field(
                    row.get("map_author"), 80, strip_path=False)
                game_version = row.get("game_version")
                if game_version and game_version not in map_versions:
                    map_versions.append(game_version)
                if row.get("annotation"):
                    annotation_count += 1
            top = rows[0] if rows else {}
            maps.append({
                "map_key": group["map_key"],
                "map_hash": (group["map_hash"] or "").lower() or None,
                "map_name": _map_display_name(map_name, group["map_hash"]),
                "map_author": map_author,
                "occurrence": group["occurrence"],
                "fingerprint_count": group["fingerprint_count"],
                "versions": map_versions,
                "first_seen": group["first_seen"],
                "last_seen": group["last_seen"],
                "annotation_count": annotation_count,
                "top_fingerprint": {
                    "signature": top.get("signature"),
                    "fingerprint": top.get("fingerprint"),
                    "module": _module(top.get("module")),
                    "relative_offset": top.get("relative_offset"),
                    "attribution": top.get("attribution"),
                    "occurrence": top.get("occurrence"),
                } if top else None,
            })

    conn.close()
    return jsonify({
        "summary": summary,
        "total": summary["map_count"],
        "maps": maps,
        "versions": versions,
        "limit": limit,
        "offset": offset,
    })


@bp.route('/api/map', methods=['GET'])
def get_map_detail():
    """单张地图：指纹排行、版本分布、趋势与累计样本数。"""
    key = (request.args.get('key') or '').strip()
    if not (_MAP_KEY_MD5.match(key) or _MAP_KEY_NAME.match(key)):
        return jsonify({"error": "invalid map key", "message": "地图标识无效"}), 404
    try:
        days = max(7, min(180, int(request.args.get('days', 30))))
    except (TypeError, ValueError):
        days = 30

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT signature, map_key, map_hash, map_name, map_author, "
              "fingerprint, game_version, module, relative_offset, attribution, "
              "occurrence, annotation, annotation_source, annotation_confidence, "
              "annotator, annotated_at, first_seen, last_seen "
              "FROM crash_aggregates WHERE map_key = ? "
              "ORDER BY occurrence DESC, last_seen DESC", (key,))
    rows = [dict(row) for row in c.fetchall()]
    if not rows:
        conn.close()
        return jsonify({"error": "not found", "message": "地图不存在或暂无数据"}), 404

    map_name = None
    map_author = None
    map_hash = None
    versions = []
    occurrences = {}
    annotation_count = 0
    for row in rows:
        map_name = _preferred_map_name(map_name, row.get("map_name"))
        map_author = map_author or _clean_map_field(
            row.get("map_author"), 80, strip_path=False)
        map_hash = map_hash or (row.get("map_hash") or "").lower() or None
        game_version = row.get("game_version") or "未知版本"
        occurrences[game_version] = occurrences.get(game_version, 0) + row["occurrence"]
        if row.get("annotation"):
            annotation_count += 1
    versions = sorted(occurrences)

    fingerprints = []
    for row in rows:
        fingerprints.append({
            "signature": row["signature"],
            "fingerprint": row["fingerprint"],
            "game_version": row["game_version"],
            "module": _module(row.get("module")),
            "relative_offset": row.get("relative_offset"),
            "attribution": row.get("attribution"),
            "occurrence": row["occurrence"],
            "annotation": _public_text(row.get("annotation")),
            "annotation_source": row.get("annotation_source"),
            "annotation_confidence": row.get("annotation_confidence"),
            "annotator": _text(row.get("annotator"), 80),
            "annotated_at": row.get("annotated_at"),
            "first_seen": row.get("first_seen"),
            "last_seen": row.get("last_seen"),
        })

    names = sorted({(row.get("map_name") or "").strip().lower()
                    for row in rows if (row.get("map_name") or "").strip()})
    if key.startswith("md5:"):
        digest = key[4:]
        report_where = ("(lower(map_hash) = ? OR lower(trim(map_name)) IN (?, ?, ?, ?))")
        report_params = [digest, digest, digest + ".w3x", digest + ".w3m", digest + ".w3n"]
    else:
        report_where = "lower(trim(map_name)) IN (" + ", ".join("?" for _ in names) + ")"
        report_params = names
    c.execute(f"SELECT COUNT(*) FROM crash_reports WHERE {report_where}", report_params)
    sample_total = c.fetchone()[0]

    c.execute(f"SELECT date(timestamp) AS day, COUNT(*) AS count "
              f"FROM crash_reports WHERE {report_where} "
              f"AND date(timestamp) >= date('now', 'localtime', ?) GROUP BY day",
              report_params + [f"-{days - 1} days"])
    counts = {item["day"]: item["count"] for item in c.fetchall() if item["day"]}
    today = datetime.now().date()
    trend = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        trend.append({"day": day, "count": counts.get(day, 0)})

    conn.close()
    return jsonify({
        "map": {
            "map_key": key,
            "map_hash": map_hash,
            "map_name": _map_display_name(map_name, map_hash),
            "map_author": map_author,
            "occurrence": sum(row["occurrence"] for row in rows),
            "fingerprint_count": len(rows),
            "versions": versions,
            "first_seen": min((row.get("first_seen") for row in rows
                               if row.get("first_seen")), default=None),
            "last_seen": max((row.get("last_seen") for row in rows
                              if row.get("last_seen")), default=None),
            "annotation_count": annotation_count,
        },
        "version_distribution": [
            {"version": version, "count": count}
            for version, count in sorted(occurrences.items(),
                                         key=lambda item: item[1], reverse=True)],
        "fingerprints": fingerprints,
        "trend": trend,
        "trend_days": days,
        "sample_total": sample_total,
    })


@bp.route('/api/aggregate/<signature>/annotation', methods=['POST'])
def save_annotation(signature):
    """作者回填根因；需服务端配置 WAR3_ANNOTATION_TOKEN 并通过请求头携带。"""
    signature = (signature or '').strip().upper()
    if not re.fullmatch(r"[0-9A-F]{12}", signature):
        return jsonify({"error": "invalid signature"}), 404
    denied = _annotation_denied()
    if denied:
        return denied

    data = request.json or {}
    cause = _text(data.get('annotation'), 2000)
    if not cause:
        return jsonify({"error": "annotation required",
                        "message": "标注内容不能为空"}), 400
    source = _text(data.get('source'), 40)
    if source not in ANNOTATION_SOURCES:
        return jsonify({"error": "invalid source",
                        "message": "标注来源无效"}), 400
    try:
        confidence = float(data.get('confidence'))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid confidence",
                        "message": "置信度需为 0~1"}), 400
    if not 0 <= confidence <= 1:
        return jsonify({"error": "invalid confidence",
                        "message": "置信度需为 0~1"}), 400
    annotator = _text(data.get('annotator'), 80)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT signature, map_hash, map_name, fingerprint, game_version, "
              "module, relative_offset, occurrence, first_seen, last_seen "
              "FROM crash_aggregates WHERE signature = ?", (signature,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404

    c.execute('''UPDATE crash_aggregates SET
                 annotation = ?, annotation_source = ?, annotation_confidence = ?,
                 annotator = ?, annotated_at = ?
                 WHERE signature = ?''',
              (cause, source, confidence, annotator, now, signature))
    c.execute('''INSERT INTO knowledge_cases
                 (signature, map_hash, map_name, fingerprint, game_version,
                  module, relative_offset, cause, source, confidence, annotator,
                  occurrence, first_seen, last_seen, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(signature) DO UPDATE SET
                  cause = excluded.cause,
                  source = excluded.source,
                  confidence = excluded.confidence,
                  annotator = excluded.annotator,
                  occurrence = excluded.occurrence,
                  first_seen = COALESCE(knowledge_cases.first_seen, excluded.first_seen),
                  last_seen = excluded.last_seen,
                  updated_at = excluded.updated_at''',
              (signature, row["map_hash"], row["map_name"], row["fingerprint"],
               row["game_version"], row["module"], row["relative_offset"],
               cause, source, confidence, annotator, row["occurrence"],
               row["first_seen"], row["last_seen"], now))
    conn.commit()
    conn.close()
    return jsonify({
        "status": "success",
        "signature": signature,
        "annotation": cause,
        "source": source,
        "confidence": confidence,
        "annotator": annotator,
        "annotated_at": now,
    })


@bp.route('/api/knowledge/cases', methods=['GET'])
def get_knowledge_cases():
    """作者标注沉淀的案例缓存，供维护者筛选后合并进全局知识库。"""
    raw_hash = (request.args.get('map_hash') or '').strip()
    map_hash = _map_hash(raw_hash) if raw_hash else None
    if raw_hash and not map_hash:
        return jsonify({"total": 0, "cases": []})
    map_name = (request.args.get('map') or '').strip()
    fingerprint = _fingerprint(request.args.get('fingerprint'))
    try:
        limit = max(1, min(200, int(request.args.get('limit', 50))))
    except (TypeError, ValueError):
        limit = 50

    where_clauses = []
    params = []
    if map_hash:
        where_clauses.append("lower(map_hash) = ?")
        params.append(map_hash)
    if map_name:
        where_clauses.append("map_name = ?")
        params.append(map_name)
    if fingerprint:
        where_clauses.append("fingerprint = ?")
        params.append(fingerprint)
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM knowledge_cases{where_clause}", params)
    total = c.fetchone()[0]
    c.execute(f"SELECT signature, map_hash, map_name, fingerprint, game_version, "
              f"module, relative_offset, cause, source, confidence, annotator, "
              f"occurrence, first_seen, last_seen, updated_at "
              f"FROM knowledge_cases{where_clause} "
              f"ORDER BY updated_at DESC LIMIT ?", params + [limit])
    cases = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({"total": total, "cases": cases})
