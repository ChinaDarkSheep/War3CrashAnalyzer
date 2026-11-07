"""P5.2 JASS CFG 回归测试。

覆盖语句级控制流图的关键契约：
1. entry/exit、顺序连接、if/elseif/else 的分叉与汇合；
2. loop/exitwhen 的回边与循环归属；
3. return、不可达语句、sleep 标记；
4. 支配关系与“移除销毁点后是否仍能到达出口”。
"""

from __future__ import annotations

import unittest

from core.jass_cfg import build_cfg
from core.jass_parser import parse_script


def _parse_one(source):
    script = parse_script(source)
    if script.errors:
        raise AssertionError(script.errors)
    return script.functions[0]


def _cfg(source):
    return build_cfg(_parse_one(source))


class CFGStructureTests(unittest.TestCase):
    def test_empty_function_connects_entry_to_exit(self):
        cfg = _cfg("function Empty takes nothing returns nothing\nendfunction")
        self.assertEqual(cfg.nodes[cfg.entry].kind, "entry")
        self.assertEqual(cfg.nodes[cfg.exit].kind, "exit")
        self.assertIn(cfg.exit, cfg.nodes[cfg.entry].successors)
        self.assertIn(cfg.entry, cfg.nodes[cfg.exit].predecessors)
        self.assertEqual(cfg.reachable, {cfg.entry, cfg.exit})
        self.assertEqual(cfg.returns, [])

    def test_linear_statements_are_chained(self):
        function = _parse_one(
            "function Linear takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call SetUnitPositionLoc(u, loc)\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        decl, call = function.body.statements
        decl_node = cfg.node_for_statement(decl)
        call_node = cfg.node_for_statement(call)
        self.assertIn(decl_node, cfg.nodes[cfg.entry].successors)
        self.assertIn(call_node, cfg.nodes[decl_node].successors)
        self.assertIn(cfg.exit, cfg.nodes[call_node].successors)
        self.assertTrue(cfg.dominates(decl_node, call_node))
        self.assertTrue(cfg.dominates(decl_node, cfg.exit))

    def test_if_branches_meet_at_merge(self):
        function = _parse_one(
            "function Branch takes integer x returns nothing\n"
            "    if x > 0 then\n"
            "        call A()\n"
            "    else\n"
            "        call B()\n"
            "    endif\n"
            "    call C()\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        branch = function.body.statements[0]
        branch_node = cfg.node_for_statement(branch)
        self.assertEqual(cfg.nodes[branch_node].kind, "branch")
        self.assertEqual(len(cfg.nodes[branch_node].successors), 2)
        true_call = branch.branches[0].body.statements[0]
        false_call = branch.else_body.statements[0]
        true_node = cfg.node_for_statement(true_call)
        false_node = cfg.node_for_statement(false_call)
        self.assertIn(true_node, cfg.nodes[branch_node].successors)
        self.assertIn(false_node, cfg.nodes[branch_node].successors)
        merge = cfg.nodes[true_node].successors
        self.assertEqual(len(merge), 1)
        merge_node = merge[0]
        self.assertIn(false_node, cfg.nodes[merge_node].predecessors)
        call_c = cfg.node_for_statement(function.body.statements[1])
        self.assertIn(call_c, cfg.nodes[merge_node].successors)
        self.assertFalse(cfg.dominates(true_node, call_c))
        self.assertTrue(cfg.dominates(merge_node, call_c))

    def test_elseif_chains_false_edges(self):
        function = _parse_one(
            "function Chain takes integer x returns nothing\n"
            "    if x > 0 then\n"
            "        call A()\n"
            "    elseif x < 0 then\n"
            "        call B()\n"
            "    else\n"
            "        call C()\n"
            "    endif\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        branch = function.body.statements[0]
        self.assertEqual(len(branch.branches), 2)
        first_node = cfg.node_for_statement(branch.branches[0])
        second_node = cfg.node_for_statement(branch.branches[1])
        self.assertIn(second_node, cfg.nodes[first_node].successors)
        body_a = cfg.node_for_statement(branch.branches[0].body.statements[0])
        body_b = cfg.node_for_statement(branch.branches[1].body.statements[0])
        body_c = cfg.node_for_statement(branch.else_body.statements[0])
        merge = cfg.nodes[body_a].successors[0]
        self.assertEqual(
            set(cfg.nodes[merge].predecessors), {body_a, body_b, body_c}
        )

    def test_return_terminates_path(self):
        function = _parse_one(
            "function Early takes boolean flag returns nothing\n"
            "    if flag then\n"
            "        return\n"
            "    endif\n"
            "    call A()\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        return_stmt = function.body.statements[0].branches[0].body.statements[0]
        return_node = cfg.node_for_statement(return_stmt)
        self.assertEqual(cfg.nodes[return_node].kind, "return")
        self.assertEqual(cfg.nodes[return_node].successors, [])
        self.assertEqual(cfg.returns, [return_node])
        self.assertIn(return_node, cfg.exits)

    def test_loop_has_body_exit_and_back_edge(self):
        function = _parse_one(
            "function Loop takes integer n returns nothing\n"
            "    local integer i = 0\n"
            "    loop\n"
            "        exitwhen i >= n\n"
            "        set i = i + 1\n"
            "    endloop\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        loop_stmt = function.body.statements[1]
        loop_node = cfg.node_for_statement(loop_stmt)
        self.assertEqual(cfg.nodes[loop_node].kind, "loop")
        self.assertEqual(len(cfg.loops), 1)
        info = cfg.loops[0]
        self.assertEqual(info.header, loop_node)
        self.assertEqual(len(cfg.nodes[loop_node].successors), 2)
        self.assertIn(info.exit, cfg.nodes[loop_node].successors)
        exitwhen = loop_stmt.body.statements[0]
        increment = loop_stmt.body.statements[1]
        exitwhen_node = cfg.node_for_statement(exitwhen)
        increment_node = cfg.node_for_statement(increment)
        self.assertIn(info.exit, cfg.nodes[exitwhen_node].successors)
        self.assertIn(increment_node, cfg.nodes[exitwhen_node].successors)
        self.assertIn(loop_node, cfg.nodes[increment_node].successors)
        self.assertIn(exitwhen_node, info.body_nodes)
        self.assertIn(increment_node, info.body_nodes)
        self.assertTrue(cfg.is_in_loop(increment_node))
        self.assertIs(cfg.loop_containing(increment_node), info)
        self.assertFalse(cfg.is_in_loop(cfg.entry))

    def test_nested_loops_are_attributed_to_inner_loop(self):
        function = _parse_one(
            "function Nested takes integer n returns nothing\n"
            "    local integer i = 0\n"
            "    loop\n"
            "        exitwhen i >= n\n"
            "        loop\n"
            "            exitwhen i >= 10\n"
            "            set i = i + 1\n"
            "        endloop\n"
            "    endloop\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        self.assertEqual(len(cfg.loops), 2)
        inner = next(loop for loop in cfg.loops
                     if loop.header != cfg.node_for_statement(
                         function.body.statements[1]))
        inner_set = inner.body_nodes
        target = max(inner_set)
        self.assertTrue(cfg.is_in_loop(target))
        self.assertIs(cfg.loop_containing(target), inner)
        self.assertEqual(len(inner.exitwhen_nodes), 1)


class CFGReachabilityTests(unittest.TestCase):
    def test_sleep_functions_are_marked(self):
        cfg = _cfg(
            "function Sleepy takes nothing returns nothing\n"
            "    call TriggerSleepAction(1.0)\n"
            "    debug call PolledWait(0.5)\n"
            "endfunction\n"
        )
        self.assertTrue(cfg.has_sleep)
        self.assertEqual(cfg.sleep_lines, {2, 3})
        self.assertEqual(len(cfg.sleep_nodes), 2)

    def test_statements_after_return_are_unreachable(self):
        function = _parse_one(
            "function Dead takes nothing returns nothing\n"
            "    return\n"
            "    call A()\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        dead = cfg.node_for_statement(function.body.statements[1])
        self.assertNotIn(dead, cfg.reachable)

    def test_destroy_in_one_branch_is_partial_cleanup(self):
        function = _parse_one(
            "function BranchDestroy takes boolean flag, unit u returns nothing\n"
            "    local group g = CreateGroup()\n"
            "    if flag then\n"
            "        call GroupAddUnit(g, u)\n"
            "        call DestroyGroup(g)\n"
            "    else\n"
            "        call GroupAddUnit(g, u)\n"
            "    endif\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        create_node = cfg.node_for_statement(function.body.statements[0])
        destroy_stmt = function.body.statements[1].branches[0].body.statements[1]
        destroy_node = cfg.node_for_statement(destroy_stmt)
        self.assertTrue(cfg.can_reach_exit(create_node, frozenset({destroy_node})))
        self.assertFalse(cfg.dominates(destroy_node, cfg.exit))

    def test_destroy_on_all_paths_blocks_exit(self):
        function = _parse_one(
            "function Clean takes unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    call RemoveLocation(loc)\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        create_node = cfg.node_for_statement(function.body.statements[0])
        destroy_node = cfg.node_for_statement(function.body.statements[1])
        self.assertFalse(cfg.can_reach_exit(create_node, frozenset({destroy_node})))
        self.assertTrue(cfg.dominates(destroy_node, cfg.exit))

    def test_return_path_blocks_complete_cleanup(self):
        function = _parse_one(
            "function Multi takes boolean flag, unit u returns nothing\n"
            "    local location loc = GetUnitLoc(u)\n"
            "    if flag then\n"
            "        return\n"
            "    endif\n"
            "    call RemoveLocation(loc)\n"
            "endfunction\n"
        )
        cfg = build_cfg(function)
        create_node = cfg.node_for_statement(function.body.statements[0])
        destroy_node = cfg.node_for_statement(function.body.statements[2])
        self.assertTrue(cfg.can_reach_exit(create_node, frozenset({destroy_node})))

    def test_dominator_tree_roots_at_entry(self):
        cfg = _cfg(
            "function Dom takes integer x returns nothing\n"
            "    if x > 0 then\n"
            "        call A()\n"
            "    endif\n"
            "    call B()\n"
            "endfunction\n"
        )
        dominators = cfg.compute_dominators()
        for node_id in cfg.reachable:
            self.assertIn(cfg.entry, dominators[node_id])
        self.assertEqual(dominators[cfg.entry], {cfg.entry})


if __name__ == "__main__":
    unittest.main()
