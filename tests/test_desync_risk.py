"""P6 异步风险扫描的语料回归与报告测试。"""

import json
import unittest
from pathlib import Path

from core.desync_risk import (
    RULES,
    RiskFinding,
    RiskReport,
    render_markdown,
    scan_text,
    summary_text,
)

CORPUS_DIR = Path(__file__).resolve().parent / "desync_corpus"


def _load_cases():
    with open(CORPUS_DIR / "corpus.json", encoding="utf-8") as handle:
        return json.load(handle)["cases"]


class CorpusTests(unittest.TestCase):
    def test_corpus_expectations(self):
        for case in _load_cases():
            path = CORPUS_DIR / case["file"]
            with self.subTest(case=case["file"]):
                text = path.read_text(encoding="utf-8")
                report = scan_text(text, case["language"])

                self.assertEqual(report.language, case["language"])
                if case["language"] == "jass":
                    self.assertEqual(report.parse_errors, 0)
                    self.assertEqual(
                        report.coverage, 1.0,
                        f"{case['file']} 应能完整解析")

                found = {
                    (item.rule_id, item.function, item.line)
                    for item in report.findings
                }
                for expected in case["expect"]:
                    key = (expected["rule"], expected["function"],
                           expected["line"])
                    self.assertIn(
                        key, found,
                        f"{case['file']} 漏报 {key}，实际 {sorted(found)}")
                for rule_id in case["absent_rules"]:
                    self.assertNotIn(
                        rule_id, {item.rule_id for item in report.findings},
                        f"{case['file']} 不应出现 {rule_id}")

    def test_corpus_has_safe_cases(self):
        safe = [case for case in _load_cases() if not case["expect"]]
        self.assertGreaterEqual(len(safe), 2)


class ReportTests(unittest.TestCase):
    def test_empty_script(self):
        report = scan_text("", "jass")
        self.assertEqual(report.findings, [])
        self.assertEqual(report.level, "无")
        self.assertEqual(summary_text(report), "未发现静态异步风险。")

    def test_level_uses_highest_severity(self):
        report = RiskReport(language="jass", total_lines=10, findings=[
            RiskFinding("D5", "低", RULES["D5"][1], "F", 1, "", ""),
            RiskFinding("D3", "高", RULES["D3"][1], "F", 2, "", ""),
            RiskFinding("D4", "中", RULES["D4"][1], "F", 3, "", ""),
        ])
        self.assertEqual(report.level, "高")
        self.assertEqual(report.counts(), {"高": 1, "中": 1, "低": 1})
        self.assertEqual(report.rule_counts(), {"D5": 1, "D3": 1, "D4": 1})
        self.assertIn("高 1", summary_text(report))

    def test_markdown_contains_evidence_and_escapes_pipes(self):
        report = RiskReport(language="jass", total_lines=10, findings=[
            RiskFinding("D1", "高", RULES["D1"][1], "Trig_X", 4,
                        "call CreateUnit(a | b)", "说明 | 内容"),
        ])
        text = render_markdown(
            report, "测试地图.w3x", "war3map.j", "gbk", "abc")
        self.assertIn("掉线风险扫描报告", text)
        self.assertIn("测试地图.w3x", text)
        self.assertIn("CreateUnit(a \\| b)", text)
        self.assertIn("说明 \\| 内容", text)
        self.assertIn("不会修改地图", text)

    def test_lua_evidence_keeps_original_line(self):
        text = "-- math.random(1, 10)\nlocal roll = math.random(1, 3)\n"
        report = scan_text(text, "lua")
        self.assertEqual(
            [(item.rule_id, item.line) for item in report.findings],
            [("L2", 2)])
        self.assertIn("math.random", report.findings[0].evidence)

    def test_scan_map_script_adapter(self):
        class FakeScript:
            text = ("function Trig_X takes nothing returns nothing\n"
                    "    if GetLocalPlayer() == Player(0) then\n"
                    "        call CreateUnit(Player(0), 'hfoo', 0.0, 0.0, 0.0)\n"
                    "    endif\n"
                    "endfunction\n")
            language = "jass"

        from core.desync_risk import scan_map_script
        report = scan_map_script(FakeScript())
        self.assertEqual([item.rule_id for item in report.findings], ["D1"])


if __name__ == "__main__":
    unittest.main()
