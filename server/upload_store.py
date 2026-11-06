"""上传文件存储、zip 安全校验、崩溃区/KK 区解析与保留清理。"""

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import zipfile
from collections import defaultdict, deque
from datetime import datetime

from flask import request

from common import _map_hash, _parse_json, normalize_offset, normalize_version
from settings import (
    DB_PATH,
    KK_LOG_NAMES,
    MAX_FILES_PER_ZONE,
    MAX_STORED_FILES,
    MAX_UPLOAD_BYTES,
    MAX_ZIP_ENTRIES,
    RAW_RETENTION_DAYS,
    UPLOAD_EXTENSIONS,
    UPLOAD_ROOT,
    UPLOAD_SALT,
    ZIP_EXTENSIONS,
)
from legacy_report import analyze_crash, extract_crash_info, extract_map_name


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
        text = None
        primary_path = primaries[0][0] if primaries else (dmps[0] if dmps else None)
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
            'path': primary_path,
            'text': text,
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
    keys = row.keys()
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
        'fingerprint': row['fingerprint'] if 'fingerprint' in keys else None,
        'attribution': row['attribution'] if 'attribution' in keys else None,
        'confidence': row['confidence'] if 'confidence' in keys else None,
        'report_count': row['report_count'] if 'report_count' in keys else None,
        'summary': summary,
    }


def _representative_index(crash_records):
    if not crash_records:
        return -1
    return max(
        range(len(crash_records)),
        key=lambda index: (
            crash_records[index]['relative_offset'] is not None,
            crash_records[index]['dmps'] > 0,
            crash_records[index]['files'],
        ))


def _upload_map_hash(map_name, kk_info, allow_unknown):
    """只有地图名与 KK 会话一致（或崩溃记录本身没有地图名）时才附哈希。"""
    if not kk_info:
        return None
    kk_hash = kk_info.get('map_hash')
    if not kk_hash:
        return None
    kk_name = (kk_info.get('map_name') or '').strip()
    name = (map_name or '').strip()
    if not name or name == 'Unknown':
        return kk_hash if allow_unknown else None
    if kk_name and name.lower() == kk_name.lower():
        return kk_hash
    return None
