"""P5.5 界面冒烟测试：不自动扫描、勾选、导出、写回与撤销。"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from gui.tabs.leak_fix_tab import LeakFixTab

CASES = Path(__file__).resolve().parent / "leak_corpus" / "cases"
REPO = Path(__file__).resolve().parent.parent


class FakeApp:
    def __init__(self, root, data_dir):
        self.root = root
        self.map_path = tk.StringVar()
        self.war3_path = tk.StringVar()
        self.status_var = tk.StringVar()
        self.data_dir = str(data_dir)
        self.base_dir = str(REPO)
        self.exe_dir = str(REPO)
        self.mpq_editor_path = str(REPO / "MPQEditor.exe")
        self.report_area = None

    def log(self, _message):
        pass


class LeakFixTabSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:  # pragma: no cover - 无图形环境时跳过
            raise unittest.SkipTest(f"Tk 不可用: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = FakeApp(self.root, self.temp.name)
        self.patches = [
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showinfo"),
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showwarning"),
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showerror"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.tab = LeakFixTab(self.root, self.app)
        self.tab.pack(fill=tk.BOTH, expand=True)
        self.root.update_idletasks()

    def tearDown(self):
        self.tab.destroy()
        self.temp.cleanup()

    def _map_copy(self, name):
        target = Path(self.temp.name) / name
        shutil.copy2(CASES / name, target)
        return str(target)

    def _pump(self, done, timeout):
        deadline = time.time() + timeout

        def poll():
            if done() or time.time() > deadline:
                self.root.quit()
            else:
                self.root.after(50, poll)

        self.root.after(0, poll)
        self.root.mainloop()

    def _scan(self, path):
        self.app.map_path.set(path)
        self.root.after(0, self.tab.start_scan)
        self._pump(
            lambda: not self.tab._busy and self.tab.plan is not None, 20)
        if self.tab.plan is None:
            self.fail("等待扫描完成超时")

    def test_page_open_does_not_scan(self):
        self.assertIsNone(self.tab.plan)
        self.assertIsNone(self.tab.report)
        self.assertEqual(self.tab.tree.get_children(), ())
        self.assertIn("不会自动扫描", self.tab.detail_text.get("1.0", tk.END))

    def test_scan_populates_rows_and_selects_a_level(self):
        self._scan(self._map_copy("01_single_return_location.j"))
        self.assertEqual(len(self.tab.report["rows"]), 1)
        self.assertEqual(len(self.tab.tree.get_children()), 1)
        self.assertEqual(len(self.tab._checked), 1)
        detail = self.tab.detail_text.get("1.0", tk.END)
        self.assertIn("RemoveLocation", detail)
        self.assertIn("GetUnitLoc", detail)
        self.assertEqual(str(self.tab.apply_btn.cget("state")), tk.NORMAL)

    def test_export_report_writes_three_files(self):
        self._scan(self._map_copy("01_single_return_location.j"))
        self.tab.export_report()
        out_dir = os.path.join(self.temp.name, "leak_reports")
        names = sorted(os.listdir(out_dir))
        self.assertEqual(len(names), 3)
        self.assertTrue(any(name.endswith("_leak_report.md") for name in names))
        self.assertTrue(any(name.endswith("_leak_report.json") for name in names))
        self.assertTrue(any(name.endswith("_leak_report.csv") for name in names))

    def test_export_patch_without_writing_map(self):
        source = self._map_copy("01_single_return_location.j")
        self._scan(source)
        self.tab.export_patch()
        out_dir = os.path.join(self.temp.name, "leak_reports")
        patches = [name for name in os.listdir(out_dir)
                   if name.endswith("_leakfix.patch")]
        self.assertEqual(len(patches), 1)
        text = (Path(out_dir) / patches[0]).read_text(encoding="utf-8")
        self.assertIn("RemoveLocation", text)
        self.assertFalse(os.path.exists(
            os.path.splitext(source)[0] + "_leakfixed.j"))

    def test_apply_and_undo_copy(self):
        source = self._map_copy("01_single_return_location.j")
        self._scan(source)
        self.tab._confirm_diff = lambda _diff, _keys: True
        self.root.after(0, self.tab.apply_selected)
        self._pump(lambda: not self.tab._busy, 30)
        self.root.update()
        output = os.path.splitext(source)[0] + "_leakfixed.j"
        self.assertTrue(os.path.exists(output))
        fixed = Path(output).read_text(encoding="utf-8")
        self.assertIn("RemoveLocation(loc)", fixed)
        self.assertIn("set loc = null", fixed)
        original = Path(source).read_text(encoding="utf-8")
        self.assertNotIn("RemoveLocation(loc)", original)
        self.assertFalse(self.tab._busy)
        self.assertEqual(str(self.tab.undo_btn.cget("state")), tk.NORMAL)

        self.tab.undo_last_write()
        self.assertFalse(os.path.exists(output))
        self.assertTrue(Path(source).is_file())

    def test_lua_is_readonly(self):
        target = Path(self.temp.name) / "map.lua"
        target.write_text(
            "local loc = Location(0, 0)\n", encoding="utf-8")
        self._scan(str(target))
        self.assertTrue(self.tab.plan.readonly)
        self.assertEqual(str(self.tab.apply_btn.cget("state")), tk.DISABLED)
        self.assertEqual(str(self.tab.patch_btn.cget("state")), tk.DISABLED)


if __name__ == "__main__":
    unittest.main()
