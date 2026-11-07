"""崩溃记录：本机历史、诊断资料与上传入口。"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from core.auditor import Auditor
from core.bundle import default_bundle_name, export_bundle
from gui.tabs.base import BaseTab


class RecordsTab(BaseTab):
    def setup_ui(self):
        self.auditor = Auditor(self.log, self.update_status, self.app.data_dir)

        outer = tk.Frame(self, bg="#f5f6f7", padx=10, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer, text="本机崩溃记录与上报", font=("微软雅黑", 12, "bold"),
            bg="#f5f6f7", fg="#2c3e50").pack(anchor=tk.W)
        tk.Label(
            outer,
            text="查看历史崩溃、导出诊断包，或把日志上传给地图作者；"
                 "上报前会先在本机完成诊断。",
            font=("微软雅黑", 9), bg="#f5f6f7", fg="#7f8c8d",
            anchor=tk.W).pack(fill=tk.X, pady=(2, 8))

        history_card = tk.LabelFrame(
            outer, text=" 崩溃历史 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        history_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            history_card,
            text="按时间查看每次崩溃的地图、归属结论、置信度与上报状态。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
            anchor=tk.W).pack(fill=tk.X)
        self.history_btn = tk.Button(
            history_card, text="打开崩溃历史", command=self.open_history,
            bg="#607d8b", fg="white", font=("微软雅黑", 9, "bold"), width=14)
        self.history_btn.pack(anchor=tk.W, pady=(8, 0))

        material_card = tk.LabelFrame(
            outer, text=" 诊断资料 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        material_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            material_card,
            text="诊断包包含最新崩溃日志、同名 dmp、诊断 JSON 与可粘贴摘要，"
                 "可直接交给地图作者；批量诊断会回溯处理全部未处理日志。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
            anchor=tk.W, justify=tk.LEFT).pack(fill=tk.X)

        material_row = tk.Frame(material_card, bg="#ffffff")
        material_row.pack(fill=tk.X, pady=(8, 0))
        self.export_bundle_btn = tk.Button(
            material_row, text="导出诊断包", command=self.export_diagnostic_bundle,
            bg="#16a085", fg="white", font=("微软雅黑", 9, "bold"), width=13)
        self.export_bundle_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.batch_btn = tk.Button(
            material_row, text="批量诊断全部日志", command=self.batch_analyze,
            bg="#8e44ad", fg="white", font=("微软雅黑", 9, "bold"), width=17)
        self.batch_btn.pack(side=tk.LEFT)

        server_card = tk.LabelFrame(
            outer, text=" 上传与分享 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        server_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            server_card,
            text="上传后会返回 6 位上传码，可把上传码发给地图作者；"
                 "查询上传码可查看作者的处理状态。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
            anchor=tk.W, justify=tk.LEFT).pack(fill=tk.X)

        server_row = tk.Frame(server_card, bg="#ffffff")
        server_row.pack(fill=tk.X, pady=(8, 0))
        self.upload_btn = tk.Button(
            server_row, text="上传日志到服务器",
            command=self.app.open_upload_dialog,
            bg="#2980b9", fg="white", font=("微软雅黑", 9, "bold"), width=17)
        self.upload_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.upload_status_btn = tk.Button(
            server_row, text="查询上传码状态",
            command=self.app.open_upload_status_dialog,
            bg="#34495e", fg="white", font=("微软雅黑", 9, "bold"), width=16)
        self.upload_status_btn.pack(side=tk.LEFT)

        log_frame = tk.LabelFrame(outer, text=" 执行日志 ", bg="#f5f6f7")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.records_log_area = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.records_log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log(self, message):
        self.records_log_area.insert(tk.END, message + "\n")
        self.records_log_area.see(tk.END)
        self.update_status(message)

    def open_history(self):
        from gui.history_dialog import CrashHistoryDialog
        dialog = getattr(self, "history_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            dialog.refresh()
            return
        self.history_dialog = CrashHistoryDialog(self, self.app)

    def batch_analyze(self):
        war3_dir = self.app.war3_path.get().strip('"')
        if not war3_dir or not os.path.isdir(war3_dir):
            messagebox.showwarning("提示", "请先在“崩溃诊断”页设置魔兽目录！")
            return
        self.batch_btn.config(state=tk.DISABLED)
        self.update_status("正在批量诊断未处理日志...")

        def run():
            try:
                res = self.auditor.analyze_last_crash(war3_dir)
            except Exception as e:
                res = f"[-] 批量诊断失败: {e}"

            def done():
                self.log(res)
                self.batch_btn.config(state=tk.NORMAL)
                self.update_status("批量诊断完成")

            self.app.root.after(0, done)

        threading.Thread(target=run, daemon=True).start()

    def export_diagnostic_bundle(self):
        war3_dir = self.app.war3_path.get().strip('"')
        if not war3_dir or not os.path.isdir(war3_dir):
            messagebox.showwarning("提示", "请先设置正确的魔兽目录！")
            return
        errors_dir = os.path.join(war3_dir, "Errors")
        logs = []
        if os.path.isdir(errors_dir):
            logs = [f for f in os.listdir(errors_dir)
                    if f.lower().endswith(".txt")]
        if not logs:
            messagebox.showinfo("提示", "未找到任何崩溃日志。")
            return

        log_name = max(logs, key=lambda f: os.path.getmtime(
            os.path.join(errors_dir, f)))
        log_path = os.path.join(errors_dir, log_name)
        map_path = self.app.map_path.get().strip('"')

        try:
            result = self.auditor.analyze_log_file(log_path)
        except Exception as e:
            messagebox.showerror("导出失败", f"诊断日志时出错：{e}")
            return

        output = filedialog.asksaveasfilename(
            title="保存诊断包",
            defaultextension=".zip",
            initialfile=default_bundle_name(result.get("map_name")),
            filetypes=[("Zip 压缩包", "*.zip")])
        if not output:
            return

        self.export_bundle_btn.config(state=tk.DISABLED)
        self.update_status("正在生成诊断包...")

        def run():
            try:
                _, summary = export_bundle(
                    log_path, result, output, map_path or None)

                def done():
                    self.log(f"\n[+] 诊断包已生成: {output}")
                    self.log(summary)
                    self.update_status("诊断包已生成，摘要已复制到剪贴板")
                    try:
                        self.app.root.clipboard_clear()
                        self.app.root.clipboard_append(summary)
                    except Exception:
                        pass
                    self.export_bundle_btn.config(state=tk.NORMAL)
                    messagebox.showinfo(
                        "导出完成",
                        f"诊断包已生成：\n{output}\n\nQQ 群摘要已复制到剪贴板。")

                self.app.root.after(0, done)
            except Exception as e:
                def fail():
                    self.update_status("诊断包生成失败")
                    self.export_bundle_btn.config(state=tk.NORMAL)
                    messagebox.showerror("导出失败", str(e))

                self.app.root.after(0, fail)

        threading.Thread(target=run, daemon=True).start()
