"""JASS 抽象语法树节点。

节点只描述结构，不携带源码区间。解析器遇到无法解析的行会生成 RawStmt，
因此下游可以在部分语法失败时继续做泄露分析，而不是丢弃整个函数。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:
    line: int = 0
    column: int = 0


@dataclass(slots=True)
class Script(Node):
    globals: list["GlobalVar"] = field(default_factory=list)
    types: list["TypeDef"] = field(default_factory=list)
    functions: list["FunctionDef"] = field(default_factory=list)
    raw: list["RawTopLevel"] = field(default_factory=list)
    errors: list["ParseError"] = field(default_factory=list)
    total_lines: int = 0
    code_lines: int = 0
    parsed_statements: int = 0
    raw_statements: int = 0
    unparsed_lines: set[int] = field(default_factory=set)

    @property
    def coverage(self):
        if not self.code_lines:
            return 1.0
        return (self.code_lines - len(self.unparsed_lines)) / self.code_lines


@dataclass(slots=True)
class ParseError(Exception):
    line: int = 0
    column: int = 0
    message: str = ""

    def __str__(self):
        return f"第 {self.line} 行第 {self.column} 列：{self.message}"


@dataclass(slots=True)
class GlobalVar(Node):
    type_name: str = ""
    name: str = ""
    is_array: bool = False
    is_constant: bool = False
    value: "Expr | None" = None


@dataclass(slots=True)
class TypeDef(Node):
    name: str = ""
    extends: str = ""


@dataclass(slots=True)
class RawTopLevel(Node):
    text: str = ""
    reason: str = ""


@dataclass(slots=True)
class Param(Node):
    type_name: str = ""
    name: str = ""


@dataclass(slots=True)
class FunctionDef(Node):
    name: str = ""
    params: list[Param] = field(default_factory=list)
    return_type: str = "nothing"
    is_native: bool = False
    body: "Block | None" = None
    errors: list[ParseError] = field(default_factory=list)


@dataclass(slots=True)
class Block(Node):
    statements: list["Stmt"] = field(default_factory=list)


@dataclass(slots=True)
class Stmt(Node):
    pass


@dataclass(slots=True)
class RawStmt(Stmt):
    text: str = ""
    reason: str = ""


@dataclass(slots=True)
class LocalDecl(Stmt):
    type_name: str = ""
    name: str = ""
    is_array: bool = False
    value: "Expr | None" = None


@dataclass(slots=True)
class Set(Stmt):
    target: "VarRef | None" = None
    value: "Expr | None" = None


@dataclass(slots=True)
class CallStmt(Stmt):
    call: "Call | None" = None


@dataclass(slots=True)
class IfBranch(Node):
    condition: "Expr | None" = None
    body: Block = field(default_factory=Block)


@dataclass(slots=True)
class If(Stmt):
    branches: list[IfBranch] = field(default_factory=list)
    else_body: Block | None = None


@dataclass(slots=True)
class Loop(Stmt):
    body: Block = field(default_factory=Block)


@dataclass(slots=True)
class ExitWhen(Stmt):
    condition: "Expr | None" = None


@dataclass(slots=True)
class Return(Stmt):
    value: "Expr | None" = None


@dataclass(slots=True)
class Debug(Stmt):
    statement: Stmt | None = None


@dataclass(slots=True)
class Expr(Node):
    pass


@dataclass(slots=True)
class Literal(Expr):
    kind: str = ""
    value: str = ""


@dataclass(slots=True)
class CodeRef(Expr):
    name: str = ""


@dataclass(slots=True)
class VarRef(Expr):
    name: str = ""
    index: Expr | None = None


@dataclass(slots=True)
class Call(Expr):
    name: str = ""
    args: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class Unary(Expr):
    op: str = ""
    operand: Expr | None = None


@dataclass(slots=True)
class Binary(Expr):
    op: str = ""
    left: Expr | None = None
    right: Expr | None = None
