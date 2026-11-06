"""聚合排行、作者标注与案例缓存。"""

import hmac
import os
import re
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from common import (
    _aggregate_identity, _clean_map_field, _fingerprint, _map_hash, _module,
    _parse_json, _public_map_name, _public_text, _text)
from db import DB_PATH

bp = Blueprint('aggregates', __name__)

ANNOTATION_SOURCES = {"作者确认", "维护者确认", "社区反馈"}


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
