"""客户端自动上报、总览统计与最近崩溃流水。"""

import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request

from common import (
    _attribution, _clean_dmp, _confidence, _fingerprint, _frame_list,
    _map_hash, _module, _stack_list, _text, get_content_hash, normalize_offset,
    normalize_version)
from db import DB_PATH, _upsert_aggregate, rebuild_aggregates
from legacy_report import analyze_crash, extract_crash_info, extract_map_name

bp = Blueprint('reports', __name__)


@bp.route('/api/report', methods=['POST'])
def report_crash():
    data = request.json
    map_name = data.get('map', 'Unknown')
    os_info = data.get('os', 'Unknown')
    log_content = data.get('log_content', '')

    if not log_content:
        return jsonify({"status": "error", "message": "No log content"}), 400

    content_hash = get_content_hash(log_content)

    # 优先使用客户端提供的分析结果
    client_addr = data.get('crash_address')
    client_analysis = data.get('analysis_result')
    client_map = data.get('map')

    if client_addr and client_analysis:
        addr = client_addr
        analysis = client_analysis
    else:
        # 降级方案：服务器自行分析
        addr, relative_offset = extract_crash_info(log_content)
        addr = relative_offset if relative_offset else addr
        analysis = analyze_crash(log_content)

    # 地图名纠正：如果客户端传的是 Unknown，尝试从日志里重新提取
    if not client_map or client_map == "Unknown":
        map_name = extract_map_name(log_content)
    else:
        map_name = client_map

    module = _module(data.get('module'))
    relative_offset = normalize_offset(data.get('relative_offset'))
    game_version = normalize_version(_text(data.get('game_version'), 40))
    attribution = _attribution(data.get('attribution'))
    confidence = _confidence(data.get('confidence'))
    fingerprint = _fingerprint(data.get('fingerprint'))
    fingerprint_version = normalize_version(_text(data.get('fingerprint_version'), 40))
    fingerprint_frames = _frame_list(data.get('fingerprint_frames'))
    map_hash = _map_hash(data.get('map_hash'))
    stack = _stack_list(data.get('stack'))
    dmp_info = _clean_dmp(data.get('dmp'))
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    fields = (
        map_name,
        os_info,
        addr,
        log_content,
        content_hash,
        timestamp,
        analysis,
        module,
        relative_offset,
        game_version,
        attribution,
        confidence,
        fingerprint,
        fingerprint_version,
        fingerprint_frames,
        map_hash,
        stack,
        dmp_info,
    )

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO crash_reports
                     (map_name, os_info, crash_address, log_content, content_hash,
                      timestamp, analysis_result, module, relative_offset,
                      game_version, attribution, confidence, fingerprint,
                      fingerprint_version, fingerprint_frames, map_hash,
                      stack, dmp_info)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  fields)
        _upsert_aggregate(c, c.lastrowid, map_hash, map_name, fingerprint,
                          game_version, module, relative_offset, attribution,
                          timestamp)
        conn.commit()
        status = "success"
    except sqlite3.IntegrityError:
        status = "duplicate"
        # 旧记录可能缺少 P2 字段：同一日志再次上报时补齐，不覆盖已有值
        c.execute('''UPDATE crash_reports SET
                     module = COALESCE(module, ?),
                     relative_offset = COALESCE(relative_offset, ?),
                     game_version = COALESCE(game_version, ?),
                     attribution = COALESCE(attribution, ?),
                     confidence = COALESCE(confidence, ?),
                     fingerprint = COALESCE(fingerprint, ?),
                     fingerprint_version = COALESCE(fingerprint_version, ?),
                     fingerprint_frames = COALESCE(fingerprint_frames, ?),
                     map_hash = COALESCE(map_hash, ?),
                     stack = COALESCE(stack, ?),
                     dmp_info = COALESCE(dmp_info, ?)
                     WHERE content_hash = ?''',
                  fields[7:18] + (content_hash,))
        # 补齐字段可能改变所属指纹，重新聚合一次最稳妥
        rebuild_aggregates(conn)
        conn.commit()
    conn.close()

    return jsonify({"status": status, "analysis": analysis})


@bp.route('/api/stats', methods=['GET'])
def get_stats():
    map_filter = request.args.get('map')
    search_query = request.args.get('search')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    where_clauses = []
    params = []
    if map_filter:
        where_clauses.append("map_name = ?")
        params.append(map_filter)
    if search_query:
        where_clauses.append("(map_name LIKE ? OR crash_address LIKE ? OR analysis_result LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Top crashing maps
    c.execute("SELECT map_name, COUNT(*) as count FROM crash_reports GROUP BY map_name ORDER BY count DESC LIMIT 5")
    top_maps = [dict(row) for row in c.fetchall()]

    # Common crash reasons (based on analysis_result)
    c.execute(f"SELECT analysis_result as reason, COUNT(*) as count FROM crash_reports {where_clause} GROUP BY analysis_result ORDER BY count DESC LIMIT 5", params)
    top_reasons = [dict(row) for row in c.fetchall()]

    # Total count
    c.execute(f"SELECT COUNT(*) FROM crash_reports {where_clause}", params)
    total = c.fetchone()[0]

    # Daily trends (last 7 days)
    c.execute(f"SELECT date(timestamp) as day, COUNT(*) as count FROM crash_reports {where_clause} GROUP BY day ORDER BY day DESC LIMIT 7", params)
    trends = [dict(row) for row in c.fetchall()]

    # Get all maps for filter dropdown
    c.execute("SELECT DISTINCT map_name FROM crash_reports ORDER BY map_name")
    maps = [row['map_name'] for row in c.fetchall()]

    # P2.2 聚合排行（地图哈希/地图名 + 栈指纹）
    agg_where = []
    agg_params = []
    if map_filter:
        agg_where.append("map_name = ?")
        agg_params.append(map_filter)
    if search_query:
        agg_where.append("(map_name LIKE ? OR fingerprint LIKE ? "
                         "OR module LIKE ? OR annotation LIKE ?)")
        agg_params.extend([f"%{search_query}%"] * 4)
    agg_clause = " WHERE " + " AND ".join(agg_where) if agg_where else ""
    c.execute(f"SELECT signature, map_hash, map_name, fingerprint, game_version, "
              f"module, relative_offset, attribution, occurrence, annotation, "
              f"last_seen FROM crash_aggregates{agg_clause} "
              f"ORDER BY occurrence DESC, last_seen DESC LIMIT 10", agg_params)
    top_fingerprints = [dict(row) for row in c.fetchall()]

    conn.close()
    return jsonify({
        "total_reports": total,
        "top_maps": top_maps,
        "top_reasons": top_reasons,
        "top_fingerprints": top_fingerprints,
        "trends": trends[::-1], # chronological order
        "maps": maps
    })


@bp.route('/api/crashes', methods=['GET'])
def get_crashes():
    map_filter = request.args.get('map')
    search_query = request.args.get('search')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = ("SELECT id, map_name, map_hash, crash_address, module, relative_offset, "
             "game_version, attribution, confidence, fingerprint, fingerprint_version, "
             "analysis_result, timestamp FROM crash_reports")
    where_clauses = []
    params = []
    if map_filter:
        where_clauses.append("map_name = ?")
        params.append(map_filter)
    if search_query:
        where_clauses.append("(map_name LIKE ? OR crash_address LIKE ? OR analysis_result LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY timestamp DESC LIMIT 20"

    c.execute(query, params)
    crashes = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(crashes)
