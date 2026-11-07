"""容错 JASS 解析器。

真实地图脚本可能来自不同版本的 WorldEdit、加密工具或 vJass 转译，语法
并不总是完美。解析器以“行”为恢复单位：单条语句失败时只把该行降级为
RawStmt，函数其余部分继续解析；块结构缺少结束关键字时也会记录错误并保留
已经解析出的内容。

解析覆盖率 = 1 - 无法解析的代码行 / 全部代码行。注释行不计入代码行。
"""

from __future__ import annotations

from core.jass_ast import (
    Binary,
    Block,
    Call,
    CallStmt,
    CodeRef,
    Debug,
    ExitWhen,
    FunctionDef,
    GlobalVar,
    If,
    IfBranch,
    Literal,
    LocalDecl,
    Loop,
    Param,
    ParseError,
    RawStmt,
    RawTopLevel,
    Return,
    Script,
    Set,
    TypeDef,
    Unary,
    VarRef,
)
from core.jass_lexer import (
    Token,
    TokenKind,
    token_text,
    tokenize,
)

STATEMENT_STOP_KEYWORDS = frozenset(
    {"elseif", "else", "endif", "endloop", "endfunction", "endglobals"}
)

# 任何块遇到这些关键字都应交还给外层：它们只能关闭某个外层结构。
_BLOCK_BOUNDARY_KEYWORDS = frozenset(
    {"elseif", "else", "endif", "endloop", "endfunction", "endglobals"}
)

_COMPARISON_OPERATORS = frozenset({"==", "!=", "<", ">", "<=", ">="})


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.script = Script()
        self.code_line_numbers = set()

    def parse(self):
        tokens = self.tokens
        if tokens:
            self.script.total_lines = max(1, tokens[-1].line)
        self.code_line_numbers = {
            token.line
            for token in tokens
            if token.kind not in (TokenKind.NEWLINE, TokenKind.EOF)
        }
        self.script.code_lines = len(self.code_line_numbers)
        while True:
            self._skip_newlines()
            token = self._current()
            if token.kind == TokenKind.EOF:
                break
            try:
                if token.kind == TokenKind.KEYWORD:
                    if token.value == "globals":
                        self._parse_globals()
                        continue
                    if token.value in ("function", "native"):
                        function = self._parse_function(token.value == "native")
                        self.script.functions.append(function)
                        self.script.parsed_statements += 1
                        continue
                    if token.value == "type":
                        self.script.types.append(self._parse_typedef())
                        self.script.parsed_statements += 1
                        continue
                self._parse_raw_top_level()
            except ParseError as error:
                self.script.errors.append(error)
                self._mark_unparsed(error.line)
                self._skip_to_next_line()
        return self.script

    # --- 基础 token 操作 ---

    def _current(self):
        return self.tokens[self.index]

    def _peek(self, offset=1):
        index = self.index + offset
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def _advance(self):
        token = self.tokens[self.index]
        if token.kind != TokenKind.EOF:
            self.index += 1
        return token

    def _skip_newlines(self):
        while self._current().kind == TokenKind.NEWLINE:
            self._advance()

    def _accept_keyword(self, value):
        token = self._current()
        if token.kind == TokenKind.KEYWORD and token.value == value:
            self._advance()
            return True
        return False

    def _expect_keyword(self, value):
        token = self._current()
        if token.kind == TokenKind.KEYWORD and token.value == value:
            self._advance()
            return token
        raise ParseError(
            token.line, token.column, f"应为关键字 {value}，实际为 {token.value!r}"
        )

    def _expect_ident(self, what):
        token = self._current()
        if token.kind == TokenKind.IDENT:
            self._advance()
            return token
        raise ParseError(
            token.line, token.column, f"应为{what}，实际为 {token.value!r}"
        )

    def _expect_type(self, what="类型名"):
        token = self._current()
        if token.kind == TokenKind.IDENT:
            self._advance()
            return token.value
        if token.kind == TokenKind.KEYWORD and token.value == "nothing":
            self._advance()
            return "nothing"
        raise ParseError(
            token.line, token.column, f"应为{what}，实际为 {token.value!r}"
        )

    def _mark_unparsed(self, line):
        if line in self.code_line_numbers:
            self.script.unparsed_lines.add(line)

    def _record_error(self, line, column, message):
        error = ParseError(line, column, message)
        self.script.errors.append(error)
        self._mark_unparsed(line)
        return error

    def _skip_to_next_line(self):
        while self._current().kind not in (TokenKind.NEWLINE, TokenKind.EOF):
            self._advance()
        if self._current().kind == TokenKind.NEWLINE:
            self._advance()

    def _collect_line(self):
        start = self.index
        while self._current().kind not in (TokenKind.NEWLINE, TokenKind.EOF):
            self._advance()
        collected = self.tokens[start:self.index]
        if self._current().kind == TokenKind.NEWLINE:
            self._advance()
        return collected

    def _finish_statement(self):
        token = self._current()
        if token.kind == TokenKind.NEWLINE:
            self._advance()
            return
        if token.kind == TokenKind.EOF:
            return
        if token.kind == TokenKind.ERROR:
            raise ParseError(token.line, token.column, token.message)
        if token.kind == TokenKind.KEYWORD and token.value in STATEMENT_STOP_KEYWORDS:
            return
        raise ParseError(
            token.line, token.column, f"语句后存在多余内容 {token.value!r}"
        )

    # --- 顶层 ---

    def _parse_raw_top_level(self):
        token = self._current()
        raw_tokens = self._collect_line()
        text = token_text(raw_tokens) or token.value
        if token.kind == TokenKind.ERROR:
            reason = token.message
            self._record_error(token.line, token.column, reason)
        else:
            reason = "无法识别的顶层语句"
            self._record_error(token.line, token.column, reason)
        self.script.raw.append(
            RawTopLevel(text=text, reason=reason, line=token.line,
                        column=token.column)
        )
        self.script.raw_statements += 1

    def _parse_globals(self):
        start = self._current()
        self._advance()
        self._skip_newlines()
        while True:
            token = self._current()
            if token.kind == TokenKind.EOF:
                self._record_error(
                    start.line, start.column, "globals 缺少 endglobals"
                )
                return
            if token.kind == TokenKind.KEYWORD and token.value == "endglobals":
                self._advance()
                self._finish_statement()
                return
            checkpoint = self.index
            try:
                self.script.globals.append(self._parse_global_var())
                self.script.parsed_statements += 1
            except ParseError as error:
                self.script.errors.append(error)
                self._mark_unparsed(error.line)
                self._mark_unparsed(token.line)
                self.index = checkpoint
                raw_tokens = self._collect_line()
                self.script.raw.append(
                    RawTopLevel(
                        text=token_text(raw_tokens), reason=error.message,
                        line=token.line, column=token.column,
                    )
                )
                self.script.raw_statements += 1
            self._skip_newlines()

    def _parse_global_var(self):
        token = self._current()
        is_constant = self._accept_keyword("constant")
        type_name = self._expect_type("全局变量类型")
        is_array = self._accept_keyword("array")
        name = self._expect_ident("全局变量名")
        value = None
        current = self._current()
        if current.kind == TokenKind.OP and current.value == "=":
            self._advance()
            value = self._parse_expression()
        self._finish_statement()
        return GlobalVar(
            type_name=type_name, name=name.value, is_array=is_array,
            is_constant=is_constant, value=value,
            line=token.line, column=token.column,
        )

    def _parse_typedef(self):
        token = self._current()
        self._advance()
        name = self._expect_ident("类型名")
        self._expect_keyword("extends")
        extends = self._expect_ident("父类型")
        self._finish_statement()
        return TypeDef(
            name=name.value, extends=extends.value,
            line=token.line, column=token.column,
        )

    def _parse_function(self, is_native):
        start = self._current()
        self._advance()
        name = ""
        params = []
        return_type = "nothing"
        errors = []
        try:
            name_token = self._expect_ident("函数名")
            name = name_token.value
            self._expect_keyword("takes")
            params = self._parse_params()
            self._expect_keyword("returns")
            return_type = self._expect_type("返回类型")
            self._finish_statement()
        except ParseError as error:
            errors.append(error)
            self.script.errors.append(error)
            self._mark_unparsed(error.line)
            self._mark_unparsed(start.line)
            self._skip_to_next_line()

        function = FunctionDef(
            name=name, params=params, return_type=return_type,
            is_native=is_native, errors=errors,
            line=start.line, column=start.column,
        )
        if is_native:
            return function

        body = self._parse_block({"endfunction"})
        function.body = body
        token = self._current()
        if token.kind == TokenKind.KEYWORD and token.value == "endfunction":
            self._advance()
            try:
                self._finish_statement()
            except ParseError as error:
                self.script.errors.append(error)
                self._mark_unparsed(error.line)
                self._skip_to_next_line()
        elif token.kind == TokenKind.EOF:
            self._mark_unparsed(start.line)
            return function
        else:
            error = self._record_error(
                start.line, start.column, "函数缺少 endfunction"
            )
            function.errors.append(error)
        return function

    def _parse_params(self):
        if self._accept_keyword("nothing"):
            return []
        params = []
        while True:
            token = self._current()
            type_name = self._expect_type("参数类型")
            name = self._expect_ident("参数名")
            params.append(
                Param(type_name=type_name, name=name.value,
                      line=token.line, column=token.column)
            )
            current = self._current()
            if current.kind == TokenKind.PUNCT and current.value == ",":
                self._advance()
                continue
            return params

    # --- 语句块 ---

    def _parse_block(self, stop_keywords):
        block = Block(line=self._current().line, column=self._current().column)
        while True:
            self._skip_newlines()
            token = self._current()
            if token.kind == TokenKind.EOF:
                self._record_error(
                    token.line, token.column,
                    "代码块未闭合，缺少 " + "/".join(sorted(stop_keywords)),
                )
                self._mark_unparsed(block.line)
                return block
            if token.kind == TokenKind.KEYWORD and (
                token.value in stop_keywords
                or token.value in _BLOCK_BOUNDARY_KEYWORDS
            ):
                return block
            self._parse_statement_with_recovery(block)
        return block

    def _parse_statement_with_recovery(self, block):
        checkpoint = self.index
        start = self._current()
        try:
            statement = self._parse_statement()
            block.statements.append(statement)
            self.script.parsed_statements += 1
        except ParseError as error:
            self.script.errors.append(error)
            if error.line:
                self._mark_unparsed(error.line)
            self._mark_unparsed(start.line)
            self.index = checkpoint
            raw_tokens = self._collect_line()
            block.statements.append(
                RawStmt(
                    text=token_text(raw_tokens), reason=error.message,
                    line=start.line, column=start.column,
                )
            )
            self.script.raw_statements += 1

    def _parse_statement(self):
        token = self._current()
        if token.kind == TokenKind.ERROR:
            raise ParseError(token.line, token.column, token.message)
        if token.kind == TokenKind.KEYWORD:
            value = token.value
            if value == "local":
                return self._parse_local()
            if value == "set":
                return self._parse_set()
            if value == "call":
                return self._parse_call_statement()
            if value == "if":
                return self._parse_if()
            if value == "loop":
                return self._parse_loop()
            if value == "exitwhen":
                return self._parse_exitwhen()
            if value == "return":
                return self._parse_return()
            if value == "debug":
                return self._parse_debug()
        if token.kind == TokenKind.IDENT:
            if (
                self._peek().kind == TokenKind.PUNCT
                and self._peek().value == "("
            ):
                return self._parse_call_statement()
        raise ParseError(
            token.line, token.column, f"无法识别的语句 {token.value!r}"
        )

    def _parse_local(self):
        start = self._current()
        self._advance()
        type_name = self._expect_type("局部变量类型")
        is_array = self._accept_keyword("array")
        name = self._expect_ident("局部变量名")
        value = None
        current = self._current()
        if current.kind == TokenKind.OP and current.value == "=":
            self._advance()
            value = self._parse_expression()
        self._finish_statement()
        return LocalDecl(
            type_name=type_name, name=name.value, is_array=is_array,
            value=value, line=start.line, column=start.column,
        )

    def _parse_set(self):
        start = self._current()
        self._advance()
        target = self._parse_lvalue()
        operator = self._current()
        if operator.kind != TokenKind.OP or operator.value != "=":
            raise ParseError(
                operator.line, operator.column, "set 缺少 '='"
            )
        self._advance()
        value = self._parse_expression()
        self._finish_statement()
        return Set(
            target=target, value=value, line=start.line, column=start.column
        )

    def _parse_lvalue(self):
        token = self._current()
        if token.kind != TokenKind.IDENT:
            raise ParseError(
                token.line, token.column, f"应为变量名，实际为 {token.value!r}"
            )
        self._advance()
        index = None
        if self._accept_punct("["):
            index = self._parse_expression()
            self._expect_punct("]")
        return VarRef(
            name=token.value, index=index, line=token.line, column=token.column
        )

    def _parse_call_statement(self):
        start = self._current()
        if start.kind == TokenKind.KEYWORD and start.value == "call":
            self._advance()
        call = self._parse_call()
        self._finish_statement()
        return CallStmt(call=call, line=start.line, column=start.column)

    def _parse_call(self):
        name = self._expect_ident("函数名")
        self._expect_punct("(")
        args = []
        if not self._accept_punct(")"):
            while True:
                args.append(self._parse_expression())
                if self._accept_punct(","):
                    continue
                self._expect_punct(")")
                break
        return Call(
            name=name.value, args=args, line=name.line, column=name.column
        )

    def _parse_if(self):
        start = self._current()
        self._advance()
        condition = self._parse_expression()
        self._expect_keyword("then")
        self._finish_statement()
        body = self._parse_block({"elseif", "else", "endif"})
        node = If(line=start.line, column=start.column)
        node.branches.append(
            IfBranch(condition=condition, body=body,
                     line=start.line, column=start.column)
        )
        while True:
            token = self._current()
            if token.kind == TokenKind.KEYWORD and token.value == "elseif":
                self._advance()
                condition = self._parse_expression()
                self._expect_keyword("then")
                self._finish_statement()
                branch = IfBranch(
                    condition=condition,
                    body=self._parse_block({"elseif", "else", "endif"}),
                    line=token.line, column=token.column,
                )
                node.branches.append(branch)
                continue
            if token.kind == TokenKind.KEYWORD and token.value == "else":
                self._advance()
                self._finish_statement()
                node.else_body = self._parse_block({"endif"})
                continue
            if token.kind == TokenKind.KEYWORD and token.value == "endif":
                self._advance()
                self._finish_statement()
                return node
            if token.kind == TokenKind.EOF:
                self._mark_unparsed(start.line)
                return node
            self._record_error(start.line, start.column, "if 缺少 endif")
            return node

    def _parse_loop(self):
        start = self._current()
        self._advance()
        self._finish_statement()
        body = self._parse_block({"endloop"})
        node = Loop(body=body, line=start.line, column=start.column)
        token = self._current()
        if token.kind == TokenKind.KEYWORD and token.value == "endloop":
            self._advance()
            self._finish_statement()
        elif token.kind == TokenKind.EOF:
            self._mark_unparsed(start.line)
        else:
            self._record_error(start.line, start.column, "loop 缺少 endloop")
        return node

    def _parse_exitwhen(self):
        start = self._current()
        self._advance()
        condition = self._parse_expression()
        self._finish_statement()
        return ExitWhen(
            condition=condition, line=start.line, column=start.column
        )

    def _parse_return(self):
        start = self._current()
        self._advance()
        token = self._current()
        value = None
        if token.kind not in (TokenKind.NEWLINE, TokenKind.EOF) and not (
            token.kind == TokenKind.KEYWORD
            and token.value in STATEMENT_STOP_KEYWORDS
        ):
            value = self._parse_expression()
        self._finish_statement()
        return Return(value=value, line=start.line, column=start.column)

    def _parse_debug(self):
        start = self._current()
        self._advance()
        statement = self._parse_statement()
        return Debug(
            statement=statement, line=start.line, column=start.column
        )

    # --- 表达式 ---

    def _parse_expression(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._accept_keyword("or"):
            operator = self.tokens[self.index - 1]
            right = self._parse_and()
            left = Binary(
                op="or", left=left, right=right,
                line=operator.line, column=operator.column,
            )
        return left

    def _parse_and(self):
        left = self._parse_comparison()
        while self._accept_keyword("and"):
            operator = self.tokens[self.index - 1]
            right = self._parse_comparison()
            left = Binary(
                op="and", left=left, right=right,
                line=operator.line, column=operator.column,
            )
        return left

    def _parse_comparison(self):
        left = self._parse_additive()
        while True:
            token = self._current()
            if token.kind == TokenKind.OP and token.value in _COMPARISON_OPERATORS:
                self._advance()
                right = self._parse_additive()
                left = Binary(
                    op=token.value, left=left, right=right,
                    line=token.line, column=token.column,
                )
                continue
            return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while True:
            token = self._current()
            if token.kind == TokenKind.OP and token.value in ("+", "-"):
                self._advance()
                right = self._parse_multiplicative()
                left = Binary(
                    op=token.value, left=left, right=right,
                    line=token.line, column=token.column,
                )
                continue
            return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while True:
            token = self._current()
            if token.kind == TokenKind.OP and token.value in ("*", "/"):
                self._advance()
                right = self._parse_unary()
                left = Binary(
                    op=token.value, left=left, right=right,
                    line=token.line, column=token.column,
                )
                continue
            return left

    def _parse_unary(self):
        token = self._current()
        if token.kind == TokenKind.KEYWORD and token.value == "not":
            self._advance()
            return Unary(
                op="not", operand=self._parse_unary(),
                line=token.line, column=token.column,
            )
        if token.kind == TokenKind.OP and token.value in ("-", "+"):
            self._advance()
            return Unary(
                op=token.value, operand=self._parse_unary(),
                line=token.line, column=token.column,
            )
        return self._parse_primary()

    def _parse_primary(self):
        token = self._current()
        if token.kind == TokenKind.NUMBER:
            self._advance()
            return Literal(
                kind="number", value=token.value,
                line=token.line, column=token.column,
            )
        if token.kind == TokenKind.STRING:
            self._advance()
            return Literal(
                kind="string", value=token.value,
                line=token.line, column=token.column,
            )
        if token.kind == TokenKind.RAWCODE:
            self._advance()
            return Literal(
                kind="rawcode", value=token.value,
                line=token.line, column=token.column,
            )
        if token.kind == TokenKind.KEYWORD:
            if token.value in ("true", "false"):
                self._advance()
                return Literal(
                    kind="bool", value=token.value,
                    line=token.line, column=token.column,
                )
            if token.value == "null":
                self._advance()
                return Literal(
                    kind="null", value="null",
                    line=token.line, column=token.column,
                )
            if token.value == "function":
                self._advance()
                name = self._expect_ident("函数引用名")
                return CodeRef(
                    name=name.value, line=token.line, column=token.column
                )
        if token.kind == TokenKind.PUNCT and token.value == "(":
            self._advance()
            expression = self._parse_expression()
            self._expect_punct(")")
            return expression
        if token.kind == TokenKind.IDENT:
            self._advance()
            following = self._current()
            if (
                following.kind == TokenKind.PUNCT
                and following.value == "("
            ):
                self._advance()
                args = []
                if not self._accept_punct(")"):
                    while True:
                        args.append(self._parse_expression())
                        if self._accept_punct(","):
                            continue
                        self._expect_punct(")")
                        break
                return Call(
                    name=token.value, args=args,
                    line=token.line, column=token.column,
                )
            index = None
            if self._accept_punct("["):
                index = self._parse_expression()
                self._expect_punct("]")
            return VarRef(
                name=token.value, index=index,
                line=token.line, column=token.column,
            )
        raise ParseError(
            token.line, token.column, f"表达式不完整，遇到 {token.value!r}"
        )

    def _accept_punct(self, value):
        token = self._current()
        if token.kind == TokenKind.PUNCT and token.value == value:
            self._advance()
            return True
        return False

    def _expect_punct(self, value):
        token = self._current()
        if token.kind == TokenKind.PUNCT and token.value == value:
            self._advance()
            return token
        raise ParseError(
            token.line, token.column, f"应为 {value!r}，实际为 {token.value!r}"
        )


def parse_script(text):
    """解析整份脚本；永不因语法错误抛异常，错误记录在 Script.errors。"""
    return Parser(tokenize(text)).parse()


def parse_file(path):
    from core.map_extract import read_script_text

    return parse_script(read_script_text(path))
