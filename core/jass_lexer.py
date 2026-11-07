"""JASS 词法分析：把脚本切成带行号、列号的 Token。

JASS 是逐行语法。真实地图脚本里常见 CR、CRLF、BOM、注释以及字符串中的
关键字，这里只做词法切分，不判断语法。无法识别的字符会生成 ERROR token
并保留位置，由解析器决定是否降级为 RawStmt。
"""

from __future__ import annotations

from dataclasses import dataclass


class TokenKind:
    IDENT = "ident"
    KEYWORD = "keyword"
    NUMBER = "number"
    STRING = "string"
    RAWCODE = "rawcode"
    OP = "op"
    PUNCT = "punct"
    NEWLINE = "newline"
    EOF = "eof"
    ERROR = "error"


KEYWORDS = frozenset(
    {
        "and", "array", "call", "constant", "debug", "else", "elseif",
        "endfunction", "endif", "endglobals", "endloop", "exitwhen",
        "extends", "false", "function", "globals", "if", "local", "loop",
        "native", "not", "nothing", "null", "or", "return", "set", "takes",
        "then", "true", "type", "returns",
    }
)

TWO_CHAR_OPERATORS = frozenset({"==", "!=", "<=", ">="})
ONE_CHAR_OPERATORS = frozenset("=<>+-*/")
PUNCTUATION = frozenset("()[],")

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_IDENT_START = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
)
_IDENT_BODY = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
)
# JASS 字符串里的反斜杠是普通字符，且真实地图中存在跨行字符串。
# 设置上限是为了让真正缺少结尾引号的文件不会吞掉后续全部脚本。
MAX_STRING_LINES = 16


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    line: int
    column: int
    message: str = ""

    @property
    def is_error(self):
        return self.kind == TokenKind.ERROR

    def __str__(self):
        return f"{self.kind}:{self.value}@{self.line}:{self.column}"


class Lexer:
    """按行扫描 JASS 文本。token 位置从 1 开始，行列均指向 token 首字符。"""

    def __init__(self, text):
        text = text or ""
        if text.startswith("\ufeff"):
            text = text[1:]
        self.text = text
        self.length = len(text)
        self.pos = 0
        self.line = 1
        self.column = 1

    def tokenize(self):
        tokens = []
        append = tokens.append
        while True:
            token = self._next_token()
            append(token)
            if token.kind == TokenKind.EOF:
                return tokens

    def _next_token(self):
        text = self.text
        while self.pos < self.length:
            ch = text[self.pos]
            if ch in " \t\f\v":
                self._advance(1)
                continue
            if ch in "\r\n":
                return self._newline()
            if ch == "/" and self.pos + 1 < self.length:
                nxt = text[self.pos + 1]
                if nxt == "/":
                    self._skip_line_comment()
                    continue
                if nxt == "*":
                    token = self._skip_block_comment()
                    if token is not None:
                        return token
                    continue
            line, column = self.line, self.column
            if ch == '"':
                return self._string(line, column)
            if ch == "'":
                return self._rawcode(line, column)
            if ch == "$" or (ch.isdigit()) or (
                ch == "." and self.pos + 1 < self.length
                and text[self.pos + 1].isdigit()
            ):
                return self._number(line, column)
            if ch in _IDENT_START:
                return self._identifier(line, column)
            two = text[self.pos:self.pos + 2]
            if two in TWO_CHAR_OPERATORS:
                self._advance(2)
                return Token(TokenKind.OP, two, line, column)
            if ch in ONE_CHAR_OPERATORS:
                self._advance(1)
                return Token(TokenKind.OP, ch, line, column)
            if ch in PUNCTUATION:
                self._advance(1)
                return Token(TokenKind.PUNCT, ch, line, column)
            self._advance(1)
            return Token(
                TokenKind.ERROR, ch, line, column,
                f"无法识别的字符 {ch!r}",
            )
        return Token(TokenKind.EOF, "", self.line, self.column)

    def _advance(self, count):
        text = self.text
        end = min(self.pos + count, self.length)
        while self.pos < end:
            ch = text[self.pos]
            if ch == "\n":
                self.line += 1
                self.column = 1
            elif ch == "\r":
                if self.pos + 1 < self.length and text[self.pos + 1] == "\n":
                    self.pos += 1
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def _newline(self):
        line, column = self.line, self.column
        ch = self.text[self.pos]
        self._advance(2 if ch == "\r" and self.text[self.pos:self.pos + 2] == "\r\n" else 1)
        return Token(TokenKind.NEWLINE, "\n", line, column)

    def _skip_line_comment(self):
        text = self.text
        while self.pos < self.length and text[self.pos] not in "\r\n":
            self._advance(1)

    def _skip_block_comment(self):
        line, column = self.line, self.column
        start = self.pos
        end = self.text.find("*/", self.pos + 2)
        if end < 0:
            self._advance(self.length - self.pos)
            return Token(
                TokenKind.ERROR, self.text[start:start + 2], line, column,
                "块注释未闭合",
            )
        self._advance(end + 2 - self.pos)
        return None

    def _string(self, line, column):
        text = self.text
        start = self.pos
        self._advance(1)
        line_breaks = 0
        while self.pos < self.length:
            ch = text[self.pos]
            if ch == '"':
                self._advance(1)
                return Token(
                    TokenKind.STRING, text[start:self.pos], line, column,
                )
            if ch == "\\" and self.pos + 1 < self.length:
                # JASS 常见 \" 与 \\；反斜杠本身不结束字符串。
                if text[self.pos + 1] in "\r\n":
                    line_breaks += 1
                self._advance(2)
                continue
            if ch in "\r\n":
                line_breaks += 1
                if line_breaks > MAX_STRING_LINES:
                    return Token(
                        TokenKind.ERROR, text[start:self.pos], line, column,
                        f"字符串超过 {MAX_STRING_LINES} 行仍未闭合",
                    )
            self._advance(1)
        return Token(
            TokenKind.ERROR, text[start:self.pos], line, column, "字符串未闭合",
        )

    def _rawcode(self, line, column):
        text = self.text
        start = self.pos
        self._advance(1)
        while self.pos < self.length:
            ch = text[self.pos]
            if ch in "\r\n":
                return Token(
                    TokenKind.ERROR, text[start:self.pos], line, column,
                    "rawcode 未闭合",
                )
            self._advance(1)
            if ch == "'":
                return Token(
                    TokenKind.RAWCODE, text[start:self.pos], line, column,
                )
        return Token(
            TokenKind.ERROR, text[start:self.pos], line, column,
            "rawcode 未闭合",
        )

    def _number(self, line, column):
        text = self.text
        start = self.pos
        if text[self.pos] == "$":
            self._advance(1)
            while self.pos < self.length and text[self.pos] in _HEX_DIGITS:
                self._advance(1)
            return Token(
                TokenKind.NUMBER, text[start:self.pos], line, column,
            )
        if text[self.pos] == "0" and self.pos + 2 < self.length \
                and text[self.pos + 1] in "xX" \
                and text[self.pos + 2] in _HEX_DIGITS:
            self._advance(2)
            while self.pos < self.length and text[self.pos] in _HEX_DIGITS:
                self._advance(1)
            return Token(
                TokenKind.NUMBER, text[start:self.pos], line, column,
            )
        while self.pos < self.length and text[self.pos].isdigit():
            self._advance(1)
        if self.pos < self.length and text[self.pos] == ".":
            self._advance(1)
            while self.pos < self.length and text[self.pos].isdigit():
                self._advance(1)
        if self.pos < self.length and text[self.pos] in "eE":
            nxt = self.text[self.pos + 1:self.pos + 2]
            if nxt.isdigit() or (
                nxt in "+-" and self.text[self.pos + 2:self.pos + 3].isdigit()
            ):
                self._advance(1)
                if self.text[self.pos] in "+-":
                    self._advance(1)
                while self.pos < self.length and text[self.pos].isdigit():
                    self._advance(1)
        return Token(TokenKind.NUMBER, text[start:self.pos], line, column)

    def _identifier(self, line, column):
        text = self.text
        start = self.pos
        while self.pos < self.length and text[self.pos] in _IDENT_BODY:
            self._advance(1)
        value = text[start:self.pos]
        kind = TokenKind.KEYWORD if value in KEYWORDS else TokenKind.IDENT
        return Token(kind, value, line, column)


def tokenize(text):
    """返回包含 EOF 的完整 token 列表；调用方可用 `until` 截断。"""
    return Lexer(text).tokenize()


def token_text(tokens):
    """把 token 还原成可直接阅读的一行文本，用于 RawStmt 与诊断信息。"""
    parts = []
    previous = None
    for token in tokens:
        if token.kind in (TokenKind.EOF, TokenKind.NEWLINE):
            continue
        value = token.value
        if previous is not None:
            needs_space = (
                previous.kind in (TokenKind.IDENT, TokenKind.KEYWORD,
                                  TokenKind.NUMBER, TokenKind.RAWCODE,
                                  TokenKind.STRING)
                and token.kind in (TokenKind.IDENT, TokenKind.KEYWORD,
                                   TokenKind.NUMBER, TokenKind.RAWCODE,
                                   TokenKind.STRING)
            )
            if needs_space:
                parts.append(" ")
        parts.append(value)
        previous = token
    return "".join(parts)
