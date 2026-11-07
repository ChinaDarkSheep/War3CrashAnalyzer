"""P5.4 安全修复器测试：编辑生成、补丁、幂等与只读边界。"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from core.jass_parser import parse_script
from core.leak_fixer import (
    FixEdit,
    apply_edits,
    build_fix_plan,
    match_key,
    validate_fixed_text,
)

CASES = Path(__file__).resolve().parent / "leak_corpus" / "cases"

AUTO_CASES = {
    "01_single_return_location.j": ("RemoveLocation", "loc"),
    "04_loop_inline_location.j": ("RemoveLocation", "leakfix_loc_1"),
    "05_sleep_group.j": ("DestroyGroup", "g"),
    "09_new_force_local.j": ("DestroyForce", "f"),
    "14_idempotent_location.j": ("RemoveLocation", "loc"),
}

SAFETY_CASES = (
    "06_gui_group.j",
    "07_escape_global_location.j",
    "08_shared_force.j",
    "10_comment_and_string.j",
    "12_return_handle.j",
    "13_long_lived_timer.j",
    "15_return_inline_location.j",
    "16_local_rect_scope.j",
    "17_substring_creator.j",
    "18_global_rect_init.j",
)

RECT_PATCH = """function LocalRectPatch takes unit u returns nothing
    local rect r = Rect(0.0, 0.0, 100.0, 100.0)
    if RectContainsUnit(r, u) then
        call KillUnit(u)
    endif
endfunction
"""

EFFECT_PATCH = """function LocalEffect takes nothing returns nothing
    local effect e = AddSpecialEffect("x.mdl", 0.0, 0.0)
    call SetUnitAnimation(GetTriggerUnit(), "stand")
endfunction
"""

MULTI_INLINE = """function ManyInline takes unit u returns nothing
    call SetUnitPositionLoc(u, GetUnitLoc(u))
    call SetUnitPositionLoc(u, GetUnitLoc(u))
endfunction
"""

BAD_LOCAL_ORDER = """function BadOrder takes nothing returns nothing
    call SetUnitPositionLoc(GetTriggerUnit(), GetUnitLoc(GetTriggerUnit()))
    local location late = GetUnitLoc(GetTriggerUnit())
endfunction
"""


def case_text(name):
    return (CASES / name).read_text(encoding="utf-8")


def plan_for(name):
    return build_fix_plan(case_text(name))


def count(pattern, text):
    return len(re.findall(pattern, text))


class AutoFixTests(unittest.TestCase):
    def test_a_level_corpus_is_idempotent(self):
        for name in AUTO_CASES:
            with self.subTest(case=name):
                plan = plan_for(name)
                self.assertGreater(len(plan.auto_edits), 0, name)
                self.assertTrue(plan.idempotent, name)
                fixed = plan.fixed_text()
                second = build_fix_plan(fixed)
                self.assertEqual(second.auto_edits, [], name)

    def test_a_level_cleanup_destroys_once(self):
        for name, (destroyer, variable) in AUTO_CASES.items():
            with self.subTest(case=name):
                fixed = plan_for(name).fixed_text()
                pattern = rf"\b{destroyer}\s*\(\s*{re.escape(variable)}\s*\)"
                self.assertEqual(count(pattern, fixed), 1, fixed)

    def test_a_level_adds_null_after_destroy(self):
        for name, (destroyer, variable) in AUTO_CASES.items():
            with self.subTest(case=name):
                fixed = plan_for(name).fixed_text()
                self.assertIn(f"set {variable} = null", fixed)

    def test_inline_hoist_declares_local_before_loop(self):
        fixed = plan_for("04_loop_inline_location.j").fixed_text()
        declaration = fixed.index("local location leakfix_loc_1")
        loop = fixed.index("    loop")
        self.assertLess(declaration, loop)
        self.assertIn("set leakfix_loc_1 = GetUnitLoc(u)", fixed)
        self.assertNotIn("GetUnitLoc(u))", fixed)

    def test_fixed_text_parses_cleanly(self):
        for name in AUTO_CASES:
            with self.subTest(case=name):
                script = parse_script(plan_for(name).fixed_text())
                self.assertEqual(script.errors, [])
                self.assertEqual(script.unparsed_lines, set())

    def test_multiple_inline_declarations_stay_before_statements(self):
        fixed = build_fix_plan(MULTI_INLINE).fixed_text()
        self.assertEqual(fixed.count("local location leakfix_loc_"), 2)
        seen_statement = False
        for line in fixed.splitlines():
            content = line.strip()
            if not content or content.startswith("//"):
                continue
            if content.startswith("function ") or content == "endfunction":
                continue
            if content.startswith("local "):
                self.assertFalse(seen_statement, fixed)
            else:
                seen_statement = True

    def test_validate_flags_local_after_statement(self):
        result = validate_fixed_text(
            BAD_LOCAL_ORDER, pjass_path=str(CASES / "missing-pjass.exe")
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any(
            "Local declaration after first statement" in error["message"]
            for error in result["errors"]
        ))


class PatchAndReportTests(unittest.TestCase):
    def test_multi_return_is_patch_only(self):
        plan = plan_for("02_multi_return_location.j")
        self.assertEqual(plan.auto_edits, [])
        self.assertEqual(len(plan.patch_edits), 2)
        self.assertEqual(plan.fixed_text(), plan.source_text)
        patched = plan.fixed_text(include_patch=True)
        self.assertEqual(count(r"RemoveLocation\(loc\)", patched), 2)

    def test_multi_return_patch_cleans_every_return(self):
        patched = plan_for("02_multi_return_location.j").fixed_text(
            include_patch=True
        )
        lines = patched.splitlines()
        for index, line in enumerate(lines):
            if line.strip() == "return":
                window = "\n".join(lines[max(0, index - 3):index])
                self.assertIn("RemoveLocation(loc)", window)

    def test_partial_branch_destroy_is_manual(self):
        plan = plan_for("03_branch_destroy_group.j")
        self.assertEqual(plan.auto_edits, [])
        self.assertEqual(plan.patch_edits, [])
        self.assertTrue(
            any("部分路径" in note.message for note in plan.notes)
        )

    def test_safety_cases_produce_no_edits(self):
        for name in SAFETY_CASES:
            with self.subTest(case=name):
                plan = plan_for(name)
                self.assertEqual(plan.edits, [], name)
                self.assertEqual(plan.fixed_text(include_patch=True), case_text(name))

    def test_spaced_destroy_adds_only_null(self):
        plan = plan_for("11_spaced_destroy.j")
        self.assertEqual(len(plan.auto_edits), 1)
        fixed = plan.fixed_text()
        self.assertEqual(count(r"\bRemoveLocation\s*\(", fixed), 1)
        self.assertIn("RemoveLocation ( loc )", fixed)
        self.assertIn("set loc = null", fixed)
        self.assertNotIn("call RemoveLocation(loc)", fixed)
        self.assertEqual(build_fix_plan(fixed).auto_edits, [])

    def test_rect_generates_patch_not_auto(self):
        plan = build_fix_plan(RECT_PATCH)
        self.assertEqual(plan.auto_edits, [])
        self.assertEqual(len(plan.patch_edits), 1)
        self.assertEqual(plan.fixed_text(), RECT_PATCH)
        patched = plan.fixed_text(include_patch=True)
        self.assertIn("call RemoveRect(r)", patched)
        self.assertIn("set r = null", patched)

    def test_effect_generates_patch_not_auto(self):
        plan = build_fix_plan(EFFECT_PATCH)
        self.assertEqual(plan.auto_edits, [])
        self.assertEqual(len(plan.patch_edits), 1)
        patched = plan.fixed_text(include_patch=True)
        self.assertIn("call DestroyEffect(e)", patched)

    def test_shared_force_has_no_edit(self):
        plan = plan_for("08_shared_force.j")
        self.assertEqual(plan.edits, [])
        self.assertEqual(plan.fixed_text(include_patch=True), case_text("08_shared_force.j"))


class PlanMechanicsTests(unittest.TestCase):
    def test_unified_diff(self):
        diff = plan_for("01_single_return_location.j").diff()
        self.assertIn("--- a/war3map.j", diff)
        self.assertIn("+++ b/war3map.j", diff)
        self.assertIn("+    call RemoveLocation(loc)", diff)

    def test_lua_is_readonly(self):
        plan = build_fix_plan("function F() end\n", language="lua")
        self.assertTrue(plan.readonly)
        self.assertEqual(plan.edits, [])
        self.assertEqual(plan.auto_edits, [])
        self.assertEqual(plan.fixed_text(), plan.source_text)

    def test_overlapping_edits_are_rejected(self):
        edits = [
            FixEdit("replace", 0, 6, "a", None, "A", "F", 1, "one", True, 1),
            FixEdit("replace", 3, 9, "b", None, "A", "F", 1, "two", True, 2),
        ]
        with self.assertRaises(ValueError):
            apply_edits("0123456789", edits)

    def test_all_corpus_auto_plans_are_idempotent(self):
        for path in sorted(CASES.glob("*.j")):
            with self.subTest(case=path.name):
                plan = build_fix_plan(path.read_text(encoding="utf-8"))
                self.assertTrue(plan.idempotent, path.name)

    def test_missing_pjass_is_unchecked(self):
        result = validate_fixed_text(
            "function F takes nothing returns nothing\nendfunction\n",
            pjass_path="Z:/missing/pjass.exe",
        )
        self.assertEqual(result["status"], "unchecked")
        self.assertFalse(result["available"])

    def test_stats_shape(self):
        stats = plan_for("01_single_return_location.j").stats()
        self.assertEqual(stats["language"], "jass")
        self.assertEqual(stats["findings"], 1)
        self.assertGreater(stats["auto_edits"], 0)
        self.assertTrue(stats["idempotent"])


TWO_FUNCTIONS = """function Cleaned takes nothing returns nothing
    local location a = Location(0.0, 0.0)
    call RemoveLocation(a)
endfunction

function Leaked takes nothing returns nothing
    local location b = Location(1.0, 1.0)
endfunction
"""


class SelectionTests(unittest.TestCase):
    def test_selection_only_applies_selected_finding(self):
        plan = build_fix_plan(TWO_FUNCTIONS)
        leaked = [m for m in plan.findings if m.creation.function == "Leaked"]
        self.assertEqual(len(leaked), 1)
        fixed = plan.fixed_text(keys={match_key(leaked[0])})
        self.assertIn("call RemoveLocation(b)", fixed)
        self.assertNotIn("set a = null", fixed)
        self.assertEqual(count(r"call RemoveLocation\(a\)", fixed), 1)

    def test_auxiliary_null_can_be_selected_alone(self):
        plan = build_fix_plan(TWO_FUNCTIONS)
        cleaned = [
            match for match in plan.matches
            if match.creation.function == "Cleaned"
        ][0]
        self.assertTrue(cleaned.auxiliary)
        keys = {match_key(cleaned.auxiliary[0])}
        fixed = plan.fixed_text(keys=keys)
        self.assertIn("set a = null", fixed)
        self.assertNotIn("RemoveLocation(b)", fixed)

    def test_empty_selection_changes_nothing(self):
        plan = build_fix_plan(TWO_FUNCTIONS)
        self.assertEqual(plan.fixed_text(keys=set()), plan.source_text)
        self.assertEqual(plan.diff_for([]), "")

    def test_selection_diff_only_contains_selected_function(self):
        plan = build_fix_plan(TWO_FUNCTIONS)
        leaked = [m for m in plan.findings if m.creation.function == "Leaked"][0]
        diff = plan.diff(keys={match_key(leaked)})
        self.assertIn("+    call RemoveLocation(b)", diff)
        self.assertNotIn("+    call RemoveLocation(a)", diff)


if __name__ == "__main__":
    unittest.main()
