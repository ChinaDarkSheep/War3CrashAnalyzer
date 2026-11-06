"""SQLite 建表/迁移与聚合统计。"""

import sqlite3

from common import _aggregate_signature, _map_key
from settings import DB_PATH, UPLOAD_DB_SCHEMA


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
        'upload_code': 'TEXT',
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
    c.execute("CREATE INDEX IF NOT EXISTS idx_reports_upload_code "
              "ON crash_reports(upload_code)")

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

    # P2.9 案例合并：记录已写入知识库的目标，避免重复合并
    c.execute("PRAGMA table_info(knowledge_cases)")
    case_columns = [row[1] for row in c.fetchall()]
    for name, decl in {'merged_at': 'DATETIME', 'merged_key': 'TEXT'}.items():
        if name not in case_columns:
            print(f"[*] 正在为案例表添加 {name} 列...")
            c.execute(f"ALTER TABLE knowledge_cases ADD COLUMN {name} {decl}")

    # P2.6 原始日志上传：只记账单与派生字段，原始文件另存私有目录
    c.execute(UPLOAD_DB_SCHEMA)
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_uploads_hash "
              "ON raw_uploads(content_hash)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_uploads_expires "
              "ON raw_uploads(expires_at)")

    # P2.7 上传入库：记录服务端诊断结论，便于管理端列表直接展示
    c.execute("PRAGMA table_info(raw_uploads)")
    upload_columns = [row[1] for row in c.fetchall()]
    upload_migrations = {
        'fingerprint': 'TEXT',
        'attribution': 'TEXT',
        'confidence': 'REAL',
        'report_count': 'INTEGER',
    }
    for name, decl in upload_migrations.items():
        if name not in upload_columns:
            print(f"[*] 正在为 upload 表添加 {name} 列...")
            c.execute(f"ALTER TABLE raw_uploads ADD COLUMN {name} {decl}")

    # P2.7 管理端操作审计：下载 / 预览 / 删除留痕
    c.execute('''CREATE TABLE IF NOT EXISTS admin_audit
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at DATETIME NOT NULL,
                  action TEXT NOT NULL,
                  code TEXT,
                  detail TEXT,
                  ip_hash TEXT)''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_time "
              "ON admin_audit(created_at)")

    conn.commit()
    conn.close()


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
