"""P5.2 JASS 语义分析回归测试。

用 18 个合成语料锁定以下事实：
- 单出口/多出口、分支内销毁、循环内创建与内联创建的生命周期；
- 写入全局、返回、传参、数组/哈希表存储、RegionAddRect 接管等逃逸；
- 共享句柄、长期计时器/触发器、GUI 单位组不会被判为可自动修复；
- 符号表、函数签名、调用图（直接调用/回调/ExecuteFunc）与不可解析语句的保守处理。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from core.jass_parser import parse_script
from core.jass_semantics import analyze_file, analyze_script, analyze_source

_HERE = Path(__file__).resolve().parent
_CASES_DIR = _HERE / "leak_corpus" / "cases"


def _case(name):
    return analyze_file(_CASES_DIR / f"{name}.j")


def _creations(semantics):
    return [
        creation
        for analysis in semantics.functions.values()
        for creation in analysis.creations
    ]


def _creation_index(semantics):
    result = {}
    for creation in _creations(semantics):
        result[(creation.function, creation.variable, creation.handle_type)] = creation
    return result


def _single(source):
    semantics = analyze_source(source)
    creations = _creations(semantics)
    if len(creations) != 1:
        raise AssertionError(
            f"期望 1 个创建点，实际 {len(creations)}："
            f"{[(c.function, c.variable, c.creator) for c in creations]}"
        )
    return semantics, creations[0]


# (function, variable, type, kind, status, cleanup, auto_fix)
_CORPUS_EXPECTATIONS = {
    "01_single_return_location": [
        ("SingleReturn", "loc", "location", "local", "leaked", "none", True),
    ],
    "02_multi_return_location": [
        ("MultiReturn", "loc", "location", "local", "leaked", "none", False),
    ],
    "03_branch_destroy_group": [
        ("BranchDestroy", "g", "group", "local", "leaked", "partial", False),
    ],
    "04_loop_inline_location": [
        ("LoopInline", None, "location", "inline", "leaked", "none", True),
    ],
    "05_sleep_group": [
        ("Sleepy", "g", "group", "local", "leaked", "none", True),
    ],
    "06_gui_group": [
        ("GuiGroup", None, "group", "inline", "managed", "managed", False),
    ],
    "07_escape_global_location": [
        ("EscapeGlobal", "loc", "location", "local", "escaped", "none", False),
    ],
    "08_shared_force": [
        ("SharedForceGlobal", "bj_sharedForce", "force", "global", "global_owned", "global", False),
        ("SharedForceLocal", "f", "force", "local", "shared", "none", False),
    ],
    "09_new_force_local": [
        ("NewForceLocal", "f", "force", "local", "leaked", "none", True),
    ],
    "10_comment_and_string": [],
    "11_spaced_destroy": [
        ("SpacedDestroy", "loc", "location", "local", "cleaned", "complete", False),
    ],
    "12_return_handle": [
        ("ReturnHandle", "loc", "location", "local", "escaped", "none", False),
    ],
    "13_long_lived_timer": [
        ("LongTimer", "t", "timer", "local", "long_lived", "none", False),
    ],
    "14_idempotent_location": [
        ("Idempotent", "loc", "location", "local", "leaked", "none", True),
    ],
    "15_return_inline_location": [
        ("ReturnInline", None, "location", "inline", "escaped", "none", False),
    ],
    "16_local_rect_scope": [
        ("LocalRect", "r", "rect", "local", "escaped", "none", False),
    ],
    "17_substring_creator": [
        ("SubstringCreator", None, "rect", "inline", "escaped", "none", False),
    ],
    "18_global_rect_init": [
        ("InitRects", "gg_rct_Test", "rect", "global", "global_owned", "global", False),
    ],
}


class CorpusSemanticsTests(unittest.TestCase):
    def test_all_corpus_cases_match_expected_facts(self):
        for case_id, expectations in _CORPUS_EXPECTATIONS.items():
            with self.subTest(case=case_id):
                semantics = _case(case_id)
                actual = {
                    (c.function, c.variable, c.handle_type, c.kind,
                     c.status, c.cleanup, c.auto_fix)
                    for c in _creations(semantics)
                }
                self.assertEqual(actual, set(expectations))

    def test_case_04_inline_creation_is_inside_loop(self):
        semantics = _case("04_loop_inline_location")
        creation = _creations(semantics)[0]
        self.assertTrue(creation.in_loop)
        self.assertEqual(creation.kind, "inline")

    def test_case_03_reports_partial_cleanup(self):
        semantics = _case("03_branch_destroy_group")
        creation = _creations(semantics)[0]
        self.assertEqual(creation.cleanup, "partial")
        self.assertEqual(
            [fact.kind for fact in creation.escapes], []
        )
        self.assertTrue(any("部分路径" in reason for reason in creation.reasons))

    def test_case_05_marks_sleep(self):
        analysis = _case("05_sleep_group").functions["Sleepy"]
        self.assertTrue(analysis.cfg.has_sleep)
        self.assertEqual(analysis.cfg.sleep_lines, {3})

    def test_case_06_gui_group_is_managed(self):
        creation = _creations(_case("06_gui_group"))[0]
        self.assertTrue(creation.gui_managed)
        self.assertEqual(creation.status, "managed")
        self.assertFalse(creation.auto_fix)

    def test_case_07_escape_is_global_store(self):
        creation = _creations(_case("07_escape_global_location"))[0]
        self.assertEqual([fact.kind for fact in creation.escapes], ["global_store"])
        self.assertEqual(creation.escapes[0].detail, "udg_savedLoc")
        self.assertFalse(creation.auto_fix)

    def test_case_08_shared_force_facts(self):
        semantics = _case("08_shared_force")
        self.assertEqual(semantics.shared_globals, {"bj_sharedForce"})
        index = _creation_index(semantics)
        global_force = index[("SharedForceGlobal", "bj_sharedForce", "force")]
        local_force = index[("SharedForceLocal", "f", "force")]
        self.assertTrue(global_force.shared)
        self.assertTrue(local_force.shared)
        self.assertFalse(global_force.auto_fix)
        self.assertFalse(local_force.auto_fix)

    def test_case_11_spaced_destroy_is_recognized(self):
        creation = _creations(_case("11_spaced_destroy"))[0]
        self.assertEqual(creation.cleanup, "complete")
        self.assertEqual(creation.status, "cleaned")
        self.assertEqual(creation.destroys[0].destroyer, "RemoveLocation")

    def test_case_12_return_transfers_ownership(self):
        creation = _creations(_case("12_return_handle"))[0]
        self.assertEqual([fact.kind for fact in creation.escapes], ["return"])
        self.assertFalse(creation.auto_fix)

    def test_case_13_timer_is_long_lived(self):
        creation = _creations(_case("13_long_lived_timer"))[0]
        self.assertTrue(creation.long_lived)
        self.assertEqual(creation.cleanup, "none")
        self.assertFalse(creation.auto_fix)

    def test_case_16_and_17_region_add_rect_is_ownership_sink(self):
        local_rect = _creations(_case("16_local_rect_scope"))[0]
        inline_rect = _creations(_case("17_substring_creator"))[0]
        self.assertEqual([fact.kind for fact in local_rect.escapes], ["ownership_sink"])
        self.assertEqual([fact.kind for fact in inline_rect.escapes], ["ownership_sink"])
        self.assertFalse(local_rect.auto_fix)
        self.assertFalse(inline_rect.auto_fix)

    def test_case_18_global_rect_is_never_localized(self):
        semantics = _case("18_global_rect_init")
        creation = _creations(semantics)[0]
        self.assertEqual(creation.kind, "global")
        self.assertEqual(creation.status, "global_owned")
        self.assertFalse(creation.auto_fix)
        self.assertEqual(semantics.globals["gg_rct_Test"].type_name, "rect")

    def test_case_10_has_no_creations(self):
        semantics = _case("10_comment_and_string")
        self.assertEqual(_creations(semantics), [])
        self.assertEqual(semantics.global_creations, [])


class SymbolAndCallGraphTests(unittest.TestCase):
    def test_symbol_table_tracks_defs_and_uses(self):
        semantics = _case("01_single_return_location")
        analysis = semantics.functions["SingleReturn"]
        symbol = analysis.symbols["loc"]
        self.assertEqual(symbol.scope, "local")
        self.assertEqual(symbol.type_name, "location")
        self.assertEqual([site.kind for site in symbol.defs], ["local"])
        self.assertTrue(any(site.kind == "arg" for site in symbol.uses))
        signature = semantics.signatures["SingleReturn"]
        self.assertEqual(signature.params, (("u", "unit"),))
        self.assertEqual(signature.return_type, "nothing")

    def test_implicit_globals_are_created_from_assignments(self):
        semantics = _case("07_escape_global_location")
        symbol = semantics.globals["udg_savedLoc"]
        self.assertEqual(symbol.scope, "global")
        self.assertTrue(symbol.implicit)
        self.assertTrue(symbol.uses or symbol.defs)

    def test_callback_edges_are_recorded(self):
        semantics = _case("13_long_lived_timer")
        self.assertTrue(semantics.call_graph.has_edge("LongTimer", "Tick"))
        callbacks = [
            edge for edge in semantics.call_graph.edges if edge.kind == "callback"
        ]
        self.assertTrue(any(edge.callee == "Tick" for edge in callbacks))
        semantics = _case("03_branch_destroy_group")
        callbacks = [
            edge for edge in semantics.call_graph.edges if edge.kind == "callback"
        ]
        self.assertTrue(any(edge.callee == "DoNothing" for edge in callbacks))

    def test_executefunc_literal_and_dynamic_calls(self):
        semantics = analyze_source(
            "function A takes nothing returns nothing\n"
            "    call ExecuteFunc(\"B\")\n"
            "endfunction\n"
            "function B takes nothing returns nothing\n"
            "    call C()\n"
            "endfunction\n"
            "function C takes nothing returns nothing\n"
            "endfunction\n"
            "function D takes string name returns nothing\n"
            "    call ExecuteFunc(name)\n"
            "endfunction\n"
        )
        self.assertTrue(semantics.call_graph.has_edge("A", "B"))
        self.assertTrue(semantics.call_graph.has_edge("B", "C"))
        self.assertEqual(
            semantics.call_graph.reachable_from("A"), {"A", "B", "C"}
        )
        dynamic = semantics.unresolved_calls()
        self.assertEqual([(site.caller, site.kind) for site in dynamic], [("D", "dynamic")])

    def test_no_creations_for_native_only_script(self):
        semantics = analyze_source(
            "native GetUnitLoc takes unit u returns location\n"
            "function A takes nothing returns nothing\n"
            "endfunction\n"
        )
        self.assertEqual(_creations(semantics), [])
        self.assertIn("GetUnitLoc", semantics.signatures)


class EscapeAnalysisTests(unittest.TestCase):
    def test_local_alias_destroy_counts_as_cleanup(self):
        semantics, creation = _single(
            "function Alias takes unit u returns nothing\n"
            "    local location a = GetUnitLoc(u)\n"
            "    local location b = a\n"
            "    call RemoveLocation(b)\n"
            "endfunction\n"
        )
        self.assertEqual(creation.status, "cleaned")
        self.assertEqual(creation.cleanup, "complete")
        self.assertFalse(creation.auto_fix)

    def test_argument_to_map_function_is_escape(self):
        semantics = analyze_source(
            "function Helper takes location l returns nothing\n"
            "endfunction\n"
            "function Caller takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call Helper(loc)\n"
            "endfunction\n"
        )
        creation = _creations(semantics)[0]
        self.assertEqual(creation.status, "escaped")
        self.assertEqual([fact.kind for fact in creation.escapes], ["argument"])
        self.assertEqual(creation.escapes[0].detail, "Helper")
        self.assertFalse(creation.auto_fix)

    def test_safe_native_consumer_does_not_escape(self):
        _, creation = _single(
            "function Safe takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call SetUnitPositionLoc(u, loc)\n"
            "endfunction\n"
        )
        self.assertEqual(creation.escapes, [])
        self.assertEqual(creation.status, "leaked")
        self.assertTrue(creation.auto_fix)

    def test_hashtable_store_is_escape(self):
        semantics, creation = _single(
            "function Save takes unit u, hashtable ht returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call SaveLocationHandle(ht, 0, 0, loc)\n"
            "endfunction\n"
        )
        self.assertEqual(creation.status, "escaped")
        self.assertEqual([fact.kind for fact in creation.escapes], ["hashtable_store"])
        self.assertFalse(creation.auto_fix)

    def test_array_store_is_escape(self):
        semantics, creation = _single(
            "function Arr takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    set udg_locs[0] = loc\n"
            "endfunction\n"
        )
        self.assertEqual(creation.status, "escaped")
        self.assertEqual([fact.kind for fact in creation.escapes], ["array_store"])
        self.assertFalse(creation.auto_fix)

    def test_array_element_creation_is_not_auto_fixable(self):
        semantics, creation = _single(
            "function ArrCreate takes nothing returns nothing\n"
            "    set udg_groups[0] = CreateGroup()\n"
            "endfunction\n"
        )
        self.assertEqual(creation.kind, "array")
        self.assertEqual(creation.status, "escaped")
        self.assertFalse(creation.auto_fix)

    def test_types_outside_auto_fix_whitelist_are_report_only(self):
        _, timer_creation = _single(
            "function Timers takes nothing returns nothing\n"
            "    local timer t = CreateTimer()\n"
            "endfunction\n"
        )
        self.assertEqual(timer_creation.handle_type, "timer")
        self.assertEqual(timer_creation.status, "leaked")
        self.assertFalse(timer_creation.auto_fix)

        _, rect_creation = _single(
            "function Rects takes nothing returns nothing\n"
            "    local rect r = Rect(0, 0, 1, 1)\n"
            "endfunction\n"
        )
        self.assertEqual(rect_creation.handle_type, "rect")
        self.assertEqual(rect_creation.status, "leaked")
        self.assertFalse(rect_creation.auto_fix)

    def test_shared_force_returned_stays_shared(self):
        semantics, creation = _single(
            "function SharedReturn takes player p returns force\n"
            "    local force f = GetPlayersAll()\n"
            "    call ForceAddPlayer(f, p)\n"
            "    return f\n"
            "endfunction\n"
        )
        self.assertTrue(creation.shared)
        self.assertEqual(creation.status, "shared")
        self.assertEqual([fact.kind for fact in creation.escapes], ["return"])
        self.assertFalse(creation.auto_fix)

    def test_null_overwrite_marks_reference_lost(self):
        semantics, creation = _single(
            "function Lost takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    set loc = null\n"
            "endfunction\n"
        )
        self.assertTrue(creation.released)
        self.assertEqual(creation.status, "leaked")
        self.assertEqual(creation.cleanup, "none")
        self.assertFalse(creation.auto_fix)

    def test_null_after_destroy_is_normal(self):
        semantics, creation = _single(
            "function Clean takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call RemoveLocation(loc)\n"
            "    set loc = null\n"
            "endfunction\n"
        )
        self.assertFalse(creation.released)
        self.assertEqual(creation.status, "cleaned")
        self.assertEqual(creation.cleanup, "complete")


class LifecycleTests(unittest.TestCase):
    def test_trigger_registration_is_long_lived(self):
        semantics, creation = _single(
            "function Trig takes nothing returns nothing\n"
            "    local trigger t = CreateTrigger()\n"
            "    call TriggerRegisterTimerEvent(t, 1.0, true)\n"
            "endfunction\n"
        )
        self.assertTrue(creation.long_lived)
        self.assertEqual(creation.status, "long_lived")
        self.assertFalse(creation.auto_fix)

    def test_registered_boolexpr_is_long_lived(self):
        semantics = analyze_source(
            "function Trig takes nothing returns nothing\n"
            "    local trigger t = CreateTrigger()\n"
            "    local boolexpr c = Condition(function Cond)\n"
            "    call TriggerAddCondition(t, c)\n"
            "endfunction\n"
            "function Cond takes nothing returns boolean\n"
            "    return true\n"
            "endfunction\n"
        )
        creations = {
            creation.variable: creation for creation in _creations(semantics)
        }
        self.assertEqual(creations["c"].handle_type, "boolexpr")
        self.assertTrue(creations["c"].long_lived)
        self.assertFalse(creations["c"].auto_fix)
        self.assertTrue(creations["t"].long_lived)
        self.assertTrue(semantics.call_graph.has_edge("Trig", "Cond"))

    def test_gui_flag_only_manages_forgroupbj(self):
        with_flag, managed = _single(
            "function Gui takes player p returns nothing\n"
            "    set bj_wantDestroyGroup = true\n"
            "    call ForGroupBJ(GetUnitsOfPlayerAll(p), function DoNothing)\n"
            "endfunction\n"
        )
        self.assertTrue(managed.gui_managed)
        self.assertEqual(managed.status, "managed")
        self.assertFalse(managed.auto_fix)

        without_flag, leaked = _single(
            "function Plain takes player p returns nothing\n"
            "    call ForGroupBJ(GetUnitsOfPlayerAll(p), function DoNothing)\n"
            "endfunction\n"
        )
        self.assertFalse(leaked.gui_managed)
        self.assertEqual(leaked.status, "leaked")

    def test_unparsed_statement_blocks_auto_fix(self):
        semantics = analyze_source(
            "function Broken takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    this is not jass\n"
            "endfunction\n"
        )
        analysis = semantics.functions["Broken"]
        self.assertTrue(analysis.has_unparsed)
        creation = analysis.creations[0]
        self.assertFalse(creation.auto_fix)
        self.assertTrue(any("无法解析" in reason for reason in creation.reasons))

    def test_multi_return_cleanup_is_not_auto_fixable(self):
        semantics = _case("02_multi_return_location")
        analysis = semantics.functions["MultiReturn"]
        self.assertEqual(len(analysis.cfg.returns), 2)
        creation = _creations(semantics)[0]
        self.assertEqual(creation.status, "leaked")
        self.assertFalse(creation.auto_fix)


if __name__ == "__main__":
    unittest.main()
