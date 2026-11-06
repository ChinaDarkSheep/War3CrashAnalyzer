import os
import time
import threading
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
from gui.tabs.base import BaseTab
from core.auditor import Auditor


class StaticTab(BaseTab):
    def setup_ui(self):
        self.auditor = Auditor(self.log, self.update_status, self.app.data_dir)
        self.selected_log_path = None
        self.diagnosed_log_path = None
        self._log_choices = {}

        pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        self.pane = pane

        top_container = tk.Frame(pane, bg="#f5f6f7", padx=5, pady=5)
        pane.add(top_container, weight=1)
        self.top_container = top_container

        card = tk.LabelFrame(
            top_container, text=" 崩溃诊断（按步骤操作） ", bg="#ffffff",
            pady=10, padx=14, font=("微软雅黑", 10, "bold"), fg="#2c3e50")
        card.pack(fill=tk.X, pady=(2, 4))

        step1 = tk.Frame(card, bg="#ffffff")
        step1.pack(fill=tk.X)
        tk.Label(step1, text="第 1 步", bg="#ffffff", fg="#e67e22",
                 font=("微软雅黑", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(step1, text="确认魔兽安装目录", bg="#ffffff", fg="#2c3e50",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(8, 0))
        self.path_status = tk.Label(step1, text="", bg="#ffffff",
                                    font=("微软雅黑", 9, "bold"))
        self.path_status.pack(side=tk.RIGHT)

        path_row = tk.Frame(card, bg="#ffffff")
        path_row.pack(fill=tk.X, pady=(6, 12))
        tk.Entry(path_row, textvariable=self.app.war3_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(path_row, text="选择目录", command=self.browse_war3,
                  width=10).pack(side=tk.LEFT, padx=(8, 0))

        step2 = tk.Frame(card, bg="#ffffff")
        step2.pack(fill=tk.X)
        tk.Label(step2, text="第 2 步", bg="#ffffff", fg="#e67e22",
                 font=("微软雅黑", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(step2, text="选择日志并开始诊断", bg="#ffffff", fg="#2c3e50",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(8, 0))

        log_row = tk.Frame(card, bg="#ffffff")
        log_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(log_row, text="日志来源：", bg="#ffffff", fg="#2c3e50",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.log_choice_var = tk.StringVar(value="自动：最新一份日志")
        self.log_combo = ttk.Combobox(
            log_row, textvariable=self.log_choice_var, state="readonly",
            values=["自动：最新一份日志"])
        self.log_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self.log_combo.bind("<<ComboboxSelected>>", self._on_log_choice)
        self.log_combo.configure(postcommand=self._refresh_log_options)
        tk.Button(log_row, text="浏览…", command=self.browse_log,
                  width=8).pack(side=tk.LEFT, padx=(8, 0))

        self.crash_btn = tk.Button(
            card, text="🔍 开始诊断最新崩溃", command=self.analyze_last_crash,
            bg="#9b59b6", fg="white", font=("微软雅黑", 12, "bold"),
            height=2, cursor="hand2", relief=tk.RAISED)
        self.crash_btn.pack(fill=tk.X, pady=(8, 0))
        tk.Label(card, text="默认诊断 Errors 目录里最新的一份日志；也可以在上方切换或浏览其他日志。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
                 anchor=tk.W).pack(fill=tk.X, pady=(4, 0))

        self.step3_frame = tk.Frame(card, bg="#ffffff")
        tk.Frame(self.step3_frame, bg="#ecf0f1", height=1).pack(fill=tk.X, pady=(0, 8))
        step3_head = tk.Frame(self.step3_frame, bg="#ffffff")
        step3_head.pack(fill=tk.X)
        tk.Label(step3_head, text="第 3 步", bg="#ffffff", fg="#e67e22",
                 font=("微软雅黑", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(step3_head, text="上传本次崩溃样本（建议）", bg="#ffffff",
                 fg="#2c3e50", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(self.step3_frame,
                 text="把这次崩溃日志上传到服务器，帮助我们采集错误样本、构建大数据平台，"
                      "让后续的故障定位更加精准。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 9),
                 wraplength=820, justify=tk.LEFT, anchor=tk.W).pack(
                     fill=tk.X, pady=(4, 6))
        self.upload_btn = tk.Button(
            self.step3_frame, text="⬆ 上传服务器",
            command=self.upload_diagnosed_log, bg="#2980b9", fg="white",
            font=("微软雅黑", 11, "bold"), height=2, cursor="hand2")
        self.upload_btn.pack(fill=tk.X)
        tk.Label(self.step3_frame,
                 text="上传成功后会获得 6 位上传码；日志可能包含 Windows 用户名、计算机名和本地路径。",
                 bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
                 anchor=tk.W).pack(fill=tk.X, pady=(4, 0))

        log_frame = tk.LabelFrame(pane, text=" 📜 诊断日志 ", bg="#f5f6f7")
        pane.add(log_frame, weight=2)

        self.report_area = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 10), bg="#ffffff")
        self.report_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.app.report_area = self.report_area

        self.app.war3_path.trace_add("write", self._refresh_path_status)
        self._refresh_path_status()
        self._refresh_log_options()

    def _refresh_path_status(self, *_args):
        path = self.app.war3_path.get().strip('"')
        if not path:
            self.path_status.config(text="尚未设置", fg="#e74c3c")
        elif os.path.isdir(path):
            self.path_status.config(text="✓ 已设置", fg="#27ae60")
        else:
            self.path_status.config(text="⚠ 目录不存在", fg="#e67e22")

    def _refresh_log_options(self):
        choices = {"自动：最新一份日志": None}
        values = ["自动：最新一份日志"]
        war3_dir = self.app.war3_path.get().strip('"')
        errors_dir = os.path.join(war3_dir, "Errors") if war3_dir else ""
        entries = []
        if errors_dir and os.path.isdir(errors_dir):
            for name in os.listdir(errors_dir):
                if not name.lower().endswith(".txt"):
                    continue
                path = os.path.join(errors_dir, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = 0
                entries.append((mtime, name, path))
        entries.sort(key=lambda item: item[0], reverse=True)
        for mtime, name, path in entries:
            if mtime:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                label = f"{stamp}  {name}"
            else:
                label = name
            if label in choices:
                label = f"{label}  ({path})"
            choices[label] = path
            values.append(label)

        selected = self.selected_log_path
        if selected and selected not in choices.values():
            if os.path.isfile(selected):
                label = f"手动选择：{os.path.basename(selected)}"
                choices[label] = selected
                values.append(label)
                self.log_choice_var.set(label)
            else:
                self.selected_log_path = None
                self.log_choice_var.set("自动：最新一份日志")

        self._log_choices = choices
        self.log_combo.config(values=values)

    def _on_log_choice(self, _event=None):
        self.selected_log_path = self._log_choices.get(
            self.log_choice_var.get())
        self._restore_crash_btn()

    def browse_log(self):
        path = filedialog.askopenfilename(
            title="选择崩溃日志",
            filetypes=[("崩溃日志", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        self.selected_log_path = path
        self._refresh_log_options()
        self.log_choice_var.set(f"手动选择：{os.path.basename(path)}")
        self._restore_crash_btn()
        self.update_status(f"已选择日志: {os.path.basename(path)}")

    def _restore_crash_btn(self):
        text = ("🔍 诊断所选日志" if self.selected_log_path
                else "🔍 开始诊断最新崩溃")
        try:
            self.crash_btn.config(state=tk.NORMAL, text=text)
        except tk.TclError:
            pass

    def _selected_or_latest(self):
        if self.selected_log_path and os.path.isfile(self.selected_log_path):
            return self.selected_log_path
        war3_dir = self.app.war3_path.get().strip('"')
        errors_dir = os.path.join(war3_dir, "Errors") if war3_dir else ""
        if not errors_dir or not os.path.isdir(errors_dir):
            return None
        candidates = []
        for name in os.listdir(errors_dir):
            if not name.lower().endswith(".txt"):
                continue
            path = os.path.join(errors_dir, name)
            try:
                candidates.append((os.path.getmtime(path), path))
            except OSError:
                continue
        if not candidates:
            return None
        return max(candidates)[1]

    def _fit_top_pane(self):
        self.update_idletasks()
        try:
            self.pane.sashpos(0, self.top_container.winfo_reqheight())
        except tk.TclError:
            pass

    def browse_war3(self):
        path = filedialog.askdirectory(title="选择魔兽争霸 III 安装根目录 (包含 war3.exe)")
        if path:
            war3_path = path.replace('/', '\\')
            # 检测目录下是否存在核心程序
            has_exe = any(os.path.exists(os.path.join(war3_path, exe)) for exe in ["war3.exe", "Warcraft III.exe", "War3.exe"])

            if not has_exe:
                if not tk.messagebox.askyesno("目录警告", "选中的目录下未找到 war3.exe 或 Warcraft III.exe，这可能导致分析功能失效。\n\n是否仍要选择该目录？"):
                    return

            self.selected_log_path = None
            self.app.war3_path.set(war3_path)
            self.app.save_config()
            self._refresh_log_options()
            self._restore_crash_btn()
            self.update_status(f"魔兽目录已设置为: {os.path.basename(war3_path)}")

    def analyze_last_crash(self):
        target = self._selected_or_latest()
        if not target:
            tk.messagebox.showinfo(
                "未找到崩溃日志",
                "没有找到可诊断的日志。请先确认魔兽目录，或点击“浏览…”手动选择日志文件。")
            return

        self.update_status("正在诊断...")
        self.crash_btn.config(state=tk.DISABLED, text="正在诊断，请稍候...")

        def run():
            try:
                res = self.auditor.analyze_selected_log(target)
            except Exception as e:
                res = f"[-] 分析过程出错: {e}"
            self.app.root.after(0, lambda: self._finish_diagnosis(res, target))

        threading.Thread(target=run, daemon=True).start()

    def _finish_diagnosis(self, res, target):
        self._restore_crash_btn()
        self.update_status("崩溃日志分析完毕")
        self.log(res)
        self._refresh_log_options()
        if res.startswith("[+]"):
            self.diagnosed_log_path = target
            self.step3_frame.pack(fill=tk.X, pady=(12, 0))
            self._fit_top_pane()

    def upload_diagnosed_log(self):
        if not self.diagnosed_log_path:
            return
        self.app.open_upload_dialog(self.diagnosed_log_path)
