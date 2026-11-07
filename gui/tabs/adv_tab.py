"""高级与设置：实时监控、插件上报与帮助。"""

import tkinter as tk
import tkinter.scrolledtext
from tkinter import messagebox, ttk

from core.plugin_manager import PluginManager
from gui.tabs.base import BaseTab
from gui.tabs.local_tab import LocalTab


class AdvTab(BaseTab):
    def setup_ui(self):
        self.plugin_manager = PluginManager(self.log, self.update_status)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.local_tab = LocalTab(notebook, self.app)
        notebook.add(self.local_tab, text=" 实时监控（高危） ")

        tools_page = tk.Frame(notebook, bg="#f5f6f7")
        notebook.add(tools_page, text=" 插件与上报 ")
        self._build_tools(tools_page)

        help_page = tk.Frame(notebook, bg="#f5f6f7")
        notebook.add(help_page, text=" 帮助与关于 ")
        self._build_help(help_page)

    # ---------------------------------------------------------------- 插件与上报
    def _build_tools(self, parent):
        main_frame = tk.Frame(parent, bg="#f5f6f7", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        warning_frame = tk.Frame(
            main_frame, bg="#fff3cd", pady=5, padx=10,
            highlightbackground="#ffeeba", highlightthickness=1)
        warning_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            warning_frame,
            text="警告：JassDebug 插件会挂接游戏进程，严禁在对战平台联网环境使用，以免触发封号风险。",
            bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold")).pack()

        jd_card = tk.LabelFrame(
            main_frame, text=" JassDebug 崩溃追踪插件 ", bg="#ffffff",
            padx=15, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        jd_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            jd_card,
            text="集成 ASI 插件，在崩溃发生时弹出 JASS 语句、函数链与代码偏移；"
                 "本工具只读读取并解析该弹窗。",
            bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d",
            justify=tk.LEFT).pack(side=tk.LEFT, padx=(0, 20))

        jd_btn_box = tk.Frame(jd_card, bg="#ffffff")
        jd_btn_box.pack(side=tk.RIGHT)
        tk.Button(
            jd_btn_box, text="解析弹窗", command=self.open_jassdebug_dialog,
            bg="#2980b9", fg="white", font=("微软雅黑", 9, "bold"),
            width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(
            jd_btn_box, text="安装插件", command=self.install_jassdebug,
            bg="#27ae60", fg="white", font=("微软雅黑", 9, "bold"),
            width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(
            jd_btn_box, text="卸载", command=self.uninstall_jassdebug,
            bg="#95a5a6", fg="white", font=("微软雅黑", 9),
            width=8).pack(side=tk.LEFT, padx=5)

        settings_frame = tk.LabelFrame(
            main_frame, text=" 系统与云端配置 ", bg="#ffffff", pady=10, padx=15,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        settings_frame.pack(fill=tk.X, pady=(0, 8))

        set_box = tk.Frame(settings_frame, bg="#ffffff")
        set_box.pack(fill=tk.X, pady=5)

        tk.Label(set_box, text="自动上报间隔 (分钟):", bg="#ffffff",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.app.report_interval))
        tk.Spinbox(
            set_box, from_=5, to=1440, textvariable=self.interval_var, width=6,
            font=("Consolas", 10)).pack(side=tk.LEFT, padx=10)
        tk.Button(
            set_box, text="应用更改", command=self.update_report_interval,
            bg="#3498db", fg="white", font=("微软雅黑", 8)).pack(side=tk.LEFT)

        switch_box = tk.Frame(settings_frame, bg="#ffffff")
        switch_box.pack(fill=tk.X, pady=5)

        self.boot_var = tk.BooleanVar(value=self.app.boot_start)
        tk.Checkbutton(
            switch_box, text="Windows 开机自启动", variable=self.boot_var,
            command=self.on_boot_toggle, bg="#ffffff",
            font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))

        self.tray_var = tk.BooleanVar(value=self.app.min_to_tray)
        tk.Checkbutton(
            switch_box, text="关闭时最小化到托盘", variable=self.tray_var,
            command=self.on_tray_toggle, bg="#ffffff",
            font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))

        self.report_var = tk.BooleanVar(value=self.app.allow_report)
        tk.Checkbutton(
            switch_box, text="开启自动上报 (支持我们)", variable=self.report_var,
            command=self.on_report_toggle, bg="#ffffff",
            font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))

        self.collect_var = tk.BooleanVar(value=self.app.auto_collect)
        tk.Checkbutton(
            switch_box, text="自动收集新崩溃", variable=self.collect_var,
            command=self.on_collect_toggle, bg="#ffffff",
            font=("微软雅黑", 9)).pack(side=tk.LEFT)

        manual_card = tk.LabelFrame(
            main_frame, text=" 开发者上报通道 ", bg="#ffffff", pady=8, padx=15,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        manual_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            manual_card,
            text="旧版批量通道：把 Errors 目录里尚未上报的日志和诊断结果发送给开发者。"
                 "只提交日志文本与诊断数据，不上传地图文件或 dmp 原始文件。",
            bg="#ffffff", font=("微软雅黑", 8), fg="#7f8c8d",
            justify=tk.LEFT, anchor=tk.W).pack(fill=tk.X)

        self.report_btn = tk.Button(
            manual_card, text="立即上报历史崩溃（帮助开发者）",
            command=self.app.report_crash_to_server,
            bg="#95a5a6", fg="white", font=("微软雅黑", 9, "bold"))
        self.report_btn.pack(anchor=tk.W, pady=(6, 0))

        log_frame = tk.LabelFrame(main_frame, text=" 工具执行日志 ", bg="#ffffff",
                                  padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.adv_log_area = tkinter.scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.adv_log_area.pack(fill=tk.BOTH, expand=True)

        self.plugin_manager.log = self.adv_log

    # ------------------------------------------------------------------ 帮助与关于
    def _build_help(self, parent):
        main_frame = tk.Frame(parent, bg="#f5f6f7", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        guide_card = tk.LabelFrame(
            main_frame, text=" 使用帮助 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        guide_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            guide_card,
            text="崩溃后怎么排查、各页面分别做什么、日志会上传哪些内容，都在这里。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8),
            anchor=tk.W).pack(fill=tk.X)

        guide_row = tk.Frame(guide_card, bg="#ffffff")
        guide_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            guide_row, text="查看崩溃恢复引导", command=self.show_recovery_guide,
            bg="#16a085", fg="white", font=("微软雅黑", 9, "bold"),
            width=16).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            guide_row, text="查看功能与上报指南", command=self.show_manual_guide,
            bg="#f5f6f7", fg="#2c3e50", font=("微软雅黑", 9),
            width=16).pack(side=tk.LEFT)

        scope_card = tk.LabelFrame(
            main_frame, text=" 功能边界与隐私 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        scope_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            scope_card,
            text="• 实时监控与 JassDebug 只用于本地客户端测试，严禁在对战平台联网环境使用。\n"
                 "• 地图体检的修复只写入 *_leakfixed 副本，不会覆盖原图。\n"
                 "• 自动上报会上传崩溃日志文本、系统版本、地图名与诊断结果；"
                 "日志中可能出现 Windows 用户名、计算机名和本地路径，可随时在「插件与上报」关闭。\n"
                 "• 上传日志返回的 6 位上传码用于和地图作者沟通，不会公开原始日志。",
            bg="#ffffff", fg="#566573", font=("微软雅黑", 8),
            justify=tk.LEFT, anchor=tk.W, wraplength=900).pack(fill=tk.X)

        about_card = tk.LabelFrame(
            main_frame, text=" 关于 ", bg="#ffffff", padx=12, pady=10,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        about_card.pack(fill=tk.X)
        tk.Label(
            about_card,
            text="魔兽 RPG 崩溃分析工具 v1.1.0 · By DarkSheep (肥羊小站)",
            bg="#ffffff", fg="#2c3e50", font=("微软雅黑", 9)).pack(anchor=tk.W)
        tk.Label(
            about_card,
            text="面向中文魔兽 RPG 玩家与地图作者：崩溃诊断、地图体检与诊断资料整理。",
            bg="#ffffff", fg="#7f8c8d", font=("微软雅黑", 8)).pack(
                anchor=tk.W, pady=(4, 0))

    def adv_log(self, message):
        self.adv_log_area.insert(tk.END, message + "\n")
        self.adv_log_area.see(tk.END)
        self.update_status(message)

    def show_recovery_guide(self):
        self.adv_log("[*] 正在检索崩溃恢复方案库...")
        self.update_status("正在加载恢复引导...")
        
        guide_win = tk.Toplevel(self.app.root)
        guide_win.title("魔兽崩溃恢复引导")
        guide_win.geometry("600x500")
        guide_win.configure(bg="#ffffff")
        
        content = tk.Text(guide_win, font=("微软雅黑", 10), padx=20, pady=20, wrap=tk.WORD, relief=tk.FLAT)
        content.pack(fill=tk.BOTH, expand=True)
        
        text = """魔兽崩溃恢复与预防引导

当地图频繁发生崩溃时，请尝试以下排查步骤：

1. 先拿到可信的崩溃线索：
   - 软件会自动监控魔兽崩溃日志与 .dmp 文件，解析崩溃地址并判断责任归属。
   - 也可以在“崩溃诊断”页面按步骤操作：确认目录、选择并诊断日志、上传日志。

2. 处理内存泄露导致的崩溃：
   - 在“地图体检 → 泄露检查”页面执行扫描，查看未销毁的点、单位组、矩形区域。
   - 降低地图内的特效密度，检查是否有每秒多次的大规模单位组枚举。

3. 针对退出地图时的崩溃：
   - 这类崩溃多由定时器、触发器或回调在退出后仍然执行引起。
   - 建议用泄露检查功能查看未清理的句柄，本工具不提供自动补丁。

4. 定位到具体脚本行号：
   - 安装 JassDebug 插件后，本地客户端崩溃时会弹出标题为“调试输出”的窗口。
   - 保持弹窗打开，回到“高级与设置 → 插件与上报”点击“解析弹窗”，
     即可读出 JASS 语句、所属函数、上级函数链与代码偏移。

5. 环境与版本：
   - 不同游戏版本（1.24e / 1.27a / 1.28.5 等）的偏移不同，请确认日志中的版本与地图要求一致。
   - 对战平台或第三方插件会改变调用栈，诊断结果中会标注可疑模块。

如果问题依然存在，请通过“崩溃记录”导出诊断包或上传日志，把上传码发给地图作者。"""
        content.insert(tk.END, text)
        content.config(state=tk.DISABLED)
        self.update_status("崩溃恢复引导已加载")

    def open_jassdebug_dialog(self):
        self.adv_log("[*] 正在打开 JassDebug 弹窗解析...")
        from gui.jassdebug_dialog import JassDebugDialog
        JassDebugDialog(self.app.root)

    def install_jassdebug(self):
        self.adv_log("[*] 正在安装 JassDebug 插件...")
        self.plugin_manager.install_jassdebug(self.app.war3_path.get(), self.app.base_dir)

    def uninstall_jassdebug(self):
        self.adv_log("[*] 正在卸载 JassDebug 插件...")
        self.plugin_manager.uninstall_jassdebug(self.app.war3_path.get())

    def update_report_interval(self):
        try:
            val = int(self.interval_var.get())
            if 5 <= val <= 1440:
                self.app.report_interval = val
                self.app.save_config()
                self.update_status(f"上报间隔已更新为 {val} 分钟")
                self.adv_log(f"[*] 上报间隔已更新为 {val} 分钟")
            else: raise ValueError
        except: messagebox.showerror("错误", "请输入 5 到 1440 之间的整数。")

    def on_boot_toggle(self):
        self.app.boot_start = self.boot_var.get()
        self.app.save_config()
        status = "已开启" if self.app.boot_start else "已关闭"
        self.update_status(f"开机自启动{status}")
        self.adv_log(f"[*] 开机自启动{status}")

    def on_tray_toggle(self):
        self.app.min_to_tray = self.tray_var.get()
        self.app.save_config()
        status = "已开启" if self.app.min_to_tray else "已关闭"
        self.update_status(f"最小化到托盘{status}")
        self.adv_log(f"[*] 最小化到托盘{status}")

    def on_report_toggle(self):
        self.app.allow_report = self.report_var.get()
        self.app.save_config()
        if self.app.allow_report:
            self.adv_log("[+] 自动上报功能已开启，感谢您的支持！")
            self.update_status("自动上报功能已开启")
        else:
            self.adv_log("[-] 自动上报功能已禁用。")
            self.update_status("自动上报功能已禁用")

    def on_collect_toggle(self):
        self.app.auto_collect = self.collect_var.get()
        self.app.save_config()
        status = "已开启" if self.app.auto_collect else "已关闭"
        self.update_status(f"自动收集新崩溃{status}")
        self.adv_log(f"[*] 自动收集新崩溃{status}")

    def show_manual_guide(self):
        guide_win = tk.Toplevel(self.app.root)
        guide_win.title("软件功能与上报指南")
        guide_win.geometry("600x500")
        guide_win.configure(bg="#ffffff")
        
        content = tk.Text(guide_win, font=("微软雅黑", 10), padx=20, pady=20, wrap=tk.WORD, relief=tk.FLAT)
        content.pack(fill=tk.BOTH, expand=True)
        
        text = """软件功能使用与上报指南

欢迎使用魔兽 RPG 崩溃分析工具，可以按以下顺序使用：

1. 崩溃诊断：
   - 第 1 步：确认魔兽安装目录（包含 war3.exe 的文件夹）。
   - 第 2 步：默认诊断 Errors 里最新的一份日志；也可以切换或浏览其他日志。
   - 第 3 步：诊断完成后可直接上传日志，获得 6 位上传码。

2. 崩溃记录：
   - 打开崩溃历史，查看每次崩溃的地图、归属结论与上报状态。
   - 导出诊断包：把最新崩溃日志、dmp、诊断 JSON 与摘要打包，直接交给地图作者。
   - 批量诊断会回溯处理 Errors 里全部未处理日志。

3. 地图体检：
   - 泄露检查：选择地图后开始扫描，查看未销毁的点、组和泄漏证据；
     修复只写入带 *_leakfixed 后缀的副本，原图保持不变。
   - 脚本与资源：解包地图、审计资源与 JASS 脚本，或按崩溃地址定位脚本位置。

4. 高级与设置：
   - 实时监控（高危）：先启动魔兽进入地图，再开启监控；
     “引擎对象”可实时观察单位、点、组的数量。仅限本地客户端测试。
   - 插件与上报：安装 JassDebug 插件、配置自动上报、开机自启与托盘；
     也可以在这里手动触发开发者上报通道。
   - 帮助与关于：崩溃恢复引导、功能说明与隐私边界。

5. 如何上报崩溃：
   - 方式一（推荐）：在“插件与上报”开启“自动上报”，软件会随崩溃日志一起
     提交诊断结果。
   - 上报内容包含崩溃日志原文（其中可能出现 Windows 用户名、计算机名和本地
     文件路径）、地图名与崩溃地址分析结果。可在同一页随时关闭自动上报。
   - 方式二：在“崩溃诊断”页完成诊断后上传日志，或在“崩溃记录”页上传已有日志。

感谢您为魔兽生态稳定性做出的贡献！"""
        content.insert(tk.END, text)
        content.config(state=tk.DISABLED)
        self.update_status("正在查看功能使用指南")
