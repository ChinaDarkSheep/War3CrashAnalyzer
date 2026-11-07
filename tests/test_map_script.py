"""P5.4 地图脚本封装测试：副本写入、备份撤销、Lua 只读与真实地图回归。"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.leak_fixer import build_fix_plan, write_fix_plan
from core.map_extract import find_w3x2lni
from core.map_script import MapScript

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE = REPO_ROOT / "tests" / "leak_corpus" / "cases" / "01_single_return_location.j"


def copy_case(temp_dir, name="case.j"):
    target = Path(temp_dir) / name
    shutil.copy2(CASE, target)
    return target


def fixed_text_for(path):
    plan = build_fix_plan(path.read_text(encoding="utf-8"))
    return plan, plan.fixed_text()


class ScriptWriteTests(unittest.TestCase):
    def test_script_load_write_verify_and_undo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = copy_case(temp_dir)
            original = source.read_text(encoding="utf-8")
            map_script = MapScript.load(source, temp_dir)
            self.assertEqual(map_script.kind, "script")
            self.assertEqual(map_script.language, "jass")
            self.assertTrue(map_script.writable)
            self.assertEqual(map_script.internal_path, source.name)

            plan, fixed = fixed_text_for(source)
            result = map_script.write(fixed)
            self.assertTrue(result.written, result.error)
            self.assertEqual(result.write_count, 1)
            self.assertTrue(result.verification["verified"])
            self.assertTrue(Path(result.output_path).is_file())
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertTrue(map_script.source_unchanged)

            self.assertTrue(map_script.undo())
            self.assertFalse(Path(result.output_path).exists())
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_second_write_backs_up_and_undo_restores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = copy_case(temp_dir)
            map_script = MapScript.load(source, temp_dir)
            _, first = fixed_text_for(source)
            first_result = map_script.write(first)
            first_output = Path(first_result.output_path).read_text(encoding="utf-8")

            second = first + "\n// second pass\n"
            second_result = map_script.write(second)
            self.assertTrue(second_result.written)
            self.assertTrue(Path(second_result.backup_path).is_file())

            self.assertTrue(map_script.undo())
            self.assertEqual(
                Path(second_result.output_path).read_text(encoding="utf-8"),
                first_output,
            )

    def test_lua_script_is_readonly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "war3map.lua"
            source.write_text("function F() end\n", encoding="utf-8")
            original = source.read_bytes()
            map_script = MapScript.load(source, temp_dir)
            self.assertEqual(map_script.language, "lua")
            self.assertFalse(map_script.writable)

            result = map_script.write("function G() end\n")
            self.assertFalse(result.written)
            self.assertTrue(result.readonly)
            self.assertEqual(result.write_count, 0)
            self.assertIn("Lua", result.error)
            self.assertFalse(Path(map_script.output_path).exists())
            self.assertEqual(source.read_bytes(), original)

    def test_lua_map_write_count_is_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            map_script = MapScript(
                source_path=str(Path(temp_dir) / "map.w3x"),
                kind="map",
                script_path=str(Path(temp_dir) / "war3map.lua"),
                internal_path="war3map.lua",
                language="lua",
                text="",
                encoding="utf-8",
                method="test",
                writable=False,
                readonly_reason="检测到 Lua 脚本，本版只读，不写入地图。",
            )
            result = map_script.write("-- changed\n")
            self.assertFalse(result.written)
            self.assertEqual(result.write_count, 0)
            self.assertTrue(result.readonly)

    def test_directory_input_is_readonly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "mapdir"
            source_dir.mkdir()
            shutil.copy2(CASE, source_dir / "war3map.j")
            map_script = MapScript.load(source_dir, temp_dir)
            self.assertEqual(map_script.kind, "directory")
            self.assertFalse(map_script.writable)
            result = map_script.write("x")
            self.assertEqual(result.write_count, 0)
            self.assertTrue(result.readonly)


@unittest.skipUnless(
    os.environ.get("WAR3_LEAK_MAP_DIR"), "设置 WAR3_LEAK_MAP_DIR 后运行真实地图写回"
)
class RealMapWriteTests(unittest.TestCase):
    def test_real_map_write_re_extract_and_undo(self):
        map_dir = Path(os.environ["WAR3_LEAK_MAP_DIR"])
        mpq_editor = Path(
            os.environ.get("WAR3_MPQ_EDITOR", REPO_ROOT / "MPQEditor.exe")
        )
        if not mpq_editor.is_file():
            self.skipTest(f"缺少 MPQEditor: {mpq_editor}")
        maps = sorted(
            (
                path
                for path in map_dir.iterdir()
                if path.suffix.lower() in {".w3x", ".w3m"}
            ),
            key=lambda path: path.stat().st_size,
        )
        if not maps:
            self.skipTest("地图目录为空")
        source_map = maps[0]

        with tempfile.TemporaryDirectory(prefix="leak_map_write_") as temp_dir:
            local_map = Path(temp_dir) / source_map.name
            shutil.copy2(source_map, local_map)
            original_sha = local_map.read_bytes()
            map_script = MapScript.load(
                local_map,
                temp_dir,
                mpq_editor_path=str(mpq_editor),
                w3x2lni_path=find_w3x2lni(),
            )
            self.assertTrue(map_script.writable, map_script.readonly_reason)
            self.assertTrue(map_script.internal_path)

            plan = build_fix_plan(map_script.text)
            self.assertGreater(len(plan.auto_edits), 0)
            self.assertTrue(plan.idempotent)

            result = write_fix_plan(
                plan, map_script, validate=False, pjass_path=None
            )
            self.assertTrue(result["written"], result.get("error"))
            self.assertEqual(result["write_count"], 1)
            self.assertTrue(result["verification"]["verified"])
            self.assertEqual(local_map.read_bytes(), original_sha)
            self.assertTrue(map_script.source_unchanged)

            verification = map_script.verify(
                result["output_path"], plan.fixed_text()
            )
            self.assertTrue(verification["verified"], verification)

            self.assertTrue(map_script.undo())
            self.assertFalse(Path(result["output_path"]).exists())
            self.assertEqual(local_map.read_bytes(), original_sha)


if __name__ == "__main__":
    unittest.main()
