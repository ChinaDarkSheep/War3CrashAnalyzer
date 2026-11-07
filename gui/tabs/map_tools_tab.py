"""地图脚本与资源工具：解包、审计与指纹定位。"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from core.auditor import Auditor
from gui.tabs.base import BaseTab


class MapToolsTab(BaseTab):
    def setup_ui(self):
        self.auditor = Auditor(self.log, self.update_status, self.app.data_dir)

        outer = tk.Frame(self, bg="#f5f6f7", padx=10, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        map_card = tk.LabelFrame(
            outer, text=" 地图脚本与资源 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        map_card.pack(fill=tk.X, pady=(0, 8))

        map_row = tk.Frame(map_card, bg="#ffffff")
        map_row.pack(fill=tk.X)
        tk.Label(map_row, text="地图文件:", bg="#ffffff",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Entry(map_row, textvariable=self.app.map_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        tk.Button(map_row, text="浏览", command=self.browse_map,
                  width=8).pack(side=tk.LEFT)

        tools_row = tk.Frame(map_card, bg="#ffffff")
        tools_row.pack(fill=tk.X, pady=(8, 0))

        self.deep_extract_btn = tk.Button(
            tools_row, text="强力提取", command=self.start_deep_extraction,
            bg="#e74c3c", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.deep_extract_btn.pack(side=tk.LEFT, padx=2)

        self.audit_btn = tk.Button(
            tools_row, text="资源审计", command=self.start_audit,
            bg="#2ecc71", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.audit_btn.pack(side=tk.LEFT, padx=2)

        self.jass_audit_btn = tk.Button(
            tools_row, text="JASS 审计", command=self.start_jass_audit,
            bg="#3498db", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.jass_audit_btn.pack(side=tk.LEFT, padx=2)

        self.locator_btn = tk.Button(
            tools_row, text="指纹定位", command=self.open_locator,
            bg="#1abc9c", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.locator_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(
            map_card,
            text="审计地图资源与脚本、按崩溃地址定位脚本位置；"
                 "加密地图的文件名还原依赖外部 w3x2lni / MPQEditor。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
            anchor=tk.W).pack(fill=tk.X, pady=(6, 0))

        log_frame = tk.LabelFrame(outer, text=" 工具执行日志 ", bg="#f5f6f7")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.map_log_area = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.map_log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log(self, message):
        self.map_log_area.insert(tk.END, message + "\n")
        self.map_log_area.see(tk.END)
        self.update_status(message)

    def browse_map(self):
        path = filedialog.askopenfilename(filetypes=[("魔兽地图", "*.w3x;*.w3m")])
        if path:
            self.app.map_path.set(path)
            self.app.save_config()
            self.update_status(f"地图文件已设置为: {os.path.basename(path)}")

    def start_deep_extraction(self):
        map_file = self.app.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.deep_extract_btn.config(state=tk.DISABLED)
        self.update_status("正在进行强力提取...")
        threading.Thread(
            target=self.auditor.deep_extract_worker,
            args=(map_file, self.app.mpq_editor_path, self.app.data_dir,
                  lambda: self.deep_extract_btn.config(state=tk.NORMAL)),
            daemon=True).start()

    def start_audit(self):
        map_file = self.app.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.audit_btn.config(state=tk.DISABLED)
        self.update_status("正在进行资源审计...")
        threading.Thread(
            target=self.auditor.audit_worker,
            args=(map_file, self.app.mpq_editor_path, self.app.data_dir,
                  lambda: self.audit_btn.config(state=tk.NORMAL)),
            daemon=True).start()

    def start_jass_audit(self):
        map_file = self.app.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.jass_audit_btn.config(state=tk.DISABLED)
        self.update_status("正在进行 JASS 审计...")
        threading.Thread(
            target=self.auditor.jass_audit_worker,
            args=(map_file, self.app.mpq_editor_path, self.app.data_dir,
                  lambda: self.jass_audit_btn.config(state=tk.NORMAL)),
            daemon=True).start()

    def open_locator(self):
        from gui.locator_dialog import FingerprintLocatorDialog
        dialog = getattr(self, "locator_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.lift()
            dialog.focus_force()
            return
        self.locator_dialog = FingerprintLocatorDialog(self, self.app)
