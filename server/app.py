import os
import sqlite3
import json
import time
import hashlib
import re
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime

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
    letter = re.search(r"(1\.\d{2}[a-z])", str(text), re.IGNORECASE)
    if letter:
        return letter.group(1).lower()
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(text))
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
        
    conn.commit()
    conn.close()

init_db()

def get_content_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

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

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO crash_reports (map_name, os_info, crash_address, log_content, content_hash, timestamp, analysis_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (map_name, os_info, addr, log_content, content_hash, now_str, analysis))
        conn.commit()
        status = "success"
    except sqlite3.IntegrityError:
        status = "duplicate"
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
    
    conn.close()
    return jsonify({
        "total_reports": total,
        "top_maps": top_maps,
        "top_reasons": top_reasons,
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
    
    query = "SELECT id, map_name, crash_address, analysis_result, timestamp FROM crash_reports"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2234, debug=True)
