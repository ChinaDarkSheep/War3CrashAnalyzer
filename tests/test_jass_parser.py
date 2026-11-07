"""P5.1 JASS 词法/语法回归测试。

覆盖三类行为：
1. 词法边界：注释、跨行字符串、转义引号、hex/rawcode、CR/CRLF、错误位置；
2. 语法结构：globals/type/native/function 与全部常用语句、表达式优先级；
3. 容错：单行失败不丢函数，块结构缺失时仍保留已解析内容。

真实脚本覆盖率默认读取本机 `tests/leak_corpus/.real_baseline/annotation/scripts`，
也可用 `WAR3_JASS_SCRIPT_DIR` 指向其他目录；目录不存在时自动跳过。
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from core.jass_ast import (
    Binary,
    CallStmt,
    CodeRef,
    Debug,
    If,
    Literal,
    LocalDecl,
    Loop,
    RawStmt,
    Return,
    Set,
    Unary,
    VarRef,
)
from core.jass_lexer import TokenKind, tokenize
from core.jass_parser import parse_script
from core.map_extract import read_script_text

_HERE = Path(__file__).resolve().parent
_CASES_DIR = _HERE / "leak_corpus" / "cases"
_DEFAULT_REAL_DIR = (
    _HERE / "leak_corpus" / ".real_baseline" / "annotation" / "scripts"
)
_REAL_DIR = Path(os.environ.get("WAR3_JASS_SCRIPT_DIR", "")) \
    if os.environ.get("WAR3_JASS_SCRIPT_DIR") else _DEFAULT_REAL_DIR


def _kinds(tokens):
    return [token.kind for token in tokens]


class LexerTests(unittest.TestCase):
    def test_comments_are_skipped_and_newlines_preserved(self):
        tokens = tokenize("// comment\ncall A()\r\ncall B()\rcall C()")
        idents = [token.value for token in tokens
                  if token.kind == TokenKind.IDENT]
        self.assertEqual(idents, ["A", "B", "C"])
        self.assertEqual(_kinds(tokens).count(TokenKind.NEWLINE), 3)
        self.assertEqual(
            [token.line for token in tokens
             if token.kind == TokenKind.IDENT],
            [2, 3, 4],
        )

    def test_bom_is_ignored(self):
        tokens = tokenize("\ufefffunction Foo takes nothing returns nothing")
        self.assertEqual(tokens[0].kind, TokenKind.KEYWORD)
        self.assertEqual(tokens[0].value, "function")
        self.assertEqual(tokens[0].line, 1)

    def test_keywords_and_identifiers_are_distinct(self):
        tokens = tokenize("if then else endif Foo")
        self.assertEqual(
            _kinds(tokens),
            [
                TokenKind.KEYWORD, TokenKind.KEYWORD, TokenKind.KEYWORD,
                TokenKind.KEYWORD, TokenKind.IDENT, TokenKind.EOF,
            ],
        )

    def test_numbers_hex_rawcode_and_reals(self):
        tokens = tokenize("$FF00 $ff 'hfoo' 'A000' 0 1. 1.5 .5 1.5e3 0x1F")
        values = [token.value for token in tokens
                  if token.kind in (TokenKind.NUMBER, TokenKind.RAWCODE)]
        self.assertEqual(
            values,
            ["$FF00", "$ff", "'hfoo'", "'A000'", "0", "1.", "1.5", ".5",
             "1.5e3", "0x1F"],
        )

    def test_escaped_quote_does_not_end_string(self):
        tokens = tokenize('set s = "a \\"b\\" c"')
        strings = [token for token in tokens
                   if token.kind == TokenKind.STRING]
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, '"a \\"b\\" c"')

    def test_backslash_is_literal_before_ordinary_characters(self):
        tokens = tokenize('set s = "C:\\path\\file.txt"')
        strings = [token for token in tokens
                   if token.kind == TokenKind.STRING]
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, '"C:\\path\\file.txt"')

    def test_multiline_string_is_one_token(self):
        tokens = tokenize('set s = "line1\nline2"\ncall Foo()')
        strings = [token for token in tokens
                   if token.kind == TokenKind.STRING]
        self.assertEqual(len(strings), 1)
        self.assertIn("\n", strings[0].value)
        call = [token for token in tokens if token.value == "Foo"]
        self.assertEqual(call[0].line, 3)

    def test_unterminated_string_reports_position_and_reason(self):
        tokens = tokenize('call Preload("\\")\ncall Foo()')
        errors = [token for token in tokens if token.kind == TokenKind.ERROR]
        self.assertTrue(errors)
        self.assertGreater(errors[0].line, 0)
        self.assertGreater(errors[0].column, 0)
        self.assertIn("未闭合", errors[0].message)

    def test_unknown_character_does_not_stop_tokenization(self):
        tokens = tokenize("set x = @\ncall Foo()")
        errors = [token for token in tokens if token.kind == TokenKind.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertEqual((errors[0].line, errors[0].column), (1, 9))
        self.assertIn("无法识别", errors[0].message)
        self.assertIn("Foo", [token.value for token in tokens])

    def test_block_comment_is_skipped(self):
        tokens = tokenize("call A() /* skip * this */\ncall B()")
        idents = [token.value for token in tokens
                  if token.kind == TokenKind.IDENT]
        self.assertEqual(idents, ["A", "B"])


class ParserStructureTests(unittest.TestCase):
    SOURCE = """
globals
    constant integer array Foo
    location locVar = null
endglobals

type mytype extends handle

native UnitAddAbility takes unit whichUnit, integer abilId returns boolean

function Test takes nothing returns nothing
    local location loc = GetUnitLoc(GetTriggerUnit())
    local integer array nums
    call RemoveLocation(loc)
    set loc = null
    set nums[0] = $FF00 + 'hfoo'
    if GetRandomInt(1, 2) == 1 then
        call KillUnit(GetTriggerUnit())
    elseif true then
        call DoNothing()
    else
        call DoNothing()
    endif
    loop
        exitwhen nums[0] > 10
        set nums[0] = nums[0] + 1
    endloop
    debug call BJDebugMsg("done")
    return
endfunction
"""

    @classmethod
    def setUpClass(cls):
        cls.script = parse_script(cls.SOURCE)

    def test_top_level_declarations(self):
        self.assertEqual(len(self.script.globals), 2)
        constant = self.script.globals[0]
        self.assertTrue(constant.is_constant)
        self.assertTrue(constant.is_array)
        self.assertEqual((constant.type_name, constant.name),
                         ("integer", "Foo"))
        self.assertEqual(self.script.globals[1].type_name, "location")
        self.assertEqual(len(self.script.types), 1)
        self.assertEqual(self.script.types[0].name, "mytype")
        self.assertEqual(self.script.types[0].extends, "handle")

        functions = {function.name: function for function in self.script.functions}
        native = functions["UnitAddAbility"]
        self.assertTrue(native.is_native)
        self.assertEqual([param.name for param in native.params],
                         ["whichUnit", "abilId"])
        self.assertEqual(native.return_type, "boolean")

    def test_function_body_constructs(self):
        function = [
            item for item in self.script.functions if item.name == "Test"
        ][0]
        statements = function.body.statements
        self.assertIsInstance(statements[0], LocalDecl)
        self.assertIsInstance(statements[1], LocalDecl)
        self.assertTrue(statements[1].is_array)
        self.assertIsInstance(statements[2], CallStmt)
        self.assertIsInstance(statements[3], Set)
        self.assertIsInstance(statements[4], Set)
        self.assertIsInstance(statements[4].target, VarRef)
        self.assertIsInstance(statements[4].target.index, Literal)
        self.assertIsInstance(statements[5], If)
        self.assertEqual(len(statements[5].branches), 2)
        self.assertIsNotNone(statements[5].else_body)
        self.assertIsInstance(statements[6], Loop)
        self.assertEqual(len(statements[6].body.statements), 2)
        self.assertIsInstance(statements[7], Debug)
        self.assertIsInstance(statements[8], Return)

    def test_operator_precedence(self):
        script = parse_script(
            "function A takes nothing returns nothing\n"
            "set x = 1 + 2 * 3 == 7 and not false or true\n"
            "endfunction\n"
        )
        statement = script.functions[0].body.statements[0]
        self.assertIsInstance(statement.value, Binary)
        self.assertEqual(statement.value.op, "or")
        self.assertEqual(statement.value.right.kind, "bool")
        left = statement.value.left
        self.assertEqual(left.op, "and")
        self.assertIsInstance(left.right, Unary)
        comparison = left.left
        self.assertEqual(comparison.op, "==")
        self.assertIsInstance(comparison.right, Literal)
        product = comparison.left
        self.assertEqual(product.op, "+")
        self.assertEqual(product.right.op, "*")

    def test_function_reference_argument(self):
        script = parse_script(
            "function A takes nothing returns nothing\n"
            "call Foo(function Bar, 1)\n"
            "endfunction\n"
        )
        call = script.functions[0].body.statements[0].call
        self.assertIsInstance(call.args[0], CodeRef)
        self.assertEqual(call.args[0].name, "Bar")

    def test_nothing_parameters_and_no_return_value(self):
        script = parse_script(
            "function A takes nothing returns nothing\nreturn\nendfunction\n"
        )
        self.assertEqual(script.functions[0].params, [])
        self.assertIsNone(script.functions[0].body.statements[0].value)


class ParserToleranceTests(unittest.TestCase):
    def test_bad_line_does_not_drop_function(self):
        script = parse_script(
            "function Broken takes nothing returns nothing\n"
            "call Before()\n"
            "???\n"
            "call After()\n"
            "endfunction\n"
        )
        self.assertEqual(len(script.functions), 1)
        body = script.functions[0].body.statements
        self.assertEqual(sum(isinstance(item, CallStmt) for item in body), 2)
        raw = [item for item in body if isinstance(item, RawStmt)]
        self.assertEqual(len(raw), 1)
        self.assertEqual(script.errors[0].line, 3)
        self.assertGreater(script.errors[0].column, 0)
        self.assertTrue(script.errors[0].message)
        self.assertLess(script.coverage, 1.0)

    def test_malformed_header_still_parses_body(self):
        script = parse_script(
            "function Broken takes ??? returns nothing\n"
            "call Inside()\n"
            "endfunction\n"
        )
        self.assertEqual(len(script.functions), 1)
        self.assertTrue(script.functions[0].errors)
        calls = [
            item for item in script.functions[0].body.statements
            if isinstance(item, CallStmt)
        ]
        self.assertEqual(len(calls), 1)

    def test_missing_endif_is_reported_at_if_line(self):
        script = parse_script(
            "function A takes nothing returns nothing\n"
            "if true then\n"
            "call Inside()\n"
            "endfunction\n"
        )
        errors = script.errors
        self.assertTrue(errors)
        self.assertEqual(errors[0].line, 2)
        self.assertIn("endif", errors[0].message)
        self.assertEqual(len(script.functions), 1)

    def test_missing_endfunction_is_reported(self):
        script = parse_script(
            "function A takes nothing returns nothing\n"
            "call Inside()\n"
        )
        self.assertTrue(script.errors)
        self.assertIn("endfunction", script.errors[-1].message)
        self.assertLess(script.coverage, 1.0)

    def test_unclosed_empty_function_reduces_coverage(self):
        script = parse_script("function A takes nothing returns nothing\n")
        self.assertTrue(script.errors)
        self.assertLess(script.coverage, 1.0)

    def test_comment_only_lines_are_not_code(self):
        script = parse_script(
            "// header\n"
            "function A takes nothing returns nothing\n"
            "// body\n"
            "call Inside()\n"
            "endfunction\n"
        )
        self.assertEqual(script.code_lines, 3)
        self.assertEqual(script.unparsed_lines, set())
        self.assertEqual(script.coverage, 1.0)


class CorpusParseTests(unittest.TestCase):
    def test_all_corpus_cases_parse_fully(self):
        files = sorted(_CASES_DIR.glob("*.j"))
        self.assertGreaterEqual(len(files), 18)
        for path in files:
            with self.subTest(case=path.name):
                script = parse_script(
                    path.read_text(encoding="utf-8", errors="ignore")
                )
                self.assertEqual(script.errors, [], path.name)
                self.assertEqual(script.raw_statements, 0, path.name)
                self.assertEqual(script.coverage, 1.0, path.name)
                self.assertGreater(len(script.functions), 0, path.name)


@unittest.skipUnless(
    _REAL_DIR.is_dir() and any(_REAL_DIR.glob("*.j")),
    "未找到真实 JASS 脚本；可用 WAR3_JASS_SCRIPT_DIR 指定目录",
)
class RealScriptCoverageTests(unittest.TestCase):
    def test_each_real_script_coverage_at_least_99_percent(self):
        for path in sorted(_REAL_DIR.glob("*.j")):
            with self.subTest(script=path.name):
                script = parse_script(read_script_text(path))
                self.assertGreater(len(script.functions), 0, path.name)
                self.assertGreaterEqual(
                    script.coverage, 0.99,
                    f"{path.name} 覆盖率 {script.coverage:.4f}",
                )
                for error in script.errors:
                    self.assertGreater(error.line, 0, path.name)
                    self.assertGreater(error.column, 0, path.name)
                    self.assertTrue(error.message, path.name)


if __name__ == "__main__":
    unittest.main()
