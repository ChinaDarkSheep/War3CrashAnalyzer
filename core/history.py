import sqlite3
import os
import json
import hashlib
import re

class HistoryTracker:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_logs (
                    filename TEXT PRIMARY KEY,
                    file_hash TEXT,
                    last_modified REAL,
                    diagnosed INTEGER DEFAULT 0,
                    reported INTEGER DEFAULT 0,
                    analysis_result TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crash_fingerprints (
                    signature TEXT PRIMARY KEY,
                    version TEXT,
                    frames TEXT,
                    module TEXT,
                    rva TEXT,
                    attribution TEXT,
                    confidence REAL,
                    samples INTEGER DEFAULT 0,
                    map_count INTEGER DEFAULT 0,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crash_fingerprint_samples (
                    log_name TEXT PRIMARY KEY,
                    signature TEXT NOT NULL,
                    map_name TEXT,
                    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to init history DB: {e}")

    @staticmethod
    def _refresh_fingerprint_stats(cursor, signature):
        cursor.execute('''
            SELECT COUNT(*), COUNT(DISTINCT CASE
                WHEN map_name IS NOT NULL AND map_name <> '' THEN map_name END)
            FROM crash_fingerprint_samples WHERE signature = ?
        ''', (signature,))
        samples, maps = cursor.fetchone()
        cursor.execute('''
            UPDATE crash_fingerprints SET samples = ?, map_count = ?
            WHERE signature = ?
        ''', (samples, maps, signature))

    def fingerprint_sample_count(self):
        try:
            conn = sqlite3.connect(self.db_path)
            count = conn.execute(
                "SELECT COUNT(*) FROM crash_fingerprint_samples").fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def record_fingerprint(self, fingerprint, log_name, map_name=None,
                           attribution=None, confidence=None):
        """记录一次崩溃样本；同一日志重复诊断只计一次。

        返回 {"signature", "version", "frames", "samples", "maps",
        "first_seen", "last_seen", "new"}，失败时返回 None。
        """
        signature = (fingerprint or {}).get("signature")
        if not signature or not log_name:
            return None
        clean_map = (map_name if map_name and map_name != "Unknown"
                     and not map_name.startswith(".") else None)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO crash_fingerprints
                    (signature, version, frames, module, rva, attribution,
                     confidence, samples, map_count, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(signature) DO UPDATE SET
                    version = excluded.version,
                    frames = excluded.frames,
                    module = excluded.module,
                    rva = excluded.rva,
                    attribution = COALESCE(excluded.attribution, crash_fingerprints.attribution),
                    confidence = COALESCE(excluded.confidence, crash_fingerprints.confidence),
                    last_seen = CURRENT_TIMESTAMP
            ''', (
                signature,
                fingerprint.get("version"),
                json.dumps(fingerprint.get("frames") or [], ensure_ascii=False),
                fingerprint.get("module"),
                fingerprint.get("rva"),
                attribution,
                confidence,
            ))
            previous = cursor.execute(
                "SELECT signature FROM crash_fingerprint_samples WHERE log_name = ?",
                (log_name,)).fetchone()
            is_new = previous is None or previous[0] != signature
            cursor.execute('''
                INSERT INTO crash_fingerprint_samples (log_name, signature, map_name, seen_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(log_name) DO UPDATE SET
                    signature = excluded.signature,
                    map_name = COALESCE(excluded.map_name, crash_fingerprint_samples.map_name),
                    seen_at = CURRENT_TIMESTAMP
            ''', (log_name, signature, clean_map))

            affected = {signature}
            if previous and previous[0] != signature:
                affected.add(previous[0])
            for sig in affected:
                self._refresh_fingerprint_stats(cursor, sig)

            row = cursor.execute('''
                SELECT samples, map_count, first_seen, last_seen
                FROM crash_fingerprints WHERE signature = ?
            ''', (signature,)).fetchone()
            conn.commit()
            conn.close()
            return {
                "signature": signature,
                "version": fingerprint.get("version"),
                "frames": fingerprint.get("frames") or [],
                "samples": row[0],
                "maps": row[1],
                "first_seen": row[2],
                "last_seen": row[3],
                "new": is_new,
            }
        except Exception as e:
            print(f"Failed to record fingerprint: {e}")
            return None

    def get_log_status(self, filename):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT diagnosed, reported, file_hash FROM processed_logs WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"diagnosed": bool(row[0]), "reported": bool(row[1]), "hash": row[2]}
            return None
        except:
            return None

    def mark_diagnosed(self, filename, file_hash, last_modified, result):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processed_logs (filename, file_hash, last_modified, diagnosed, analysis_result)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    last_modified = excluded.last_modified,
                    diagnosed = 1,
                    analysis_result = excluded.analysis_result
            ''', (filename, file_hash, last_modified, result))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to mark diagnosed: {e}")

    def mark_reported(self, filename, file_hash):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processed_logs (filename, file_hash, reported)
                VALUES (?, ?, 1)
                ON CONFLICT(filename) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    reported = 1
            ''', (filename, file_hash))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to mark reported: {e}")

    def get_all_logs(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT filename, diagnosed, reported, timestamp FROM processed_logs ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except:
            return []

    def summary(self):
        """历史库概览：诊断日志数、指纹组数与重复崩溃组数。"""
        try:
            conn = sqlite3.connect(self.db_path)
            logs = conn.execute("SELECT COUNT(*) FROM processed_logs").fetchone()[0]
            fingerprints = conn.execute(
                "SELECT COUNT(*) FROM crash_fingerprints").fetchone()[0]
            repeated = conn.execute(
                "SELECT COUNT(*) FROM crash_fingerprints WHERE samples > 1").fetchone()[0]
            conn.close()
            return {"logs": logs, "fingerprints": fingerprints,
                    "repeated": repeated}
        except Exception:
            return {"logs": 0, "fingerprints": 0, "repeated": 0}

    def list_fingerprints(self, limit=200, query="", repeated_only=False):
        """按累计次数列出指纹聚类；query 匹配指纹、版本、模块、偏移与归属。"""
        limit = max(1, min(1000, int(limit or 200)))
        clauses = []
        params = []
        if repeated_only:
            clauses.append("samples > 1")
        query = (query or "").strip()
        if query:
            variants = [query]
            match = re.fullmatch(r"(?:0[xX])?([0-9a-fA-F]{1,8})", query)
            if match:
                raw = match.group(1)
                variants.extend(["0x" + raw.zfill(8).upper(), raw.upper()])
            variants = list(dict.fromkeys(variants))
            clauses.append(
                "(instr(lower(signature), lower(?)) > 0"
                " OR instr(lower(COALESCE(version, '')), lower(?)) > 0"
                " OR instr(lower(COALESCE(module, '')), lower(?)) > 0"
                " OR instr(lower(COALESCE(attribution, '')), lower(?)) > 0"
                " OR " + " OR ".join(
                    ["instr(lower(COALESCE(rva, '')), lower(?)) > 0"]
                    * len(variants)) + ")")
            params.extend([query] * 4)
            params.extend(variants)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = ("SELECT signature, version, frames, module, rva, attribution,"
               " confidence, samples, map_count, first_seen, last_seen"
               " FROM crash_fingerprints" + where +
               " ORDER BY samples DESC, last_seen DESC, signature LIMIT ?")
        params.append(limit)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
        except Exception:
            return []
        result = []
        for row in rows:
            item = dict(row)
            try:
                frames = json.loads(item.get("frames") or "[]")
            except (TypeError, ValueError):
                frames = []
            item["frames"] = frames if isinstance(frames, list) else []
            result.append(item)
        return result

    def fingerprint_samples(self, signature, limit=100):
        """某个指纹的样本日志，按最近出现时间倒序。"""
        if not signature:
            return []
        limit = max(1, min(500, int(limit or 100)))
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT log_name, map_name, seen_at
                FROM crash_fingerprint_samples
                WHERE signature = ? COLLATE NOCASE
                ORDER BY seen_at DESC, log_name
                LIMIT ?
            ''', (signature, limit)).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def list_logs(self, limit=200, query=""):
        """诊断日志列表；只取摘要，完整分析结果用 get_log 按需读取。"""
        limit = max(1, min(1000, int(limit or 200)))
        clauses = []
        params = []
        query = (query or "").strip()
        if query:
            clauses.append(
                "(instr(lower(filename), lower(?)) > 0"
                " OR instr(lower(COALESCE(analysis_result, '')), lower(?)) > 0)")
            params.extend([query, query])
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = ("SELECT filename, diagnosed, reported, last_modified, timestamp,"
               " substr(COALESCE(analysis_result, ''), 1, 200) AS summary"
               " FROM processed_logs" + where +
               " ORDER BY COALESCE(last_modified, 0) DESC, timestamp DESC,"
               " filename LIMIT ?")
        params.append(limit)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def get_log(self, filename):
        """按日志名读取完整诊断文本。"""
        if not filename:
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT filename, file_hash, last_modified, diagnosed, reported,
                       timestamp, analysis_result
                FROM processed_logs WHERE filename = ?
            ''', (filename,)).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception:
            return None
