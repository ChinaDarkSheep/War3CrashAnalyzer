"""崩溃栈指纹：游戏版本 + 栈顶 N 帧，用于本地聚类与后续服务端聚合。

同一崩溃（相同游戏版本、相同调用栈顶部若干帧）得到相同指纹，
与地图、日志文件名无关。操作系统 DLL 的帧不参与指纹，因为它们的
RVA 随 Windows 版本变化，会把同一崩溃拆成多组。
"""

import hashlib

TOP_FRAMES = 5

_SYSTEM_MODULES = frozenset({
    "ntdll.dll", "kernel32.dll", "kernelbase.dll", "user32.dll",
    "gdi32.dll", "advapi32.dll", "rpcrt4.dll", "ole32.dll",
    "oleaut32.dll", "msvcrt.dll", "comctl32.dll", "comdlg32.dll",
    "shell32.dll", "shlwapi.dll", "winmm.dll", "ws2_32.dll",
    "version.dll", "imm32.dll", "uxtheme.dll", "dbghelp.dll",
})


def _module_name(module):
    return (module or "").replace("/", "\\").rsplit("\\", 1)[-1].strip().lower()


def _frame_key(frame):
    module = _module_name(frame.get("module"))
    if module in ("", "<unknown>", "unknown"):
        return None
    if frame.get("rva") is not None:
        return f"{module}+0x{int(frame['rva']):08X}"
    if frame.get("section") and frame.get("offset"):
        return f"{module}#{str(frame['section']).upper()}:{str(frame['offset']).upper()}"
    return None


def _is_system_frame(key):
    return key.split("+", 1)[0].split("#", 1)[0] in _SYSTEM_MODULES


def select_frames(frames, top_n=TOP_FRAMES):
    """取栈顶 N 个可用的非系统帧，按自身到调用方的顺序返回。"""
    keys = []
    for frame in frames or []:
        key = _frame_key(frame)
        if not key or _is_system_frame(key):
            continue
        keys.append(key)
        if len(keys) >= top_n:
            break
    return keys


def _normalize_version(version):
    if not version:
        return "unknown"
    try:
        from core.knowledge import normalize_version
        return normalize_version(version) or str(version).strip()
    except Exception:
        return str(version).strip()


def build_fingerprint(frames, version=None, module_name=None, rva=None,
                      top_n=TOP_FRAMES):
    """生成指纹；没有可用的栈信息且无模块偏移时返回 None。

    返回的 signature 为 12 位十六进制哈希，由版本与规范化帧序列决定。
    """
    keys = select_frames(frames, top_n)
    if not keys and module_name and rva:
        try:
            keys = [f"{_module_name(module_name)}+0x{int(str(rva), 16):08X}"]
        except ValueError:
            keys = []
    if not keys:
        return None

    version = _normalize_version(version)
    material = "|".join([version.lower()] + keys)
    signature = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12].upper()
    return {
        "signature": signature,
        "version": version,
        "frames": keys,
        "frame_count": len(keys),
        "module": module_name,
        "rva": rva,
        "text": f"{signature} · {version} · {' → '.join(keys)}",
    }
