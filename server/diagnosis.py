"""服务端诊断：复用客户端解析模块，上传日志入库并累加聚合。"""

import hashlib
import os
import re
import sqlite3
import sys

from common import (
    _frame_list, _is_weak_map_name, _json_text, _module_from_analysis,
    _resolve_map_identity, normalize_offset, normalize_version)
from db import _upsert_aggregate, rebuild_aggregates
from legacy_report import analyze_crash, extract_crash_info, extract_map_name
from upload_store import _upload_map_hash

# 复用客户端的纯 Python 解析模块；服务端单独部署缺少 core/ 时退回轻量解析
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
try:
    from core.knowledge import lookup as kb_lookup, lookup_any_module as kb_lookup_any
    from core.stack_parser import (
        find_crash_frame, first_valid_frame, parse_stack_trace, describe_stack)
    from core.logtext import detect_host, diagnose_plain
    from core.environment import analyze_environment
    from core.diagnosis import build_conclusion
    from core.fingerprint import build_fingerprint
    CORE_READY = True
except Exception as _core_error:
    CORE_READY = False
    print(f"[!] core 解析模块不可用，上传日志将使用轻量解析: {_core_error}")


_ADDR_PATTERNS = (
    r'occurred at (0x[0-9A-F]+)',
    r'at [0-9A-F]{4}:([0-9A-F]{8})',
    r"The instruction at '(0x[0-9A-F]+)'",
    r"The instruction at ([0-9A-F]{8})",
    r'Address:\s+(0x[0-9A-F]{8})',
)


def _extract_crash_addr(text):
    for pattern in _ADDR_PATTERNS:
        match = re.search(pattern, text or '', re.IGNORECASE)
        if match:
            return match.group(1).upper()
    start = (text or '').find("Address  Frame    Logical addr  Module")
    if start != -1:
        for line in text[start:].splitlines()[1:]:
            match = re.search(
                r'([0-9A-F]{8})\s+[0-9A-F]{8}\s+[0-9A-F]{4}:[0-9A-F]{8}\s+(.*)',
                line, re.IGNORECASE)
            if match:
                return match.group(1).upper()
    return "Unknown"


def _module_name(path):
    """Linux 上 os.path.basename 不会拆分反斜杠路径，这里手动归一化。"""
    text = (path or "").replace("/", "\\").rsplit("\\", 1)[-1].strip()
    return text or None


def _frame_rva(frame):
    """只有 .text（0001 节）的节内偏移 +0x1000 才能换算成 RVA。"""
    if frame.get('rva') is None:
        return None
    return normalize_offset("0x%08X" % frame['rva'])


def _stack_payload(frames, limit=48):
    stack = []
    for frame in (frames or [])[:limit]:
        module = (frame.get('module') or '').replace('/', '\\').rsplit('\\', 1)[-1]
        rva = frame.get('rva')
        if module or rva is not None:
            stack.append({'module': module or None, 'rva': rva})
    return stack


def _diagnose_with_core(text):
    addr = _extract_crash_addr(text)
    frames = parse_stack_trace(text)
    relative_offset = None
    module_name = None
    used_fallback = False

    crash_frame = find_crash_frame(frames, addr)
    if crash_frame and (crash_frame.get('module') or '').lower() not in (
            '<unknown>', 'unknown', ''):
        relative_offset = _frame_rva(crash_frame)
        module_name = _module_name(crash_frame['module'])
    else:
        fallback = first_valid_frame(frames)
        if fallback:
            relative_offset = _frame_rva(fallback)
            module_name = _module_name(fallback['module'])
            used_fallback = addr != "Unknown"

    if relative_offset is None and addr != "Unknown" and not used_fallback:
        clean_addr = addr.replace("0X", "")[-8:]
        try:
            if 0 < int(clean_addr, 16) < 0x05000000:
                relative_offset = normalize_offset(clean_addr)
                exe_match = re.search(r'Exe:\s+(.*)', text, re.IGNORECASE)
                if exe_match:
                    module_name = _module_name(exe_match.group(1).strip())
        except ValueError:
            pass

    map_name = extract_map_name(text)
    plain = diagnose_plain(text)
    exe_match = re.search(r"^(?:Exe|Program):\s*(.+)$", text, re.M | re.I)
    log_exe = exe_match.group(1).strip() if exe_match else None
    environment = analyze_environment(
        text, frames=frames, focus_module=module_name, exe=log_exe,
        allow_hint=not (plain and plain.get("attribution") == "地图"))

    build = re.search(r'War3Build:\s*([0-9.]+)', text, re.IGNORECASE)
    build_raw = build.group(1) if build else None
    version = normalize_version(build_raw) if build_raw else None
    rva = normalize_offset(relative_offset)

    if plain and plain.get('host') == 'editor':
        conclusion = build_conclusion(
            plain=plain, environment=environment, matches=None,
            module_name=plain.get('exe') or module_name or 'Unknown', rva=None,
            addr=addr, log_version=None, used_fallback=False, host='editor')
        return {
            'addr': addr,
            'relative_offset': None,
            'module': plain.get('exe') or module_name,
            'map_name': map_name,
            'version': None,
            'stack': _stack_payload(frames),
            'fingerprint': None,
            'fingerprint_version': None,
            'fingerprint_frames': [],
            'attribution': conclusion['attribution'],
            'confidence': conclusion['confidence'],
            'analysis': conclusion['text'],
        }

    if rva:
        if module_name:
            matches = [(module_name, ver, entry)
                       for ver, entry in kb_lookup(module_name, version, rva)]
        else:
            matches = kb_lookup_any(version, rva)
    else:
        matches = []

    fingerprint = build_fingerprint(
        frames, version=version or build_raw,
        module_name=module_name, rva=rva)
    conclusion = build_conclusion(
        plain=plain, environment=environment, matches=matches,
        module_name=module_name or 'Unknown', rva=rva, addr=addr,
        log_version=version, used_fallback=used_fallback,
        host=detect_host(text)[0])

    return {
        'addr': addr,
        'relative_offset': relative_offset,
        'module': module_name,
        'map_name': map_name,
        'version': version,
        'stack': _stack_payload(frames),
        'fingerprint': (fingerprint or {}).get('signature'),
        'fingerprint_version': (fingerprint or {}).get('version'),
        'fingerprint_frames': (fingerprint or {}).get('frames') or [],
        'attribution': conclusion['attribution'],
        'confidence': conclusion['confidence'],
        'analysis': conclusion['text'],
    }


def _diagnose_light(text):
    """服务端未部署 core/ 时的兜底：只做偏移、地图与知识库查表。"""
    addr, relative_offset = extract_crash_info(text)
    relative_offset = normalize_offset(relative_offset)
    map_name = extract_map_name(text)
    analysis = analyze_crash(text)
    module_name = _module_from_analysis(analysis)
    build = re.search(r'War3Build:\s*([0-9.]+)', text, re.IGNORECASE)
    version = normalize_version(build.group(1)) if build else None
    signature = None
    if relative_offset and module_name:
        material = f"{version or 'unknown'}|{module_name.lower()}+{relative_offset}"
        signature = hashlib.sha1(material.encode('utf-8')).hexdigest()[:12].upper()
    return {
        'addr': addr,
        'relative_offset': relative_offset,
        'module': module_name,
        'map_name': map_name,
        'version': version,
        'stack': [],
        'fingerprint': signature,
        'fingerprint_version': version,
        'fingerprint_frames': [f"{module_name.lower()}+{relative_offset}"]
        if signature else [],
        'attribution': None,
        'confidence': None,
        'analysis': analysis,
    }


def _diagnose_text(text):
    try:
        return _diagnose_with_core(text) if CORE_READY else _diagnose_light(text)
    except Exception as exc:
        print(f"[!] 上传日志诊断失败: {exc}")
        return _diagnose_light(text)


def _ingest_crash_records(conn, records, code, kk_info, timestamp,
                          representative_index=0, map_meta=None):
    """把每份崩溃记录写入 crash_reports 并累加聚合；返回入库统计。"""
    text_count = sum(1 for record in records if record.get('text'))
    meta = map_meta or {}
    kk_map = (kk_info or {}).get('map_name')
    diagnoses = []
    inserted = 0
    duplicates = 0
    rebuilt = False

    for record in records:
        text = record.get('text')
        if not text:
            diagnoses.append(None)
            continue
        diagnosis = _diagnose_text(text)
        diagnoses.append(diagnosis)

        crash_map = record.get('map_name')
        if _is_weak_map_name(crash_map):
            crash_map = diagnosis.get('map_name') or crash_map
        map_name, map_author = _resolve_map_identity(
            crash_map, kk_map, meta.get('name'), meta.get('author'),
            (kk_info or {}).get('map_hash'))
        if not map_name:
            map_name = kk_map or crash_map or 'Unknown'
        map_hash = _upload_map_hash(
            map_name, kk_info, text_count == 1, crash_name=crash_map)

        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        stack = diagnosis.get('stack') or []
        frames = diagnosis.get('fingerprint_frames') or []
        fields = (
            map_name,
            '网页上传',
            diagnosis.get('addr'),
            text,
            content_hash,
            timestamp,
            diagnosis.get('analysis'),
            diagnosis.get('module'),
            diagnosis.get('relative_offset'),
            diagnosis.get('version'),
            diagnosis.get('attribution'),
            diagnosis.get('confidence'),
            diagnosis.get('fingerprint'),
            diagnosis.get('fingerprint_version'),
            _frame_list(frames),
            map_hash,
            map_author,
            _json_text(stack) if stack else None,
            None,
            code,
        )
        try:
            cursor = conn.execute('''INSERT INTO crash_reports
                                     (map_name, os_info, crash_address, log_content,
                                      content_hash, timestamp, analysis_result, module,
                                      relative_offset, game_version, attribution,
                                      confidence, fingerprint, fingerprint_version,
                                      fingerprint_frames, map_hash, map_author, stack,
                                      dmp_info, upload_code)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                  fields)
            inserted += 1
            _upsert_aggregate(
                conn, cursor.lastrowid, map_hash, map_name,
                diagnosis.get('fingerprint'), diagnosis.get('version'),
                diagnosis.get('module'), diagnosis.get('relative_offset'),
                diagnosis.get('attribution'), timestamp, map_author)
        except sqlite3.IntegrityError:
            duplicates += 1
            conn.execute('''UPDATE crash_reports SET
                             module = COALESCE(module, ?),
                             relative_offset = COALESCE(relative_offset, ?),
                             game_version = COALESCE(game_version, ?),
                             attribution = COALESCE(attribution, ?),
                             confidence = COALESCE(confidence, ?),
                             fingerprint = COALESCE(fingerprint, ?),
                             fingerprint_version = COALESCE(fingerprint_version, ?),
                             fingerprint_frames = COALESCE(fingerprint_frames, ?),
                             map_hash = COALESCE(map_hash, ?),
                             map_author = COALESCE(map_author, ?),
                             map_name = CASE
                                 WHEN map_name IS NULL OR map_name = 'Unknown'
                                   OR lower(map_name) IN ('.w3x', '.w3m', '.w3n')
                                   OR map_name = 'WorldEdit 测试地图'
                                 THEN COALESCE(?, map_name) ELSE map_name END,
                             stack = COALESCE(stack, ?),
                             upload_code = COALESCE(upload_code, ?)
                             WHERE content_hash = ?''',
                          (diagnosis.get('module'),
                           diagnosis.get('relative_offset'),
                           diagnosis.get('version'),
                           diagnosis.get('attribution'),
                           diagnosis.get('confidence'),
                           diagnosis.get('fingerprint'),
                           diagnosis.get('fingerprint_version'),
                           _frame_list(frames),
                           map_hash,
                           map_author,
                           map_name,
                           _json_text(stack) if stack else None,
                           code,
                           content_hash))
            rebuilt = True

    if rebuilt:
        rebuild_aggregates(conn)

    representative = None
    if 0 <= representative_index < len(diagnoses):
        representative = diagnoses[representative_index]
    return {
        'inserted': inserted,
        'duplicates': duplicates,
        'representative': representative,
        'with_offset': sum(1 for item in diagnoses
                           if item and item.get('relative_offset')),
    }
