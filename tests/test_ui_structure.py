"""界面结构回归：四个主标签、内页顺序与功能入口。"""

from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from unittest import mock

from gui.tabs.adv_tab import AdvTab
from gui.tabs.desync_tab import DesyncRiskTab
from gui.tabs.health_tab import HealthTab
from gui.tabs.records_tab import RecordsTab


class FakeApp:
    def __init__(self, root, data_dir):
        self.root = root
        self.data_dir = str(data_dir)
        self.base_dir = str(data_dir)
        self.exe_dir = str(data_dir)
        self.mpq_editor_path = "MPQEditor.exe"
        self.map_path = tk.StringVar()
        self.war3_path = tk.StringVar()
        self.status_var = tk.StringVar()
        self.report_area = None
        self.report_interval = 30
        self.boot_start = False
        self.min_to_tray = True
        self.allow_report = False
        self.auto_collect = True
        self.upload_opened = 0
        self.status_queries = 0
        self.manual_reports = 0

    def log(self, _message):
        pass

    def save_config(self):
        pass

    def open_upload_dialog(self, *_args, **_kwargs):
        self.upload_opened += 1

    def open_upload_status_dialog(self):
        self.status_queries += 1

    def report_crash_to_server(self):
        self.manual_reports += 1


class UiStructureTests(unittest.TestCase):
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
            mock.patch("gui.tabs.records_tab.messagebox.showinfo"),
            mock.patch("gui.tabs.records_tab.messagebox.showwarning"),
            mock.patch("gui.tabs.records_tab.messagebox.showerror"),
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showinfo"),
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showwarning"),
            mock.patch("gui.tabs.leak_fix_tab.messagebox.showerror"),
            mock.patch("gui.tabs.desync_tab.messagebox.showinfo"),
            mock.patch("gui.tabs.desync_tab.messagebox.showwarning"),
            mock.patch("gui.tabs.desync_tab.messagebox.showerror"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temp.cleanup()

    def _make(self, cls):
        tab = cls(self.root, self.app)
        self.addCleanup(tab.destroy)
        self.root.update_idletasks()
        return tab

    def test_records_tab_keeps_history_and_upload_entries(self):
        tab = self._make(RecordsTab)
        self.assertEqual(tab.history_btn["text"], "打开崩溃历史")
        self.assertEqual(tab.export_bundle_btn["text"], "导出诊断包")
        self.assertEqual(tab.batch_btn["text"], "批量诊断全部日志")
        tab.upload_btn.invoke()
        tab.upload_status_btn.invoke()
        self.assertEqual(self.app.upload_opened, 1)
        self.assertEqual(self.app.status_queries, 1)

    def test_health_tab_orders_scans_before_tools(self):
        tab = self._make(HealthTab)
        labels = [tab.notebook.tab(i, "text").strip() for i in tab.notebook.tabs()]
        self.assertEqual(labels, ["泄露检查", "掉线风险", "脚本与资源"])
        self.assertIs(tab.notebook.nametowidget(tab.notebook.tabs()[0]), tab.leak_tab)
        self.assertIs(tab.notebook.nametowidget(tab.notebook.tabs()[1]), tab.desync_tab)

    def test_desync_tab_is_read_only_and_does_not_auto_scan(self):
        tab = self._make(DesyncRiskTab)
        self.assertIsNone(tab.report)
        self.assertEqual(tab.scan_btn["text"], "开始扫描")
        self.assertEqual(str(tab.export_btn["state"]), "disabled")
        self.assertFalse(hasattr(tab, "apply_btn"))
        self.assertFalse(hasattr(tab, "patch_btn"))

    def test_health_tab_has_no_desync_log_entry(self):
        tab = self._make(HealthTab)
        texts = []

        def walk(widget):
            try:
                texts.append(str(widget.cget("text")))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)

        walk(tab)
        self.assertNotIn("同步日志", texts)

    def test_advanced_tab_embeds_monitor_and_manual_report(self):
        tab = self._make(AdvTab)
        notebook = tab.local_tab.master
        labels = [notebook.tab(i, "text").strip() for i in notebook.tabs()]
        self.assertEqual(labels, ["实时监控（高危）", "插件与上报", "帮助与关于"])
        tab.report_btn.invoke()
        self.assertEqual(self.app.manual_reports, 1)


if __name__ == "__main__":
    unittest.main()
