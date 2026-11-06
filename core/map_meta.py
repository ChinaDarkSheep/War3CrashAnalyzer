"""从 .w3x/.w3m 读取地图名与作者（war3map.w3i + war3map.wts）。

只读地图文件，不上传、不修改。支持未压缩与 zlib 压缩、常见 MPQ 加密；
遇到 PKWare、bzip2 等不支持的压缩方式时返回 None，由调用方回退到日志中的
地图名。字符串优先按 UTF-8 解码，失败后回退 GBK。
"""

import os
import re
import struct

from core.mpq_index import MpqArchive

MAX_W3I_BYTES = 2 * 1024 * 1024
MAX_WTS_BYTES = 8 * 1024 * 1024
MAX_FIELD = 120

_COLOR_CODE = re.compile(r"\|c[0-9a-fA-F]{8}|\|r", re.IGNORECASE)
_TRIGSTR = re.compile(r"^TRIGSTR_(\d+)$", re.IGNORECASE)
_WTS_ENTRY = re.compile(r"STRING\s+(\d+)\s*\{(.*?)\}", re.IGNORECASE | re.DOTALL)


def _decode(raw):
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_string(data, pos):
    end = data.find(b"\x00", pos)
    if end < 0:
        raise ValueError("字符串未结束")
    raw = data[pos:end]
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding), end + 1
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), end + 1


def _clean(value):
    text = (value or "").replace("\r", " ").replace("\n", " ")
    text = _COLOR_CODE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip().strip('"')
    return text[:MAX_FIELD] or None


def _parse_wts(raw):
    values = {}
    for match in _WTS_ENTRY.finditer(_decode(raw)):
        values[int(match.group(1))] = match.group(2).strip()
    return values


def _resolve(value, strings):
    match = _TRIGSTR.match((value or "").strip())
    if not match:
        return value
    return strings.get(int(match.group(1)))


def read_map_meta(map_path):
    """读取地图元数据；无法解析时返回 None，不抛异常给上传流程。"""
    try:
        if not map_path or not os.path.isfile(map_path):
            return None
        if os.path.splitext(map_path)[1].lower() not in (".w3x", ".w3m", ".w3n"):
            return None

        archive = MpqArchive(map_path)
        w3i = archive.read_file("war3map.w3i", max_size=MAX_W3I_BYTES)
        if not w3i or len(w3i) < 16:
            return None

        version = struct.unpack_from("<I", w3i, 0)[0]
        if version < 8 or version > 100:
            return None

        pos = 12
        name, pos = _read_string(w3i, pos)
        author, pos = _read_string(w3i, pos)

        if _TRIGSTR.match((name or "").strip()) or _TRIGSTR.match((author or "").strip()):
            wts = archive.read_file("war3map.wts", max_size=MAX_WTS_BYTES)
            strings = _parse_wts(wts) if wts else {}
            name = _resolve(name, strings)
            author = _resolve(author, strings)

        result = {"name": _clean(name), "author": _clean(author)}
        return result if result["name"] or result["author"] else None
    except (OSError, ValueError, struct.error, IndexError):
        return None
