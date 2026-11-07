"""地图体检：泄露检查、脚本审计与脚本级风险扫描的统一入口。"""

import tkinter as tk
from tkinter import ttk

from gui.tabs.base import BaseTab
from gui.tabs.desync_tab import DesyncRiskTab
from gui.tabs.leak_fix_tab import LeakFixTab
from gui.tabs.map_tools_tab import MapToolsTab


class HealthTab(BaseTab):
    def setup_ui(self):
        outer = tk.Frame(self, bg="#f5f6f7", padx=6, pady=6)
        outer.pack(fill=tk.BOTH, expand=True)

        head = tk.Frame(outer, bg="#f5f6f7")
        head.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            head, text="地图体检", font=("微软雅黑", 12, "bold"),
            bg="#f5f6f7", fg="#2c3e50").pack(side=tk.LEFT)
        tk.Label(
            head, text="检查只读，修复只写入 *_leakfixed 副本，原图保持不变。",
            font=("微软雅黑", 9), bg="#f5f6f7", fg="#7f8c8d").pack(
                side=tk.LEFT, padx=(10, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.leak_tab = LeakFixTab(self.notebook, self.app)
        self.notebook.add(self.leak_tab, text=" 泄露检查 ")

        self.desync_tab = DesyncRiskTab(self.notebook, self.app)
        self.notebook.add(self.desync_tab, text=" 掉线风险 ")

        self.map_tools_tab = MapToolsTab(self.notebook, self.app)
        self.notebook.add(self.map_tools_tab, text=" 脚本与资源 ")

        # 第 4 个内页预留给 JASS 注入配置，接入前不放出空按钮。
