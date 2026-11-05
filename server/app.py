import os
import sqlite3
import json
import time
import hashlib
import hmac
import re
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='static')
DB_PATH = os.path.join(os.path.dirname(__file__), 'crash_data.db')

# --- 共享知识库：读取仓库根目录 knowledge.json，与客户端同源 ---
def _locate_knowledge():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.path.join(here, '..', 'knowledge.json'), os.path.join(here, 'knowledge.json')]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

def _load_kb():
    try:
        with open(_locate_knowledge(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] 知识库加载失败，将只使用日志中的本地分析结果: {e}")
        return {"modules": {}, "build_prefixes": {}, "exceptions": {}}

KB = _load_kb()
BUILD_PREFIXES = KB.get("build_prefixes", {})

def normalize_offset(value):
    if value is None:
        return None
    s = str(value).strip().upper()
    if s.startswith("0X"):
        s = s[2:]
    if not re.fullmatch(r"[0-9A-F]+", s) or len(s) > 8:
        return None
    return "0x" + s.zfill(8)

def normalize_version(text):
    if not text:
        return None
    letter = re.search(r"\b(1\.\d{2}[a-z])\b", str(text), re.IGNORECASE)
    if letter:
        return letter.group(1).lower()
    m = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?", str(text))
    if not m:
        return None
    parts = [g for g in m.groups() if g is not None]
    for size in (3, 2):
        key = ".".join(parts[:size])
        if key in BUILD_PREFIXES:
            return BUILD_PREFIXES[key]
    return None

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS crash_reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  map_name TEXT,
                  os_info TEXT,
                  crash_address TEXT,
                  log_content TEXT,
                  content_hash TEXT UNIQUE,
                  timestamp DATETIME,
                  analysis_result TEXT)''')
    
    # Auto migration: check for analysis_result and content_hash columns
    c.execute("PRAGMA table_info(crash_reports)")
    columns = [row[1] for row in c.fetchall()]
    if 'analysis_result' not in columns:
        print("[*] 正在为旧数据库添加 analysis_result 列...")
        c.execute("ALTER TABLE crash_reports ADD COLUMN analysis_result TEXT")
    
    if 'content_hash' not in columns:
        print("[*] 正在为旧数据库添加 content_hash 列...")
        c.execute("ALTER TABLE crash_reports ADD COLUMN content_hash TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON crash_reports(content_hash)")

    # P2.1 上报字段：版本 / 模块 / 归属 / 指纹 / 地图哈希 / 调用栈
    new_columns = {
        'module': 'TEXT',
        'relative_offset': 'TEXT',
        'game_version': 'TEXT',
        'attribution': 'TEXT',
        'confidence': 'REAL',
        'fingerprint': 'TEXT',
        'fingerprint_version': 'TEXT',
        'fingerprint_frames': 'TEXT',
        'map_hash': 'TEXT',
        'stack': 'TEXT',
        'dmp_info': 'TEXT',
    }
    for name, decl in new_columns.items():
        if name not in columns:
            print(f"[*] 正在为旧数据库添加 {name} 列...")
            c.execute(f"ALTER TABLE crash_reports ADD COLUMN {name} {decl}")

    # P2.2 聚合表：地图身份 + 栈指纹 → 签名 / 次数 / 作者标注
    c.execute('''CREATE TABLE IF NOT EXISTS crash_aggregates
                 (signature TEXT PRIMARY KEY,
                  map_key TEXT NOT NULL,
                  map_hash TEXT,
                  map_name TEXT,
                  fingerprint TEXT NOT NULL,
                  game_version TEXT,
                  module TEXT,
                  relative_offset TEXT,
                  attribution TEXT,
                  occurrence INTEGER NOT NULL DEFAULT 0,
                  annotation TEXT,
                  first_seen DATETIME,
                  last_seen DATETIME,
                  last_report_id INTEGER)''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_reports_map_fingerprint "
              "ON crash_reports(map_hash, fingerprint)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_reports_fingerprint "
              "ON crash_reports(fingerprint)")

    # P2.4 作者标注：根因 + 来源 / 置信度 / 标注人
    c.execute("PRAGMA table_info(crash_aggregates)")
    aggregate_columns = [row[1] for row in c.fetchall()]
    annotation_columns = {
        'annotation_source': 'TEXT',
        'annotation_confidence': 'REAL',
        'annotator': 'TEXT',
        'annotated_at': 'DATETIME',
    }
    for name, decl in annotation_columns.items():
        if name not in aggregate_columns:
            print(f"[*] 正在为聚合表添加 {name} 列...")
            c.execute(f"ALTER TABLE crash_aggregates ADD COLUMN {name} {decl}")

    # 案例缓存：作者标注按签名沉淀，供维护者合并进全局知识库
    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_cases
                 (signature TEXT PRIMARY KEY,
                  map_hash TEXT,
                  map_name TEXT,
                  fingerprint TEXT NOT NULL,
                  game_version TEXT,
                  module TEXT,
                  relative_offset TEXT,
                  cause TEXT NOT NULL,
                  source TEXT,
                  confidence REAL,
                  annotator TEXT,
                  occurrence INTEGER,
                  first_seen DATETIME,
                  last_seen DATETIME,
                  updated_at DATETIME)''')

    conn.commit()
    conn.close()

init_db()

def get_content_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def _text(value, limit):
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] or None


ATTRIBUTIONS = {"地图", "本机环境或对战平台", "编辑器", "暂无法确定"}


def _attribution(value):
    text = _text(value, 40)
    return text if text in ATTRIBUTIONS else None


def _module(value):
    text = _text(value, 120)
    return None if not text or text.lower() == "unknown" else text


def _confidence(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, number))


def _fingerprint(value):
    text = _text(value, 64)
    return text.upper() if text and re.fullmatch(r"[0-9A-Fa-f]{6,64}", text) else None


def _map_hash(value):
    text = _text(value, 64)
    return text.lower() if text and re.fullmatch(r"[0-9A-Fa-f]{32}", text) else None


def _json_text(value, limit=4000):
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except (TypeError, ValueError):
        return None


def _parse_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _frame_list(values, limit=10):
    if not isinstance(values, list):
        return None
    frames = [_text(value, 120) for value in values[:limit]]
    frames = [frame for frame in frames if frame]
    return _json_text(frames) if frames else None


def _stack_list(frames, limit=48):
    if not isinstance(frames, list):
        return None
    stack = []
    for frame in frames[:limit]:
        if not isinstance(frame, dict):
            continue
        module = _text(frame.get('module'), 120)
        rva = frame.get('rva')
        if isinstance(rva, bool) or not isinstance(rva, int) or rva < 0:
            rva = None
        if module or rva is not None:
            stack.append({'module': module, 'rva': rva})
    return _json_text(stack) if stack else None


def _clean_dmp(value):
    if not isinstance(value, dict):
        return None
    exception = value.get('exception')
    if isinstance(exception, dict):
        exception = exception.get('code')
    cleaned = {
        'engine': _text(value.get('engine'), 20),
        'exception': _text(exception, 20),
        'module': _module(value.get('module')),
        'rva': _text(value.get('rva'), 20),
        'file_version': _text(value.get('file_version'), 40),
        'version': _text(value.get('version'), 20),
        'fallback': bool(value.get('fallback')),
    }
    return _json_text(cleaned) if any(cleaned.values()) else None


# --- P2.2 聚合：地图身份优先用 map_hash，旧数据回退到地图名 ---

def _map_key(map_hash, map_name):
    if map_hash:
        return "md5:" + map_hash.lower()
    name = (map_name or "").strip().lower()
    if not name or name == "unknown":
        return None
    return "name:" + name


def _aggregate_signature(map_key, fingerprint):
    material = f"{map_key}|{fingerprint.upper()}"
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:12].upper()


def _aggregate_identity(aggregate):
    """返回定位该聚合样本的 SQL 条件：有哈希按哈希，否则按小写地图名。"""
    if aggregate["map_hash"]:
        return "fingerprint = ? AND lower(map_hash) = ?", [
            aggregate["fingerprint"], aggregate["map_hash"]]
    key = aggregate["map_key"] or ""
    name = key[5:] if key.startswith("name:") else (aggregate["map_name"] or "")
    return "fingerprint = ? AND lower(trim(map_name)) = ?", [
        aggregate["fingerprint"], name.strip().lower()]


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


def _upsert_aggregate(c, report_id, map_hash, map_name, fingerprint,
                      game_version, module, relative_offset, attribution,
                      timestamp):
    """新崩溃入库时累加聚合次数；同一日志只入库一次，所以不会重复计数。"""
    key = _map_key(map_hash, map_name)
    fp = (fingerprint or "").strip().upper()
    if not key or not fp:
        return
    map_hash = map_hash.lower() if map_hash else None
    signature = _aggregate_signature(key, fp)
    c.execute('''INSERT INTO crash_aggregates
                 (signature, map_key, map_hash, map_name, fingerprint,
                  game_version, module, relative_offset, attribution,
                  occurrence, annotation, first_seen, last_seen, last_report_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, ?, ?, ?)
                 ON CONFLICT(signature) DO UPDATE SET
                  occurrence = crash_aggregates.occurrence + 1,
                  last_seen = excluded.last_seen,
                  last_report_id = excluded.last_report_id,
                  map_hash = COALESCE(crash_aggregates.map_hash, excluded.map_hash),
                  map_name = COALESCE(crash_aggregates.map_name, excluded.map_name),
                  game_version = COALESCE(crash_aggregates.game_version, excluded.game_version),
                  module = COALESCE(crash_aggregates.module, excluded.module),
                  relative_offset = COALESCE(crash_aggregates.relative_offset, excluded.relative_offset),
                  attribution = COALESCE(crash_aggregates.attribution, excluded.attribution)''',
              (signature, key, map_hash, map_name, fp, game_version, module,
               relative_offset, attribution, timestamp, timestamp, report_id))


def rebuild_aggregates(conn=None):
    """按 map_key + 指纹重建聚合表；保留已有作者标注。"""
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        annotations = {
            row["signature"]: dict(row)
            for row in conn.execute(
                "SELECT signature, annotation, annotation_source, "
                "annotation_confidence, annotator, annotated_at "
                "FROM crash_aggregates "
                "WHERE annotation IS NOT NULL AND annotation <> ''")
        }
        conn.execute("DELETE FROM crash_aggregates")
        rows = conn.execute(
            "SELECT id, map_hash, map_name, fingerprint, game_version, module, "
            "relative_offset, attribution, timestamp FROM crash_reports "
            "WHERE fingerprint IS NOT NULL AND fingerprint <> '' "
            "ORDER BY timestamp, id")

        aggregates = {}
        for row in rows:
            key = _map_key(row["map_hash"], row["map_name"])
            fp = (row["fingerprint"] or "").strip().upper()
            if not key or not fp:
                continue
            signature = _aggregate_signature(key, fp)
            entry = aggregates.get(signature)
            if entry is None:
                entry = {
                    "signature": signature,
                    "map_key": key,
                    "map_hash": (row["map_hash"] or "").lower() or None,
                    "map_name": row["map_name"],
                    "fingerprint": fp,
                    "game_version": row["game_version"],
                    "module": row["module"],
                    "relative_offset": row["relative_offset"],
                    "attribution": row["attribution"],
                    "occurrence": 0,
                    "first_seen": row["timestamp"],
                }
                aggregates[signature] = entry
            else:
                for field in ("map_hash", "map_name", "game_version",
                              "module", "relative_offset", "attribution"):
                    if not entry[field] and row[field]:
                        entry[field] = row[field]
            entry["occurrence"] += 1
            entry["last_seen"] = row["timestamp"]
            entry["last_report_id"] = row["id"]

        for entry in aggregates.values():
            annotation = annotations.get(entry["signature"], {})
            conn.execute('''INSERT INTO crash_aggregates
                            (signature, map_key, map_hash, map_name, fingerprint,
                             game_version, module, relative_offset, attribution,
                             occurrence, annotation, annotation_source,
                             annotation_confidence, annotator, annotated_at,
                             first_seen, last_seen, last_report_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (entry["signature"], entry["map_key"], entry["map_hash"],
                          entry["map_name"], entry["fingerprint"],
                          entry["game_version"], entry["module"],
                          entry["relative_offset"], entry["attribution"],
                          entry["occurrence"],
                          annotation.get("annotation"),
                          annotation.get("annotation_source"),
                          annotation.get("annotation_confidence"),
                          annotation.get("annotator"),
                          annotation.get("annotated_at"),
                          entry["first_seen"], entry["last_seen"],
                          entry["last_report_id"]))
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


rebuild_aggregates()

def extract_crash_info(log_content):
    """
    Extract crash address and Game.dll relative offset from log content
    """
    addr = "Unknown"
    relative_offset = None
    
    # Try multiple formats for address
    match_a = re.search(r'occurred at (0x[0-9A-F]+)', log_content, re.IGNORECASE)
    match_b = re.search(r'at [0-9A-F]{4}:([0-9A-F]{8})', log_content, re.IGNORECASE)
    
    if match_a:
        addr = match_a.group(1).upper()
    elif match_b:
        addr = match_b.group(1).upper()
    
    if addr != "Unknown":
        # Try to find Game.dll offset in stack trace
        stack_match = re.search(rf'{addr}\s+[0-9A-F]{{8}}\s+0001:([0-9A-F]{{8}})\s+.*Game\.dll', log_content, re.IGNORECASE)
        if stack_match:
            relative_offset = normalize_offset(hex(int(stack_match.group(1), 16) + 0x1000))
        else:
            # Fallback for simple offsets
            clean_addr = addr.replace("0X", "")
            if len(clean_addr) <= 8:
                try:
                    val = int(clean_addr, 16)
                    if val < 0x01000000:
                        relative_offset = "0x" + clean_addr.zfill(8)
                except:
                    pass
    
    return addr, relative_offset

def extract_map_name(log_content):
    """
    Extract map name from log content
    """
    map_name = "Unknown"
    map_match = re.search(r'Played Maps\\(.*?)\.(?:w3x|w3m|w3n)', log_content, re.IGNORECASE)
    if map_match:
        full_name = map_match.group(1)
        suffix_match = re.search(r'\.(w3x|w3m|w3n)', log_content[map_match.start():map_match.end()], re.IGNORECASE)
        suffix = suffix_match.group(1) if suffix_match else "w3x"
        
        if '\\' in full_name:
            map_name = full_name.split('\\')[-1] + "." + suffix
        else:
            map_name = full_name + "." + suffix
            
    if map_name == "Unknown" or map_name == ".w3m" or map_name == ".w3x":
        alt_match = re.search(r'([^\\]+\.(?:w3x|w3m|w3n))', log_content, re.IGNORECASE)
        if alt_match:
            alt_name = alt_match.group(1)
            if "war3" not in alt_name.lower() and "exe" not in alt_name.lower():
                map_name = alt_name
    return map_name

def analyze_crash(log_content):
    addr, relative_offset = extract_crash_info(log_content)
    rva = normalize_offset(relative_offset)
    if not rva:
        return "无法定位崩溃原因（日志中没有可用的模块内偏移）"

    build = re.search(r'War3Build:\s*([0-9.]+)', log_content, re.IGNORECASE)
    version = normalize_version(build.group(1)) if build else None

    for mod, versions in KB.get("modules", {}).items():
        if version:
            entry = versions.get(version, {}).get(rva)
            if entry:
                return f"[{mod} {version}] {entry['desc']}"
        else:
            for ver, offsets in versions.items():
                entry = offsets.get(rva)
                if entry:
                    return f"[{mod} {ver}（版本未确认）] {entry['desc']}"

    if version:
        return f"该版本（{version}）知识库未收录偏移 {rva}"
    return f"未知偏移量 ({rva})"

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/author')
def author_page():
    return send_from_directory(app.static_folder, 'author.html')

@app.route('/api/report', methods=['POST'])
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

@app.route('/api/stats', methods=['GET'])
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

@app.route('/api/crashes', methods=['GET'])
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


@app.route('/api/aggregates', methods=['GET'])
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
    c.execute(f"SELECT signature, map_key, map_hash, map_name, fingerprint, "
              f"game_version, module, relative_offset, attribution, occurrence, "
              f"annotation, first_seen, last_seen, last_report_id "
              f"FROM crash_aggregates{where_clause} "
              f"ORDER BY occurrence DESC, last_seen DESC LIMIT ?",
              params + [limit])
    aggregates = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({"total": total, "aggregates": aggregates})


@app.route('/api/aggregate/<signature>', methods=['GET'])
def get_aggregate_detail(signature):
    """作者查询：聚合详情、30 天趋势与脱敏样本（不含原始日志与本机信息）。"""
    signature = (signature or '').strip().upper()
    if not re.fullmatch(r"[0-9A-F]{12}", signature):
        return jsonify({"error": "invalid signature"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT signature, map_key, map_hash, map_name, fingerprint, "
              "game_version, module, relative_offset, attribution, occurrence, "
              "annotation, annotation_source, annotation_confidence, annotator, "
              "annotated_at, first_seen, last_seen, last_report_id "
              "FROM crash_aggregates WHERE signature = ?", (signature,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404

    aggregate = dict(row)
    where, params = _aggregate_identity(aggregate)

    c.execute(f"SELECT COUNT(*) FROM crash_reports WHERE {where}", params)
    sample_total = c.fetchone()[0]

    c.execute(f"SELECT map_name, timestamp, game_version, attribution, confidence, "
              f"module, relative_offset, crash_address, analysis_result, stack, "
              f"fingerprint_frames, dmp_info FROM crash_reports WHERE {where} "
              f"ORDER BY timestamp DESC LIMIT 20", params)
    samples = []
    for item in c.fetchall():
        sample = dict(item)
        sample["stack"] = _parse_json(sample.pop("stack", None)) or []
        sample["fingerprint_frames"] = _parse_json(
            sample.pop("fingerprint_frames", None)) or []
        sample["dmp"] = _parse_json(sample.pop("dmp_info", None))
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


@app.route('/api/aggregate/<signature>/annotation', methods=['POST'])
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


@app.route('/api/knowledge/cases', methods=['GET'])
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2234, debug=True)
