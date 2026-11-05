import os
import threading
import tkinter as tk
import tkinter.scrolledtext
import tkinter.messagebox
import subprocess
from gui.tabs.base import BaseTab
from core.fixer import Fixer
from core.auditor import Auditor

class LeakFixTab(BaseTab):
    def setup_ui(self):
        # 使用 app 中统一的 fixer 实例，如果没有则创建一个
        if not hasattr(self.app, 'fixer') or self.app.fixer is None:
            self.app.fixer = Fixer(self.log, self.app.config.get("api_key"))
        self.fixer = self.app.fixer
        
        # 引入审计器用于代码切片
        self.auditor = Auditor(self.leak_fix_log, self.update_status, self.app.base_dir)
        
        main_frame = tk.Frame(self, bg="#f5f6f7", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 介绍
        intro_frame = tk.Frame(main_frame, bg="#f5f6f7")
        intro_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(intro_frame, text="✨ 泄露定位&修复 引擎", font=("微软雅黑", 12, "bold"), bg="#f5f6f7", fg="#2c3e50").pack(anchor=tk.W)
        tk.Label(intro_frame, text="基于静态分析与 AI 预诊断技术，精准定位并修复 JASS 脚本中的内存泄露风险。", font=("微软雅黑", 9), bg="#f5f6f7", fg="#7f8c8d").pack(anchor=tk.W)

        # 功能卡片
        card = tk.LabelFrame(main_frame, text=" 泄露定位&修复操作 ", bg="#ffffff", padx=20, pady=20, font=("微软雅黑", 9, "bold"), fg="#2980b9")
        card.pack(fill=tk.BOTH, expand=True)

        # 增加可勾选的修复选项
        self.fix_options = {}
        features = [
            ("fix_point", "✅ 修复点 (Location) 泄露 (自动添加 RemoveLocation)"),
            ("fix_group", "✅ 修复单位组 (Group) 泄露 (自动添加 DestroyGroup)"),
            ("fix_rect", "✅ 修复矩形区域 (Rect) 泄露 (自动添加 RemoveRect)"),
            ("optimize_jass", "✅ 优化 JASS 脚本执行效率与内存占用")
        ]
        
        for key, text in features:
            var = tk.BooleanVar(value=True)
            self.fix_options[key] = var
            chk = tk.Checkbutton(card, text=text, variable=var, bg="#ffffff", font=("微软雅黑", 10), pady=2,
                                activebackground="#ffffff", selectcolor="#ffffff")
            chk.pack(anchor=tk.W)

        self.use_ai_fix = tk.BooleanVar(value=False)
        ai_check = tk.Checkbutton(card, text="✨ 启用 AI 智能修复 (直接修改 war3map.j)", variable=self.use_ai_fix, bg="#ffffff", font=("微软雅黑", 10, "bold"), fg="#e67e22",
                                 activebackground="#ffffff", selectcolor="#ffffff")
        ai_check.pack(anchor=tk.W, pady=(10, 0))
        
        self.gen_locate_report = tk.BooleanVar(value=True)
        locate_report_check = tk.Checkbutton(card, text="📄 输出详细定位报告 (.md)", variable=self.gen_locate_report, bg="#ffffff", font=("微软雅黑", 10),
                                            activebackground="#ffffff", selectcolor="#ffffff")
        locate_report_check.pack(anchor=tk.W)

        btn_container = tk.Frame(card, bg="#ffffff", pady=10)
        btn_container.pack(fill=tk.X)

        self.leak_fix_btn = tk.Button(btn_container, text="🛠️ 执行基础修复", command=self.start_leak_fix, 
                                     bg="#3498db", fg="white", font=("微软雅黑", 11, "bold"), width=20)
        self.leak_fix_btn.pack(side=tk.LEFT, padx=5)

        self.leak_locate_btn = tk.Button(btn_container, text="🔍 仅执行泄露定位", command=self.start_leak_locate, 
                                        bg="#9b59b6", fg="white", font=("微软雅黑", 11, "bold"), width=20)
        self.leak_locate_btn.pack(side=tk.LEFT, padx=5)

        self.diag_report_btn = tk.Button(btn_container, text="📊 生成 AI 诊断报告", command=self.generate_report, 
                                        bg="#2ecc71", fg="white", font=("微软雅黑", 11, "bold"), width=20)
        self.diag_report_btn.pack(side=tk.LEFT, padx=5)
        
        self.fix_result_frame = tk.Frame(card, bg="#ffffff")
        self.fix_result_frame.pack(fill=tk.X, pady=5)
        self.fix_stats_label = tk.Label(self.fix_result_frame, text="状态: 待处理...", bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d")
        self.fix_stats_label.pack(anchor=tk.W)

        # 独立日志窗口
        log_frame = tk.LabelFrame(main_frame, text=" 执行日志与诊断反馈 ", bg="#ffffff", padx=10, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.leak_fix_log_area = tk.scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.leak_fix_log_area.pack(fill=tk.BOTH, expand=True)

    def leak_fix_log(self, message):
        self.leak_fix_log_area.insert(tk.END, message + "\n")
        self.leak_fix_log_area.see(tk.END)
        if hasattr(self, 'app') and hasattr(self.app, 'status_var'):
            self.app.status_var.set(message)

    def start_leak_fix(self):
        path = self.app.map_path.get().strip('"')
        if not path or not os.path.exists(path):
            tk.messagebox.showwarning("提示", "请先选择地图！")
            return
            
        options = {key: var.get() for key, var in self.fix_options.items()}
        options['ai_fix'] = self.use_ai_fix.get()
        
        self.leak_fix_btn.config(state=tk.DISABLED)
        self.leak_fix_log("[*] 正在启动泄露定位&修复引擎...")
        
        self.fixer.log = self.leak_fix_log
        
        threading.Thread(target=self.fixer.leak_fix_worker, 
                         args=(path, self.app.mpq_editor_path, self.app.base_dir, self.update_fix_stats, self.on_fix_finish, options), 
                         daemon=True).start()

    def start_leak_locate(self):
        path = self.app.map_path.get().strip('"')
        if not path or not os.path.exists(path):
            tk.messagebox.showwarning("提示", "请先选择地图！")
            return
            
        options = {key: var.get() for key, var in self.fix_options.items()}
        options['gen_report'] = self.gen_locate_report.get()
        
        self.leak_locate_btn.config(state=tk.DISABLED)
        self.leak_fix_log("[*] 正在启动泄露定位引擎...")
        
        self.fixer.log = self.leak_fix_log
        
        def on_finish():
            self.app.root.after(0, lambda: self.leak_locate_btn.config(state=tk.NORMAL))
            self.leak_fix_log("[+] 定位分析结束。")
            if options['gen_report']:
                os.startfile(self.app.base_dir)

        threading.Thread(target=self.fixer.leak_locate_worker, 
                         args=(path, self.app.mpq_editor_path, self.app.base_dir, on_finish, options), 
                         daemon=True).start()

    def generate_report(self):
        path = self.app.map_path.get().strip('"')
        if not path or not os.path.exists(path):
            tk.messagebox.showwarning("提示", "请先选择地图！")
            return
            
        self.diag_report_btn.config(state=tk.DISABLED)
        
        def run():
            try:
                # 使用 Auditor 的代码切片功能
                self.auditor.generate_ai_slicing_report(path, self.app.mpq_editor_path, self.app.base_dir)
                
                # 同时生成原有的 Fixer 报告 (互补)
                temp_dir = os.path.join(self.app.base_dir, "ai_slicing")
                os.makedirs(temp_dir, exist_ok=True)
                
                script_path = os.path.join(temp_dir, "war3map.j")
                if os.path.exists(script_path):
                    with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    
                    options = {key: var.get() for key, var in self.fix_options.items()}
                    report = self.fixer.generate_ai_report(text, options)
                    report_path = os.path.join(self.app.base_dir, f"Leak_Fixer_{os.path.basename(path)}.md")
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(report)
                    self.leak_fix_log(f"[+] 详细泄露报告已生成: {report_path}")
                
                os.startfile(self.app.base_dir) # 打开文件夹查看生成的 md 文件
            except Exception as e:
                self.leak_fix_log(f"[-] 生成报告失败: {e}")
            finally:
                self.app.root.after(0, lambda: self.diag_report_btn.config(state=tk.NORMAL))

        threading.Thread(target=run, daemon=True).start()

    def update_fix_stats(self, message):
        self.fix_stats_label.config(text=message)
        self.leak_fix_log(message)

    def on_fix_finish(self):
        self.leak_fix_btn.config(state=tk.NORMAL)
        self.leak_fix_log("[+] 修复任务结束。")
