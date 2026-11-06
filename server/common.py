"""纯函数：版本/偏移归一化、上报字段校验、聚合签名。"""

import hashlib
import json
import re

from settings import BUILD_PREFIXES


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


def _module_from_analysis(analysis):
    match = re.match(r'\[([^\s\]]+)', analysis or '')
    return _module(match.group(1)) if match else None


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
