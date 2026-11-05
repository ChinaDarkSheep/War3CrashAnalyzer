"""读取地图 MPQ 哈希表，补全被占位名掩盖的资源文件名。

只读取 MPQ 头与哈希表，不改动地图。候选路径来自 MPQEditor 展开后的脚本、
物编和模型文件，只有在地图哈希表中真实存在的名字才会被采纳，因此不会把
魔兽本体资源误认成地图导入文件。

MPQEditor 的占位名 ``File%08d.ext`` 编号等于 block index，补名后可直接
重命名；这一点已用文件内容比对验证。
"""

import os
import re
import struct

_MAGIC = b"MPQ\x1a"
_MAX_SCAN_BYTES = 16 * 1024 * 1024
_MAX_NAME_LENGTH = 260

_SCRIPT_EXTS = {".j", ".lua"}
_OBJECT_EXTS = {
    ".w3u", ".w3t", ".w3a", ".w3b", ".w3d", ".w3h", ".w3q", ".w3i",
    ".wts", ".mmp", ".imp", ".w3e", ".w3s", ".w3c", ".w3r", ".doo",
    ".w3o", ".w3v",
}
_MODEL_EXTS = {".mdx", ".mdl"}
_TEXT_EXTS = {".txt", ".slk", ".fdf", ".toc", ".xml", ".ini"}
_SCAN_EXTS = _SCRIPT_EXTS | _OBJECT_EXTS | _MODEL_EXTS | _TEXT_EXTS

# 同一 block 被多个来源引用时，按这个顺序归属，保证统计稳定。
_ASSIGN_ORDER = ("物编", "模型", "脚本", "其他")
_REPORT_ORDER = ("脚本", "物编", "模型", "其他", "字典")

_ASSET_PATH = re.compile(
    rb"(?i)[A-Za-z0-9_ .\-]+(?:\\+[A-Za-z0-9_ .\-]+)+"
    rb"\.(?:mdx|mdl|blp|tga|dds|wav|mp3|w3d|w3a|w3u|w3t|w3b|w3h|w3q|"
    rb"w3i|wts|mmp|imp|w3e|w3s|w3c|w3r|doo|w3o|w3v|fdf|ttf|dll)")
_PLACEHOLDER = re.compile(r"(?i)^File(\d+)\.")
_BAD_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _build_crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 0x10
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[index2] = temp1 | (seed & 0xFFFF)
            index2 += 0x100
    return table


_CRYPT = _build_crypt_table()


def _hash_string(name, hash_type):
    seed1 = 0x7FED7FED
    seed2 = 0xEEEEEEEE
    for ch in name.upper().encode("latin-1", "replace"):
        seed1 = (_CRYPT[(hash_type << 8) + ch] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def _decrypt(data, key):
    seed1 = key & 0xFFFFFFFF
    seed2 = 0xEEEEEEEE
    out = bytearray(len(data))
    for offset in range(0, len(data) - 3, 4):
        seed2 = (seed2 + _CRYPT[0x400 + (seed1 & 0xFF)]) & 0xFFFFFFFF
        value = struct.unpack_from("<I", data, offset)[0]
        value ^= (seed1 + seed2) & 0xFFFFFFFF
        struct.pack_into("<I", out, offset, value)
        seed1 = (((~seed1) << 21) + 0x11111111 | (seed1 >> 11)) & 0xFFFFFFFF
        seed2 = (value + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return bytes(out)


def normalize_name(name):
    """归一化地图内路径：JASS 双反斜杠、正斜杠、引号与首尾反斜杠。"""
    name = name.strip().strip("\"'").strip()
    name = re.sub(r"\\{2,}", r"\\", name)
    name = name.replace("/", "\\")
    return name.lstrip("\\")


class MpqArchive:
    """只解析 MPQ 头与哈希表，用于按文件名反查 block index。"""

    def __init__(self, path):
        self.path = path
        self.header_offset = 0
        self.hash_count = 0
        self.block_count = 0
        self._pairs = {}
        self._load()

    def _load(self):
        size = os.path.getsize(self.path)
        with open(self.path, "rb") as f:
            head = f.read(0x10000)
            if head[:4] == _MAGIC:
                offset = 0
            elif head[512:516] == _MAGIC:
                offset = 512
            else:
                offset = head.find(_MAGIC)
            if offset < 0 or offset + 32 > len(head):
                raise ValueError("未找到 MPQ 头")
            (_magic, _header_size, _archive_size, _version, _sector_shift,
             hash_pos, _block_pos, hash_count,
             block_count) = struct.unpack_from("<4sIIHHIIII", head, offset)
            if not 0 < hash_count <= 1 << 20 or block_count <= 0:
                raise ValueError("MPQ 表大小异常")
            if offset + hash_pos + hash_count * 16 > size:
                raise ValueError("MPQ 哈希表越界")
            f.seek(offset + hash_pos)
            raw = f.read(hash_count * 16)
        raw = _decrypt(raw, _hash_string("(hash table)", 3))

        pairs = {}
        for index in range(hash_count):
            name1, name2, _locale, _platform, block = struct.unpack_from(
                "<IIHHI", raw, index * 16)
            if block != 0xFFFFFFFF and block < block_count:
                pairs.setdefault((name1, name2), block)
        self._pairs = pairs
        self.header_offset = offset
        self.hash_count = hash_count
        self.block_count = block_count

    def find_block(self, name):
        """返回文件名对应的 block index；不存在返回 None。"""
        name = normalize_name(name)
        if not name or len(name) > _MAX_NAME_LENGTH:
            return None
        pair = (_hash_string(name, 1), _hash_string(name, 2))
        return self._pairs.get(pair)


def scan_asset_paths(data):
    """从脚本/物编/模型字节中提取带目录的资源路径。"""
    found = set()
    for match in _ASSET_PATH.finditer(data):
        name = normalize_name(match.group().decode("latin-1", "ignore"))
        if name and len(name) <= _MAX_NAME_LENGTH:
            found.add(name)
    return found


def _source_of(filename):
    ext = os.path.splitext(filename.lower())[1]
    if ext in _SCRIPT_EXTS:
        return "脚本"
    if ext in _OBJECT_EXTS:
        return "物编"
    if ext in _MODEL_EXTS:
        return "模型"
    return "其他"


def recover_names(map_file, directory, extra_names=()):
    """扫描展开目录并用地图哈希表验证候选名。

    返回 ``{"names": {block: name}, "counts": {来源: 数量}, "blocks": 总块数,
    "scanned": 扫描文件数}``；无法解析地图时返回 ``error``。
    """
    try:
        archive = MpqArchive(map_file)
    except (OSError, ValueError, struct.error) as exc:
        return {"names": {}, "counts": {}, "blocks": 0, "scanned": 0,
                "error": f"无法读取地图 MPQ：{exc}"}

    by_source = {}
    scanned = 0
    for root, _dirs, files in os.walk(directory):
        for filename in files:
            ext = os.path.splitext(filename.lower())[1]
            if ext not in _SCAN_EXTS:
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, "rb") as f:
                    data = f.read(_MAX_SCAN_BYTES)
            except OSError:
                continue
            scanned += 1
            by_source.setdefault(_source_of(filename), set()).update(
                scan_asset_paths(data))

    names = {}
    counts = {}
    for source in _ASSIGN_ORDER:
        for candidate in sorted(by_source.get(source, ())):
            block = archive.find_block(candidate)
            if block is not None and block not in names:
                names[block] = candidate
                counts[source] = counts.get(source, 0) + 1
    for candidate in sorted(extra_names):
        block = archive.find_block(candidate)
        if block is not None and block not in names:
            names[block] = normalize_name(candidate)
            counts["字典"] = counts.get("字典", 0) + 1

    return {"names": names, "counts": counts, "blocks": archive.block_count,
            "scanned": scanned}


def report_counts(counts):
    """按固定顺序生成 ``脚本 42、物编 762`` 形式的统计文本。"""
    order = list(_REPORT_ORDER) + sorted(
        set(counts) - set(_REPORT_ORDER))
    return "、".join(
        f"{key} {counts[key]}" for key in order if counts.get(key))


def _target_name(name):
    base = os.path.basename(normalize_name(name).replace("\\", "/"))
    base = _BAD_FILENAME.sub("_", base).strip(" .")
    return base[:255]


def rename_placeholder_files(directory, names):
    """把 ``File%08d.ext`` 占位文件重命名为已验证的真实文件名。

    只重命名确实存在的占位文件；目标名冲突时跳过，不覆盖已有文件。
    返回重命名数量。
    """
    pending = {}
    for root, _dirs, files in os.walk(directory):
        for filename in files:
            match = _PLACEHOLDER.match(filename)
            if match:
                pending.setdefault(int(match.group(1)),
                                   os.path.join(root, filename))
    renamed = 0
    for block, name in sorted(names.items()):
        source = pending.get(block)
        if not source:
            continue
        target_name = _target_name(name)
        if not target_name:
            continue
        target = os.path.join(os.path.dirname(source), target_name)
        if os.path.lexists(target):
            continue
        try:
            os.rename(source, target)
        except OSError:
            continue
        renamed += 1
    return renamed
