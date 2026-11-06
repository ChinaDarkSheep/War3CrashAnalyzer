import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext

from gui.tabs.base import BaseTab
from core.auditor import Auditor
from core.bundle import default_bundle_name, export_bundle


class AuthorTab(BaseTab):
    def setup_ui(self):
        self.auditor = Auditor(self.log, self.update_status, self.app.data_dir)

        outer = tk.Frame(self, bg="#f5f6f7", padx=10, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        map_card = tk.LabelFrame(
            outer, text=" 地图分析工具 ", bg="#ffffff", padx=12, pady=10,
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
            tools_row, text="🚀 强力提取", command=self.start_deep_extraction,
            bg="#e74c3c", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.deep_extract_btn.pack(side=tk.LEFT, padx=2)

        self.audit_btn = tk.Button(
            tools_row, text="🔍 资源审计", command=self.start_audit,
            bg="#2ecc71", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.audit_btn.pack(side=tk.LEFT, padx=2)

        self.jass_audit_btn = tk.Button(
            tools_row, text="📜 JASS 审计", command=self.start_jass_audit,
            bg="#3498db", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.jass_audit_btn.pack(side=tk.LEFT, padx=2)

        self.locator_btn = tk.Button(
            tools_row, text="🎯 指纹定位", command=self.open_locator,
            bg="#1abc9c", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.locator_btn.pack(side=tk.LEFT, padx=2)

        self.desync_log_btn = tk.Button(
            tools_row, text="🌐 同步日志", command=self.start_desync_log_analysis,
            bg="#f39c12", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.desync_log_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(map_card,
                 text="审计地图资源与脚本、定位可疑调用、分析同步日志；"
                      "加密地图的文件名还原依赖外部 w3x2lni / MPQEditor。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
                 anchor=tk.W).pack(fill=tk.X, pady=(6, 0))

        material_card = tk.LabelFrame(
            outer, text=" 诊断资料 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        material_card.pack(fill=tk.X, pady=(0, 8))

        material_row = tk.Frame(material_card, bg="#ffffff")
        material_row.pack(fill=tk.X)

        self.export_bundle_btn = tk.Button(
            material_row, text="📦 导出诊断包", command=self.export_diagnostic_bundle,
            bg="#16a085", fg="white", font=("微软雅黑", 9, "bold"), width=13)
        self.export_bundle_btn.pack(side=tk.LEFT, padx=2)

        self.history_btn = tk.Button(
            material_row, text="📊 崩溃历史", command=self.open_history,
            bg="#607d8b", fg="white", font=("微软雅黑", 9, "bold"), width=13)
        self.history_btn.pack(side=tk.LEFT, padx=2)

        self.batch_btn = tk.Button(
            material_row, text="🗂 批量诊断全部日志", command=self.batch_analyze,
            bg="#8e44ad", fg="white", font=("微软雅黑", 9, "bold"), width=17)
        self.batch_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(material_card,
                 text="诊断包内含最新崩溃日志、同名 dmp、诊断 JSON 与可粘贴的摘要，"
                      "可直接交给地图作者；批量诊断会回溯处理全部未处理日志。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
                 anchor=tk.W).pack(fill=tk.X, pady=(6, 0))

        server_card = tk.LabelFrame(
            outer, text=" 服务器 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        server_card.pack(fill=tk.X, pady=(0, 8))

        server_row = tk.Frame(server_card, bg="#ffffff")
        server_row.pack(fill=tk.X)

        self.upload_btn = tk.Button(
            server_row, text="⬆ 上传日志到服务器", command=self.app.open_upload_dialog,
            bg="#2980b9", fg="white", font=("微软雅黑", 9, "bold"), width=17)
        self.upload_btn.pack(side=tk.LEFT, padx=2)

        self.upload_status_btn = tk.Button(
            server_row, text="🔎 查询上传码状态",
            command=self.app.open_upload_status_dialog,
            bg="#34495e", fg="white", font=("微软雅黑", 9, "bold"), width=16)
        self.upload_status_btn.pack(side=tk.LEFT, padx=2)

        self.report_btn = tk.Button(
            server_row, text="📤 手动上报诊断数据",
            command=self.app.report_crash_to_server,
            bg="#95a5a6", fg="white", font=("微软雅黑", 9, "bold"), width=17)
        self.report_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(server_card,
                 text="上传日志会返回 6 位上传码；手动上报只提交诊断数据与日志文本，"
                      "不上传地图文件或 dmp 原始文件。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
                 anchor=tk.W).pack(fill=tk.X, pady=(6, 0))

        log_frame = tk.LabelFrame(outer, text=" 工具执行日志 ", bg="#f5f6f7")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.author_log_area = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.author_log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log(self, message):
        self.author_log_area.insert(tk.END, message + "\n")
        self.author_log_area.see(tk.END)
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
            tk.messagebox.showwarning("提示", "请先选择地图文件！")
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
            tk.messagebox.showwarning("提示", "请先选择地图文件！")
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
            tk.messagebox.showwarning("提示", "请先选择地图文件！")
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
            tk.messagebox.showwarning("提示", "请先在“崩溃诊断”页设置魔兽目录！")
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
            tk.messagebox.showwarning("提示", "请先设置正确的魔兽目录！")
            return
        errors_dir = os.path.join(war3_dir, "Errors")
        logs = []
        if os.path.isdir(errors_dir):
            logs = [f for f in os.listdir(errors_dir)
                    if f.lower().endswith(".txt")]
        if not logs:
            tk.messagebox.showinfo("提示", "未找到任何崩溃日志。")
            return

        log_name = max(logs, key=lambda f: os.path.getmtime(
            os.path.join(errors_dir, f)))
        log_path = os.path.join(errors_dir, log_name)
        map_path = self.app.map_path.get().strip('"')

        try:
            result = self.auditor.analyze_log_file(log_path)
        except Exception as e:
            tk.messagebox.showerror("导出失败", f"诊断日志时出错：{e}")
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
                    tk.messagebox.showinfo(
                        "导出完成",
                        f"诊断包已生成：\n{output}\n\nQQ 群摘要已复制到剪贴板。")

                self.app.root.after(0, done)
            except Exception as e:
                def fail():
                    self.update_status("诊断包生成失败")
                    self.export_bundle_btn.config(state=tk.NORMAL)
                    tk.messagebox.showerror("导出失败", str(e))

                self.app.root.after(0, fail)

        threading.Thread(target=run, daemon=True).start()

    def start_desync_log_analysis(self):
        self.update_status("正在分析同步日志...")
        self.auditor.desync_log_analysis(self.app.war3_path.get())
        self.update_status("同步日志分析完毕")
