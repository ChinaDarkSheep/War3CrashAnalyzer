"""运行环境识别：从日志的 Loaded Modules 段与调用栈判断平台/插件/驱动。

只识别已知特征模块，不做"陌生 DLL 一律可疑"的猜测，避免误报。
识别结果用于把责任从"地图"区分到"本地环境/平台/编辑器"。
"""

import os
import re

_MODULE_EXT = r"(?:dll|exe|asi|flt|ime|cpl)"

# 目录特征用于消解同名模块的归属歧义：编辑器插件目录下的 kk*.dll / yd_*.dll
# 不能仅凭文件名算作对战平台。
_EDITOR_PATH = re.compile(r"(?:雪月|编辑器|editor|ydwe|worldedit|\\plugin\\)", re.I)
_PLATFORM_PATH = re.compile(r"(?:对战平台|对战|平台|azurewrath|kkplatform)", re.I)

# (类别, 模块名规则, 展示名)；KK 平台只匹配明确的平台模块名，
# 不再用 ^kk.*\.dll$ 把 kkapi.dll 这类编辑器插件一并吞掉。
_RULES = (
    ("platform", re.compile(r"^azurewrath\.dll$", re.I), "80对战平台"),
    ("platform", re.compile(r"^kk(?:platform|client|game|login|sdk)[a-z0-9_\-]*\.dll$", re.I), "KK对战平台"),
    ("platform", re.compile(r"^(?:11platform|platform11)[a-z0-9_\-]*\.dll$", re.I), "11对战平台"),
    ("platform", re.compile(r"^(?:netease|ntplatform)[a-z0-9_\-]*\.dll$", re.I), "网易对战平台"),
    ("editor_shell", re.compile(r"^worldeditkkwe\.exe$", re.I), "KK 地图编辑器"),
    ("editor_plugin", re.compile(r"^kkapi\.dll$", re.I), "雪月编辑器插件"),
    ("editor_runtime", re.compile(r"^yd(?:we)?[_a-z0-9]*\.dll$", re.I), "YDWE 运行时"),
    ("debug_plugin", re.compile(r"^jassdebug\.(?:asi|dll)$", re.I), "JassDebug 插件"),
    ("gpu", re.compile(r"^nv(?:oglv|d3d|api|wgf|umd)[a-z0-9_]*\.dll$", re.I), "NVIDIA 显卡驱动"),
    ("gpu", re.compile(r"^(?:ati|amd)(?:oglxx|dxx|umd|vlk|xc)[a-z0-9_]*\.dll$", re.I), "AMD 显卡驱动"),
    ("gpu", re.compile(r"^ig(?:d|4icd|75icd|9icd|fx)[a-z0-9_]*\.dll$", re.I), "Intel 显卡驱动"),
    ("ime", re.compile(r"(?:sogou|qqpinyin|baidupinyin|\.ime$)", re.I), "输入法模块"),
)

_CATEGORY_ORDER = ("platform", "editor_shell", "editor_plugin", "editor_runtime",
                   "debug_plugin", "gpu", "ime")

_HINTS = {
    "platform": "本地环境（对战平台插件）",
    "editor_shell": "编辑器环境",
    "editor_plugin": "编辑器插件环境",
    "editor_runtime": "地图运行环境（YDWE）",
    "debug_plugin": "本地环境（JassDebug 插件）",
    "gpu": "本地环境（显卡驱动）",
    "ime": "本地环境（输入法）",
}

_ADVICE = {
    "platform": "建议先在单机模式下复现；平台插件参与的崩溃通常需要平台侧处理。",
    "editor_plugin": "该崩溃与编辑器插件相关，建议关闭插件或更换编辑器版本后重试。",
    "editor_runtime": "地图依赖 YDWE 运行时，请确认运行环境完整。",
    "debug_plugin": "建议先卸载 JassDebug 插件再复现，以排除诊断工具自身影响。",
    "gpu": "建议更新或回滚显卡驱动后重试。",
    "ime": "建议切换或关闭输入法后重试。",
}

_HEADER = re.compile(r"^\s*(?:Loaded Modules|Modules|模块列表)\s*:?\s*$", re.I | re.M)
_STOP = re.compile(
    r"^\s*(?:Stack Trace|Exe|Program|File|CommandLine|Error Code|War3Build|Played Maps)\b",
    re.I)
_SEPARATOR = re.compile(r"^\s*[-=]{10,}\s*$")
_TOKEN = re.compile(rf"[A-Za-z0-9_.\-]+\.{_MODULE_EXT}\b", re.I)
_ADDR_LINE = re.compile(r"^\s*0x[0-9A-Fa-f]+\s*-\s*0x[0-9A-Fa-f]+\s+(.+?)\s*$")


def _loaded_module_records(text):
    """提取 Loaded Modules 段的 (模块名, 完整路径)；没有该段时返回空列表。

    日志行会在 80 字符处截断，文件名可能丢掉扩展名，因此同时保留路径，
    供按目录判定归属使用。
    """
    m = _HEADER.search(text)
    if not m:
        return []

    records = []
    for line in text[m.end():].splitlines():
        line = line.strip()
        if not line:
            continue
        if _STOP.match(line) or _SEPARATOR.match(line):
            break
        addr_line = _ADDR_LINE.match(line)
        if addr_line:
            path = addr_line.group(1)
            name = os.path.basename(path)
            if name:
                records.append({"name": name, "path": path})
        else:
            for name in _TOKEN.findall(line):
                records.append({"name": name, "path": ""})
        if len(records) >= 400:
            break
    return records


def _classify(module, path=None):
    """返回 (类别, 展示名)；未命中返回 None。

    path 存在时用于消解同名歧义：编辑器目录下的 kkapi.dll 归编辑器插件；
    只有明确位于平台目录时才改判为平台。
    """
    name = os.path.basename((module or "").strip())
    if not name:
        return None

    editor_path = bool(path and _EDITOR_PATH.search(path))
    platform_path = bool(path and _PLATFORM_PATH.search(path))

    if name.casefold() == "kkapi.dll" and platform_path and not editor_path:
        return "platform", "KK对战平台"

    for category, pattern, label in _RULES:
        if pattern.search(name):
            return category, label
    return None


def _unique(items):
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _path_for(name, path_by_stem):
    stem = os.path.splitext(os.path.basename(name or ""))[0].casefold()
    return path_by_stem.get(stem) if stem else None


def analyze_environment(log_content, frames=None, focus_module=None, exe=None, allow_hint=True):
    """识别运行环境。

    frames: core.stack_parser.parse_stack_trace 的结果
    focus_module: 实际用于诊断的模块名（崩溃帧或回退帧）
    """
    records = _loaded_module_records(log_content or "")
    path_by_stem = {}
    for record in records:
        stem = os.path.splitext(record["name"])[0].casefold()
        if stem and record["path"]:
            path_by_stem.setdefault(stem, record["path"])

    names = []
    if exe:
        names.append(os.path.basename(exe))
    names.extend(record["name"] for record in records)
    frame_names = [frame["module"] for frame in (frames or []) if frame.get("module")]
    names.extend(frame_names)
    names = _unique(names)
    stack_stems = {os.path.splitext(os.path.basename(n))[0].casefold()
                   for n in frame_names}

    findings = {category: [] for category in _CATEGORY_ORDER}
    for name in names:
        path = _path_for(name, path_by_stem)
        if not path and exe and os.path.basename(exe).casefold() == os.path.basename(name).casefold():
            path = exe
        hit = _classify(name, path)
        if not hit:
            continue
        category, label = hit
        module = os.path.basename(name)
        if any(item["module"].casefold() == module.casefold()
               for item in findings[category]):
            continue
        findings[category].append({
            "module": module,
            "label": label,
            "in_stack": os.path.splitext(module)[0].casefold() in stack_stems,
        })

    platform_evidence = findings["platform"]
    focus_hit = None
    if focus_module:
        focus_hit = _classify(focus_module, _path_for(focus_module, path_by_stem))
    attribution_hint = None
    advice = None

    if allow_hint:
        if focus_hit:
            attribution_hint = _HINTS[focus_hit[0]]
            advice = _ADVICE.get(focus_hit[0])
        elif platform_evidence:
            attribution_hint = "本地环境（对战平台插件已加载）"
            advice = _ADVICE["platform"]
        elif findings["editor_plugin"]:
            attribution_hint = _HINTS["editor_plugin"]
            advice = _ADVICE["editor_plugin"]
        elif findings["debug_plugin"]:
            attribution_hint = "本地环境（诊断插件已加载）"
            advice = _ADVICE["debug_plugin"]
        elif findings["editor_runtime"]:
            attribution_hint = "地图运行环境（YDWE）"
            advice = _ADVICE["editor_runtime"]
        elif findings["gpu"]:
            attribution_hint = "本地环境（显卡驱动已加载）"
            advice = _ADVICE["gpu"]
        elif findings["ime"]:
            attribution_hint = "本地环境（输入法已加载）"
            advice = _ADVICE["ime"]

    env = {
        "modules": names,
        "findings": findings,
        "focus_category": focus_hit[0] if focus_hit else None,
        "focus_label": focus_hit[1] if focus_hit else None,
        "platform_evidence": platform_evidence,
        "platform_in_stack": any(item["in_stack"] for item in platform_evidence),
        "attribution_hint": attribution_hint,
        "advice": advice,
        "text": "",
    }
    env["text"] = describe_environment(env)
    return env


def describe_environment(env):
    if not env:
        return ""
    parts = []
    for category in _CATEGORY_ORDER:
        items = env["findings"].get(category) or []
        if not items:
            continue
        shown = "、".join(
            f"{item['label']}（{item['module']}{'，位于调用栈' if item.get('in_stack') else ''}）"
            for item in items[:3])
        if len(items) > 3:
            shown += f" 等 {len(items)} 个"
        parts.append(shown)
    if not parts:
        return ""

    text = "环境提示：检测到 " + "；".join(parts) + "。"
    if env.get("attribution_hint"):
        text += f"责任判断更偏向{env['attribution_hint']}。"
    if env.get("advice"):
        text += env["advice"]
    return text
