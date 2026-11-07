"""P5.3 规则目录回归测试。

锁定三件事：
1. L01-L10 的元数据完整（级别、修复方式、证据、条件、不适用条件）；
2. 18 个合成语料的分类结果与预期一致；
3. A 级规则在语料上的 precision 不低于 95%，共享 force 的自动修复数恒为 0。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from core.jass_semantics import analyze_file, analyze_source
from core.leak_catalog import (
    RULES,
    RULE_BY_ID,
    auto_fix_matches,
    classify_creation,
    classify_semantics,
    coverage_statement,
    rule_for_creator,
    rules_for_type,
)
from tests.leak_corpus.runner import load_manifest

_CASES_DIR = Path(__file__).resolve().parent / "leak_corpus" / "cases"


def _case(name):
    return analyze_file(_CASES_DIR / f"{name}.j")


def _matches(source):
    return classify_semantics(analyze_source(source))


def _single(source):
    matches = _matches(source)
    if len(matches) != 1:
        raise AssertionError(f"期望 1 个创建点，实际 {len(matches)}")
    return matches[0]


# (rule_id, type, kind, finding, fix_mode)
_CORPUS_RULES = {
    "01_single_return_location": [("L01", "location", "local", True, "auto")],
    "02_multi_return_location": [("L01", "location", "local", True, "patch")],
    "03_branch_destroy_group": [("L02", "group", "local", True, "patch")],
    "04_loop_inline_location": [("L01", "location", "inline", True, "auto")],
    "05_sleep_group": [("L02", "group", "local", True, "auto")],
    "06_gui_group": [("L08", "group", "inline", False, "report")],
    "07_escape_global_location": [("L01", "location", "local", False, "none")],
    "08_shared_force": [
        ("L10", "force", "global", False, "report"),
        ("L10", "force", "local", False, "report"),
    ],
    "09_new_force_local": [("L03", "force", "local", True, "auto")],
    "10_comment_and_string": [],
    "11_spaced_destroy": [("L01", "location", "local", False, "none")],
    "12_return_handle": [("L01", "location", "local", False, "none")],
    "13_long_lived_timer": [("L10", "timer", "local", False, "report")],
    "14_idempotent_location": [("L01", "location", "local", True, "auto")],
    "15_return_inline_location": [("L01", "location", "inline", False, "none")],
    "16_local_rect_scope": [("L04", "rect", "local", False, "none")],
    "17_substring_creator": [("L04", "rect", "inline", False, "none")],
    "18_global_rect_init": [(None, "rect", "global", False, "none")],
}


class RuleMetadataTests(unittest.TestCase):
    def test_rule_ids_are_unique_and_ordered(self):
        ids = [rule.id for rule in RULES]
        self.assertEqual(ids, [f"L{index:02d}" for index in range(1, 11)])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(RULE_BY_ID), set(ids))

    def test_every_rule_has_evidence_conditions_and_exclusions(self):
        for rule in RULES:
            with self.subTest(rule=rule.id):
                self.assertIn(rule.level, ("A", "B", "C"))
                self.assertGreaterEqual(rule.confidence, 0.0)
                self.assertLessEqual(rule.confidence, 1.0)
                self.assertIn(rule.fix_mode, ("auto", "patch", "report", "none"))
                self.assertTrue(rule.evidence.strip())
                self.assertTrue(rule.conditions)
                self.assertTrue(rule.exclusions)

    def test_levels_and_fix_modes_match_the_plan(self):
        self.assertEqual(
            [rule.id for rule in RULES if rule.level == "A"],
            ["L01", "L02", "L03", "L09"],
        )
        self.assertEqual(
            [rule.id for rule in RULES if rule.level == "B"],
            ["L04", "L05", "L06", "L07", "L08"],
        )
        self.assertEqual([rule.id for rule in RULES if rule.level == "C"], ["L10"])
        for rule_id in ("L01", "L02", "L03"):
            self.assertTrue(RULE_BY_ID[rule_id].auto_whitelist)
            self.assertFalse(RULE_BY_ID[rule_id].shared_or_global)
        self.assertTrue(RULE_BY_ID["L09"].auxiliary)
        self.assertFalse(RULE_BY_ID["L09"].auto_whitelist)
        self.assertTrue(RULE_BY_ID["L10"].shared_or_global)
        self.assertTrue(RULE_BY_ID["L10"].long_lived)

    def test_force_whitelist_excludes_shared_creators(self):
        self.assertNotIn("GetPlayersAll", RULE_BY_ID["L03"].creators)
        self.assertIn("CreateForce", RULE_BY_ID["L03"].creators)
        self.assertIn("GetPlayersMatching", RULE_BY_ID["L03"].creators)

    def test_effect_and_lightning_are_in_type_catalog(self):
        for creator in ("AddSpecialEffect", "AddLightning", "AddLightningLoc"):
            with self.subTest(creator=creator):
                handle_type, destroyer = rule_for_creator(creator)
                self.assertIn(handle_type, ("effect", "lightning"))
                self.assertIn(destroyer, ("DestroyEffect", "DestroyLightning"))
        self.assertEqual(
            [rule.id for rule in rules_for_type("effect")], ["L05", "L09", "L10"]
        )


class CorpusCatalogTests(unittest.TestCase):
    def test_all_corpus_cases_match_expected_rules(self):
        for case_id, expected in _CORPUS_RULES.items():
            with self.subTest(case=case_id):
                actual = [
                    (
                        match.rule_id,
                        match.creation.handle_type,
                        match.creation.kind,
                        match.finding,
                        match.fix_mode,
                    )
                    for match in classify_semantics(_case(case_id))
                ]
                self.assertEqual(actual, expected)

    def test_a_level_precision_on_corpus(self):
        manifest = load_manifest()
        expected_total = 0
        actual_total = 0
        matched_total = 0
        for case in manifest["cases"]:
            semantics = analyze_file(
                Path(__file__).resolve().parent / "leak_corpus" / case["file"]
            )
            a_matches = [
                match
                for match in classify_semantics(semantics)
                if match.finding and match.level == "A"
            ]
            expected = case.get("expected_findings") or []
            matched, used = _match_expected(expected, a_matches)
            expected_total += len(expected)
            actual_total += len(a_matches)
            matched_total += matched
            self.assertEqual(
                used,
                set(range(len(a_matches))),
                f"{case['id']} 存在未匹配的 A 级发现",
            )
        precision = matched_total / actual_total if actual_total else 1.0
        self.assertGreaterEqual(precision, 0.95)
        self.assertGreaterEqual(actual_total, 5)
        # 两个 B 级用例（全局逃逸、RegionAddRect 接管）按语义不属于泄露，
        # 因此 A 级召回只统计真正的泄露。
        self.assertGreater(matched_total, 0)
        self.assertLessEqual(expected_total, 9)

    def test_shared_force_has_zero_auto_fix(self):
        matches = classify_semantics(_case("08_shared_force"))
        self.assertEqual([match.rule_id for match in matches], ["L10", "L10"])
        self.assertEqual(auto_fix_matches(matches), [])
        for match in matches:
            self.assertFalse(match.auto_fixable)
            self.assertEqual(match.fix_mode, "report")
            self.assertIn("共享句柄", "".join(match.reasons))

    def test_rect_and_timer_are_never_auto_fixable(self):
        for case_id in ("13_long_lived_timer", "16_local_rect_scope"):
            with self.subTest(case=case_id):
                self.assertEqual(auto_fix_matches(classify_semantics(_case(case_id))), [])

    def test_gui_group_is_explained_not_edited(self):
        match = classify_semantics(_case("06_gui_group"))[0]
        self.assertEqual(match.rule_id, "L08")
        self.assertFalse(match.finding)
        self.assertTrue(match.notice)
        self.assertFalse(match.auto_fixable)
        self.assertIn("bj_wantDestroyGroup", match.evidence)


class SyntheticRuleTests(unittest.TestCase):
    def test_cleaned_agent_without_null_gets_l09_advice(self):
        match = _single(
            "function F takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call SetUnitPositionLoc(u, loc)\n"
            "    call RemoveLocation(loc)\n"
            "endfunction\n"
        )
        self.assertEqual(match.rule_id, "L01")
        self.assertFalse(match.finding)
        self.assertEqual([aux.rule_id for aux in match.auxiliary], ["L09"])
        self.assertIn("set loc = null", match.auxiliary[0].evidence)

    def test_cleaned_agent_with_null_has_no_l09_advice(self):
        match = _single(
            "function F takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call SetUnitPositionLoc(u, loc)\n"
            "    call RemoveLocation(loc)\n"
            "    set loc = null\n"
            "endfunction\n"
        )
        self.assertEqual(match.auxiliary, ())

    def test_effect_leak_is_patch_only(self):
        match = _single(
            "function Fx takes nothing returns nothing\n"
            "    local effect e = AddSpecialEffect(\"A.mdl\", 0, 0)\n"
            "endfunction\n"
        )
        self.assertEqual(match.rule_id, "L05")
        self.assertTrue(match.finding)
        self.assertEqual(match.fix_mode, "patch")
        self.assertFalse(match.auto_fixable)
        self.assertIn("DestroyEffect", match.evidence)

    def test_inline_group_is_patch_only(self):
        match = _single(
            "function F takes nothing returns nothing\n"
            "    call ForGroup(CreateGroup(), null)\n"
            "endfunction\n"
        )
        self.assertEqual(match.rule_id, "L06")
        self.assertEqual(match.fix_mode, "patch")
        self.assertFalse(match.auto_fixable)
        self.assertIn("内联", match.evidence)

    def test_boolexpr_is_patch_only(self):
        match = _single(
            "function F takes nothing returns nothing\n"
            "    local boolexpr b = Condition(null)\n"
            "endfunction\n"
        )
        self.assertEqual(match.rule_id, "L07")
        self.assertEqual(match.fix_mode, "patch")
        self.assertIn("DestroyBoolExpr", match.evidence)

    def test_escaped_global_store_is_notice_not_finding(self):
        match = _single(
            "function F takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    set gg_loc = loc\n"
            "endfunction\n"
        )
        self.assertFalse(match.finding)
        self.assertTrue(match.notice)
        self.assertEqual(match.fix_mode, "none")
        self.assertIn("所有权已转移", match.evidence)

    def test_return_ownership_is_not_reported(self):
        match = _single(
            "function F takes unit u returns location\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    return loc\n"
            "endfunction\n"
        )
        self.assertFalse(match.finding)
        self.assertFalse(match.notice)

    def test_global_handle_is_not_a_leak(self):
        match = _single(
            "globals\n"
            "    rect gg_r = null\n"
            "endglobals\n"
            "function Init takes nothing returns nothing\n"
            "    set gg_r = Rect(0, 0, 1, 1)\n"
            "endfunction\n"
        )
        self.assertIsNone(match.rule)
        self.assertFalse(match.finding)
        self.assertTrue(match.notice)
        self.assertIn("全局", match.evidence)

    def test_coverage_statement_lists_limits(self):
        text = coverage_statement()
        for token in ("自动修复", "补丁建议", "只报告", "不处理", "Lua"):
            self.assertIn(token, text)
        for handle_type in ("location", "effect", "lightning", "boolexpr"):
            self.assertIn(handle_type, text)


def _match_expected(expected, matches):
    used = set()
    matched = 0
    for wanted in expected:
        for index, match in enumerate(matches):
            if index in used:
                continue
            creation = match.creation
            if wanted.get("function") and creation.function != wanted["function"]:
                continue
            if wanted.get("type") and creation.handle_type != wanted["type"]:
                continue
            if wanted.get("variable") and creation.variable != wanted["variable"]:
                continue
            used.add(index)
            matched += 1
            break
    return matched, used


if __name__ == "__main__":
    unittest.main()
