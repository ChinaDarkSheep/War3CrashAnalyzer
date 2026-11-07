"""P5.5 统一泄露报告。

一份报告同时覆盖定位结果、逐条证据、可疑函数完整片段、A/B 补丁与覆盖范围，
可导出 Markdown / JSON / CSV。报告只读取修复计划，不修改地图。
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
from collections import Counter, defaultdict

from core.leak_catalog import coverage_statement
from core.leak_fixer import match_key

LEVEL_SEVERITY = {"A": "高", "B": "中", "C": "低"}
LEVEL_ORDER = {"A": 0, "B": 1, "C": 2}

_LEAK_SIGNALS = (
    "out of memory",
    "not enough memory",
    "memory allocation",
    "too many handles",
    "handle limit",
    "内存不足",
    "内存耗尽",
    "内存分配失败",
    "句柄耗尽",
    "句柄数过多",
)


def _suggestion(match, *, auto, patch):
    if auto:
        return "在函数出口前插入对应的销毁调用；默认勾选，应用前会展示 diff。"
    if patch:
        return "生成补丁建议，不自动写盘；可与 A 级一起应用或单独导出 diff。"
    if match.fix_mode == "patch":
        return "当前条目的销毁位置无法静态确定，只报告，不生成补丁。"
    if match.fix_mode == "report":
        return "只报告，不自动销毁；请人工确认对象生命周期。"
    return "没有可用编辑，请人工复核。"


def _row(match, lines, auto_keys, patch_keys, *, auxiliary=False):
    creation = match.creation
    level = match.level or "C"
    key = match_key(match)
    auto = bool(match.finding or auxiliary) and bool(
        match.auto_fixable or key in auto_keys)
    patch = bool(
        (match.finding or auxiliary)
        and match.fix_mode == "patch"
        and key in patch_keys
    )
    return {
        "key": key,
        "rule_id": match.rule_id,
        "title": match.rule.title if match.rule else "未分类",
        "level": level,
        "severity": LEVEL_SEVERITY.get(level, "低"),
        "function": creation.function,
        "line": creation.line,
        "column": creation.column,
        "handle_type": creation.handle_type,
        "variable": creation.variable or "",
        "creator": creation.creator,
        "confidence": match.confidence,
        "fix_mode": match.fix_mode,
        "status": creation.status,
        "kind": creation.kind,
        "evidence": match.evidence,
        "suggestion": (
            "在已销毁语句后追加 `set var = null`；不改变销毁逻辑。"
            if auxiliary
            else _suggestion(match, auto=auto, patch=patch)
        ),
        "reasons": list(match.reasons),
        "context": _context(lines, creation.line),
        "auto": auto,
        "patch": patch,
        "auxiliary": auxiliary,
        "finding": bool(match.finding) and not auxiliary,
    }


def _context(lines, line, radius=3):
    if not lines:
        return ""
    line = max(1, min(line, len(lines)))
    start = max(0, line - 1 - radius)
    end = min(len(lines), line + radius)
    return "\n".join(
        f"{index + 1:>6}  {lines[index]}" for index in range(start, end)
    )


def _function_snippets(lines, names):
    wanted = set(names)
    snippets = {}
    for index, line in enumerate(lines):
        match = re.match(r"^\s*function\s+(\w+)", line)
        if not match:
            continue
        name = match.group(1)
        if name not in wanted or name in snippets:
            continue
        end = index
        while end < len(lines) and not re.match(
            r"^\s*endfunction\b", lines[end]
        ):
            end += 1
        end = min(end, len(lines) - 1)
        snippets[name] = "\n".join(
            f"{number + 1:>6}  {lines[number]}"
            for number in range(index, end + 1)
        )
    return snippets


def _is_global_notice(match):
    if match.finding:
        return False
    if "全局变量" in (match.evidence or ""):
        return True
    return any("全局变量" in reason for reason in (match.reasons or ()))


def build_leak_report(
    plan,
    *,
    map_name="",
    script_internal_path="",
    encoding="",
    source_sha256="",
    validation=None,
    generated_at=None,
):
    rows = []
    global_skipped = 0
    lines = plan.source_text.splitlines()
    auto_keys = {
        (edit.rule_id, edit.function, edit.anchor_line or edit.line)
        for edit in plan.auto_edits
    }
    patch_keys = {
        (edit.rule_id, edit.function, edit.anchor_line or edit.line)
        for edit in plan.patch_edits
    }
    for match in plan.matches:
        if _is_global_notice(match):
            global_skipped += 1
            continue
        if match.finding or match.notice:
            rows.append(_row(match, lines, auto_keys, patch_keys))
        for auxiliary in match.auxiliary:
            rows.append(
                _row(
                    auxiliary, lines, auto_keys, patch_keys,
                    auxiliary=True,
                )
            )

    rows.sort(
        key=lambda row: (
            LEVEL_ORDER.get(row["level"], 9),
            row["function"],
            row["line"],
            row["rule_id"] or "",
        )
    )

    by_level = Counter(row["level"] for row in rows)
    by_rule = Counter(row["rule_id"] or "未分类" for row in rows)
    by_type = Counter(row["handle_type"] for row in rows)
    findings = [row for row in rows if row["finding"]]

    functions = _function_snippets(
        lines, {row["function"] for row in rows}
    )

    auto_edits = plan.auto_edits
    patch_edits = plan.patch_edits
    validation = validation or {"status": "unchecked"}
    report = {
        "meta": {
            "tool": "War3CrashAnalyzer",
            "report_version": "P5.5",
            "generated_at": generated_at or time.strftime("%Y-%m-%d %H:%M:%S"),
            "map_name": map_name or "未命名地图",
            "script_internal_path": script_internal_path or "",
            "encoding": encoding or "",
            "source_sha256": source_sha256 or "",
        },
        "summary": {
            "findings": len(findings),
            "auto_findings": len([row for row in findings if row["auto"]]),
            "patch_findings": len([row for row in findings if row["patch"]]),
            "notices": len([row for row in rows if not row["finding"]]),
            "by_level": dict(by_level),
            "by_rule": dict(by_rule),
            "by_type": dict(by_type),
            "auto_edits": len(auto_edits),
            "patch_edits": len(patch_edits),
            "manual_notes": len(plan.notes),
            "parse_errors": plan.parse_errors,
            "idempotent": bool(plan.idempotent),
            "readonly": bool(plan.readonly),
            "readonly_reason": plan.readonly_reason or "",
            "global_skipped": global_skipped,
        },
        "validation": validation,
        "coverage": coverage_statement(),
        "rows": rows,
        "functions": functions,
        "auto_diff": plan.diff(include_patch=False),
        "patch_diff": plan.diff_for(patch_edits),
        "notes": [
            {
                "rule_id": note.rule_id,
                "level": note.level,
                "function": note.function,
                "line": note.line,
                "message": note.message,
                "kind": note.kind,
            }
            for note in plan.notes
        ],
    }
    return report


def _md_cell(value):
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _validation_text(validation):
    status = (validation or {}).get("status", "unchecked")
    if status == "ok":
        return "pjass 语法检查通过（0 错误）"
    if status == "failed":
        errors = validation.get("errors") or []
        return f"pjass 校验未通过（{len(errors)} 个错误），不会写入地图"
    return "未校验：未找到 pjass 或本次未执行校验"


def render_markdown(report):
    meta = report["meta"]
    summary = report["summary"]
    lines = [
        "# 地图泄露诊断报告",
        "",
        "> 本报告由 War3CrashAnalyzer 本地生成，只读取地图副本；"
        "修复输出始终写入 `*_leakfixed` 副本，原图保持不变。",
        "",
        "## 基本信息",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 地图文件 | {_md_cell(meta['map_name'])} |",
        f"| 脚本路径 | {_md_cell(meta['script_internal_path'] or '未记录')} |",
        f"| 编码 | {_md_cell(meta['encoding'] or '未记录')} |",
        f"| 脚本 SHA-256 | `{_md_cell(meta['source_sha256'] or '未记录')}` |",
        f"| 生成时间 | {_md_cell(meta['generated_at'])} |",
        f"| pjass 校验 | {_validation_text(report.get('validation'))} |",
        "",
        "## 结果摘要",
        "",
        f"- 发现（A/B 级）：**{summary['findings']}** 条，"
        f"其中可自动修复 {summary['auto_findings']} 条、补丁建议 "
        f"{summary['patch_findings']} 条。",
        f"- 提示/保护（C 级与 L08）：{summary['notices']} 条。",
        f"- 生成编辑：自动 {summary['auto_edits']} 条、补丁 "
        f"{summary['patch_edits']} 条、人工提示 {summary['manual_notes']} 条。",
        f"- 幂等自检：{'通过' if summary['idempotent'] else '未通过'}；"
        f"解析错误：{summary['parse_errors']} 行。",
    ]
    if summary["readonly"]:
        lines.append(f"- **只读**：{_md_cell(summary['readonly_reason'])}")
    if summary["global_skipped"]:
        lines.append(
            f"- 全局变量持有的普通句柄 {summary['global_skipped']} 条，"
            "按设计不列为泄露。"
        )
    lines.extend(["", "## 覆盖范围", "", report["coverage"], ""])

    lines.extend(
        [
            "## 发现列表",
            "",
            "| # | 级别 | 规则 | 函数 | 行 | 类型 | 变量 | 置信度 | 处理 |",
            "| ---: | :---: | --- | --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for index, row in enumerate(report["rows"], 1):
        handling = (
            "自动修复"
            if row["auto"]
            else "补丁预览"
            if row["patch"]
            else "只报告"
        )
        if row["auxiliary"]:
            handling = "辅助置空"
        lines.append(
            f"| {index} | {row['level']} | {row['rule_id'] or '-'} | "
            f"{_md_cell(row['function'])} | {row['line']} | "
            f"{_md_cell(row['handle_type'])} | "
            f"{_md_cell(row['variable'] or '-')} | "
            f"{int(round(row['confidence'] * 100))}% | {handling} |"
        )
    if not report["rows"]:
        lines.append("| - | - | - | 未发现可报告的创建点 | - | - | - | - | - |")

    grouped = defaultdict(list)
    for row in report["rows"]:
        grouped[row["function"]].append(row)

    lines.extend(["", "## 证据与可疑函数片段", ""])
    for function, function_rows in grouped.items():
        lines.append(f"### 函数 `{function}`")
        lines.append("")
        snippet = report["functions"].get(function)
        if snippet:
            lines.extend(["```jass", snippet, "```", ""])
        for row in function_rows:
            handling = "（辅助置空）" if row["auxiliary"] else ""
            lines.append(
                f"#### 第 {row['line']} 行 · {row['rule_id'] or '未分类'} "
                f"{row['title']}{handling}"
            )
            lines.append("")
            lines.append(f"- 级别：{row['level']}（{row['severity']}）")
            lines.append(
                f"- 对象：{row['handle_type']}"
                + (f" `{row['variable']}`" if row["variable"] else "（内联）")
            )
            lines.append(f"- 创建函数：`{row['creator']}`")
            lines.append(f"- 证据：{row['evidence']}")
            lines.append(f"- 建议：{row['suggestion']}")
            if row["reasons"]:
                lines.append(f"- 判定依据：{'；'.join(row['reasons'])}")
            lines.extend(["", "```jass", row["context"], "```", ""])

    lines.extend(["## 补丁建议", ""])
    if report["auto_diff"]:
        lines.extend(
            [
                "### A 级自动修复 diff",
                "",
                "```diff",
                report["auto_diff"].rstrip("\n"),
                "```",
                "",
            ]
        )
    if report["patch_diff"]:
        lines.extend(
            [
                "### B 级补丁建议 diff",
                "",
                "```diff",
                report["patch_diff"].rstrip("\n"),
                "```",
                "",
            ]
        )
    if not report["auto_diff"] and not report["patch_diff"]:
        lines.extend(["没有生成任何编辑。", ""])

    lines.extend(["## 人工处理提示", ""])
    if report["notes"]:
        for note in report["notes"]:
            location = f"{note['function']} 第 {note['line']} 行"
            rule = note["rule_id"] or "未分类"
            lines.append(f"- `{rule}` {location}：{note['message']}")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 校验与限制", ""])
    lines.append(f"- {_validation_text(report.get('validation'))}。")
    lines.append("- 报告只做静态分析，不保证覆盖所有句柄类型；"
                 "未列出的类型与 `coverage` 声明中的不处理项不会被修改。")
    lines.append("- 共享 force、长期 timer/trigger/hashtable 与 Lua 地图只报告，"
                 "不会自动销毁或写入。")
    lines.append("")
    return "\n".join(lines)


def render_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2, default=str)


CSV_FIELDS = (
    "level",
    "severity",
    "rule_id",
    "title",
    "function",
    "line",
    "column",
    "handle_type",
    "variable",
    "creator",
    "confidence",
    "fix_mode",
    "status",
    "auto",
    "patch",
    "auxiliary",
    "evidence",
    "suggestion",
)


def render_csv(report, include_headers=True):
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if include_headers:
        writer.writeheader()
    for row in report["rows"]:
        writer.writerow(row)
    return buffer.getvalue()


def _safe_base_name(name):
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" .")
    return stem or "leak_report"


def write_leak_report(report, out_dir, base_name=None):
    os.makedirs(out_dir, exist_ok=True)
    base = _safe_base_name(base_name or report["meta"]["map_name"])
    paths = {
        "markdown": os.path.join(out_dir, f"{base}_leak_report.md"),
        "json": os.path.join(out_dir, f"{base}_leak_report.json"),
        "csv": os.path.join(out_dir, f"{base}_leak_report.csv"),
    }
    with open(paths["markdown"], "w", encoding="utf-8") as handle:
        handle.write(render_markdown(report))
    with open(paths["json"], "w", encoding="utf-8") as handle:
        handle.write(render_json(report))
    with open(paths["csv"], "w", encoding="utf-8-sig", newline="") as handle:
        handle.write(render_csv(report))
    return paths


def leak_suspected_from_diagnosis(result):
    """崩溃日志是否出现内存/句柄耗尽特征；只用于追加只读证据。"""
    if not isinstance(result, dict):
        return False
    reason = result.get("reason") or {}
    if isinstance(reason, dict) and reason.get("kind") == "out_of_memory":
        return True
    text = " ".join(
        str(value or "")
        for value in (
            result.get("analysis_text"),
            result.get("detail_text"),
            (result.get("conclusion") or {}).get("text")
            if isinstance(result.get("conclusion"), dict)
            else "",
        )
    ).lower()
    return any(signal in text for signal in _LEAK_SIGNALS)


def crash_evidence_text():
    return (
        "[疑似地图泄露证据]\n"
        "本次崩溃特征与内存/句柄耗尽一致。可以在「地图体检 → 泄露检查」页选择该地图并"
        "手动开始扫描；本页只提供证据，不会修改地图，也不会上传脚本。"
    )
