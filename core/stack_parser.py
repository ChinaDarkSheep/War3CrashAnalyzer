"""调用栈解析：从文本日志中提取整段 Stack Trace (Manual)。

格式目标：
    Stack Trace (Manual)
    Address      Frame      Logical addr  Module
    0804F123     00E1F2A4   0001:5A3B2C1D  Game.dll
    ...

EIP 指向无效地址（如空函数指针调用 0x10000000）时，日志首帧的模块名
通常是 `<unknown>`；此时需要回退到调用栈中第一个落在真实模块内的帧。
"""

import re

_UNKNOWN_MODULES = ("<unknown>", "unknown", "")


def _is_unknown(module):
    return module.strip().lower() in _UNKNOWN_MODULES


def parse_stack_trace(log_content):
    """解析整段调用栈，按栈顶到栈底返回帧列表。

    每帧为 dict：address / frame / section / offset / module / rva。
    rva 只在 .text（0001 节）时可换算（节内偏移 + 0x1000）；其他节为 None，
    因为换算需要读取目标模块的 PE 节表，不能凭空猜测。
    """
    if not log_content:
        return []

    header = re.search(r"Stack Trace(?:\s*\([^)]*\))?", log_content, re.I)
    if not header:
        return []

    # 区块在 Exe/Program/File 等下一个字段或分隔线处结束
    tail = log_content[header.start():]
    end = re.search(
        r"\r?\n\s*(?:Exe|Program|File|CommandLine|Object|Error Code|Bug Report)\s*:|"
        r"\r?\n\s*-{10,}|\r?\n\s*={10,}",
        tail, re.I)
    block = tail[:end.start()] if end else tail

    frames = []
    for line in block.splitlines():
        row = re.search(
            r'([0-9A-F]{8})\s+([0-9A-F]{8})\s+([0-9A-F]{4}):([0-9A-F]{8})\s+(.+)$',
            line.strip(), re.I)
        if not row:
            continue
        address, frame, section, offset, module = row.groups()
        rva = None
        if section == "0001":
            value = int(offset, 16) + 0x1000
            if value > 0x1000:
                rva = value
        frames.append({
            "address": address.upper(),
            "frame": frame.upper(),
            "section": section.upper(),
            "offset": offset.upper(),
            "module": module.strip(),
            "rva": rva,
        })
    return frames


def find_crash_frame(frames, crash_addr):
    """按崩溃地址在栈中定位对应帧；找不到返回 None。"""
    if not crash_addr:
        return None
    target = crash_addr.upper().replace("0X", "").lstrip("0")
    if not target:
        return None
    for frame in frames:
        if frame["address"].lstrip("0") == target:
            return frame
    return None


def first_valid_frame(frames):
    """返回第一个非未知模块的帧；优先选择能换算 RVA 的帧。"""
    for frame in frames:
        if not _is_unknown(frame["module"]) and frame["rva"] is not None:
            return frame
    for frame in frames:
        if not _is_unknown(frame["module"]):
            return frame
    return None


def describe_stack(frames, limit=5):
    """把帧列表压缩成一行可读文本，便于放入诊断结论。"""
    parts = []
    for frame in frames:
        if _is_unknown(frame["module"]):
            continue
        if frame["rva"] is not None:
            parts.append(f"{frame['module']}+0x{frame['rva']:08X}")
        else:
            parts.append(f"{frame['module']}（{frame['section']}:{frame['offset']}）")
        if len(parts) >= limit:
            break
    return " → ".join(parts)
