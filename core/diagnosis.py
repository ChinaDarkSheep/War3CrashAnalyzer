"""统一诊断结论：把明文原因、知识库查表与运行环境合成玩家可读结论。

玩家首页只看到四行：一句话结论、责任归属、建议、置信度。
归属限定为：地图 / 本机环境或对战平台 / 编辑器 / 暂无法确定。
"""

_EDITOR_CATEGORIES = ("editor_shell", "editor_runtime", "editor_plugin")
_ENV_CATEGORIES = ("platform", "debug_plugin", "gpu", "ime")

_PLATFORM_NOTE = "若只在平台对局中崩溃，建议先单机复现以排除平台插件影响。"


def _clip(text, limit=90):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _best_match(matches):
    return max(matches, key=lambda m: (m[2].get("confidence") or 0))


def build_conclusion(plain=None, environment=None, matches=None, module_name="Unknown",
                     rva=None, addr=None, log_version=None, used_fallback=False, host=None):
    """生成统一结论。

    plain: core.logtext.diagnose_plain 的结果（可为 None）
    environment: core.environment.analyze_environment 的结果
    matches: [(模块, 版本, 知识库条目), ...]
    """
    matches = matches or []
    env = environment or {}
    findings = env.get("findings") or {}
    focus_category = env.get("focus_category")
    focus_label = env.get("focus_label")
    env_advice = env.get("advice")
    host = host or (plain or {}).get("host")

    attribution = "暂无法确定"
    confidence = 0.2
    summary = ""
    suggestion = ""

    if plain:
        confidence = plain.get("confidence", 0.5)
        summary = plain.get("conclusion") or plain.get("critical_text") or "日志报告了一个崩溃。"
        suggestion = plain.get("suggestion") or ""
        kind = plain.get("kind")
        if kind in ("corrupt_file", "open_failed", "load_failed"):
            attribution = "地图"
        elif kind == "out_of_memory":
            attribution = "本机环境或对战平台"
        elif host == "editor":
            attribution = "编辑器"
        else:
            attribution = "本机环境或对战平台"
    elif focus_category in _EDITOR_CATEGORIES:
        attribution = "编辑器"
        confidence = 0.65
        target = f"{focus_label}（{module_name}+{rva}）" if rva else f"{focus_label}（{module_name}）"
        summary = f"崩溃发生在 {target}，属于编辑器或编辑器插件的问题。"
        suggestion = env_advice or "关闭编辑器插件或更换编辑器版本后重试；单机模式可正常运行时不必修改地图。"
    elif focus_category in _ENV_CATEGORIES:
        attribution = "本机环境或对战平台"
        confidence = 0.7 if focus_category in ("platform", "gpu") else 0.6
        target = f"{focus_label}（{module_name}+{rva}）" if rva else f"{focus_label}（{module_name}）"
        summary = f"崩溃发生在 {target}，更可能是本机运行环境或平台插件导致的。"
        suggestion = env_advice or "更新驱动、关闭插件后重试；若仅在平台对局中出现，请换单机模式复现。"
    elif matches:
        best = _best_match(matches)
        entry = best[2]
        attribution = entry.get("attribution") or "地图"
        confidence = min(max(entry.get("confidence") or 0.5, 0.3), 0.9)
        summary = f"可能原因：{_clip(entry.get('desc'))}"
        suggestion = entry.get("suggestion") or "将该诊断报告与日志、.dmp 一并发给地图作者，以便按模块和偏移定位。"
    elif rva:
        attribution = "地图"
        confidence = 0.3
        summary = (f"崩溃位于 {module_name}+{rva}，知识库暂未收录；"
                   f"按经验更可能与地图脚本或资源有关。")
        suggestion = "将该诊断报告发给地图作者确认；避免在其他工具中直接修改地图。"
    else:
        attribution = "暂无法确定"
        confidence = 0.2
        summary = "日志中没有足够信息定位崩溃原因。"
        suggestion = "将完整日志与同名 .dmp 提交给地图作者或平台客服。"

    if used_fallback and not (plain and plain.get("confidence", 0) >= 0.85):
        summary = "崩溃指令地址无效（可能为空函数指针调用），已按调用栈首个有效帧分析。" + summary
        confidence *= 0.85

    if attribution == "地图" and findings.get("platform"):
        if "单机" not in suggestion:
            stack_modules = [item["module"] for item in (env.get("platform_evidence") or [])
                             if item.get("in_stack")]
            if stack_modules:
                suggestion += (f"崩溃调用栈包含平台模块 {'、'.join(stack_modules[:2])}；"
                               "若只在平台对局中崩溃，建议先单机复现以排除平台插件影响。")
            else:
                suggestion += _PLATFORM_NOTE

    confidence = min(max(confidence, 0.05), 0.99)
    return {
        "summary": summary,
        "attribution": attribution,
        "suggestion": suggestion,
        "confidence": round(confidence, 2),
        "evidence": {
            "plain_reason": (plain or {}).get("kind"),
            "knowledge_hits": len(matches),
            "environment": focus_category,
            "fallback_frame": bool(used_fallback),
            "module": module_name,
            "rva": rva,
            "log_version": log_version,
            "addr": addr,
            "platform_in_stack": bool(env.get("platform_in_stack")),
            "platform_modules": [item["module"] for item in (env.get("platform_evidence") or [])],
        },
        "text": (f"【结论】{summary}\n"
                 f"【归属】{attribution}\n"
                 f"【建议】{suggestion}\n"
                 f"【置信度】{int(round(confidence * 100))}%"),
    }
