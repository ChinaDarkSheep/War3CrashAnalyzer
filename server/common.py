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

_EMPTY_MAP_NAMES = {
    "", "unknown", "<unknown>", ".w3x", ".w3m", ".w3n",
    "worldedit 测试地图", "worldedit test map",
}
_MAP_EXT = re.compile(r'\.(?:w3x|w3m|w3n)$', re.IGNORECASE)
_MAP_VERSION_SUFFIX = re.compile(r'[\s_\-]+v?\d+(?:[._]\d+)*[a-z]?\s*$', re.IGNORECASE)
_MAP_CONTROL = re.compile(r'[\x00-\x1f\x7f]+')
_TRIGSTR = re.compile(r'^trigstr_\d+$', re.IGNORECASE)
_MAP_HASH_NAME = re.compile(
    r'^([0-9A-Fa-f]{32})(?:\.(?:w3x|w3m|w3n))?$', re.IGNORECASE)
_WIN_ABS_PATH = re.compile(
    r'(?i)\b[A-Za-z]:\\(?:[^\\\s"<>|*?：，。；、]+\\)*'
    r'[^\\\s"<>|*?：，。；、]+')


def _public_map_name(value):
    """公开页展示用：旧数据里的 ``.w3m`` 视为 WorldEdit 测试地图。"""
    text = _text(value, 160)
    if not text or text.lower() in _EMPTY_MAP_NAMES:
        if text and text.startswith('.'):
            return "WorldEdit 测试地图"
        return None
    return text


def _clean_map_field(value, limit=120, strip_path=True):
    """地图名/作者来自客户端或旧日志：去掉路径、控制字符与占位值。

    地图名允许从旧日志的绝对路径里取文件名；作者名一旦带路径就视为无效，
    避免把 ``C:\\Users\\...`` 截成 ``secret.txt`` 展示出去。
    """
    text = _text(value, limit * 2)
    if not text:
        return None
    if strip_path:
        text = text.replace('/', '\\').rsplit('\\', 1)[-1]
    elif '/' in text or '\\' in text:
        return None
    text = _MAP_CONTROL.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text or text.lower() in _EMPTY_MAP_NAMES or _TRIGSTR.match(text):
        return None
    return text[:limit]


def _is_weak_map_name(value):
    return (value or '').strip().lower() in _EMPTY_MAP_NAMES


def _normalized_map_name(value):
    text = _clean_map_field(value)
    if not text:
        return ''
    text = _MAP_EXT.sub('', text).strip().lower()
    return '' if text in _EMPTY_MAP_NAMES else text


def _map_names_match(left, right):
    """文件名的版本后缀常与日志地图名不一致，比对时忽略 ``_2.5b`` 这类尾巴。"""
    a = _normalized_map_name(left)
    b = _normalized_map_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    a = _MAP_VERSION_SUFFIX.sub('', a).strip(' _-')
    b = _MAP_VERSION_SUFFIX.sub('', b).strip(' _-')
    return bool(a) and a == b


def _resolve_map_identity(crash_name, kk_name, client_name=None, client_author=None,
                          kk_hash=None):
    """客户端从地图文件读到的名字，只在能对上崩溃日志或平台会话时采用。"""
    client_name = _clean_map_field(client_name)
    crash_clean = _clean_map_field(crash_name)
    kk_clean = _clean_map_field(kk_name)
    crash_hash = _map_hash_from_name(crash_name)
    kk_hash = _map_hash(kk_hash)
    weak_crash = _is_weak_map_name(crash_name)
    # 崩溃日志常把地图写成 ``<md5>.w3x``：和平台会话哈希一致即确认同一张图
    hash_confirmed = bool(crash_hash and kk_hash and crash_hash == kk_hash)
    if not client_name:
        if kk_clean and (weak_crash or hash_confirmed):
            return kk_clean, None
        return crash_clean or kk_clean, None
    if _map_names_match(client_name, crash_name):
        accepted = True
    elif hash_confirmed:
        accepted = True
    elif weak_crash and _map_names_match(client_name, kk_name):
        accepted = True
    elif weak_crash and not kk_clean:
        accepted = True
    else:
        accepted = False
    if accepted:
        return client_name, _clean_map_field(client_author, 80, strip_path=False)
    return crash_clean or kk_clean, None


def _public_text(value, limit=4000):
    """公开诊断文本中不保留 Windows 绝对路径，只留文件名。"""
    text = _text(value, limit)
    if not text:
        return None
    return _WIN_ABS_PATH.sub(
        lambda match: match.group(0).replace('/', '\\').rsplit('\\', 1)[-1],
        text)


def _attribution(value):
    text = _text(value, 40)
    return text if text in ATTRIBUTIONS else None


def _module(value):
    """公开字段只保留模块文件名，兼容旧数据里的 Windows 绝对路径。"""
    text = _text(value, 400)
    if not text:
        return None
    text = text.replace("/", "\\").rsplit("\\", 1)[-1].strip()
    if not text or text.lower() in ("unknown", "<unknown>"):
        return None
    return text[:120]


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


def _map_hash_from_name(value):
    """崩溃日志里的 ``<md5>.w3x`` 地图名本身携带哈希。"""
    text = _clean_map_field(value)
    if not text:
        return None
    match = _MAP_HASH_NAME.match(text)
    return match.group(1).lower() if match else None


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
