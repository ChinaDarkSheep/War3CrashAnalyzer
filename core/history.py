import sqlite3
import os
import json
import hashlib

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
