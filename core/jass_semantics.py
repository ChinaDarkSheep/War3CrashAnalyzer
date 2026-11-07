"""JASS 语义分析：符号表、调用图、逃逸分析与句柄生命周期。

P5.2 的职责不是直接改代码，而是把“哪些句柄能安全处理”的事实讲清楚：

- 每个局部/内联句柄在哪里创建，在哪些路径上销毁，是否只清理了部分分支；
- 句柄是否写入全局、作为返回值转移、传入未知函数、存入数组或哈希表、
  交给 RegionAddRect 这类所有权接收入口；
- 是否来自共享对象（GetPlayersAll）、是否注册为长期对象（计时器/触发器）；
- 内联创建（创建函数直接嵌套在参数里）的所有权去向。

所有判断都基于 P5.1 的 AST 和 P5.2 的 CFG，不使用子串匹配。无法确认的
调用一律按逃逸处理：宁可少修，不可错修。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from core.constants import (
    ALL_LEAK_TYPES,
    AUTO_FIX_TYPES,
    BOOLEXPR_FUNCS,
    NO_AUTO_DESTROY,
    OWNERSHIP_SINK_FUNCS,
    SHARED_HANDLE_CREATORS,
)
from core.jass_ast import (
    Binary,
    Call,
    CallStmt,
    CodeRef,
    Debug,
    ExitWhen,
    FunctionDef,
    If,
    Literal,
    LocalDecl,
    Loop,
    RawStmt,
    Return,
    Script,
    Set,
    Unary,
    VarRef,
)
from core.jass_cfg import CFG, build_cfg
from core.jass_parser import parse_file, parse_script

# --- 类型目录 -------------------------------------------------------------

DESTROYER_BY_TYPE = {name: destroyer for name, (destroyer, _) in ALL_LEAK_TYPES.items()}
TYPE_BY_CREATOR = {
    creator: handle_type
    for handle_type, (_, creators) in ALL_LEAK_TYPES.items()
    for creator in creators
}
for _func in BOOLEXPR_FUNCS:
    TYPE_BY_CREATOR[_func] = "boolexpr"
for _creator in SHARED_HANDLE_CREATORS:
    # 共享创建函数不在 ALL_LEAK_TYPES 里（永不销毁），但仍需要作为“共享句柄”
    # 事实进入语义层，供规则层解释为什么不能修复。
    TYPE_BY_CREATOR.setdefault(_creator, "force")
DESTROYER_BY_TYPE["boolexpr"] = "DestroyBoolExpr"
DESTROYER_TYPE = {destroyer: handle_type for handle_type, destroyer in DESTROYER_BY_TYPE.items()}

TRACKED_HANDLE_TYPES = frozenset(DESTROYER_BY_TYPE)

# 这些函数只读取或临时使用句柄，不会长期持有。列表刻意保守：漏掉的函数会被
# 当成“未知函数”处理，结果只是少自动修复，不会产生错误编辑。
SAFE_ARGUMENT_FUNCS = frozenset({
    # location
    "GetLocationX", "GetLocationY", "GetLocationZ",
    "SetUnitPositionLoc", "SetUnitPositionLocFacingBJ",
    "SetUnitPositionLocFacingBearclaw", "MoveLocation",
    "DistanceBetweenPoints", "AngleBetweenPoints",
    "IssuePointOrderLoc", "IssuePointOrderLocBJ",
    "AddSpecialEffectLoc", "AddSpecialEffectLocBJ", "ReviveHeroLoc",
    "AddSpellEffectLoc", "AddSpellEffectByIdLoc", "AddLightningLoc",
    "PolarProjectionBJ", "OffsetLocation",
    "MeleeGetLocWithinRect", "MeleeGetProjectedLoc",
    # group
    "GroupAddUnit", "GroupRemoveUnit", "GroupClear", "ForGroup",
    "FirstOfGroup", "GroupPickRandomUnit", "CountUnitsInGroup",
    "IsUnitInGroup", "GroupEnumUnitsInRange", "GroupEnumUnitsInRect",
    "GroupEnumUnitsOfPlayer", "GroupEnumUnitsOfType",
    "GroupEnumUnitsSelected",
    # force
    "ForceAddPlayer", "ForceRemovePlayer", "ForceClear", "ForForce",
    "IsPlayerInForce", "CountPlayersInForceBJ",
    "ForceEnumPlayers", "ForceEnumPlayersCounted",
    "ForceEnumAllies", "ForceEnumEnemies",
    # timer
    "TimerStart", "TimerGetRemaining", "TimerGetElapsed", "TimerGetTimeout",
    "PauseTimer", "ResumeTimer",
    # trigger
    "TriggerAddAction", "TriggerAddCondition", "TriggerEvaluate",
    "TriggerExecute", "EnableTrigger", "DisableTrigger", "IsTriggerEnabled",
    "TriggerWaitOnSleeps",
    # rect
    "SetRect", "SetRectFromLoc", "MoveRectTo", "MoveRectToLoc",
    "GetRectCenter", "GetRandomLocInRect", "RectFromCenterSizeBJ",
    "IsUnitInRect", "RectContainsUnit", "RectContainsCoords", "RectContainsLoc",
    "GetUnitsInRectMatching", "GetUnitsInRectAll", "GetUnitsInRectOfPlayer",
    # 以位置/矩形为输入、只读取的枚举创建函数
    "GetUnitsInRangeOfLocMatching", "GetUnitsInRangeOfLocAll",
    "YDWEGetUnitsInRangeOfLocAllNull",
    # hashtable 读取
    "HaveSavedHandle", "HaveSavedInteger", "HaveSavedReal",
    "HaveSavedString", "HaveSavedBoolean",
    # 只读取句柄的原生/BJ 函数（不长期持有传入句柄）
    "GetHandleId",
    "CreateNUnitsAtLoc", "CreateNUnitsAtLocFacingLocBJ", "CreateUnitAtLoc",
    "CreateDestructableLoc", "CreateItemLoc", "CreateTextTagLocBJ",
    "DisplayTimedTextToForce", "DisplayTextToForce",
    "TransmissionFromUnitWithNameBJ", "TransmissionFromUnitTypeWithNameBJ",
    "IssuePointOrderByIdLoc", "IssuePointOrderLoc",
    "PanCameraToTimedLocForPlayer", "PingMinimapLocForForce",
    "PingMinimapLocForForceEx",
    "SetUnitFacingToFaceLocTimed", "SetUnitPositionLocFacingLocBJ",
    "PlaySoundAtPointBJ", "CreateFogModifierRadiusLocBJ",
    "SetBlightRadiusLocBJ", "EnumDestructablesInRect",
    "RandomUnitFromGroup", "GetRandomSubGroup", "GetUnitsOfPlayerMatching",
    "ShowTextTagForceBJ", "ShowInterfaceForceOn", "ShowInterfaceForceOff",
    "CinematicModeBJ", "SetItemPositionLoc", "CreateTimerDialogBJ",
})

# 原生命名空间前缀：这些函数族按值使用句柄，不会把句柄保存到别处。
SAFE_ARGUMENT_PREFIXES = (
    "Group", "ForGroup", "Force", "Timer", "Trigger", "Rect",
    "Load", "HaveSaved", "Flush", "RemoveSaved",
)

_HASHTABLE_SAVE_PREFIX = "Save"
_HASHTABLE_SAVE_SUFFIX = "Handle"
_FOR_GROUP_BJ = "ForGroupBJ"


def _is_safe_consumer(name):
    if name in SAFE_ARGUMENT_FUNCS:
        return True
    return name.startswith(SAFE_ARGUMENT_PREFIXES)


def _is_hashtable_save(name):
    return name.startswith(_HASHTABLE_SAVE_PREFIX) and name.endswith(_HASHTABLE_SAVE_SUFFIX)


def is_handle_type(type_name):
    return type_name in TRACKED_HANDLE_TYPES


# --- 符号与事实模型 -------------------------------------------------------


@dataclass(slots=True)
class FunctionSignature:
    name: str
    params: tuple[tuple[str, str], ...] = ()
    return_type: str = "nothing"
    is_native: bool = False

    @property
    def param_names(self):
        return tuple(name for name, _ in self.params)

    def param_type(self, index):
        if 0 <= index < len(self.params):
            return self.params[index][1]
        return ""


@dataclass(slots=True)
class DefSite:
    name: str
    line: int
    column: int
    kind: str


@dataclass(slots=True)
class UseSite:
    name: str
    line: int
    column: int
    kind: str


@dataclass(slots=True)
class VariableSymbol:
    name: str
    type_name: str = ""
    scope: str = "global"
    is_array: bool = False
    implicit: bool = False
    line: int = 0
    column: int = 0
    defs: list[DefSite] = field(default_factory=list)
    uses: list[UseSite] = field(default_factory=list)


@dataclass(slots=True)
class CallSite:
    caller: str
    callee: str
    line: int
    column: int
    kind: str = "direct"
    target_resolved: bool = True
    arg_count: int = 0


@dataclass(slots=True)
class EscapeFact:
    kind: str
    line: int
    column: int
    detail: str = ""
    variable: str | None = None

    @property
    def description(self):
        if self.kind == "global_store":
            return f"写入全局变量 {self.detail}"
        if self.kind == "return":
            return "作为返回值转移所有权"
        if self.kind == "argument":
            return f"传入函数 {self.detail}，无法确认其是否长期持有"
        if self.kind == "array_store":
            return f"存入数组 {self.detail}"
        if self.kind == "hashtable_store":
            return f"存入哈希表（{self.detail}）"
        if self.kind == "ownership_sink":
            return f"所有权移交给 {self.detail}"
        return self.kind


@dataclass(slots=True)
class DestroySite:
    destroyer: str
    line: int
    column: int
    variable: str | None = None
    node: int | None = None


@dataclass(slots=True)
class CreationSite:
    function: str
    creator: str
    handle_type: str
    kind: str  # local / param / array / global / inline
    line: int
    column: int
    variable: str | None = None
    statement: object | None = None
    node: int | None = None
    in_loop: bool = False
    shared: bool = False
    long_lived: bool = False
    gui_managed: bool = False
    cleanup: str = "none"
    status: str = ""
    auto_fix: bool = False
    released: bool = False
    reasons: list[str] = field(default_factory=list)
    escapes: list[EscapeFact] = field(default_factory=list)
    destroys: list[DestroySite] = field(default_factory=list)
    releases: list[tuple[int, int]] = field(default_factory=list)

    @property
    def suspected_leak(self):
        return self.status == "leaked"


@dataclass(slots=True)
class FunctionAnalysis:
    name: str
    signature: FunctionSignature
    cfg: CFG
    definition: FunctionDef
    symbols: dict[str, VariableSymbol] = field(default_factory=dict)
    creations: list[CreationSite] = field(default_factory=list)
    destroys: list[DestroySite] = field(default_factory=list)
    escapes: list[EscapeFact] = field(default_factory=list)
    call_sites: list[CallSite] = field(default_factory=list)
    dynamic_calls: list[CallSite] = field(default_factory=list)
    gui_flag: bool = False
    has_unparsed: bool = False

    def creations_of_type(self, handle_type):
        return [item for item in self.creations if item.handle_type == handle_type]


@dataclass(slots=True)
class CallGraph:
    edges: list[CallSite] = field(default_factory=list)
    callees: dict[str, set[str]] = field(default_factory=dict)
    callers: dict[str, set[str]] = field(default_factory=dict)
    unresolved: list[CallSite] = field(default_factory=list)
    known: set[str] = field(default_factory=set)

    def add(self, site):
        self.edges.append(site)
        if site.kind == "dynamic" or not site.callee:
            self.unresolved.append(site)
            return
        if site.callee not in self.known:
            return
        self.callees.setdefault(site.caller, set()).add(site.callee)
        self.callers.setdefault(site.callee, set()).add(site.caller)

    def has_edge(self, caller, callee):
        return callee in self.callees.get(caller, set())

    def reachable_from(self, name):
        seen = set()
        queue = deque([name])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            for callee in self.callees.get(current, ()):
                if callee not in seen:
                    queue.append(callee)
        return seen


@dataclass(slots=True)
class ScriptSemantics:
    script: Script
    signatures: dict[str, FunctionSignature] = field(default_factory=dict)
    globals: dict[str, VariableSymbol] = field(default_factory=dict)
    functions: dict[str, FunctionAnalysis] = field(default_factory=dict)
    call_graph: CallGraph = field(default_factory=CallGraph)
    global_creations: list[CreationSite] = field(default_factory=list)
    shared_globals: set[str] = field(default_factory=set)
    dynamic_calls: list[CallSite] = field(default_factory=list)

    def function(self, name):
        return self.functions.get(name)

    def iter_creations(self):
        for analysis in self.functions.values():
            yield from analysis.creations

    def creations_of_type(self, handle_type):
        return [item for item in self.iter_creations() if item.handle_type == handle_type]

    def leak_candidates(self):
        return [item for item in self.iter_creations() if item.suspected_leak]

    def auto_fix_candidates(self):
        return [item for item in self.iter_creations() if item.auto_fix]

    def unresolved_calls(self):
        return list(self.call_graph.unresolved)


# --- 分析器 ---------------------------------------------------------------


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def add(self, name):
        self.parent.setdefault(name, name)

    def find(self, name):
        self.add(name)
        root = name
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[name] != root:
            self.parent[name], name = root, self.parent[name]
        return root

    def union(self, left, right):
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root

    def groups(self):
        result = {}
        for name in self.parent:
            result.setdefault(self.find(name), set()).add(name)
        return result


def _literal_bool(expr):
    return isinstance(expr, Literal) and expr.kind == "bool"


def _literal_string(expr):
    if isinstance(expr, Literal) and expr.kind == "string":
        value = expr.value
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    return None


def _walk_statements(statements):
    for statement in statements:
        if statement is None:
            continue
        yield statement
        if isinstance(statement, Debug) and statement.statement is not None:
            yield from _walk_statements([statement.statement])
        elif isinstance(statement, If):
            for branch in statement.branches:
                yield from _walk_statements(branch.body.statements)
            if statement.else_body is not None:
                yield from _walk_statements(statement.else_body.statements)
        elif isinstance(statement, Loop):
            yield from _walk_statements(statement.body.statements)


def _function_scopes(script):
    scopes = {}
    for function in script.functions:
        names = {param.name for param in function.params}
        if function.body is not None:
            for statement in _walk_statements(function.body.statements):
                if isinstance(statement, LocalDecl):
                    names.add(statement.name)
        scopes[function.name] = names
    return scopes


def _build_signatures(script):
    signatures = {}
    for function in script.functions:
        signatures[function.name] = FunctionSignature(
            name=function.name,
            params=tuple((param.name, param.type_name) for param in function.params),
            return_type=function.return_type,
            is_native=function.is_native,
        )
    return signatures


def _collect_shared_globals(script, scopes):
    """预扫描全局创建与全局别名，得到共享句柄全局集合。"""
    shared = set()
    assignments = []
    for function in script.functions:
        if function.body is None:
            continue
        local_names = scopes.get(function.name, set())
        for statement in _walk_statements(function.body.statements):
            if not isinstance(statement, Set) or statement.target is None:
                continue
            target = statement.target
            if target.name in local_names:
                continue
            value = statement.value
            if isinstance(value, Call) and value.name in SHARED_HANDLE_CREATORS:
                shared.add(target.name)
            elif isinstance(value, VarRef) and value.index is None:
                assignments.append((target.name, value.name))
    for global_var in script.globals:
        if isinstance(global_var.value, Call) and global_var.value.name in SHARED_HANDLE_CREATORS:
            shared.add(global_var.name)
    changed = True
    while changed:
        changed = False
        for target, source in assignments:
            if source in shared and target not in shared:
                shared.add(target)
                changed = True
    return shared


class _FunctionAnalyzer:
    def __init__(
        self, function, signature, script_globals, shared_globals,
        signatures, unparsed_lines=frozenset(),
    ):
        self.function = function
        self.signature = signature
        self.globals = script_globals
        self.shared_globals = shared_globals
        self.signatures = signatures

        self.cfg = None
        self.scope = {}
        self.creations = []
        self.destroys = []
        self.escapes = []
        self.call_sites = []
        self.dynamic_calls = []
        self.gui_flag = False
        self.has_unparsed = bool(function.errors) or bool(unparsed_lines)

        self._aliases = _UnionFind()
        self._shared_names = set(shared_globals)
        self._long_lived_names = set()
        self._gui_managed_names = set()
        self._releases = []

    # -- 驱动 ---------------------------------------------------------

    def analyze(self):
        for param in self.function.params:
            symbol = VariableSymbol(
                name=param.name, type_name=param.type_name, scope="param",
                line=param.line, column=param.column,
            )
            symbol.defs.append(DefSite(param.name, param.line, param.column, "param"))
            self.scope[param.name] = symbol
        if self.function.body is not None:
            self._prescan(self.function.body.statements)
            self.cfg = build_cfg(self.function)
            self._walk_block(self.function.body)
            self._finalize()
        else:
            self.cfg = build_cfg(self.function)
        return FunctionAnalysis(
            name=self.function.name,
            signature=self.signature,
            cfg=self.cfg,
            definition=self.function,
            symbols=self.scope,
            creations=self.creations,
            destroys=self.destroys,
            escapes=self.escapes,
            call_sites=self.call_sites,
            dynamic_calls=self.dynamic_calls,
            gui_flag=self.gui_flag,
            has_unparsed=self.has_unparsed,
        )

    def _prescan(self, statements):
        for statement in statements:
            if statement is None:
                continue
            if isinstance(statement, RawStmt):
                self.has_unparsed = True
            elif isinstance(statement, Debug) and statement.statement is not None:
                self._prescan([statement.statement])
            elif isinstance(statement, If):
                for branch in statement.branches:
                    self._prescan(branch.body.statements)
                if statement.else_body is not None:
                    self._prescan(statement.else_body.statements)
            elif isinstance(statement, Loop):
                self._prescan(statement.body.statements)
            elif isinstance(statement, Set) and statement.target is not None:
                if statement.target.name == "bj_wantDestroyGroup" and _literal_bool(statement.value):
                    self.gui_flag = True

    # -- 符号 ---------------------------------------------------------

    def _lookup(self, name):
        symbol = self.scope.get(name)
        if symbol is not None:
            return symbol
        return self.globals.get(name)

    def _global_symbol(self, name, type_name=""):
        symbol = self.globals.get(name)
        if symbol is None:
            symbol = VariableSymbol(name=name, type_name=type_name, scope="global", implicit=True)
            self.globals[name] = symbol
        elif type_name and not symbol.type_name:
            symbol.type_name = type_name
        return symbol

    def _declare_local(self, statement):
        symbol = VariableSymbol(
            name=statement.name,
            type_name=statement.type_name,
            scope="local",
            is_array=statement.is_array,
            line=statement.line,
            column=statement.column,
        )
        symbol.defs.append(DefSite(statement.name, statement.line, statement.column, "local"))
        self.scope[statement.name] = symbol
        return symbol

    def _record_use(self, name, line, column, kind):
        symbol = self._lookup(name)
        if symbol is None:
            symbol = self._global_symbol(name)
        symbol.uses.append(UseSite(name, line, column, kind))

    def _infer_handle_type(self, expr):
        if isinstance(expr, Call):
            return TYPE_BY_CREATOR.get(expr.name)
        if isinstance(expr, VarRef):
            symbol = self._lookup(expr.name)
            if symbol is not None and is_handle_type(symbol.type_name):
                return symbol.type_name
        return None

    # -- 语句 ---------------------------------------------------------

    def _walk_block(self, block):
        for statement in block.statements:
            if statement is not None:
                self._walk_statement(statement)

    def _walk_statement(self, statement):
        node_id = self.cfg.node_for_statement(statement)

        if isinstance(statement, Debug):
            if statement.statement is not None:
                self._walk_statement(statement.statement)
            return
        if isinstance(statement, RawStmt):
            self.has_unparsed = True
            return
        if isinstance(statement, LocalDecl):
            symbol = self._declare_local(statement)
            if statement.value is not None:
                self._walk_expr(
                    statement.value, ("root_local", symbol.name),
                    statement, node_id,
                )
            return
        if isinstance(statement, Set):
            self._walk_set(statement, node_id)
            return
        if isinstance(statement, CallStmt):
            self._walk_call_statement(statement, node_id)
            return
        if isinstance(statement, If):
            for branch in statement.branches:
                if branch.condition is not None:
                    self._walk_expr(branch.condition, ("expr",), statement, node_id)
                self._walk_block(branch.body)
            if statement.else_body is not None:
                self._walk_block(statement.else_body)
            return
        if isinstance(statement, Loop):
            self._walk_block(statement.body)
            return
        if isinstance(statement, ExitWhen):
            if statement.condition is not None:
                self._walk_expr(statement.condition, ("expr",), statement, node_id)
            return
        if isinstance(statement, Return):
            if statement.value is not None:
                self._walk_expr(statement.value, ("return",), statement, node_id)
            return

    def _walk_set(self, statement, node_id):
        target = statement.target
        if target is None:
            return
        if target.index is not None:
            self._walk_expr(target.index, ("expr",), statement, node_id)

        symbol = self._lookup(target.name)
        if symbol is None:
            symbol = self._global_symbol(target.name)
        symbol.defs.append(DefSite(target.name, statement.line, statement.column, "set"))
        if target.index is not None and symbol.type_name:
            symbol.is_array = True

        if statement.value is None:
            return

        if (
            is_handle_type(symbol.type_name)
            and symbol.scope in ("local", "param")
            and isinstance(statement.value, Literal)
            and statement.value.kind == "null"
        ):
            # 销毁之后再置空是正常写法；置空发生在销毁之前则原句柄已经丢失。
            self._releases.append((symbol.name, statement.line, statement.column))

        if target.index is not None:
            owner = ("root_index", target.name)
        elif symbol.scope == "local":
            owner = ("root_local", symbol.name)
        elif symbol.scope == "param":
            owner = ("root_param", symbol.name)
        else:
            owner = ("root_global", symbol.name)
        self._walk_expr(statement.value, owner, statement, node_id)

    def _walk_call_statement(self, statement, node_id):
        call = statement.call
        if call is None:
            return
        if call.name in DESTROYER_TYPE:
            variable = None
            if call.args:
                first = call.args[0]
                if isinstance(first, VarRef):
                    variable = first.name
            self.destroys.append(
                DestroySite(
                    destroyer=call.name,
                    line=call.line or statement.line,
                    column=call.column or statement.column,
                    variable=variable,
                    node=node_id,
                )
            )
        self._walk_expr(call, ("stmt",), statement, node_id)

    # -- 表达式 -------------------------------------------------------

    def _walk_expr(self, expr, owner, statement, node_id, parent_call=None):
        if expr is None:
            return
        if isinstance(expr, Literal) or isinstance(expr, CodeRef):
            return
        if isinstance(expr, VarRef):
            self._record_use(expr.name, expr.line, expr.column, owner[0])
            if expr.index is not None:
                self._walk_expr(expr.index, ("expr",), statement, node_id)
            self._handle_varref_owner(expr, owner, statement, node_id)
            return
        if isinstance(expr, Unary):
            self._walk_expr(expr.operand, ("expr",), statement, node_id)
            return
        if isinstance(expr, Binary):
            self._walk_expr(expr.left, ("expr",), statement, node_id)
            self._walk_expr(expr.right, ("expr",), statement, node_id)
            return
        if isinstance(expr, Call):
            self._walk_call(expr, owner, statement, node_id)
            return

    def _walk_call(self, call, owner, statement, node_id):
        line = call.line or statement.line
        column = call.column or statement.column
        handle_type = TYPE_BY_CREATOR.get(call.name)
        self._record_call(call, line, column)

        if handle_type is not None:
            self._record_creation(call, handle_type, owner, statement, node_id, line, column)
        elif owner[0] == "root_global" and call.name in SHARED_HANDLE_CREATORS:
            self._shared_names.add(owner[1])

        self._handle_special_callee(call, line, column)

        for index, arg in enumerate(call.args):
            if isinstance(arg, CodeRef):
                self._record_callback(arg, line, column)
                continue
            self._walk_expr(
                arg, ("arg", call.name, index), statement, node_id,
                parent_call=call,
            )

    def _record_call(self, call, line, column):
        self.call_sites.append(
            CallSite(
                caller=self.function.name,
                callee=call.name,
                line=line,
                column=column,
                kind="direct",
                target_resolved=True,
                arg_count=len(call.args),
            )
        )

    def _record_callback(self, code_ref, line, column):
        self.call_sites.append(
            CallSite(
                caller=self.function.name,
                callee=code_ref.name,
                line=code_ref.line or line,
                column=code_ref.column or column,
                kind="callback",
                target_resolved=True,
                arg_count=0,
            )
        )

    def _handle_special_callee(self, call, line, column):
        name = call.name
        if name == "ExecuteFunc":
            target = _literal_string(call.args[0]) if call.args else None
            if target is None:
                site = CallSite(
                    caller=self.function.name,
                    callee="",
                    line=line,
                    column=column,
                    kind="dynamic",
                    target_resolved=False,
                    arg_count=len(call.args),
                )
                self.dynamic_calls.append(site)
            else:
                self.call_sites.append(
                    CallSite(
                        caller=self.function.name,
                        callee=target,
                        line=line,
                        column=column,
                        kind="execute_func",
                        target_resolved=True,
                        arg_count=len(call.args),
                    )
                )
            return

        if name == "TimerStart" and call.args:
            first = call.args[0]
            if isinstance(first, VarRef) and self._var_type(first.name) == "timer":
                self._long_lived_names.add(first.name)
            return

        if name.startswith("Trigger") and name != "CreateTrigger":
            if call.args and isinstance(call.args[0], VarRef):
                if self._var_type(call.args[0].name) == "trigger":
                    self._long_lived_names.add(call.args[0].name)
            if name == "TriggerAddCondition" and len(call.args) >= 2:
                condition = call.args[1]
                if isinstance(condition, VarRef) and self._var_type(condition.name) == "boolexpr":
                    self._long_lived_names.add(condition.name)
            return

        if name == _FOR_GROUP_BJ and self.gui_flag and call.args:
            first = call.args[0]
            if isinstance(first, VarRef) and self._var_type(first.name) == "group":
                self._gui_managed_names.add(first.name)

    def _var_type(self, name):
        symbol = self._lookup(name)
        return symbol.type_name if symbol is not None else ""

    def _handle_varref_owner(self, expr, owner, statement, node_id):
        kind = owner[0]
        name = expr.name
        symbol = self._lookup(name)
        if symbol is None or not is_handle_type(symbol.type_name):
            return
        handle_type = symbol.type_name

        if kind == "root_local" or kind == "root_param":
            target = self.scope.get(owner[1])
            if target is not None and is_handle_type(target.type_name):
                self._aliases.union(target.name, name)
                self._aliases.add(target.name)
            if name in self._shared_names:
                self._shared_names.add(owner[1])
            return

        if kind == "root_global":
            self.escapes.append(
                EscapeFact(
                    kind="global_store",
                    line=expr.line or statement.line,
                    column=expr.column or statement.column,
                    detail=owner[1],
                    variable=name,
                )
            )
            return

        if kind == "root_index":
            self.escapes.append(
                EscapeFact(
                    kind="array_store",
                    line=expr.line or statement.line,
                    column=expr.column or statement.column,
                    detail=owner[1],
                    variable=name,
                )
            )
            return

        if kind == "return":
            self.escapes.append(
                EscapeFact(
                    kind="return",
                    line=expr.line or statement.line,
                    column=expr.column or statement.column,
                    variable=name,
                )
            )
            return

        if kind == "arg":
            self._handle_argument_use(expr, name, handle_type, owner[1], statement)

    def _handle_argument_use(self, expr, name, handle_type, callee, statement):
        line = expr.line or statement.line
        column = expr.column or statement.column

        if callee in DESTROYER_TYPE:
            return
        if callee in OWNERSHIP_SINK_FUNCS:
            self.escapes.append(
                EscapeFact("ownership_sink", line, column, detail=callee, variable=name)
            )
            return
        if _is_hashtable_save(callee):
            self.escapes.append(
                EscapeFact("hashtable_store", line, column, detail=callee, variable=name)
            )
            return
        if handle_type == "timer" and callee == "TimerStart":
            self._long_lived_names.add(name)
            return
        if handle_type == "trigger" and callee.startswith("Trigger"):
            self._long_lived_names.add(name)
            return
        if handle_type == "boolexpr" and callee == "TriggerAddCondition":
            self._long_lived_names.add(name)
            return
        if handle_type == "group" and callee == _FOR_GROUP_BJ and self.gui_flag:
            self._gui_managed_names.add(name)
            return
        if _is_safe_consumer(callee):
            return
        self.escapes.append(
            EscapeFact("argument", line, column, detail=callee, variable=name)
        )

    # -- 创建点 -------------------------------------------------------

    def _record_creation(self, call, handle_type, owner, statement, node_id, line, column):
        kind = owner[0]
        creation = CreationSite(
            function=self.function.name,
            creator=call.name,
            handle_type=handle_type,
            kind="inline",
            line=line,
            column=column,
            statement=statement,
            node=node_id,
            shared=call.name in SHARED_HANDLE_CREATORS,
            in_loop=bool(self.cfg and node_id is not None and self.cfg.is_in_loop(node_id)),
        )

        if kind == "root_local":
            creation.kind = "local"
            creation.variable = owner[1]
            self._aliases.add(owner[1])
        elif kind == "root_param":
            creation.kind = "param"
            creation.variable = owner[1]
            self._aliases.add(owner[1])
        elif kind == "root_index":
            creation.kind = "array"
            creation.variable = owner[1]
            self._aliases.add(owner[1])
            creation.escapes.append(
                EscapeFact("array_store", line, column, detail=owner[1])
            )
        elif kind == "root_global":
            creation.kind = "global"
            creation.variable = owner[1]
            symbol = self._global_symbol(owner[1], handle_type)
            if not symbol.type_name:
                symbol.type_name = handle_type
            if creation.shared:
                self._shared_names.add(owner[1])
        elif kind == "return":
            creation.escapes.append(
                EscapeFact("return", line, column)
            )
        elif kind == "arg":
            self._classify_inline_argument(creation, owner[1], owner[2], line, column)
        else:
            creation.reasons.append("创建结果被丢弃")

        self.creations.append(creation)

    def _classify_inline_argument(self, creation, callee, index, line, column):
        handle_type = creation.handle_type
        if callee in DESTROYER_TYPE:
            if DESTROYER_TYPE[callee] == handle_type:
                creation.cleanup = "cleaned"
            else:
                creation.reasons.append(f"销毁函数 {callee} 与类型 {handle_type} 不匹配")
            return
        if callee in OWNERSHIP_SINK_FUNCS:
            creation.escapes.append(
                EscapeFact("ownership_sink", line, column, detail=callee)
            )
            return
        if _is_hashtable_save(callee):
            creation.escapes.append(
                EscapeFact("hashtable_store", line, column, detail=callee)
            )
            return
        if handle_type == "timer" and callee == "TimerStart":
            creation.long_lived = True
            return
        if handle_type == "trigger" and callee.startswith("Trigger"):
            creation.long_lived = True
            return
        if handle_type == "boolexpr" and callee == "TriggerAddCondition":
            creation.long_lived = True
            return
        if handle_type == "group" and callee == _FOR_GROUP_BJ and self.gui_flag:
            creation.gui_managed = True
            creation.cleanup = "managed"
            return
        if _is_safe_consumer(callee):
            creation.reasons.append("内联创建，调用方不持有句柄")
            return
        creation.escapes.append(
            EscapeFact("argument", line, column, detail=callee)
        )

    # -- 汇总 ---------------------------------------------------------

    def _finalize(self):
        groups = self._aliases.groups()
        component_of = {}
        for root, names in groups.items():
            for name in names:
                component_of[name] = root

        bound = [item for item in self.creations if item.kind in ("local", "param", "array")]
        components = {}
        for creation in bound:
            root = component_of.get(creation.variable, creation.variable)
            data = components.setdefault(
                root,
                {
                    "names": set(), "creations": [],
                    "destroys": [], "escapes": [], "releases": [],
                },
            )
            data["names"].add(creation.variable)
            data["creations"].append(creation)
        for name in component_of:
            root = component_of[name]
            if root in components:
                components[root]["names"].add(name)

        for destroy in self.destroys:
            if destroy.variable is None:
                continue
            root = component_of.get(destroy.variable)
            if root in components:
                components[root]["destroys"].append(destroy)
        for escape in self.escapes:
            if escape.variable is None:
                continue
            root = component_of.get(escape.variable)
            if root in components:
                components[root]["escapes"].append(escape)
        for name, line, column in self._releases:
            root = component_of.get(name)
            if root in components:
                components[root]["releases"].append((line, column))

        for data in components.values():
            names = data["names"]
            shared = any(name in self._shared_names for name in names)
            long_lived = any(name in self._long_lived_names for name in names)
            gui_managed = any(name in self._gui_managed_names for name in names)
            has_param = any(
                self.scope.get(name) is not None
                and self.scope[name].scope == "param"
                for name in names
            )
            self._attribute_events(data)
            for creation in data["creations"]:
                creation.shared = creation.shared or shared
                creation.long_lived = creation.long_lived or (
                    long_lived and creation.handle_type in ("timer", "trigger", "boolexpr")
                )
                creation.gui_managed = creation.gui_managed or (
                    gui_managed and creation.handle_type == "group"
                )
                creation.reasons.append("参数句柄不归函数所有" if has_param else "")
                self._finish_bound_creation(creation, has_param=has_param)

        for creation in self.creations:
            if creation.kind in ("inline", "global"):
                self._finish_detached_creation(creation)

    def _attribute_events(self, data):
        events = []
        for creation in data["creations"]:
            events.append((creation.line, creation.column, 0, creation))
        for destroy in data["destroys"]:
            events.append((destroy.line, destroy.column, 1, destroy))
        for escape in data["escapes"]:
            events.append((escape.line, escape.column, 2, escape))
        for line, column in data["releases"]:
            events.append((line, column, 3, (line, column)))
        events.sort(key=lambda item: (item[0], item[1], item[2]))

        current = None
        for line, column, order, item in events:
            if order == 0:
                current = item
                continue
            if current is None:
                continue
            if order == 1:
                current.destroys.append(item)
            elif order == 2:
                current.escapes.append(item)
            else:
                current.releases.append(item)

    def _finish_bound_creation(self, creation, has_param):
        creation.reasons = [item for item in creation.reasons if item]
        cleanup = "none"
        if creation.destroys:
            destroy_nodes = frozenset(
                item.node for item in creation.destroys if item.node is not None
            )
            if creation.node is None or not destroy_nodes:
                cleanup = "unknown"
            elif self.cfg.can_reach_exit(creation.node, destroy_nodes):
                cleanup = "partial"
            else:
                cleanup = "complete"
        if creation.releases:
            first_release = min(line for line, _ in creation.releases)
            first_destroy = min(
                (item.line for item in creation.destroys), default=None
            )
            if first_destroy is None or first_release < first_destroy:
                creation.released = True
                cleanup = "none"
                creation.reasons.append("引用在销毁前被置空，原句柄已无法释放")
        creation.cleanup = cleanup
        creation.status = self._status_for(creation)
        creation.auto_fix = self._bound_auto_fix(creation, has_param)

    def _finish_detached_creation(self, creation):
        if creation.kind == "global":
            creation.status = "global_owned"
            creation.cleanup = "global"
            creation.reasons.append("创建结果写入全局变量，生命周期由全局持有")
        else:
            creation.status = self._status_for(creation)
            if creation.status == "leaked" and creation.cleanup == "none":
                creation.reasons.append("内联句柄没有销毁点")
        creation.auto_fix = self._inline_auto_fix(creation)

    def _status_for(self, creation):
        if creation.kind == "global":
            return "global_owned"
        if creation.shared:
            return "shared"
        if creation.long_lived:
            return "long_lived"
        if creation.gui_managed or creation.cleanup == "managed":
            return "managed"
        if creation.escapes:
            return "escaped"
        if creation.cleanup in ("complete", "cleaned"):
            return "cleaned"
        return "leaked"

    def _base_reasons(self, creation):
        reasons = []
        if creation.handle_type not in AUTO_FIX_TYPES:
            reasons.append("该类型仅报告，不自动修复")
        if creation.shared:
            reasons.append("共享句柄，禁止销毁")
        if creation.long_lived:
            reasons.append("长期对象，禁止自动销毁")
        if creation.gui_managed or creation.cleanup == "managed":
            reasons.append("由 GUI 的 bj_wantDestroyGroup 管理")
        if creation.creator in NO_AUTO_DESTROY and not creation.long_lived:
            reasons.append("创建函数属于长期对象，禁止自动销毁")
        if creation.escapes:
            reasons.append("句柄已逃逸：" + "；".join(
                sorted({item.description for item in creation.escapes})
            ))
        if creation.cleanup == "partial":
            reasons.append("仅在部分路径销毁")
        if self.has_unparsed:
            reasons.append("函数包含无法解析的语句")
        return reasons

    def _bound_auto_fix(self, creation, has_param):
        reasons = self._base_reasons(creation)
        ok = not self.has_unparsed
        if creation.handle_type not in AUTO_FIX_TYPES:
            ok = False
        if creation.kind != "local":
            ok = False
            reasons.append("只有局部变量可以自动插入清理")
        if has_param:
            ok = False
        if creation.status != "leaked":
            ok = False
        if creation.cleanup != "none":
            ok = False
        if creation.released:
            ok = False
        if creation.in_loop:
            ok = False
            reasons.append("循环内创建，需要逐次清理")
        if self.cfg.returns:
            ok = False
            if creation.status == "leaked":
                reasons.append("函数存在提前返回，清理点无法统一")
        creation.reasons.extend(reasons)
        creation.reasons = list(dict.fromkeys(creation.reasons))
        return ok

    def _inline_auto_fix(self, creation):
        reasons = self._base_reasons(creation)
        ok = not self.has_unparsed
        if creation.handle_type not in AUTO_FIX_TYPES:
            ok = False
        if creation.status != "leaked":
            ok = False
        if creation.cleanup not in ("none", ""):
            ok = False
        if creation.kind != "inline":
            ok = False
        creation.reasons.extend(reasons)
        creation.reasons = list(dict.fromkeys(creation.reasons))
        return ok


def analyze_script(script):
    """分析一个已解析的 Script，返回 ScriptSemantics。"""
    scopes = _function_scopes(script)
    signatures = _build_signatures(script)
    shared_globals = _collect_shared_globals(script, scopes)

    globals_table = {}
    for global_var in script.globals:
        symbol = VariableSymbol(
            name=global_var.name,
            type_name=global_var.type_name,
            scope="global",
            is_array=global_var.is_array,
            line=global_var.line,
            column=global_var.column,
        )
        globals_table[global_var.name] = symbol

    semantics = ScriptSemantics(
        script=script,
        signatures=signatures,
        globals=globals_table,
        shared_globals=shared_globals,
    )
    semantics.call_graph.known = set(signatures)

    for index, function in enumerate(script.functions):
        if function.name not in signatures:
            continue
        next_line = (
            script.functions[index + 1].line
            if index + 1 < len(script.functions)
            else max(script.total_lines, function.line) + 1
        )
        unparsed = {
            line for line in script.unparsed_lines
            if function.line <= line < next_line
        }
        analyzer = _FunctionAnalyzer(
            function, signatures[function.name], globals_table,
            shared_globals, signatures, unparsed,
        )
        analysis = analyzer.analyze()
        semantics.functions[function.name] = analysis
        for creation in analysis.creations:
            if creation.kind == "global":
                semantics.global_creations.append(creation)
        semantics.dynamic_calls.extend(analysis.dynamic_calls)

    for global_var in script.globals:
        if isinstance(global_var.value, Call):
            handle_type = TYPE_BY_CREATOR.get(global_var.value.name)
            if handle_type is None:
                continue
            creation = CreationSite(
                function="",
                creator=global_var.value.name,
                handle_type=handle_type,
                kind="global",
                line=global_var.line,
                column=global_var.column,
                variable=global_var.name,
                shared=global_var.value.name in SHARED_HANDLE_CREATORS,
                cleanup="global",
                status="global_owned",
                reasons=["全局初始化"],
            )
            semantics.global_creations.append(creation)

    for analysis in semantics.functions.values():
        for site in analysis.call_sites:
            semantics.call_graph.add(site)
        for site in analysis.dynamic_calls:
            semantics.call_graph.add(site)

    return semantics


def analyze_source(text):
    return analyze_script(parse_script(text))


def analyze_file(path):
    return analyze_script(parse_file(Path(path)))
