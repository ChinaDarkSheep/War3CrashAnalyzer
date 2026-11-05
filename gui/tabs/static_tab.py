import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
from gui.tabs.base import BaseTab
from core.auditor import Auditor
from core.bundle import default_bundle_name, export_bundle

class StaticTab(BaseTab):
    def setup_ui(self):
        self.auditor = Auditor(self.log, self.update_status, self.app.data_dir)
        
        pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        top_container = tk.Frame(pane, bg="#f5f6f7", padx=5, pady=5)
        pane.add(top_container, weight=1)

        top_frame = tk.LabelFrame(top_container, text=" 核心操作与配置 ", bg="#f5f6f7", pady=5, padx=10)
        top_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(top_frame, text="魔兽目录:", bg="#f5f6f7").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(top_frame, textvariable=self.app.war3_path).grid(row=0, column=1, sticky=tk.EW, padx=5)
        tk.Button(top_frame, text="浏览", command=self.browse_war3, width=8).grid(row=0, column=2)
        
        tk.Label(top_frame, text="地图文件:", bg="#f5f6f7").grid(row=1, column=0, sticky=tk.W, pady=5)
        tk.Entry(top_frame, textvariable=self.app.map_path).grid(row=1, column=1, sticky=tk.EW, padx=5)
        tk.Button(top_frame, text="浏览", command=self.browse_map, width=8).grid(row=1, column=2)
        top_frame.columnconfigure(1, weight=1)

        btn_container = tk.Frame(top_frame, bg="#f5f6f7")
        btn_container.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=5)
        
        self.deep_extract_btn = tk.Button(btn_container, text="🚀 强力提取", command=self.start_deep_extraction, bg="#e74c3c", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.deep_extract_btn.pack(side=tk.LEFT, padx=2)

        self.audit_btn = tk.Button(btn_container, text="🔍 资源审计", command=self.start_audit, bg="#2ecc71", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.audit_btn.pack(side=tk.LEFT, padx=2)

        self.jass_audit_btn = tk.Button(btn_container, text="📜 JASS 审计", command=self.start_jass_audit, bg="#3498db", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.jass_audit_btn.pack(side=tk.LEFT, padx=2)

        self.crash_btn = tk.Button(btn_container, text="📄 诊断日志", command=self.analyze_last_crash, bg="#9b59b6", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.crash_btn.pack(side=tk.LEFT, padx=2)

        self.export_bundle_btn = tk.Button(btn_container, text="📦 诊断包", command=self.export_diagnostic_bundle, bg="#16a085", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.export_bundle_btn.pack(side=tk.LEFT, padx=2)

        self.desync_log_btn = tk.Button(btn_container, text="🌐 同步日志", command=self.start_desync_log_analysis, bg="#f39c12", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.desync_log_btn.pack(side=tk.LEFT, padx=2)

        self.report_btn = tk.Button(btn_container, text="📤 上报崩溃", command=self.app.report_crash_to_server, bg="#34495e", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.report_btn.pack(side=tk.LEFT, padx=2)

        log_frame = tk.LabelFrame(pane, text=" 📜 实时诊断日志 ", bg="#f5f6f7")
        pane.add(log_frame, weight=2)
        
        self.report_area = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10), bg="#ffffff")
        self.report_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.app.report_area = self.report_area

    def browse_war3(self):
        path = filedialog.askdirectory(title="选择魔兽争霸 III 安装根目录 (包含 war3.exe)")
        if path: 
            war3_path = path.replace('/', '\\')
            # 检测目录下是否存在核心程序
            has_exe = any(os.path.exists(os.path.join(war3_path, exe)) for exe in ["war3.exe", "Warcraft III.exe", "War3.exe"])
            
            if not has_exe:
                if not tk.messagebox.askyesno("目录警告", "选中的目录下未找到 war3.exe 或 Warcraft III.exe，这可能导致分析功能失效。\n\n是否仍要选择该目录？"):
                    return

            self.app.war3_path.set(war3_path)
            self.app.save_config()
            self.update_status(f"魔兽目录已设置为: {os.path.basename(war3_path)}")

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
        threading.Thread(target=self.auditor.deep_extract_worker, 
                         args=(map_file, self.app.mpq_editor_path, self.app.data_dir, lambda: self.deep_extract_btn.config(state=tk.NORMAL)), 
                         daemon=True).start()

    def start_audit(self):
        map_file = self.app.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            tk.messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.audit_btn.config(state=tk.DISABLED)
        self.update_status("正在进行资源审计...")
        threading.Thread(target=self.auditor.audit_worker, 
                         args=(map_file, self.app.mpq_editor_path, self.app.data_dir, lambda: self.audit_btn.config(state=tk.NORMAL)), 
                         daemon=True).start()

    def start_jass_audit(self):
        map_file = self.app.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            tk.messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.jass_audit_btn.config(state=tk.DISABLED)
        self.update_status("正在进行 JASS 审计...")
        threading.Thread(target=self.auditor.jass_audit_worker, 
                         args=(map_file, self.app.mpq_editor_path, self.app.data_dir, lambda: self.jass_audit_btn.config(state=tk.NORMAL)), 
                         daemon=True).start()

    def analyze_last_crash(self):
        self.update_status("正在启动批量分析流程...")
        self.crash_btn.config(state=tk.DISABLED)
        
        def run():
            try:
                res = self.auditor.analyze_last_crash(self.app.war3_path.get())
                self.log(res)
            except Exception as e:
                self.log(f"[-] 分析过程出错: {e}")
            finally:
                self.app.root.after(0, lambda: self.crash_btn.config(state=tk.NORMAL))
                self.update_status("崩溃日志分析完毕")
        
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
