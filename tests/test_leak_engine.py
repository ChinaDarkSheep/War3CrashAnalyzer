"""P5.0 泄露分析基线测试。

两类断言：
1. 当前缺陷复现：记录现有实现的行为，任何变化都应被人工复核；
2. 目标行为：用 expectedFailure 标记 P5.1+ 必须达成的结果，修好后需移除装饰器。

更新基线：
    python tests/run_leak_corpus.py --write-baseline
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.leak_corpus import runner

_REPORT = None


def corpus_report():
    global _REPORT
    if _REPORT is None:
        _REPORT = runner.analyze_corpus()
    return _REPORT


def case_result(case_id):
    for case in corpus_report()["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def forbidden_hit(case_id, pattern):
    return any(
        item["pattern"] == pattern and item["hit"]
        for item in case_result(case_id)["forbidden_hits"]
    )


def must_fix_hit(case_id, pattern):
    return any(
        item["pattern"] == pattern and item["hit"]
        for item in case_result(case_id)["must_fix"]
    )


class CorpusStructureTests(unittest.TestCase):
    def test_manifest_is_valid(self):
        manifest = runner.load_manifest()
        self.assertGreaterEqual(len(manifest["cases"]), 16)
        ids = [case["id"] for case in manifest["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        for case in manifest["cases"]:
            self.assertTrue(
                (runner.CORPUS_DIR / case["file"]).is_file(), case["file"]
            )

    def test_all_cases_analyzed_without_error(self):
        for case in corpus_report()["cases"]:
            self.assertIsNone(case["error"], case["id"])


class BaselineSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_committed_baseline(self):
        snapshot = runner.build_snapshot(corpus_report())
        if os.environ.get("UPDATE_LEAK_BASELINE") == "1":
            runner.write_baseline(snapshot)
            return
        self.assertTrue(
            runner.BASELINE_PATH.is_file(),
            "缺少基线文件，请先运行 python tests/run_leak_corpus.py --write-baseline",
        )
        self.assertEqual(snapshot, runner.load_baseline())

    def test_snapshot_has_no_absolute_paths(self):
        payload = json.dumps(
            runner.build_snapshot(corpus_report()), ensure_ascii=False
        )
        self.assertNotIn("C:\\", payload)
        self.assertNotIn(str(runner.REPO_ROOT), payload)


class CurrentDefectTests(unittest.TestCase):
    """止血后仍存在的已知缺陷，后续由 P5.2 语义/控制流处理。"""

    def test_corpus_metrics_snapshot(self):
        summary = corpus_report()["summary"]
        self.assertEqual(summary["cases"], 18)
        self.assertEqual(summary["expected_findings"], 9)
        self.assertEqual(summary["actual_findings"], 10)
        self.assertEqual(summary["matched_findings"], 8)
        self.assertEqual(summary["violations"], 1)
        self.assertAlmostEqual(summary["precision"], 0.8, places=3)
        self.assertAlmostEqual(summary["recall"], 8 / 9, places=3)

    def test_branch_destroy_is_missed(self):
        self.assertEqual(case_result("03_branch_destroy_group")["matched_count"], 0)
        self.assertEqual(len(case_result("03_branch_destroy_group")["missed"]), 1)

    def test_long_lived_timer_is_reported(self):
        self.assertEqual(case_result("13_long_lived_timer")["actual_count"], 1)
        self.assertEqual(
            case_result("13_long_lived_timer")["extras"][0]["type"], "timer"
        )

    def test_returned_local_is_reported_without_fix(self):
        case = case_result("12_return_handle")
        self.assertEqual(case["actual_count"], 1)
        self.assertTrue(case["fixed_equals_source"])


class ExistingCapabilityTests(unittest.TestCase):
    """当前已经可用的能力，P5.1+ 不得回退。"""

    def test_simple_location_is_fixed(self):
        self.assertTrue(
            must_fix_hit("01_single_return_location", "call RemoveLocation\\(loc\\)")
        )

    def test_loop_inline_location_is_fixed(self):
        self.assertTrue(
            must_fix_hit(
                "04_loop_inline_location",
                "call RemoveLocation\\(leakfix_loc_\\d+\\)",
            )
        )

    def test_sleep_group_is_fixed(self):
        self.assertTrue(must_fix_hit("05_sleep_group", "call DestroyGroup\\(g\\)"))

    def test_idempotent_location_is_fixed(self):
        self.assertTrue(
            must_fix_hit("14_idempotent_location", "call RemoveLocation\\(loc\\)")
        )

    def test_new_force_is_auto_fixed(self):
        self.assertTrue(must_fix_hit("09_new_force_local", "call DestroyForce\\(f\\)"))

    def test_all_cases_are_idempotent(self):
        for case in corpus_report()["cases"]:
            self.assertTrue(case["idempotent"], case["id"])

    def test_multi_return_is_left_unchanged(self):
        self.assertTrue(case_result("02_multi_return_location")["fixed_equals_source"])

    def test_gui_group_is_left_unchanged(self):
        self.assertTrue(case_result("06_gui_group")["fixed_equals_source"])

    def test_escaped_handle_is_not_auto_destroyed(self):
        self.assertTrue(case_result("07_escape_global_location")["fixed_equals_source"])

    def test_shared_force_is_left_unchanged(self):
        self.assertTrue(case_result("08_shared_force")["fixed_equals_source"])

    def test_comment_and_string_are_left_unchanged(self):
        self.assertTrue(case_result("10_comment_and_string")["fixed_equals_source"])
        self.assertEqual(case_result("10_comment_and_string")["actual_count"], 0)

    def test_spaced_destroy_is_left_unchanged(self):
        self.assertTrue(case_result("11_spaced_destroy")["fixed_equals_source"])

    def test_returned_handle_is_left_unchanged(self):
        self.assertTrue(case_result("12_return_handle")["fixed_equals_source"])

    def test_returned_inline_handle_is_left_unchanged(self):
        self.assertTrue(case_result("15_return_inline_location")["fixed_equals_source"])

    def test_rect_is_not_auto_fixed(self):
        self.assertTrue(case_result("16_local_rect_scope")["fixed_equals_source"])

    def test_substring_creator_is_left_unchanged(self):
        self.assertTrue(case_result("17_substring_creator")["fixed_equals_source"])

    def test_global_rect_is_left_unchanged(self):
        self.assertTrue(case_result("18_global_rect_init")["fixed_equals_source"])


class TargetBehaviorPendingTests(unittest.TestCase):
    """P5.1+ 目标行为。现在应为 expectedFailure，修好后移除装饰器。"""

    @unittest.expectedFailure
    def test_branch_destroy_is_reported(self):
        self.assertEqual(case_result("03_branch_destroy_group")["matched_count"], 1)

    @unittest.expectedFailure
    def test_long_lived_timer_is_not_reported(self):
        self.assertEqual(case_result("13_long_lived_timer")["actual_count"], 0)


@unittest.skipUnless(
    os.environ.get("WAR3_LEAK_MAP_DIR"), "设置 WAR3_LEAK_MAP_DIR 后运行真实地图基线"
)
class RealMapBaselineTests(unittest.TestCase):
    """本地真实地图基线：只校验指标结构，不保存脚本内容。"""

    def test_local_maps_produce_metrics_without_script_content(self):
        map_dir = Path(os.environ["WAR3_LEAK_MAP_DIR"])
        mpq_editor = Path(os.environ.get("WAR3_MPQ_EDITOR", runner.REPO_ROOT / "MPQEditor.exe"))
        if not mpq_editor.is_file():
            self.skipTest(f"缺少 MPQEditor: {mpq_editor}")
        limit = int(os.environ.get("WAR3_LEAK_MAP_LIMIT", "10"))

        with tempfile.TemporaryDirectory(prefix="leak_real_") as out_dir:
            report = runner.analyze_real_maps(map_dir, Path(out_dir), mpq_editor, limit)
            self.assertLessEqual(len(report["maps"]), limit)
            self.assertTrue((Path(out_dir) / "real_baseline.json").is_file())
            entries = [entry for entry in report["maps"] if not entry["error"]]
            for entry in entries:
                self.assertGreater(entry["script_length"], 0, entry["file"])
                self.assertTrue(entry["script_sha256"], entry["file"])
                self.assertTrue(entry["fixed_sha256"], entry["file"])
                self.assertNotIn("fixed_text", entry)
            payload = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("function ", payload)
            self.assertNotIn("endfunction", payload)


if __name__ == "__main__":
    unittest.main()
