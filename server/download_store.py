"""客户端下载配置：单行表读写、长度与链接校验。"""

import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from db import DB_PATH
from settings import (
    DOWNLOAD_CODE_MAX,
    DOWNLOAD_NOTE_MAX,
    DOWNLOAD_URL_MAX,
    DOWNLOAD_VERSION_MAX,
)


class DownloadConfigError(ValueError):
    def __init__(self, message, code='invalid'):
        super().__init__(message)
        self.message = message
        self.code = code


def _payload(row):
    url = (row['url'] or '').strip() if row is not None else ''
    return {
        'configured': bool(url),
        'version': (row['version'] or '') if row is not None else '',
        'url': url,
        'extract_code': (row['extract_code'] or '') if row is not None else '',
        'note': (row['note'] or '') if row is not None else '',
        'updated_at': row['updated_at'] if row is not None else None,
    }


def get_download():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT version, url, extract_code, note, updated_at "
            "FROM client_download WHERE id = 1").fetchone()
    finally:
        conn.close()
    return _payload(row)


def _as_text(value, label):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise DownloadConfigError(f"{label}必须是文本", 'invalid_type')
    return value


def _clean_text(value, label, limit):
    text = _as_text(value, label).strip()
    if len(text) > limit:
        raise DownloadConfigError(
            f"{label}不能超过 {limit} 个字符", 'too_long')
    return text


def _clean_url(value):
    url = _as_text(value, '下载链接').strip()
    if not url:
        return ''
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise DownloadConfigError(
            '下载链接必须是 http/https 地址', 'invalid_url')
    if len(url) > DOWNLOAD_URL_MAX:
        raise DownloadConfigError(
            f"下载链接不能超过 {DOWNLOAD_URL_MAX} 个字符", 'too_long')
    return url


def save_download(version='', url='', extract_code='', note=''):
    """保存单行配置；链接留空表示下线下载入口并清空其他字段。"""
    version = _clean_text(version, '版本号', DOWNLOAD_VERSION_MAX)
    url = _clean_url(url)
    extract_code = _clean_text(extract_code, '提取码', DOWNLOAD_CODE_MAX)
    note = _clean_text(note, '更新说明', DOWNLOAD_NOTE_MAX)
    if not url:
        version = ''
        extract_code = ''
        note = ''

    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO client_download "
            "(id, version, url, extract_code, note, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "version = excluded.version, url = excluded.url, "
            "extract_code = excluded.extract_code, note = excluded.note, "
            "updated_at = excluded.updated_at",
            (version or None, url or None, extract_code or None,
             note or None, updated_at))
        conn.commit()
    finally:
        conn.close()
    return get_download()
