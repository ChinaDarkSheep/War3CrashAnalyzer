import os
import sqlite3
import json
import time
import hashlib
import hmac
import re
import shutil
import tempfile
import threading
import zipfile
import secrets
from collections import defaultdict, deque
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='static')
DB_PATH = os.environ.get('WAR3_DB_PATH') or os.path.join(os.path.dirname(__file__), 'crash_data.db')

# --- P2.5 原始日志上传：50 MB / 6 位上传码 / 原始文件 7~15 天 ---
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_ZONE = 40
MAX_STORED_FILES = 120
MAX_ZIP_ENTRIES = 200
UPLOAD_EXTENSIONS = {'.txt', '.log', '.dmp', '.mdmp', '.bin', '.zip'}
ZIP_EXTENSIONS = {'.txt', '.log', '.dmp', '.mdmp', '.bin'}
CRASH_PRIMARY_NAMES = {'crash.txt', 'error.txt', 'war3crash.txt', 'bug.txt'}
KK_LOG_NAMES = {'platform.log', 'downloader.log', 'war3dll.log'}
UPLOAD_ROOT = os.environ.get('WAR3_UPLOAD_DIR') or os.path.join(
    os.path.dirname(__file__), 'uploads')
UPLOAD_DB_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS raw_uploads (
        code TEXT PRIMARY KEY,
        created_at DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        content_hash TEXT,
        ip_hash TEXT,
        file_count INTEGER,
        total_bytes INTEGER,
        has_crash INTEGER,
        has_kk INTEGER,
        game_version TEXT,
        map_name TEXT,
        map_hash TEXT,
        crash_module TEXT,
        relative_offset TEXT,
        analysis TEXT,
        kk_session TEXT,
        summary TEXT,
        raw_deleted_at DATETIME
    )
'''
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES + 2 * 1024 * 1024


def _env_int(name, default):
    try:
        return int((os.environ.get(name) or '').strip())
    except (TypeError, ValueError):
        return default


RAW_RETENTION_DAYS = min(15, max(7, _env_int('WAR3_RAW_RETENTION_DAYS', 14)))
UPLOAD_RATE_PER_HOUR = max(1, _env_int('WAR3_UPLOAD_RATE', 10))
UPLOAD_SALT = (os.environ.get('WAR3_UPLOAD_SALT') or secrets.token_hex(16)).encode('utf-8')
UPLOAD_ROOT = os.path.abspath(UPLOAD_ROOT)

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

    # P2.5 原始日志上传：只记账单与派生字段，原始文件另存私有目录
    c.execute(UPLOAD_DB_SCHEMA)
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_uploads_hash "
              "ON raw_uploads(content_hash)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_uploads_expires "
              "ON raw_uploads(expires_at)")

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

class UploadError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _decode_bytes(data):
    for encoding in ('utf-8-sig', 'gbk', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1', errors='ignore')


def _safe_relative(raw, fallback):
    """把浏览器传入的相对路径收敛成安全路径；含 .. 或缺文件名时返回 None。"""
    raw = (raw or '').replace('\\', '/')
    parts = []
    for part in raw.split('/'):
        part = part.strip()
        if not part or part == '.':
            continue
        if part == '..':
            return None
        part = re.sub(r'[\x00-\x1f<>:"|?*]', '_', part).strip()[:120]
        if part:
            parts.append(part)
    if not parts and fallback:
        parts = [fallback]
    if not parts:
        return None
    return '/'.join(parts[-6:])


def _ext_of(name):
    return os.path.splitext(name)[1].lower()


def _request_zone_items(zone):
    """读取 multipart 中的文件与可选相对路径，顺序一一对应。"""
    files = request.files.getlist(zone)
    paths = []
    raw_paths = request.form.get(f'{zone}_paths')
    if raw_paths:
        try:
            parsed = json.loads(raw_paths)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            paths = [item if isinstance(item, str) else '' for item in parsed[:len(files)]]
    items = []
    for index, storage in enumerate(files):
        filename = (storage.filename or '').replace('\\', '/')
        fallback = os.path.basename(filename)
        rel = _safe_relative(paths[index] if index < len(paths) else fallback, fallback)
        if not rel:
            raise UploadError("文件名或路径非法")
        items.append((storage, rel))
    return items


def _extract_zip(zip_path, dest_dir, budget):
    """安全展开 zip：拒绝加密/链接/穿越/非白名单类型，并限制条目与解压体积。"""
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise UploadError("压缩包无法解析，可能已损坏")
    written = 0
    count = 0
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise UploadError(f"压缩包条目过多（上限 {MAX_ZIP_ENTRIES}）")
        for info in infos:
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise UploadError("不支持加密压缩包")
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise UploadError("压缩包内不允许符号链接")
            rel = _safe_relative(info.filename, '')
            if not rel:
                raise UploadError("压缩包内路径非法")
            if _ext_of(rel) not in ZIP_EXTENSIONS:
                raise UploadError("压缩包内含不允许的文件类型")
            if written + info.file_size > budget:
                raise UploadError("压缩包解压后体积超过 50 MB 上限", 413)
            target = os.path.join(dest_dir, *rel.split('/'))
            root = os.path.abspath(dest_dir) + os.sep
            if not os.path.abspath(target).startswith(root):
                raise UploadError("压缩包内路径非法")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            copied = 0
            with archive.open(info) as src, open(target, 'wb') as dst:
                while True:
                    chunk = src.read(64 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if written + copied > budget:
                        dst.close()
                        os.remove(target)
                        raise UploadError("压缩包解压后体积超过 50 MB 上限", 413)
                    dst.write(chunk)
            written += copied
            count += 1
    return written, count


def _write_zone(zone, items, dest_dir, state):
    if not items:
        return
    if len(items) > MAX_FILES_PER_ZONE:
        raise UploadError(f"{zone} 文件数超过上限（{MAX_FILES_PER_ZONE}）")
    for storage, rel in items:
        extension = _ext_of(rel)
        if extension not in UPLOAD_EXTENSIONS:
            raise UploadError(f"不支持的文件类型：{os.path.basename(rel)}")
        target = os.path.join(dest_dir, *rel.split('/'))
        root = os.path.abspath(dest_dir) + os.sep
        if not os.path.abspath(target).startswith(root):
            raise UploadError("文件路径非法")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        size = 0
        with open(target, 'wb') as dst:
            while True:
                chunk = storage.stream.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                state['total_bytes'] += len(chunk)
                if state['total_bytes'] > MAX_UPLOAD_BYTES:
                    raise UploadError("上传内容超过 50 MB 上限", 413)
                dst.write(chunk)
        if size == 0:
            os.remove(target)
            continue
        if extension == '.zip':
            try:
                written, count = _extract_zip(
                    target, dest_dir, MAX_UPLOAD_BYTES - state['total_bytes'])
            finally:
                if os.path.exists(target):
                    os.remove(target)
            state['total_bytes'] += written
            state['file_count'] += count
        else:
            state['file_count'] += 1
        if state['file_count'] > MAX_STORED_FILES:
            raise UploadError(f"单次上传文件数超过上限（{MAX_STORED_FILES}）")


def _walk_files(root):
    entries = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            entries.append((rel, full))
    entries.sort()
    return entries


def _tree_digest(root):
    digest = hashlib.sha256()
    entries = _walk_files(root)
    for rel, full in entries:
        digest.update(rel.encode('utf-8'))
        digest.update(b'\0')
        with open(full, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        digest.update(b'\0')
    return digest.hexdigest(), len(entries)


PRIMARY_PRIORITY = {
    'war3crash.txt': 0,
    'crash.txt': 0,
    'error.txt': 1,
    'bug.txt': 2,
}


def _primary_priority(filename):
    """Errors 里的日志常带时间前缀，如 `2026-10-14 19.11.29 Crash.txt`。"""
    lower = filename.lower()
    for primary, priority in PRIMARY_PRIORITY.items():
        if lower == primary or lower.endswith(' ' + primary) or lower.endswith('_' + primary):
            return priority
    return None


def _parse_crash_zone(root):
    """每个子目录视为一次崩溃记录，取优先级最高的文本日志做诊断。"""
    groups = defaultdict(list)
    for rel, full in _walk_files(root):
        groups[os.path.dirname(rel)].append((rel, full))
    records = []
    for _, files in sorted(groups.items()):
        primaries = sorted(
            ((rel, full) for rel, full in files
             if _primary_priority(os.path.basename(rel)) is not None),
            key=lambda item: (_primary_priority(os.path.basename(item[0])), item[0]))
        dmps = [rel for rel, _ in files if _ext_of(rel) in ('.dmp', '.mdmp')]
        if not primaries and not dmps:
            continue
        version = map_name = offset = analysis = None
        if primaries:
            with open(primaries[0][1], 'rb') as handle:
                text = _decode_bytes(handle.read(4 * 1024 * 1024))
            build = re.search(r'War3Build:\s*([0-9.]+)', text, re.IGNORECASE)
            version = normalize_version(build.group(1)) if build else None
            map_name = extract_map_name(text)
            _, offset = extract_crash_info(text)
            offset = normalize_offset(offset)
            analysis = analyze_crash(text)
        records.append({
            'files': len(files),
            'dmps': len(dmps),
            'game_version': version,
            'map_name': map_name,
            'relative_offset': offset,
            'analysis': analysis,
        })
    if not records:
        raise UploadError("崩溃文件夹中未找到 Crash.txt / Error.txt / War3Crash.txt / Bug.txt 或 .dmp")
    return records


SESSION_PATTERN = re.compile(r'^\d{4}_\d{2}_\d{2} \d{2}_\d{2}_\d{2}\.\d{3}$')


def _parse_kk_zone(root):
    files = _walk_files(root)
    names = {os.path.basename(rel).lower() for rel, _ in files}
    if not names & KK_LOG_NAMES:
        raise UploadError("平台日志文件夹中未找到 platform.log / downloader.log / war3dll.log")

    texts = []
    session = None
    pid = None
    for rel, full in files:
        base = os.path.basename(rel).lower()
        segments = rel.split('/')
        for index, segment in enumerate(segments[:-1]):
            if SESSION_PATTERN.match(segment):
                session = segment
            if (segment == 'war3' and index + 1 < len(segments) - 1
                    and segments[index + 1].isdigit()):
                pid = segments[index + 1]
        if base in KK_LOG_NAMES:
            with open(full, 'rb') as handle:
                texts.append(_decode_bytes(handle.read(4 * 1024 * 1024)))
    text = '\n'.join(texts)

    versions = re.findall(r'(?:game\.dll|war3\.exe)\s*=\s*([0-9.]+)', text, re.IGNORECASE)
    version = normalize_version(versions[-1]) if versions else None

    map_names = re.findall(r'wa\(660\),\s*map:\s*(.+)', text)
    map_name = map_names[-1].strip() if map_names else None

    paths = re.findall(r'wa\(661\),\s*path:\s*(.+)', text)
    map_path = paths[-1].strip() if paths else None

    md5s = re.findall(r'md5\(([0-9A-Fa-f]{32})\)', text, re.IGNORECASE)
    if not md5s:
        md5s = re.findall(r'([0-9A-Fa-f]{32})\.(?:w3x|w3m|w3n)', text, re.IGNORECASE)
    map_hash = _map_hash(md5s[-1]) if md5s else None

    return {
        'files': len(files),
        'game_version': version,
        'map_name': map_name,
        'map_path': map_path,
        'map_hash': map_hash,
        'session': session,
        'pid': pid,
    }


def _new_upload_code(conn):
    for _ in range(30):
        code = str(secrets.randbelow(900000) + 100000)
        row = conn.execute("SELECT 1 FROM raw_uploads WHERE code = ?", (code,)).fetchone()
        if row is None:
            return code
    raise UploadError("上传码生成失败，请稍后重试", 503)


_rl_lock = threading.Lock()
_rl_hits = defaultdict(deque)


def _rate_limited(bucket, limit):
    now = time.time()
    window = now - 3600
    with _rl_lock:
        hits = _rl_hits[bucket]
        while hits and hits[0] < window:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


def _client_ip_hash():
    ip = (request.remote_addr or 'unknown').strip()
    return hmac.new(UPLOAD_SALT, ip.encode('utf-8'), hashlib.sha256).hexdigest()[:16]


_cleanup_lock = threading.Lock()
_last_cleanup = 0.0


def cleanup_expired_uploads(force=False):
    """删除过期上传的原始文件；只保留派生元数据，便于按上传码回查。"""
    global _last_cleanup
    now_monotonic = time.time()
    with _cleanup_lock:
        if not force and now_monotonic - _last_cleanup < 600:
            return
        _last_cleanup = now_monotonic
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    now = datetime.now()
    now_text = now.strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT code, expires_at, raw_deleted_at FROM raw_uploads").fetchall()
        known = set()
        for row in rows:
            known.add(row['code'])
            if row['raw_deleted_at']:
                continue
            try:
                expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
            except (TypeError, ValueError):
                expires = now
            if expires > now:
                continue
            target = os.path.join(UPLOAD_ROOT, row['code'])
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            conn.execute("UPDATE raw_uploads SET raw_deleted_at = ? WHERE code = ?",
                         (now_text, row['code']))
        conn.commit()

        for name in os.listdir(UPLOAD_ROOT):
            path = os.path.join(UPLOAD_ROOT, name)
            if name == 'tmp':
                cutoff = now_monotonic - 24 * 3600
                for sub in os.listdir(path):
                    sub_path = os.path.join(path, sub)
                    try:
                        if os.path.getmtime(sub_path) < cutoff:
                            shutil.rmtree(sub_path, ignore_errors=True)
                    except OSError:
                        pass
                continue
            if not re.fullmatch(r'\d{6}', name) or name in known:
                continue
            try:
                if os.path.getmtime(path) < now_monotonic - 3600:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass
    finally:
        conn.close()


def _public_upload(row):
    summary = _parse_json(row['summary']) or {}
    return {
        'code': row['code'],
        'created_at': row['created_at'],
        'expires_at': row['expires_at'],
        'retention_days': RAW_RETENTION_DAYS,
        'raw_available': not bool(row['raw_deleted_at']),
        'file_count': row['file_count'],
        'total_bytes': row['total_bytes'],
        'has_crash': bool(row['has_crash']),
        'has_kk': bool(row['has_kk']),
        'game_version': row['game_version'],
        'map_name': row['map_name'],
        'map_hash': row['map_hash'],
        'module': row['crash_module'],
        'relative_offset': row['relative_offset'],
        'analysis': row['analysis'],
        'kk_session': row['kk_session'],
        'summary': summary,
    }


def _module_from_analysis(analysis):
    match = re.match(r'\[([^\s\]]+)', analysis or '')
    return _module(match.group(1)) if match else None


@app.errorhandler(413)
def upload_too_large(_):
    return jsonify({
        "error": "too_large",
        "message": "单次上传上限为 50 MB，请只保留崩溃发生前后的日志",
    }), 413


@app.route('/upload')
def upload_page():
    return send_from_directory(app.static_folder, 'upload.html')


@app.route('/u/<code>')
def upload_status_page(code):
    return send_from_directory(app.static_folder, 'upload_status.html')


@app.route('/api/upload', methods=['POST'])
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

            representative = max(
                crash_records,
                key=lambda record: (
                    record['relative_offset'] is not None,
                    record['dmps'] > 0,
                    record['files'],
                )) if crash_records else {}
            version = representative.get('game_version') or (kk_info or {}).get('game_version')
            map_name = representative.get('map_name')
            if not map_name or map_name == 'Unknown':
                map_name = (kk_info or {}).get('map_name')
            map_hash = (kk_info or {}).get('map_hash')
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
                conn.commit()
            except Exception:
                shutil.rmtree(final_root, ignore_errors=True)
                raise
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


@app.route('/api/upload/<code>', methods=['GET'])
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

cleanup_expired_uploads(force=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2234, debug=True)
