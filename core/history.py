import sqlite3
import os
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to init history DB: {e}")

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
