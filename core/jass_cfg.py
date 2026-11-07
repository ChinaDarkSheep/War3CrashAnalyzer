"""JASS 控制流图：语句级 CFG、循环归属、支配关系与 sleep 标记。

P5.2 的清理完整性判断依赖两件事：
1. 从创建点出发，在所有销毁点都被移除后，是否仍能到达函数出口；
2. 销毁点是否支配每一个出口（用于解释“为什么只在一个分支里销毁不够”）。

这里采用语句级节点，而不是基本块，节点数量与脚本行数同阶，足够支撑泄露
分析，也便于把 AST 语句和 CFG 节点一一对应。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from core.jass_ast import (
    CallStmt,
    Debug,
    ExitWhen,
    If,
    Loop,
    Return,
)

SLEEP_FUNCS = frozenset({"TriggerSleepAction", "PolledWait"})


@dataclass(slots=True)
class CFGNode:
    id: int
    kind: str
    line: int
    column: int
    statement: object | None = None
    label: str = ""
    successors: list[int] = field(default_factory=list)
    predecessors: list[int] = field(default_factory=list)


@dataclass(slots=True)
class LoopInfo:
    header: int
    exit: int
    body_nodes: set[int] = field(default_factory=set)
    exitwhen_nodes: list[int] = field(default_factory=list)


@dataclass(slots=True)
class CFG:
    function_name: str
    nodes: dict[int, CFGNode]
    entry: int
    exit: int
    returns: list[int] = field(default_factory=list)
    loops: list[LoopInfo] = field(default_factory=list)
    sleep_nodes: set[int] = field(default_factory=set)
    stmt_nodes: dict[int, int] = field(default_factory=dict)
    reachable: set[int] = field(default_factory=set)
    _dominators: dict[int, set[int]] | None = field(default=None, repr=False)

    @property
    def exits(self):
        return list(self.returns) + [self.exit]

    @property
    def has_sleep(self):
        return bool(self.sleep_nodes)

    @property
    def sleep_lines(self):
        return {self.nodes[node_id].line for node_id in self.sleep_nodes}

    def node_for_statement(self, statement):
        return self.stmt_nodes.get(id(statement))

    def is_in_loop(self, node_id):
        return any(node_id in loop.body_nodes for loop in self.loops)

    def loop_containing(self, node_id):
        for loop in self.loops:
            if node_id in loop.body_nodes:
                return loop
        return None

    def compute_dominators(self):
        """返回 node -> 支配该节点的节点集合；不可达节点不在结果中。"""
        if self._dominators is not None:
            return self._dominators
        reachable = self.reachable
        dominators = {
            node_id: set(reachable) for node_id in reachable
        }
        dominators[self.entry] = {self.entry}
        changed = True
        while changed:
            changed = False
            for node_id in reachable:
                if node_id == self.entry:
                    continue
                predecessors = [
                    pred for pred in self.nodes[node_id].predecessors
                    if pred in reachable
                ]
                if not predecessors:
                    new = {node_id}
                else:
                    first = dominators[predecessors[0]]
                    new = set(first)
                    for pred in predecessors[1:]:
                        new &= dominators[pred]
                    new.add(node_id)
                if new != dominators[node_id]:
                    dominators[node_id] = new
                    changed = True
        self._dominators = dominators
        return dominators

    def dominates(self, first, second):
        return first in self.compute_dominators().get(second, set())

    def reachable_from(self, start, blocked=frozenset()):
        """从 start 出发、跳过 blocked 节点后可达的节点集合。"""
        seen = set()
        queue = deque([start])
        while queue:
            node_id = queue.popleft()
            if node_id in seen or node_id in blocked:
                continue
            seen.add(node_id)
            for successor in self.nodes[node_id].successors:
                if successor not in seen and successor not in blocked:
                    queue.append(successor)
        return seen

    def can_reach_exit(self, start, blocked=frozenset()):
        reached = self.reachable_from(start, blocked)
        return bool(reached.intersection(self.exits))


def _node_call_name(node):
    statement = node.statement
    if isinstance(statement, CallStmt) and statement.call is not None:
        return statement.call.name
    return None


class _LoopContext:
    def __init__(self, header, exit_node):
        self.header = header
        self.exit = exit_node
        self.exitwhen_nodes = []


class _CFGBuilder:
    def __init__(self, function):
        self.function = function
        self.nodes = {}
        self.returns = []
        self.loops = []
        self.statement_nodes = {}
        self.loop_stack = []

    def new_node(self, kind, line, column, statement=None, label=""):
        node_id = len(self.nodes)
        self.nodes[node_id] = CFGNode(
            id=node_id, kind=kind, line=line, column=column,
            statement=statement, label=label,
        )
        return node_id

    def connect(self, source, target):
        if source is None or target is None:
            return
        node = self.nodes[source]
        if target not in node.successors:
            node.successors.append(target)
        target_node = self.nodes[target]
        if source not in target_node.predecessors:
            target_node.predecessors.append(source)

    def build_sequence(self, statements):
        entry = None
        ends = []
        for statement in statements:
            if statement is None:
                continue
            statement_entry, statement_ends = self.build_statement(statement)
            if statement_entry is None:
                continue
            if entry is None:
                entry = statement_entry
            if ends:
                for end in ends:
                    self.connect(end, statement_entry)
            ends = statement_ends
        return entry, ends

    def build_statement(self, statement):
        if isinstance(statement, Debug):
            if statement.statement is None:
                node = self.new_node(
                    "simple", statement.line, statement.column,
                    statement=statement,
                )
                self.statement_nodes[id(statement)] = node
                return node, [node]
            entry, ends = self.build_statement(statement.statement)
            if entry is not None:
                self.statement_nodes[id(statement)] = entry
            return entry, ends
        if isinstance(statement, If):
            return self.build_if(statement)
        if isinstance(statement, Loop):
            return self.build_loop(statement)
        if isinstance(statement, Return):
            node = self.new_node(
                "return", statement.line, statement.column,
                statement=statement,
            )
            self.statement_nodes[id(statement)] = node
            self.returns.append(node)
            return node, []

        node = self.new_node(
            "simple", statement.line, statement.column,
            statement=statement,
        )
        self.statement_nodes[id(statement)] = node
        if isinstance(statement, ExitWhen) and self.loop_stack:
            self.loop_stack[-1].exitwhen_nodes.append(node)
        return node, [node]

    def build_if(self, statement):
        merge = self.new_node("merge", statement.line, statement.column)
        first = None
        pending_false = None
        for branch in statement.branches:
            condition = self.new_node(
                "branch", branch.line, branch.column, statement=branch,
                label="condition",
            )
            self.statement_nodes[id(branch)] = condition
            if first is None:
                first = condition
            if pending_false is not None:
                self.connect(pending_false, condition)
            body_entry, body_ends = self.build_sequence(branch.body.statements)
            if body_entry is None:
                self.connect(condition, merge)
            else:
                self.connect(condition, body_entry)
                for end in body_ends:
                    self.connect(end, merge)
            pending_false = condition

        if pending_false is None:
            return merge, [merge]

        if statement.else_body is not None:
            else_entry, else_ends = self.build_sequence(
                statement.else_body.statements
            )
            if else_entry is None:
                self.connect(pending_false, merge)
            else:
                self.connect(pending_false, else_entry)
                for end in else_ends:
                    self.connect(end, merge)
        else:
            self.connect(pending_false, merge)

        self.statement_nodes[id(statement)] = first
        return first, [merge]

    def build_loop(self, statement):
        header = self.new_node(
            "loop", statement.line, statement.column, statement=statement,
        )
        loop_exit = self.new_node(
            "loop_exit", statement.line, statement.column,
        )
        context = _LoopContext(header, loop_exit)
        self.loop_stack.append(context)
        before = len(self.nodes)
        body_entry, body_ends = self.build_sequence(statement.body.statements)
        self.loop_stack.pop()

        for exitwhen in context.exitwhen_nodes:
            self.connect(exitwhen, loop_exit)
        self.connect(header, loop_exit)
        if body_entry is not None:
            self.connect(header, body_entry)
            for end in body_ends:
                self.connect(end, header)
        self.loops.append(
            LoopInfo(
                header=header,
                exit=loop_exit,
                body_nodes=set(range(before, len(self.nodes))),
                exitwhen_nodes=list(context.exitwhen_nodes),
            )
        )
        self.statement_nodes[id(statement)] = header
        return header, [loop_exit]

    def build(self):
        function = self.function
        entry = self.new_node(
            "entry", function.line, function.column, label=function.name,
        )
        if function.body is None:
            ends = [entry]
        else:
            first, ends = self.build_sequence(function.body.statements)
            if first is None:
                ends = [entry]
            else:
                self.connect(entry, first)

        exit_node = self.new_node("exit", function.line, function.column)
        for end in ends:
            self.connect(end, exit_node)

        cfg = CFG(
            function_name=function.name,
            nodes=self.nodes,
            entry=entry,
            exit=exit_node,
            returns=self.returns,
            loops=self.loops,
            stmt_nodes=self.statement_nodes,
        )
        cfg.reachable = _reachable(cfg, entry)
        for node_id in cfg.reachable:
            if _node_call_name(cfg.nodes[node_id]) in SLEEP_FUNCS:
                cfg.sleep_nodes.add(node_id)
        return cfg


def _reachable(cfg, start):
    seen = set()
    queue = deque([start])
    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        for successor in cfg.nodes[node_id].successors:
            if successor not in seen:
                queue.append(successor)
    return seen


def build_cfg(function):
    """为一个 FunctionDef 构建 CFG；native/空函数也会得到 entry -> exit。"""
    return _CFGBuilder(function).build()
