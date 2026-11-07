"""崩溃诊断页：仅在疑似泄露时追加只读证据，不提供改图入口。"""

from __future__ import annotations

import tempfile
import tkinter as tk
import unittest

from gui.tabs.static_tab import StaticTab
from core.leak_report import crash_evidence_text


class FakeApp:
    def __init__(self, data_dir):
        self.war3_path = tk.StringVar()
        self.status_var = tk.StringVar()
        self.data_dir = str(data_dir)
        self.report_area = None
        self.messages = []

    def log(self, message):
        self.messages.append(message)


class StaticTabEvidenceTests(unittest.TestCase):
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
        self.app = FakeApp(self.temp.name)
        self.tab = StaticTab(self.root, self.app)

    def tearDown(self):
        self.tab.destroy()
        self.temp.cleanup()

    def test_suspected_crash_appends_readonly_evidence(self):
        self.tab.auditor.last_diagnosis = {
            "reason": {"kind": "out_of_memory"}}
        self.tab._finish_diagnosis("[+] 已诊断: Crash.txt", None)
        output = "\n".join(self.app.messages)
        self.assertIn(crash_evidence_text(), output)
        self.assertIn("不会修改地图", output)

    def test_ordinary_crash_has_no_evidence(self):
        self.tab.auditor.last_diagnosis = {
            "analysis_text": "The instruction at 0x1234 referenced memory."}
        self.tab._finish_diagnosis("[+] 已诊断: Crash.txt", None)
        output = "\n".join(self.app.messages)
        self.assertNotIn("疑似地图泄露证据", output)

    def test_repeated_diagnosis_does_not_leak_previous_state(self):
        self.tab.auditor.last_diagnosis = {
            "reason": {"kind": "out_of_memory"}}
        self.tab._finish_diagnosis("[+] 已诊断: Crash.txt", None)
        self.app.messages.clear()
        self.tab.auditor.last_diagnosis = None
        self.tab._finish_diagnosis("[+] 已诊断: Crash.txt", None)
        self.assertNotIn(
            "疑似地图泄露证据", "\n".join(self.app.messages))


if __name__ == "__main__":
    unittest.main()
