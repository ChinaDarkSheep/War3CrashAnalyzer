"""服务端配置：路径、环境变量、上传限制与共享知识库。"""

import json
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('WAR3_DB_PATH') or os.path.join(BASE_DIR, 'crash_data.db')

# --- P2.6 原始日志上传：50 MB / 6 位上传码 / 原始文件 7~15 天 ---
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_ZONE = 40
MAX_STORED_FILES = 120
MAX_ZIP_ENTRIES = 200
UPLOAD_EXTENSIONS = {'.txt', '.log', '.dmp', '.mdmp', '.bin', '.zip'}
ZIP_EXTENSIONS = {'.txt', '.log', '.dmp', '.mdmp', '.bin'}
CRASH_PRIMARY_NAMES = {'crash.txt', 'error.txt', 'war3crash.txt', 'bug.txt'}
KK_LOG_NAMES = {'platform.log', 'downloader.log', 'war3dll.log'}
UPLOAD_ROOT = os.environ.get('WAR3_UPLOAD_DIR') or os.path.join(BASE_DIR, 'uploads')
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


def _env_int(name, default):
    try:
        return int((os.environ.get(name) or '').strip())
    except (TypeError, ValueError):
        return default


RAW_RETENTION_DAYS = min(15, max(7, _env_int('WAR3_RAW_RETENTION_DAYS', 14)))
UPLOAD_RATE_PER_HOUR = max(1, _env_int('WAR3_UPLOAD_RATE', 10))
UPLOAD_SALT = (os.environ.get('WAR3_UPLOAD_SALT') or secrets.token_hex(16)).encode('utf-8')
UPLOAD_ROOT = os.path.abspath(UPLOAD_ROOT)

# --- P2.7 管理端：默认关闭，未配置令牌时所有管理接口返回 503 ---
ADMIN_TOKEN = (os.environ.get('WAR3_ADMIN_TOKEN') or '').strip()
ADMIN_PAGE_SIZE_MAX = 200
ADMIN_PREVIEW_BYTES = 512 * 1024


# --- 共享知识库：读取仓库根目录 knowledge.json，与客户端同源 ---
def _locate_knowledge():
    override = (os.environ.get('WAR3_KB_PATH') or '').strip()
    if override:
        return os.path.abspath(override)
    candidates = [os.path.join(BASE_DIR, '..', 'knowledge.json'),
                  os.path.join(BASE_DIR, 'knowledge.json')]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


KNOWLEDGE_PATH = _locate_knowledge()
# 合并前备份：默认放在 server/knowledge_backups/（已加入 .gitignore）
KNOWLEDGE_BACKUP_DIR = os.path.abspath(
    (os.environ.get('WAR3_KB_BACKUP_DIR') or '').strip()
    or os.path.join(BASE_DIR, 'knowledge_backups'))
KNOWLEDGE_BACKUP_KEEP = 50


def _load_kb():
    try:
        with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"[!] 知识库加载失败，将只使用日志中的本地分析结果: {exc}")
        return {"modules": {}, "build_prefixes": {}, "exceptions": {}}


KB = _load_kb()
BUILD_PREFIXES = KB.get("build_prefixes", {})
