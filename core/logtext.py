"""崩溃日志的编码识别与明文原因解析。

War3 中文客户端/编辑器写出的日志是 GBK；部分平台日志是 UTF-8。
明文原因（critical error 文案 + File/Object 字段）比模块偏移更直接，
应优先于 RVA 查表用于结论。
"""

import os
import re

_ENCODINGS = ("utf-8-sig", "gbk", "latin-1")

FILE_LABELS = {
    "war3map.wtg": "触发器数据",
    "war3map.wct": "触发器文本",
    "war3map.w3u": "单位数据",
    "war3map.w3a": "技能数据",
    "war3map.w3t": "物品数据",
    "war3map.w3h": "科技数据",
    "war3map.w3b": "装饰物数据",
    "war3map.w3d": "可破坏物数据",
    "war3map.w3q": "任务/升级数据",
    "war3map.w3s": "声音数据",
    "war3map.w3r": "区域数据",
    "war3map.w3e": "地形数据",
    "war3map.w3i": "地图信息",
    "war3map.j": "地图脚本",
    "war3map.lua": "地图脚本",
}

_OOM_KEYS = ("内存资源不足", "内存不足", "out of memory", "not enough memory",
             "insufficient memory")
_CORRUPT_KEYS = ("file data is corrupt", "data is corrupt", "corrupt", "文件数据损坏", "文件损坏")
_OPEN_KEYS = ("unable to open", "cannot open", "failed to open", "无法打开", "打开失败")
_LOAD_KEYS = ("unable to load", "cannot load", "failed to load", "无法加载", "加载失败")


def read_log(path):
    """按 UTF-8(BOM) → GBK → Latin-1 的顺序解码日志。"""
    with open(path, "rb") as f:
        data = f.read()
    for enc in _ENCODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="ignore")


def _field(text, name):
    m = re.search(rf"^{name}:\s*(.+)$", text, re.M | re.I)
    return m.group(1).strip() if m else None


def _critical_text(text):
    """取 critical error 之后的说明文字：先看同一行，再看首个非字段行。"""
    m = re.search(r"critical error:[ \t]*(.*)", text, re.I)
    if not m:
        return None
    same_line = m.group(1).strip()
    if same_line:
        return " ".join(same_line.split())

    for line in text[m.end():].splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(?:Program|Object|File|CommandLine|Exe|Exception|Error Code|War3Build)\s*:", line, re.I):
            return None
        if re.match(r"^[-=]{10,}$", line):
            return None
        return " ".join(line.split())
    return None


def detect_host(text):
    """返回 (editor|game|unknown, exe 文件名)。"""
    exe = _field(text, "Exe") or _field(text, "Program") or ""
    base = os.path.basename(exe).lower()
    if "worldedit" in base:
        return "editor", base
    if "war3" in base or "warcraft" in base or "frozen throne" in base:
        return "game", base
    return "unknown", base


def _classify(critical, file_name):
    t = (critical or "").strip().lower().strip(" .!")
    if not t or t == "fatal error":
        return None
    if any(k in t for k in _OOM_KEYS):
        return "out_of_memory"
    if any(k in t for k in _CORRUPT_KEYS):
        return "corrupt_file"
    if file_name and any(k in t for k in _OPEN_KEYS):
        return "open_failed"
    if file_name and any(k in t for k in _LOAD_KEYS):
        return "load_failed"
    return "unknown_text"


def diagnose_plain(text):
    """从日志明文中提取可读原因；游戏通用 FATAL ERROR 不算有效原因。"""
    if not text:
        return None
    host, exe = detect_host(text)
    critical = _critical_text(text)
    file_name = _field(text, "File")
    obj = _field(text, "Object")
    kind = _classify(critical, file_name)
    if not kind:
        return None

    if kind == "out_of_memory":
        if host == "editor":
            conclusion = "内存资源不足，编辑器无法继续处理当前操作。"
            suggestion = ("关闭其他占用内存的程序后重试；若总是在编辑某个对象时出现，"
                          "通常说明该对象数据过大或地图复杂度超出编辑器承受能力。")
        else:
            conclusion = "游戏进程内存不足，无法继续运行。"
            suggestion = ("关闭其他占用内存的程序后重试；降低地图特效与单位密度，"
                          "并用泄露定位检查是否存在未销毁的句柄。")
        attribution = "本地环境"
        confidence = 0.9
    elif kind == "corrupt_file":
        label = FILE_LABELS.get((file_name or "").lower(), "地图内部数据")
        conclusion = f"地图文件 {file_name}（{label}）数据损坏，无法读取。"
        attribution = "地图"
        suggestion = f"从备份恢复该地图；若没有备份，请让地图作者重新导出或替换 {file_name}。"
        confidence = 0.95
    elif kind in ("open_failed", "load_failed"):
        conclusion = f"无法读取地图文件 {file_name}。"
        attribution = "地图"
        suggestion = ("确认文件存在且未被其他程序占用；若地图来自压缩包或对战平台，"
                      "请重新解压或下载，或让作者重新打包。")
        confidence = 0.85
    else:
        if host == "game":
            conclusion = f"游戏报告了未归类的错误：{critical}"
            attribution = "本地环境"
        else:
            conclusion = f"编辑器报告了未归类的错误：{critical}"
            attribution = "编辑器"
        suggestion = "请将该日志与同名 .dmp 一并提交给作者。"
        confidence = 0.5

    detail = f"（Object: {obj}）" if obj else ""
    if file_name:
        detail += f"（File: {file_name}）"
    summary = (f"日志明文：“{critical}”{detail}。结论：{conclusion} "
               f"归属：{attribution}。建议：{suggestion}"
               f"（置信度 {int(confidence * 100)}%，依据日志明文）")

    return {
        "kind": kind,
        "host": host,
        "exe": exe,
        "critical_text": critical,
        "file": file_name,
        "object": obj,
        "conclusion": conclusion,
        "attribution": attribution,
        "suggestion": suggestion,
        "confidence": confidence,
        "text": summary,
    }
