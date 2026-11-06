"""JassDebug.asi 弹窗解析：把 JASS 语句、函数链与代码偏移变成可读结论。

弹窗标题为「调试输出」（GBK 明文），典型内容：

    当前JASS语句地址为：E2122C0，内容为“调用本地函数：Player”
    当前语句所属函数为：Exception3
    上级函数为Exception2
    上级函数为Exception1
    上级函数为Trig_ExceptionActions
    JASS代码起始地址为E1D0010，JASS代码偏移为8456

只读取窗口文本，不注入、不修改游戏进程；仅限本地客户端调试使用。
"""

import os
import re

_POPUP_TITLE = "调试输出"

_ADDR_RE = re.compile(
    r"当前\s*JASS\s*语句地址为\s*[:：]\s*(?:0[xX])?([0-9A-Fa-f]+)", re.I)
_CONTENT_RE = re.compile(r"内容为\s*[“\"'](.+?)[”\"']", re.S)
_FUNCTION_RE = re.compile(r"当前语句所属函数为\s*[:：]\s*(.+)")
_PARENT_RE = re.compile(r"上级函数为\s*[:：]?\s*(.+)")
_CODE_RE = re.compile(
    r"JASS\s*代码起始地址为\s*(?:0[xX])?([0-9A-Fa-f]+)\s*[,，]\s*"
    r"JASS\s*代码偏移为\s*(?:0[xX])?([0-9A-Fa-f]+)", re.I)
_UNKNOWN_RE = re.compile(r"非\s*JASS\s*语句错误|未知错误", re.I)


def _hex(value):
    value = (value or "").strip()
    if value.lower().startswith("0x"):
        value = value[2:]
    try:
        number = int(value, 16)
    except ValueError:
        return None
    return "0x%08X" % number if number <= 0xFFFFFFFF else "0x%X" % number


def _line(value):
    return " ".join((value or "").split()).strip(" ：:")


def parse_popup(text):
    """解析弹窗文本；不是 JassDebug 弹窗时返回 None。"""
    if not text or not text.strip():
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    addr = _ADDR_RE.search(text)
    content = _CONTENT_RE.search(text)
    function = _FUNCTION_RE.search(text)
    parents = [_line(match.group(1)) for match in _PARENT_RE.finditer(text)]
    parents = [name for name in parents if name]
    code = _CODE_RE.search(text)
    unknown = bool(_UNKNOWN_RE.search(text)) and (
        _POPUP_TITLE in text or "JASS" in text.upper())

    if not (addr or function or parents or code or unknown):
        return None

    statement_addr = _hex(addr.group(1)) if addr else None
    code_base = _hex(code.group(1)) if code else None
    code_offset = _hex(code.group(2)) if code else None
    offset_value = int(code_offset, 16) if code_offset else None
    function_name = _line(function.group(1)) if function else None
    statement_content = " ".join(content.group(1).split()) if content else None

    return {
        "unknown_error": unknown,
        "statement_addr": statement_addr,
        "statement_content": statement_content,
        "function": function_name,
        "parents": parents,
        "call_chain": ([function_name] if function_name else []) + parents,
        "code_base": code_base,
        "code_offset": code_offset,
        "code_offset_decimal": offset_value,
    }


def build_conclusion(parsed):
    """把解析结果合成与主诊断一致的四行结论。"""
    if not parsed:
        return None

    if parsed.get("unknown_error") and not parsed.get("function"):
        return {
            "summary": "JassDebug 未能解析出具体的 JASS 语句（非JASS语句错误/未知错误）。",
            "attribution": "暂无法确定",
            "confidence": 0.15,
            "suggestion": ("确认崩溃是否发生在 JASS 执行阶段；"
                           "如有 Errors 日志或 .dmp，请仍以模块偏移结论为准。"),
            "text": ("【结论】JassDebug 未能解析出具体的 JASS 语句"
                     "（非JASS语句错误/未知错误）。\n"
                     "【归属】暂无法确定\n"
                     "【建议】确认崩溃是否发生在 JASS 执行阶段；"
                     "如有 Errors 日志或 .dmp，请仍以模块偏移结论为准。\n"
                     "【置信度】15%"),
        }

    function = parsed.get("function")
    content = parsed.get("statement_content")
    chain = parsed.get("call_chain") or []
    if function:
        summary = f"崩溃发生在 JASS 函数 {function}"
        if content:
            summary += f"（语句：{content}）"
        summary += "。"
    elif chain:
        summary = f"JassDebug 记录了 JASS 调用链 {' → '.join(chain)}。"
    else:
        summary = "JassDebug 记录了 JASS 代码偏移，但没有给出所属函数。"

    confidence = 0.7 if function and content and parsed.get("code_offset") else 0.5
    suggestion = ("在 war3map.j 中搜索该函数，结合 JASS 代码偏移检查附近语句；"
                  "偏移会随地图重新编译变化，请以同一版本地图为准。")
    return {
        "summary": summary,
        "attribution": "地图",
        "confidence": confidence,
        "suggestion": suggestion,
        "text": (f"【结论】{summary}\n"
                 f"【归属】地图\n"
                 f"【建议】{suggestion}\n"
                 f"【置信度】{int(round(confidence * 100))}%"),
    }


def read_popup_text(title=_POPUP_TITLE):
    """只读抓取标题为“调试输出”的弹窗文本；找不到时返回 None。

    通过 EnumWindows + WM_GETTEXT 读取系统消息框控件文字，不注入、
    不挂接游戏进程。仅支持 Windows。
    """
    if os.name != "nt":
        return None

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = [
        wintypes.HWND, enum_proc, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.SendMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM

    target = [None]

    def find_window(hwnd, _lparam):
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        if buffer.value.strip() == title:
            target[0] = hwnd
            return False
        return True

    user32.EnumWindows(enum_proc(find_window), 0)
    if not target[0]:
        return None

    parts = []

    def read_child(hwnd, _lparam):
        class_name = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        if class_name.value.lower() != "static":
            return True
        buffer = ctypes.create_unicode_buffer(65536)
        length = user32.SendMessageW(
            hwnd, 0x000D, len(buffer),
            ctypes.cast(buffer, ctypes.c_void_p).value)
        if length > 0:
            text = buffer.value.strip()
            if text:
                parts.append(text)
        return True

    user32.EnumChildWindows(
        target[0], enum_proc(read_child), 0)
    return "\n".join(parts) if parts else None
