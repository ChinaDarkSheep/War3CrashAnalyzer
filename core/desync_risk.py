"""P6 静态异步风险扫描。

只读分析地图脚本中可能引起不同步（desync）的写法，只报告、不生成补丁。
规则聚焦可静态判断的高置信模式：

- D1 本地分支创建句柄或修改同步状态；
- D2 本地分支执行 ForGroup / ForForce 枚举；
- D3 本地分支内取随机数；
- D4 本地分支写全局变量且该变量在分支外仍被读取；
- D5 本地输入（相机/鼠标/选中单位）参与分支条件；
- L1-L4 Lua 非确定遍历、本地随机、系统时间与本地玩家。

扫描不修改脚本，也不写回地图。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.jass_ast import (
    Binary,
    Block,
    Call,
    CallStmt,
    Debug,
    ExitWhen,
    If,
    LocalDecl,
    Loop,
    Return,
    Set,
    Unary,
    VarRef,
)
from core.jass_parser import parse_script

SEVERITY_ORDER = {"高": 0, "中": 1, "低": 2}

RULES = {
    "D1": ("高", "本地分支修改同步状态"),
    "D2": ("高", "本地分支执行单位组枚举"),
    "D3": ("高", "本地分支内取随机数"),
    "D4": ("中", "本地分支写全局变量"),
    "D5": ("低", "本地输入参与分支判断"),
    "L1": ("中", "Lua 非确定顺序遍历"),
    "L2": ("高", "Lua 本地随机数"),
    "L3": ("低", "Lua 系统时间"),
    "L4": ("低", "Lua 读取本地玩家"),
}

# 在本地分支内执行会改变同步状态、或创建/销毁句柄的调用。
SYNC_CALLS = frozenset({
    "CreateUnit", "CreateUnitAtLoc", "CreateUnitAtLocSaveLast",
    "CreateUnitByName", "CreateCorpse", "CreateGroup", "CreateTimer",
    "CreateTrigger", "CreateRegion", "CreateLocation", "CreateRect",
    "CreateRectCentered", "CreateForce", "CreateHashTable", "CreateDestructable",
    "CreateDestructableZ", "CreateItem", "CreateItemLoc",
    "CreateTextTag", "CreateFogModifierRect", "CreateFogModifierRadius",
    "CreateFogModifierRadiusLoc", "CreateSound", "CreateDialog", "CreateQuest",
    "CreateMultiboard", "CreateLeaderboard", "CreateTrackable", "CreateImage",
    "CreateUbersplat", "CreateLightning", "CreateWeatherEffect",
    "CreateTimerDialog", "AddSpecialEffect", "AddSpecialEffectLoc",
    "AddSpecialEffectTarget", "AddSpecialEffectTargetUnitBJ",
    "SetUnitPosition", "SetUnitPositionLoc", "SetUnitX", "SetUnitY",
    "SetUnitLife", "SetUnitState", "SetUnitMana", "SetUnitOwner",
    "SetUnitAbilityLevel", "UnitAddAbility", "UnitRemoveAbility",
    "UnitDamageTarget", "UnitDamagePoint", "KillUnit", "RemoveUnit", "ShowUnit",
    "SetHeroLevel", "SetHeroStr", "SetHeroAgi", "SetHeroInt",
    "ModifyHeroSkillPoints", "SetPlayerState", "SetPlayerTechMaxAllowed",
    "SetPlayerTechResearched", "SetPlayerAbilityAvailable", "SetPlayerHandicap",
    "SetPlayerHandicapXP", "SetPlayerHandicapReviveTime", "SetPlayerName",
    "SetPlayerColor", "SetPlayerRace", "SetPlayerTeam", "SetResourceAmount",
    "AddResourceAmount", "RemoveLocation", "DestroyGroup", "DestroyForce",
    "DestroyTimer", "DestroyTrigger", "RemoveDestructable", "RemoveItem",
    "DestroyTextTag", "DestroyFogModifier", "DestroyDialog", "DestroyQuest",
    "DestroyMultiboard", "DestroyLeaderboard", "DestroyImage", "DestroyUbersplat",
    "DestroyLightning", "DestroyEffect", "TriggerSleepAction", "PolledWait",
})

RANDOM_CALLS = frozenset({
    "GetRandomInt", "GetRandomReal", "GetRandomDirectionDeg",
    "GetRandomPercentageBJ", "GetRandomLocInRect",
})

LOCAL_INPUT_CALLS = frozenset({
    "GetCameraTargetPositionX", "GetCameraTargetPositionY",
    "GetCameraEyePositionX", "GetCameraEyePositionY", "GetCameraEyePositionZ",
    "GetCameraField", "GetMousePositionX", "GetMousePositionY",
    "GetSelectedUnit", "IsUnitSelected",
})

_LUA_RULES = (
    ("L1", re.compile(r"\b(?:pairs|next)\s*\(")),
    ("L2", re.compile(r"\bmath\.(?:random|randomseed)\b")),
    ("L3", re.compile(r"\bos\.(?:time|clock|date)\b")),
    ("L4", re.compile(r"\bGetLocalPlayer\s*\(")),
)


@dataclass(frozen=True, slots=True)
class RiskFinding:
    rule_id: str
    severity: str
    title: str
    function: str
    line: int
    evidence: str
    detail: str


@dataclass(slots=True)
class RiskReport:
    language: str
    total_lines: int
    coverage: float = 1.0
    parse_errors: int = 0
    findings: list[RiskFinding] = field(default_factory=list)

    @property
    def level(self):
        severities = {finding.severity for finding in self.findings}
        for severity in ("高", "中", "低"):
            if severity in severities:
                return severity
        return "无"

    def counts(self):
        result = {"高": 0, "中": 0, "低": 0}
        for finding in self.findings:
            result[finding.severity] = result.get(finding.severity, 0) + 1
        return result

    def rule_counts(self):
        result = {}
        for finding in self.findings:
            result[finding.rule_id] = result.get(finding.rule_id, 0) + 1
        return result


def _iter_expr(expr):
    if expr is None:
        return
    yield expr
    if isinstance(expr, Binary):
        yield from _iter_expr(expr.left)
        yield from _iter_expr(expr.right)
    elif isinstance(expr, Unary):
        yield from _iter_expr(expr.operand)
    elif isinstance(expr, Call):
        for arg in expr.args:
            yield from _iter_expr(arg)
    elif isinstance(expr, VarRef):
        yield from _iter_expr(expr.index)


def _iter_calls(expr):
    for node in _iter_expr(expr):
        if isinstance(node, Call):
            yield node


def _iter_statements(block):
    if block is None:
        return
    for statement in block.statements:
        yield statement
        if isinstance(statement, Debug) and statement.statement is not None:
            yield from _iter_statements(Block(statements=[statement.statement]))
        elif isinstance(statement, If):
            for branch in statement.branches:
                yield from _iter_statements(branch.body)
            yield from _iter_statements(statement.else_body)
        elif isinstance(statement, Loop):
            yield from _iter_statements(statement.body)


def _statement_exprs(statement):
    if isinstance(statement, CallStmt):
        yield statement.call
    elif isinstance(statement, Set):
        yield statement.target
        yield statement.value
    elif isinstance(statement, LocalDecl):
        yield statement.value
    elif isinstance(statement, If):
        for branch in statement.branches:
            yield branch.condition
    elif isinstance(statement, ExitWhen):
        yield statement.condition
    elif isinstance(statement, Return):
        yield statement.value


def _call_name(node):
    return node.name.lower() if isinstance(node, Call) else ""


def _has_call(expr, names):
    names = {name.lower() for name in names}
    return any(_call_name(call) in names for call in _iter_calls(expr))


def _calls_in(block):
    found = []
    for statement in _iter_statements(block):
        for expr in _statement_exprs(statement):
            found.extend(_iter_calls(expr))
    return found


def _var_refs_in(block):
    names = []
    for statement in _iter_statements(block):
        for expr in _statement_exprs(statement):
            for node in _iter_expr(expr):
                if isinstance(node, VarRef):
                    names.append(node.name.lower())
    return names


def _local_names(function):
    names = {param.name.lower() for param in function.params}
    if function.body is not None:
        for statement in _iter_statements(function.body):
            if isinstance(statement, LocalDecl):
                names.add(statement.name.lower())
    return names


def _line_text(lines, line):
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return ""


def _unique(findings):
    seen = set()
    result = []
    for finding in findings:
        key = (finding.rule_id, finding.function, finding.line)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result


def _scan_jass(text):
    script = parse_script(text)
    lines = text.splitlines()
    all_refs = {}
    for statement in script.functions:
        if statement.body is not None:
            for name in _var_refs_in(statement.body):
                all_refs[name] = all_refs.get(name, 0) + 1

    findings = []

    for function in script.functions:
        if function.body is None:
            continue
        locals_ = _local_names(function)
        for statement in _iter_statements(function.body):
            if not isinstance(statement, If):
                continue
            local_branches = [
                branch for branch in statement.branches
                if _has_call(branch.condition, {"GetLocalPlayer"})
                or _has_call(branch.condition, LOCAL_INPUT_CALLS)
            ]
            if not local_branches:
                continue

            for branch in local_branches:
                _scan_local_block(
                    branch.body, branch.line, function, lines,
                    locals_, all_refs, findings)
            if statement.else_body is not None:
                _scan_local_block(
                    statement.else_body, statement.line, function, lines,
                    locals_, all_refs, findings)

            for branch in local_branches:
                if _has_call(branch.condition, LOCAL_INPUT_CALLS):
                    finding = RiskFinding(
                        "D5", RULES["D5"][0], RULES["D5"][1], function.name,
                        branch.line, _line_text(lines, branch.line),
                        "分支用相机、鼠标或选中单位做了本地判断；"
                        "请确认分支内是否修改了同步状态。")
                    findings.append(finding)

    findings = _unique(findings)
    findings.sort(key=lambda item: (SEVERITY_ORDER[item.severity], item.line))

    return RiskReport(
        language="jass",
        total_lines=len(lines),
        coverage=script.coverage,
        parse_errors=len(script.errors),
        findings=findings,
    )


def _scan_local_block(block, line, function, lines, locals_, all_refs,
                      findings):
    if block is None:
        return
    calls = _calls_in(block)

    sync_hits = [call for call in calls
                 if call.name in SYNC_CALLS and call.name not in ("ForGroup", "ForForce")]
    if sync_hits:
        first = sync_hits[0]
        names = "、".join(sorted({call.name for call in sync_hits})[:4])
        findings.append(RiskFinding(
            "D1", RULES["D1"][0], RULES["D1"][1], function.name,
            first.line or line, _line_text(lines, first.line or line),
            f"分支内调用 {names}；该分支只在一部分客户端执行，"
            "创建/销毁句柄或修改同步状态会让各客户端状态分叉。"))

    group_hits = [call for call in calls if call.name in ("ForGroup", "ForForce")]
    if group_hits:
        first = group_hits[0]
        findings.append(RiskFinding(
            "D2", RULES["D2"][0], RULES["D2"][1], function.name,
            first.line or line, _line_text(lines, first.line or line),
            f"本地分支内执行 {first.name}；单位组/玩家组枚举只在一部分客户端运行，"
            "回调里的任何状态修改都会造成分叉。"))

    random_hits = [call for call in calls if call.name in RANDOM_CALLS]
    if random_hits:
        first = random_hits[0]
        findings.append(RiskFinding(
            "D3", RULES["D3"][0], RULES["D3"][1], function.name,
            first.line or line, _line_text(lines, first.line or line),
            "本地分支内取随机数，各客户端的随机序列会不同；"
            "请把随机数移到同步路径，或在本地分支内只用于显示。"))

    written = []
    written_in_block = {}
    for statement in _iter_statements(block):
        if not isinstance(statement, Set) or statement.target is None:
            continue
        name = statement.target.name
        if name.lower() in locals_:
            continue
        written.append((name, statement.line))
        written_in_block[name.lower()] = written_in_block.get(name.lower(), 0) + 1
    for name, write_line in written:
        lower = name.lower()
        outside = all_refs.get(lower, 0) - written_in_block.get(lower, 0)
        if outside <= 0:
            continue
        findings.append(RiskFinding(
            "D4", RULES["D4"][0], RULES["D4"][1], function.name,
            write_line or line, _line_text(lines, write_line or line),
            f"全局变量 {name} 在本地分支内被赋值，分支外仍有读取；"
            "各客户端的该变量可能不同，进而影响同步逻辑。"))


def _mask_lua(text):
    """把注释与字符串内容替换为空格，保留换行与位置。"""
    masked = []
    index = 0
    length = len(text)
    quote = None
    long_close = None
    while index < length:
        char = text[index]
        if long_close is not None:
            if text.startswith(long_close, index):
                masked.append(" " * len(long_close))
                index += len(long_close)
                long_close = None
                continue
            masked.append("\n" if char == "\n" else " ")
            index += 1
            continue
        if quote is not None:
            if char == "\\" and index + 1 < length:
                masked.append("  ")
                index += 2
                continue
            if char == quote:
                masked.append(" ")
                quote = None
                index += 1
                continue
            masked.append("\n" if char == "\n" else " ")
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            masked.append(" ")
            index += 1
            continue
        if char == "-" and text.startswith("--", index):
            end = text.find("\n", index)
            end = length if end < 0 else end
            masked.append(" " * (end - index))
            index = end
            continue
        if char == "[":
            cursor = index + 1
            while cursor < length and text[cursor] == "=":
                cursor += 1
            if cursor < length and text[cursor] == "[":
                long_close = "]" + "=" * (cursor - index - 1) + "]"
                masked.append(" " * (cursor - index + 1))
                index = cursor + 1
                continue
        masked.append(char)
        index += 1
    return "".join(masked)


def _scan_lua(text):
    lines = text.splitlines()
    masked_lines = _mask_lua(text).splitlines()
    findings = []
    for index, raw in enumerate(masked_lines, start=1):
        code = raw.strip()
        if not code:
            continue
        evidence = lines[index - 1].strip()
        for rule_id, pattern in _LUA_RULES:
            if not pattern.search(code):
                continue
            severity, title = RULES[rule_id]
            findings.append(RiskFinding(
                rule_id, severity, title, "", index, evidence,
                _lua_detail(rule_id)))
    findings = _unique(findings)
    findings.sort(key=lambda item: (SEVERITY_ORDER[item.severity], item.line))
    return RiskReport(
        language="lua",
        total_lines=len(lines),
        findings=findings,
    )


def _lua_detail(rule_id):
    return {
        "L1": "Lua 表遍历顺序可能随客户端不同；同步逻辑中请改用有序数组。",
        "L2": "Lua 的随机数状态不在魔兽同步校验内；用 math.random 参与玩法会分叉。",
        "L3": "系统时间在各客户端不同；用它参与同步判断会分叉。",
        "L4": "Lua 中读取本地玩家，请确认分支内没有创建句柄或修改同步状态。",
    }[rule_id]


def scan_text(text, language="jass"):
    if (language or "jass").lower() == "lua":
        return _scan_lua(text)
    return _scan_jass(text)


def scan_map_script(map_script):
    return scan_text(map_script.text, map_script.language)


def summary_text(report):
    counts = report.counts()
    if not report.findings:
        return "未发现静态异步风险。"
    return (f"共 {len(report.findings)} 条风险：高 {counts['高']} / "
            f"中 {counts['中']} / 低 {counts['低']}。")


def render_markdown(report, map_name, script_path="", encoding="", sha256=""):
    lines = [
        "# 掉线风险扫描报告",
        "",
        f"- **地图**: {map_name}",
        f"- **脚本**: {script_path or '未知'}",
        f"- **语言**: {report.language}",
        f"- **编码**: {encoding or '未知'}",
        f"- **脚本 SHA256**: {sha256 or '未知'}",
        f"- **脚本行数**: {report.total_lines}",
        f"- **解析覆盖率**: {report.coverage:.1%}",
        f"- **解析跳过**: {report.parse_errors} 处",
        f"- **风险等级**: {report.level}",
        f"- **汇总**: {summary_text(report)}",
        "",
        "> 本报告为静态检查，只提示可疑写法，不证明地图一定掉线，也不会修改地图。",
        "",
        "## 风险明细",
        "",
        "| 级别 | 规则 | 函数 | 行 | 证据 | 说明 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for finding in report.findings:
        evidence = (finding.evidence or "").replace("|", "\\|")
        detail = finding.detail.replace("|", "\\|")
        lines.append(
            f"| {finding.severity} | {finding.rule_id} {finding.title} | "
            f"{finding.function or '-'} | {finding.line} | "
            f"`{evidence}` | {detail} |")
    lines.append("")
    return "\n".join(lines)
