"""旧版 /api/report 的日志解析：地址、地图名与知识库查表。"""

import re

from common import normalize_offset, normalize_version
from settings import KB


def extract_crash_info(log_content):
    """
    Extract crash address and Game.dll relative offset from log content
    """
    addr = "Unknown"
    relative_offset = None

    # Try multiple formats for address
    match_a = re.search(r'occurred at (0x[0-9A-F]+)', log_content, re.IGNORECASE)
    match_b = re.search(r'at [0-9A-F]{4}:([0-9A-F]{8})', log_content, re.IGNORECASE)

    if match_a:
        addr = match_a.group(1).upper()
    elif match_b:
        addr = match_b.group(1).upper()

    if addr != "Unknown":
        # Try to find Game.dll offset in stack trace
        stack_match = re.search(rf'{addr}\s+[0-9A-F]{{8}}\s+0001:([0-9A-F]{{8}})\s+.*Game\.dll', log_content, re.IGNORECASE)
        if stack_match:
            relative_offset = normalize_offset(hex(int(stack_match.group(1), 16) + 0x1000))
        else:
            # Fallback for simple offsets
            clean_addr = addr.replace("0X", "")
            if len(clean_addr) <= 8:
                try:
                    val = int(clean_addr, 16)
                    if val < 0x01000000:
                        relative_offset = "0x" + clean_addr.zfill(8)
                except:
                    pass

    return addr, relative_offset


def extract_map_name(log_content):
    """
    Extract map name from log content
    """
    map_name = "Unknown"
    map_match = re.search(r'Played Maps\\(.*?)\.(?:w3x|w3m|w3n)', log_content, re.IGNORECASE)
    if map_match:
        full_name = map_match.group(1)
        suffix_match = re.search(r'\.(w3x|w3m|w3n)', log_content[map_match.start():map_match.end()], re.IGNORECASE)
        suffix = suffix_match.group(1) if suffix_match else "w3x"

        if '\\' in full_name:
            map_name = full_name.split('\\')[-1] + "." + suffix
        else:
            map_name = full_name + "." + suffix

    if map_name == "Unknown" or map_name == ".w3m" or map_name == ".w3x":
        alt_match = re.search(r'([^\\]+\.(?:w3x|w3m|w3n))', log_content, re.IGNORECASE)
        if alt_match:
            alt_name = alt_match.group(1)
            if "war3" not in alt_name.lower() and "exe" not in alt_name.lower():
                map_name = alt_name
    return map_name


def analyze_crash(log_content):
    addr, relative_offset = extract_crash_info(log_content)
    rva = normalize_offset(relative_offset)
    if not rva:
        return "无法定位崩溃原因（日志中没有可用的模块内偏移）"

    build = re.search(r'War3Build:\s*([0-9.]+)', log_content, re.IGNORECASE)
    version = normalize_version(build.group(1)) if build else None

    for mod, versions in KB.get("modules", {}).items():
        if version:
            entry = versions.get(version, {}).get(rva)
            if entry:
                return f"[{mod} {version}] {entry['desc']}"
        else:
            for ver, offsets in versions.items():
                entry = offsets.get(rva)
                if entry:
                    return f"[{mod} {ver}（版本未确认）] {entry['desc']}"

    if version:
        return f"该版本（{version}）知识库未收录偏移 {rva}"
    return f"未知偏移量 ({rva})"
