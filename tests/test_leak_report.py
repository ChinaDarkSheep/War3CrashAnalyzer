"""P5.5 统一报告测试：行数据、Markdown/JSON/CSV、疑似泄露证据。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.auditor import Auditor
from core.leak_fixer import build_fix_plan, match_key
from core.leak_report import (
    build_leak_report,
    crash_evidence_text,
    leak_suspected_from_diagnosis,
    render_csv,
    render_json,
    render_markdown,
    write_leak_report,
)

CASES = Path(__file__).resolve().parent / "leak_corpus" / "cases"

CLEAN_AND_LEAK = """function Cleaned takes nothing returns nothing
    local location a = Location(0.0, 0.0)
    call RemoveLocation(a)
endfunction

function Leaked takes nothing returns nothing
    local location b = Location(1.0, 1.0)
endfunction
"""

GLOBAL_ARRAY_ESCAPE = """globals
    location array g
endglobals

function Escape takes unit u returns nothing
    set g[0] = PolarProjectionBJ(GetUnitLoc(u), 100.0, 0.0)
endfunction
"""


def report_for(name, **kwargs):
    text = (CASES / name).read_text(encoding="utf-8")
    plan = build_fix_plan(text)
    return plan, build_leak_report(
        plan, map_name=name, validation={"status": "unchecked"}, **kwargs
    )


class ReportDataTests(unittest.TestCase):
    def test_finding_row_contains_evidence_and_actions(self):
        _, report = report_for("01_single_return_location.j")
        self.assertEqual(report["summary"]["findings"], 1)
        row = report["rows"][0]
        self.assertEqual(row["rule_id"], "L01")
        self.assertEqual(row["level"], "A")
        self.assertTrue(row["auto"])
        self.assertFalse(row["patch"])
        self.assertIn("SingleReturn", row["function"])
        self.assertTrue(row["evidence"])
        self.assertTrue(row["suggestion"])
        self.assertIn("GetUnitLoc", row["context"])
        self.assertIn("RemoveLocation", report["auto_diff"])

    def test_function_snippet_is_complete(self):
        _, report = report_for("01_single_return_location.j")
        snippet = report["functions"]["SingleReturn"]
        self.assertIn("function SingleReturn takes", snippet)
        self.assertIn("endfunction", snippet)

    def test_auxiliary_null_is_a_separate_row(self):
        plan = build_fix_plan(CLEAN_AND_LEAK)
        report = build_leak_report(plan, map_name="two.j")
        auxiliary = [row for row in report["rows"] if row["auxiliary"]]
        self.assertEqual(len(auxiliary), 1)
        self.assertEqual(auxiliary[0]["rule_id"], "L09")
        self.assertTrue(auxiliary[0]["auto"])
        self.assertIn("set var = null", auxiliary[0]["suggestion"])

    def test_global_handle_is_counted_but_not_listed(self):
        _, report = report_for("07_escape_global_location.j")
        self.assertGreaterEqual(report["summary"]["global_skipped"], 1)
        for row in report["rows"]:
            self.assertNotIn("全局变量", row["evidence"])

    def test_multi_return_generates_patch_row(self):
        _, report = report_for("02_multi_return_location.j")
        row = report["rows"][0]
        self.assertEqual(row["rule_id"], "L01")
        self.assertTrue(row["patch"])
        self.assertFalse(row["auto"])
        self.assertIn("补丁建议", row["suggestion"])
        self.assertIn("RemoveLocation", report["patch_diff"])
        self.assertNotIn("RemoveLocation", report["auto_diff"])

    def test_uneditable_patch_match_does_not_suggest_patch(self):
        _, report = report_for("03_branch_destroy_group.j")
        row = report["rows"][0]
        self.assertFalse(row["auto"])
        self.assertFalse(row["patch"])
        self.assertIn("只报告", row["suggestion"])
        self.assertNotIn("生成补丁建议", row["suggestion"])

    def test_selection_key_matches_report_row(self):
        plan = build_fix_plan(CLEAN_AND_LEAK)
        report = build_leak_report(plan, map_name="two.j")
        leaked = [row for row in report["rows"] if row["function"] == "Leaked"]
        self.assertEqual(len(leaked), 1)
        fixed = plan.fixed_text(keys={leaked[0]["key"]})
        self.assertIn("RemoveLocation(b)", fixed)
        self.assertNotIn("set a = null", fixed)

    def test_escaped_notice_is_not_checkable_but_inline_fix_is(self):
        plan = build_fix_plan(GLOBAL_ARRAY_ESCAPE)
        report = build_leak_report(plan, map_name="escape.j")
        notice = [row for row in report["rows"] if not row["finding"]]
        finding = [row for row in report["rows"] if row["finding"]]
        self.assertEqual(len(notice), 1)
        self.assertFalse(notice[0]["auto"])
        self.assertFalse(notice[0]["patch"])
        self.assertEqual(len(finding), 1)
        self.assertTrue(finding[0]["auto"])
        self.assertIn("GetUnitLoc", finding[0]["context"])


class RenderTests(unittest.TestCase):
    def test_markdown_has_required_sections(self):
        _, report = report_for("01_single_return_location.j")
        markdown = render_markdown(report)
        for heading in (
            "# 地图泄露诊断报告",
            "## 基本信息",
            "## 结果摘要",
            "## 覆盖范围",
            "## 发现列表",
            "## 证据与可疑函数片段",
            "## 补丁建议",
            "## 校验与限制",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("SingleReturn", markdown)
        self.assertIn("RemoveLocation", markdown)
        self.assertIn("未校验", markdown)

    def test_markdown_validation_ok(self):
        plan = build_fix_plan(
            (CASES / "01_single_return_location.j").read_text(encoding="utf-8")
        )
        report = build_leak_report(
            plan, map_name="01.j", validation={"status": "ok"}
        )
        self.assertIn("pjass 语法检查通过", render_markdown(report))

    def test_json_round_trip(self):
        _, report = report_for("01_single_return_location.j")
        data = json.loads(render_json(report))
        self.assertEqual(data["summary"]["findings"], 1)
        self.assertEqual(data["rows"][0]["rule_id"], "L01")

    def test_csv_has_header_and_rows(self):
        _, report = report_for("01_single_return_location.j")
        csv_text = render_csv(report)
        lines = csv_text.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("rule_id", lines[0])
        self.assertIn("L01", lines[1])

    def test_write_report_creates_three_files(self):
        _, report = report_for("01_single_return_location.j")
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_leak_report(
                report, temp_dir, base_name="测试地图.w3x"
            )
            for path in paths.values():
                self.assertTrue(Path(path).is_file(), path)
            self.assertTrue(paths["markdown"].endswith("_leak_report.md"))
            self.assertIn("L01", Path(paths["json"]).read_text(encoding="utf-8"))
            raw = Path(paths["csv"]).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))


class CrashEvidenceTests(unittest.TestCase):
    def test_out_of_memory_reason_is_suspected(self):
        self.assertTrue(
            leak_suspected_from_diagnosis({"reason": {"kind": "out_of_memory"}})
        )

    def test_text_signal_is_suspected(self):
        self.assertTrue(
            leak_suspected_from_diagnosis(
                {"analysis_text": "Fatal error: 内存不足，无法分配句柄。"}
            )
        )

    def test_ordinary_crash_is_not_suspected(self):
        self.assertFalse(
            leak_suspected_from_diagnosis(
                {"analysis_text": "The instruction at 0x1234 referenced memory."}
            )
        )
        self.assertFalse(leak_suspected_from_diagnosis(None))

    def test_evidence_text_is_read_only(self):
        text = crash_evidence_text()
        self.assertIn("泄露定位&修复", text)
        self.assertIn("不会修改地图", text)
        self.assertNotIn("自动修复", text)


class CrashIntegrationTests(unittest.TestCase):
    """真实日志走一遍 Auditor，确认 last_diagnosis 能被证据模块识别。"""

    def _analyze(self, text):
        auditor = Auditor(lambda *_: None, lambda *_: None)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Crash.txt"
            path.write_text(text, encoding="utf-8")
            auditor.analyze_log_file(str(path))
        return auditor

    def test_out_of_memory_log_marks_suspected(self):
        auditor = self._analyze("critical error: 内存不足\n")
        self.assertIsNotNone(auditor.last_diagnosis)
        self.assertEqual(
            auditor.last_diagnosis["reason"]["kind"], "out_of_memory")
        self.assertTrue(
            leak_suspected_from_diagnosis(auditor.last_diagnosis))

    def test_ordinary_crash_log_is_not_suspected(self):
        auditor = self._analyze(
            "The instruction at '0x00401000' referenced memory at "
            "'0x00000000'. The memory could not be read.\n")
        self.assertIsNotNone(auditor.last_diagnosis)
        self.assertFalse(
            leak_suspected_from_diagnosis(auditor.last_diagnosis))


if __name__ == "__main__":
    unittest.main()
