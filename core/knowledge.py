"""崩溃知识库加载与查询。

数据统一存放在项目根目录的 knowledge.json（客户端与服务端共用）。
所有偏移均为模块内 RVA（相对基址），统一格式为 0x + 8 位大写十六进制。
"""

import json
import os
import re
import sys

_KB_FILENAME = "knowledge.json"


def knowledge_path():
    if getattr(sys, "frozen", False):
        candidates = [os.path.join(sys._MEIPASS, _KB_FILENAME)]
    else:
        candidates = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), _KB_FILENAME)]
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), _KB_FILENAME))
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def _load():
    with open(knowledge_path(), "r", encoding="utf-8") as f:
        return json.load(f)


_KB = _load()

EXCEPTION_CODES = _KB.get("exceptions", {})
CRASH_KNOWLEDGE = _KB.get("modules", {})
BUILD_PREFIXES = _KB.get("build_prefixes", {})
DISPUTED = _KB.get("disputed", {})


def normalize_offset(value):
    """'0X46394' / '0x00046394' / '46394' -> '0x00046394'；超过 8 位的脏地址返回 None。"""
    if value is None:
        return None
    s = str(value).strip().upper()
    if s.startswith("0X"):
        s = s[2:]
    if not re.fullmatch(r"[0-9A-F]+", s) or len(s) > 8:
        return None
    return "0x" + s.zfill(8)


def normalize_version(text):
    """从 War3Build / 文件版本字符串归一化到知识库版本键。"""
    if not text:
        return None
    text = str(text)
    letter = re.search(r"\b(1\.\d{2}[a-z])\b", text, re.IGNORECASE)
    if letter:
        return letter.group(1).lower()
    m = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return None
    parts = [g for g in m.groups() if g is not None]
    for size in (3, 2):
        key = ".".join(parts[:size])
        if key in BUILD_PREFIXES:
            return BUILD_PREFIXES[key]
    return None


def _module_data(module):
    if not module:
        return None
    for key, data in CRASH_KNOWLEDGE.items():
        if key.lower() == str(module).lower():
            return key, data
    return None


def lookup(module, version, rva):
    """按模块 + 版本 + RVA 精确查询。version 为空时只做精确跨版本查找。

    返回 [(版本键, 条目), ...]；不会做任何后缀/模糊匹配。
    """
    rva = normalize_offset(rva)
    if not rva:
        return []
    found = _module_data(module)
    if not found:
        return []
    _, versions = found
    if version:
        entry = versions.get(version, {}).get(rva)
        return [(version, entry)] if entry else []
    return [(ver, offs[rva]) for ver, offs in versions.items() if rva in offs]


def lookup_any_module(version, rva):
    """模块未知时，按精确 RVA 在所有已知模块中查找。"""
    rva = normalize_offset(rva)
    if not rva:
        return []
    results = []
    for mod, versions in CRASH_KNOWLEDGE.items():
        if version and version in versions:
            entry = versions[version].get(rva)
            if entry:
                results.append((mod, version, entry))
        elif not version:
            for ver, offs in versions.items():
                if rva in offs:
                    results.append((mod, ver, offs[rva]))
    return results


def get_disputed(module, version, rva):
    """同地址的不同解释（历史客户端/服务端文案冲突），原样返回供 UI 提示。"""
    rva = normalize_offset(rva)
    if not rva or not version:
        return []
    return DISPUTED.get(module, {}).get(version, {}).get(rva, [])


def describe(entry, version, version_confirmed=True):
    confidence = entry.get("confidence", 0.0)
    verified = "已验证" if entry.get("verified") else "未经逆向验证，仅作线索"
    if version == "all":
        prefix = ""
    elif version and version_confirmed:
        prefix = f"[{version}] "
    else:
        prefix = f"[版本未确认，可能在 {version}] "
    return f"{prefix}{entry.get('desc', '')}（置信度 {confidence:.0%}，{verified}）"
