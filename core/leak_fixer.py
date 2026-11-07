"""P5.4 安全修复器。

把 P5.3 的规则结果转换成显式 ``FixEdit``：

- A 级且通过全部护栏：自动修复（清理局部点/组/玩家组、内联点、销毁后置空）；
- B 级或 A 级被护栏降级：只生成补丁，默认不写入；
- C 级与共享/长期/GUI/逃逸：不生成任何代码编辑。

修复器只操作文本，不直接碰地图；写回与重新提取校验由 ``map_script`` 负责。
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from difflib import unified_diff

from core.constants import ALL_LEAK_TYPES
from core.jass_ast import CallStmt, If, Return, Set
from core.jass_parser import parse_script
from core.jass_semantics import analyze_script
from core.leak_catalog import CatalogMatch, classify_semantics, leak_findings
from core.map_script import normalize_text
from core.pjass import run_pjass

_AUTO_FIX_PREFIX = {
    "location": "loc",
    "group": "gro",
    "force": "for",
}
_LOCAL_RE = re.compile(r"^\s*local\s+[A-Za-z_]\w*")
_LOCAL_STMT_RE = re.compile(r"^\s*local\b", re.IGNORECASE)
_FUNCTION_START_RE = re.compile(r"^\s*function\b", re.IGNORECASE)
_FUNCTION_END_RE = re.compile(r"^\s*endfunction\b", re.IGNORECASE)
_LEAKFIX_RE = re.compile(r"\bleakfix_[a-z]+_(\d+)\b")


@dataclass(frozen=True, slots=True)
class FixEdit:
    kind: str  # insert / replace
    start: int
    end: int
    text: str
    rule_id: str | None
    level: str
    function: str
    line: int
    description: str
    auto: bool
    order: int = 0
    anchor_line: int = 0
    priority: int = 0  # 同一偏移的插入中较小者先输出（用于提升 local 声明）


@dataclass(frozen=True, slots=True)
class FixNote:
    rule_id: str | None
    level: str
    function: str
    line: int
    message: str
    kind: str = "manual"  # manual / patch / report


def match_key(match):
    """选择/报告用的稳定键：规则 + 函数 + 创建行。"""
    creation = match.creation
    return (match.rule_id, creation.function, creation.line)


def edit_key(edit):
    return (edit.rule_id, edit.function, edit.anchor_line or edit.line)


@dataclass(slots=True)
class FixPlan:
    source_text: str
    language: str
    edits: list[FixEdit] = field(default_factory=list)
    notes: list[FixNote] = field(default_factory=list)
    matches: list[CatalogMatch] = field(default_factory=list)
    parse_errors: int = 0
    idempotent: bool = True
    readonly: bool = False
    readonly_reason: str | None = None
    _semantics: object | None = None
    _used_names: set = field(default_factory=set)
    _existing_names: set = field(default_factory=set)
    _name_counter: int = 0

    @property
    def auto_edits(self):
        return [edit for edit in self.edits if edit.auto]

    @property
    def patch_edits(self):
        return [edit for edit in self.edits if not edit.auto]

    @property
    def findings(self):
        return leak_findings(self.matches)

    def selected_edits(self, keys=None, include_patch=False):
        edits = self.edits if include_patch else self.auto_edits
        if keys is None:
            return list(edits)
        keys = set(keys)
        return [
            edit
            for edit in edits
            if (edit.rule_id, edit.function, edit.anchor_line or edit.line)
            in keys
        ]

    def fixed_text(self, include_patch=False, keys=None):
        edits = self.selected_edits(keys=keys, include_patch=include_patch)
        return apply_edits(self.source_text, edits)

    def diff(self, include_patch=False, filename="war3map.j", keys=None):
        edits = self.selected_edits(keys=keys, include_patch=include_patch)
        return self.diff_for(edits, filename=filename)

    def diff_for(self, edits, filename="war3map.j"):
        fixed = apply_edits(self.source_text, edits)
        if fixed == self.source_text:
            return ""
        target = filename
        return "".join(
            unified_diff(
                self.source_text.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile=f"a/{target}",
                tofile=f"b/{target}",
            )
        )

    def stats(self):
        return {
            "language": self.language,
            "readonly": self.readonly,
            "findings": len(self.findings),
            "auto_edits": len(self.auto_edits),
            "patch_edits": len(self.patch_edits),
            "notes": len(self.notes),
            "idempotent": self.idempotent,
            "parse_errors": self.parse_errors,
        }


class _Source:
    def __init__(self, text):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts = []
        offset = 0
        for line in self.lines:
            self.starts.append(offset)
            offset += len(line)
        self.nl = "\r\n" if "\r\n" in text else "\n"

    def __len__(self):
        return len(self.lines)

    def content(self, index):
        if index < 0 or index >= len(self.lines):
            return ""
        return self.lines[index].rstrip("\r\n")

    def start(self, index):
        if index >= len(self.lines):
            return len(self.text)
        return self.starts[index]

    def end(self, index):
        if index < 0 or index >= len(self.lines):
            return len(self.text)
        return self.starts[index] + len(self.content(index))

    def indent(self, index):
        match = re.match(r"[ \t]*", self.content(index))
        return match.group(0) if match else ""

    def function_end_line(self, start_line):
        """返回 1-based 的 endfunction 行号；找不到时返回 None。"""
        for index in range(max(0, start_line), len(self.lines)):
            if re.match(r"^\s*endfunction\b", self.content(index)):
                return index + 1
        return None

    def local_insert_offset(self, function_line_index):
        index = max(0, function_line_index) + 1
        last_local = None
        while index < len(self.lines):
            content = self.content(index)
            if _LOCAL_RE.match(content):
                last_local = index
                index += 1
                continue
            if not content.strip() and last_local is not None:
                index += 1
                continue
            break
        if last_local is not None:
            return self.start(last_local + 1)
        return self.start(function_line_index + 1)


class _EditBuilder:
    def __init__(self, source):
        self.source = source
        self.edits = []
        self.order = 0

    def insert(self, offset, text, *, rule_id, level, function, line,
               description, auto, anchor_line=None, priority=0):
        if not text:
            return
        self.order += 1
        self.edits.append(
            FixEdit(
                kind="insert",
                start=offset,
                end=offset,
                text=text,
                rule_id=rule_id,
                level=level,
                function=function,
                line=line,
                description=description,
                auto=auto,
                order=self.order,
                anchor_line=anchor_line or line,
                priority=priority,
            )
        )

    def replace(self, start, end, text, *, rule_id, level, function, line,
                description, auto, anchor_line=None):
        self.order += 1
        self.edits.append(
            FixEdit(
                kind="replace",
                start=start,
                end=end,
                text=text,
                rule_id=rule_id,
                level=level,
                function=function,
                line=line,
                description=description,
                auto=auto,
                order=self.order,
                anchor_line=anchor_line or line,
            )
        )


def apply_edits(text, edits):
    """按从后往前的顺序应用编辑；同一位置的插入保持生成顺序。"""
    if not edits:
        return text
    ordered = sorted(
        edits,
        key=lambda edit: (edit.start, edit.end, edit.priority, edit.order),
        reverse=True,
    )
    pieces = []
    cursor = len(text)
    last_start = len(text) + 1
    for edit in ordered:
        if edit.end > last_start:
            raise ValueError(
                f"修复编辑重叠：{edit.description} @ {edit.start}-{edit.end}"
            )
        pieces.append(text[edit.end:cursor])
        pieces.append(edit.text)
        cursor = edit.start
        last_start = edit.start
    pieces.append(text[:cursor])
    pieces.reverse()
    return "".join(pieces)


def _destroyer(handle_type):
    entry = ALL_LEAK_TYPES.get(handle_type)
    return entry[0] if entry else None


def _tail_reachable(block):
    if block is None or not block.statements:
        return True
    last = block.statements[-1]
    if isinstance(last, Return):
        return False
    if isinstance(last, If):
        branches = list(last.branches)
        if last.else_body is None:
            return True
        return any(
            _tail_reachable(branch.body) for branch in branches
        ) or _tail_reachable(last.else_body)
    return True


def _statement_allows_inline_hoist(statement):
    return isinstance(statement, (CallStmt, Set))


def _matching_paren(text, open_index):
    depth = 0
    in_string = False
    escape = False
    for index in range(open_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _find_call_span(source, line_index, creator, column):
    content = source.content(line_index)
    matches = [
        match.start()
        for match in re.finditer(rf"\b{re.escape(creator)}\s*\(", content)
    ]
    if not matches:
        return None
    anchored = max(0, int(column or 1) - 1)
    start = min(matches, key=lambda item: abs(item - anchored))
    open_index = content.find("(", start)
    if open_index < 0:
        return None
    close_index = _matching_paren(content, open_index)
    if close_index < 0:
        return None
    return (
        source.start(line_index) + start,
        source.start(line_index) + close_index + 1,
        content[start:close_index + 1],
    )


def _next_inline_name(plan, handle_type):
    prefix = _AUTO_FIX_PREFIX.get(handle_type, handle_type[:3])
    while True:
        plan._name_counter += 1
        name = f"leakfix_{prefix}_{plan._name_counter}"
        if name in plan._existing_names or name in plan._used_names:
            continue
        plan._used_names.add(name)
        plan._existing_names.add(name)
        return name


def _cleanup_text(source, indent, destroyer, variable):
    return (
        f"{indent}call {destroyer}({variable}){source.nl}"
        f"{indent}set {variable} = null{source.nl}"
    )


def _variable_reassigned(source, analysis, variable, creation_line):
    """同一变量在函数内被多处赋值时，单点清理无法覆盖每个句柄。"""
    if analysis is None:
        return False
    start = analysis.definition.line - 1
    end = source.function_end_line(start)
    if not end:
        return False
    pattern = re.compile(rf"^\s*set\s+{re.escape(variable)}\s*=")
    for index in range(start + 1, end - 1):
        if index == creation_line - 1:
            continue
        if pattern.match(source.content(index)):
            return True
    return False


def _cleanup_local(match, plan, source, builder, *, auto):
    creation = match.creation
    rule_id = match.rule_id
    level = match.level
    function = creation.function
    destroyer = _destroyer(creation.handle_type)
    if not creation.variable or not destroyer:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "缺少变量名或销毁函数，无法生成清理代码。",
            )
        )
        return
    if creation.cleanup not in ("none", ""):
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "检测到部分路径已销毁，自动追加清理可能造成重复销毁；"
                "请人工确认所有出口。",
            )
        )
        return
    if any(
        site.variable == creation.variable for site in creation.destroys
    ) or creation.released:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "该变量已有销毁或置空记录，跳过自动编辑。",
            )
        )
        return
    if creation.in_loop:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "句柄在循环内创建或重新赋值，不能在函数出口统一清理；"
                "需要在循环体内逐次处理。",
            )
        )
        return
    analysis = plan._semantics.function(function)
    if analysis is not None and analysis.has_unparsed:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "函数内存在无法解析的语句，跳过代码编辑。",
            )
        )
        return
    if _variable_reassigned(
        source, analysis, creation.variable, creation.line
    ):
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                f"`{creation.variable}` 在函数内被多处赋值或重复创建，"
                "单点清理无法覆盖每个句柄；请人工逐次处理。",
            )
        )
        return

    end_line = source.function_end_line(
        analysis.definition.line - 1 if analysis else creation.line - 1
    )
    if not end_line:
        plan.notes.append(
            FixNote(rule_id, level, function, creation.line, "未找到函数结束位置。")
        )
        return

    indent = "    "
    returns = (
        [
            analysis.cfg.nodes[node_id].line
            for node_id in analysis.cfg.returns
            if node_id in analysis.cfg.nodes
        ]
        if analysis
        else []
    )
    if auto and returns:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "函数存在提前返回，A 级规则已降级为补丁。",
                kind="patch",
            )
        )
        return

    targets = []
    if returns:
        for return_line in sorted(set(returns)):
            targets.append((return_line, source.indent(return_line - 1)))
        if _tail_reachable(analysis.definition.body if analysis else None):
            targets.append((end_line, indent))
    else:
        targets.append((end_line, indent))

    for target_line, target_indent in targets:
        builder.insert(
            source.start(target_line - 1),
            _cleanup_text(
                source, target_indent, destroyer, creation.variable
            ),
            rule_id=rule_id,
            level=level,
            function=function,
            line=creation.line,
            description=(
                f"{'自动' if auto else '补丁'}：第 {creation.line} 行 "
                f"{creation.handle_type} `{creation.variable}` 在函数出口清理"
            ),
            auto=auto,
        )
    if not auto:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                f"已生成补丁：追加 `{destroyer}({creation.variable})`，"
                "需预览确认后手动应用。",
                kind="patch",
            )
        )


def _cleanup_inline(match, plan, source, builder, *, auto):
    creation = match.creation
    rule_id = match.rule_id
    level = match.level
    function = creation.function
    destroyer = _destroyer(creation.handle_type)
    if not destroyer:
        plan.notes.append(
            FixNote(rule_id, level, function, creation.line, "未找到销毁函数。")
        )
        return
    if creation.cleanup not in ("none", "") or creation.released:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "内联句柄已有清理记录，跳过自动编辑。",
            )
        )
        return
    if not _statement_allows_inline_hoist(creation.statement):
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "内联创建位于条件或返回表达式中，提升后无法安全插入销毁；"
                "请人工处理。",
            )
        )
        return
    analysis = plan._semantics.function(function)
    if analysis is not None and analysis.has_unparsed:
        plan.notes.append(
            FixNote(rule_id, level, function, creation.line, "函数内存在无法解析的语句。")
        )
        return
    line_index = creation.line - 1
    span = _find_call_span(
        source, line_index, creation.creator, creation.column
    )
    if not span:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                "无法在源码中定位内联创建调用的范围。",
            )
        )
        return
    start, end, call_text = span
    variable = _next_inline_name(plan, creation.handle_type)
    declaration_line = (
        analysis.definition.line - 1 if analysis else creation.line - 1
    )
    declaration_offset = source.local_insert_offset(declaration_line)
    indent = source.indent(line_index)
    builder.insert(
        declaration_offset,
        f"    local {creation.handle_type} {variable}{source.nl}",
        rule_id=rule_id,
        level=level,
        function=function,
        line=creation.line,
        description=f"提升内联 {creation.handle_type} 到局部变量 `{variable}`",
        auto=auto,
        priority=-1,
    )
    builder.insert(
        source.start(line_index),
        f"{indent}set {variable} = {call_text}{source.nl}",
        rule_id=rule_id,
        level=level,
        function=function,
        line=creation.line,
        description=f"在语句前创建临时变量 `{variable}`",
        auto=auto,
    )
    builder.replace(
        start,
        end,
        variable,
        rule_id=rule_id,
        level=level,
        function=function,
        line=creation.line,
        description=f"用 `{variable}` 替换内联创建调用",
        auto=auto,
    )
    builder.insert(
        source.end(line_index),
        (
            f"{source.nl}{indent}call {destroyer}({variable})"
            f"{source.nl}{indent}set {variable} = null"
        ),
        rule_id=rule_id,
        level=level,
        function=function,
        line=creation.line,
        description=f"语句执行后销毁 `{variable}`",
        auto=auto,
    )
    if not auto:
        plan.notes.append(
            FixNote(
                rule_id, level, function, creation.line,
                f"已生成补丁：将内联 {creation.handle_type} 提升为 "
                f"`{variable}` 并在使用后销毁，需预览确认。",
                kind="patch",
            )
        )


def _plan_null(match, plan, source, builder):
    creation = match.creation
    if not creation.variable or not creation.destroys:
        return
    destroyer = _destroyer(creation.handle_type)
    if not destroyer:
        return
    lines = sorted(
        {
            site.line
            for site in creation.destroys
            if site.line > 0
            and site.variable == creation.variable
            and (site.destroyer or destroyer) == destroyer
        }
    )
    for line in lines:
        index = line - 1
        if index < 0 or index >= len(source):
            continue
        content = source.content(index)
        if re.search(
            rf"\bset\s+{re.escape(creation.variable)}\s*=\s*null\b", content
        ):
            continue
        builder.insert(
            source.end(index),
            f"{source.nl}{source.indent(index)}set {creation.variable} = null",
            rule_id=match.rule_id,
            level=match.level,
            function=creation.function,
            line=line,
            description=f"销毁 `{creation.variable}` 后置空，避免悬空引用",
            auto=True,
            anchor_line=creation.line,
        )


def _plan_patch(match, plan, source, builder):
    creation = match.creation
    if creation.kind == "inline":
        _cleanup_inline(match, plan, source, builder, auto=False)
    elif creation.kind == "local":
        _cleanup_local(match, plan, source, builder, auto=False)


def _build_plan(source_text, language, check_idempotency):
    plan = FixPlan(source_text=source_text, language=language)
    if language == "lua":
        plan.readonly = True
        plan.readonly_reason = "检测到 Lua 脚本，本版只读，不生成任何编辑。"
        return plan

    script = parse_script(source_text)
    plan.parse_errors = len(script.errors) + len(script.unparsed_lines)
    semantics = analyze_script(script)
    matches = classify_semantics(semantics)
    plan.matches = matches
    plan._semantics = semantics
    plan._used_names = set()
    plan._existing_names = set(re.findall(r"[A-Za-z_]\w*", source_text))
    plan._name_counter = max(
        (int(item) for item in _LEAKFIX_RE.findall(source_text)), default=0
    )

    source = _Source(source_text)
    builder = _EditBuilder(source)
    inline_counts = {}
    for match in matches:
        creation = match.creation
        if creation.kind == "inline" and (match.auto_fixable or match.finding):
            key = (creation.function, creation.line)
            inline_counts[key] = inline_counts.get(key, 0) + 1

    for match in matches:
        if match.auto_fixable:
            if match.creation.kind == "inline":
                key = (match.creation.function, match.creation.line)
                if inline_counts.get(key, 0) > 1:
                    plan.notes.append(
                        FixNote(
                            match.rule_id,
                            match.level,
                            match.creation.function,
                            match.creation.line,
                            "同一语句包含多个可处理的内联创建，提升顺序不明确；"
                            "请人工处理。",
                        )
                    )
                else:
                    _cleanup_inline(match, plan, source, builder, auto=True)
            else:
                _cleanup_local(match, plan, source, builder, auto=True)
        elif match.fix_mode == "patch" and match.finding:
            _plan_patch(match, plan, source, builder)
        for auxiliary in match.auxiliary:
            if auxiliary.rule_id == "L09":
                _plan_null(auxiliary, plan, source, builder)

    builder.edits.sort(key=lambda edit: (edit.start, edit.end, edit.order))
    plan.edits = builder.edits

    if check_idempotency and plan.auto_edits:
        try:
            second = build_fix_plan(
                plan.fixed_text(),
                language=language,
                check_idempotency=False,
            )
            plan.idempotent = not second.auto_edits
        except Exception:  # noqa: BLE001 - 幂等检查失败按未通过处理
            plan.idempotent = False
    return plan


def build_fix_plan(text, language="jass", check_idempotency=True):
    return _build_plan(text, language, check_idempotency)


def local_order_errors(text):
    """返回函数体内出现在语句之后的 local 声明；JASS 会因此拒绝编译。"""
    errors = []
    in_function = False
    seen_statement = False
    for line_no, raw in enumerate((text or "").splitlines(), 1):
        content = raw.strip()
        if not content or content.startswith("//"):
            continue
        if _FUNCTION_START_RE.match(content):
            in_function = True
            seen_statement = False
            continue
        if _FUNCTION_END_RE.match(content):
            in_function = False
            seen_statement = False
            continue
        if not in_function:
            continue
        if _LOCAL_STMT_RE.match(content):
            if seen_statement:
                errors.append({
                    "file": "",
                    "line": line_no,
                    "column": None,
                    "message": "Local declaration after first statement",
                })
        else:
            seen_statement = True
    return errors


def validate_fixed_text(text, pjass_path=None):
    """返回 pjass 校验结果；缺失 pjass 时仍做 local 位置检查。"""
    temp_dir = tempfile.mkdtemp(prefix="leakfix_pjass_")
    try:
        path = os.path.join(temp_dir, "war3map.j")
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)
        result = run_pjass(path, pjass_path=pjass_path, syntax_only=True)
        order_errors = local_order_errors(text)
        errors = order_errors + list(result.get("errors") or [])
        if order_errors:
            status = "failed"
        elif not result.get("available"):
            status = "unchecked"
        elif result.get("ok"):
            status = "ok"
        else:
            status = "failed"
        return {
            "status": status,
            "available": bool(result.get("available")),
            "ok": status != "failed",
            "errors": errors,
            "message": (
                "检测到函数内 local 声明位于语句之后"
                if order_errors else (result.get("message") or "")
            ),
            "chunked": bool(result.get("chunked")),
        }
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def write_fix_plan(
    plan,
    map_script,
    *,
    include_patch=False,
    selection=None,
    pjass_path=None,
    validate=True,
):
    """写出修复结果；先 pjass 校验，再写副本并重新提取校验。

    ``selection`` 为 ``match_key()`` 集合；为空时应用全部编辑。
    """
    if plan.readonly or plan.language == "lua":
        return {
            "written": False,
            "write_count": 0,
            "readonly": True,
            "error": plan.readonly_reason or "Lua 脚本只读",
            "validation": {"status": "unchecked"},
            "verification": {},
            "auto_edits": len(plan.auto_edits),
            "patch_edits": len(plan.patch_edits),
        }

    fixed = plan.fixed_text(
        include_patch=include_patch, keys=selection
    )
    if normalize_text(fixed) == normalize_text(plan.source_text):
        return {
            "written": False,
            "write_count": 0,
            "readonly": False,
            "error": None,
            "message": "没有可应用的编辑",
            "validation": {"status": "unchecked"},
            "verification": {},
            "auto_edits": len(plan.auto_edits),
            "patch_edits": len(plan.patch_edits),
        }

    validation = {"status": "unchecked"}
    if validate:
        validation = validate_fixed_text(fixed, pjass_path=pjass_path)
        if validation["status"] == "failed":
            return {
                "written": False,
                "write_count": 0,
                "readonly": False,
                "error": "pjass 校验失败，未写入地图",
                "validation": validation,
                "verification": {},
                "auto_edits": len(plan.auto_edits),
                "patch_edits": len(plan.patch_edits),
            }

    result = map_script.write(fixed)
    return {
        "written": result.written,
        "write_count": result.write_count,
        "readonly": result.readonly,
        "output_path": result.output_path,
        "backup_path": result.backup_path,
        "verification": result.verification,
        "validation": validation,
        "error": result.error,
        "auto_edits": len(plan.auto_edits),
        "patch_edits": len(plan.patch_edits),
    }
