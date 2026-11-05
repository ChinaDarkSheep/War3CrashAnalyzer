import tkinter as tk
import tkinter.scrolledtext
from tkinter import messagebox
from gui.tabs.base import BaseTab
from core.plugin_manager import PluginManager

class AdvTab(BaseTab):
    def setup_ui(self):
        self.plugin_manager = PluginManager(self.log, self.update_status)
        main_frame = tk.Frame(self, bg="#f5f6f7", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 警告区域
        warning_frame = tk.Frame(main_frame, bg="#fff3cd", pady=5, padx=10, highlightbackground="#ffeeba", highlightthickness=1)
        warning_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(warning_frame, text="⚠️ 警告：JassDebug 插件会挂接游戏进程，严禁在对战平台联网环境使用，以免触发封号风险。", 
                 bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold")).pack()

        # 使用网格布局的容器
        container = tk.Frame(main_frame, bg="#f5f6f7")
        container.pack(fill=tk.BOTH, expand=True)

        def create_tool_card(parent, title, desc, btn_text, cmd, color, row, col, colspan=1):
            card = tk.LabelFrame(parent, text=f" {title} ", bg="#ffffff", padx=15, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
            card.grid(row=row, column=col, columnspan=colspan, sticky=tk.NSEW, padx=5, pady=5)
            
            tk.Label(card, text=desc, bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d", wraplength=250, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 10))
            
            btn_box = tk.Frame(card, bg="#ffffff")
            btn_box.pack(side=tk.BOTTOM, fill=tk.X)
            
            tk.Button(btn_box, text=btn_text, command=cmd, bg=color, fg="white", font=("微软雅黑", 9, "bold"), height=1).pack(side=tk.RIGHT, padx=2, fill=tk.X, expand=True)
            return card

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        # 第一排：崩溃排查引导
        create_tool_card(container, "💉 崩溃恢复引导", "针对内存溢出、退出崩溃等常见类型的排查思路与预防建议。", 
                         "查看引导", self.show_recovery_guide, "#16a085", 0, 0, colspan=2)

        # 第二排：插件管理
        jd_card = tk.LabelFrame(container, text=" 🐛 JassDebug 崩溃追踪插件 ", bg="#ffffff", padx=15, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        jd_card.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        
        tk.Label(jd_card, text="集成 ASI 插件，在崩溃发生时能够精准弹出具体的 JASS 报错行号，是地图开发者的必备调试工具。", 
                 bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d").pack(side=tk.LEFT, padx=(0, 20))
        
        jd_btn_box = tk.Frame(jd_card, bg="#ffffff")
        jd_btn_box.pack(side=tk.RIGHT)
        tk.Button(jd_btn_box, text="安装插件", command=self.install_jassdebug, bg="#27ae60", fg="white", font=("微软雅黑", 9, "bold"), width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(jd_btn_box, text="卸载", command=self.uninstall_jassdebug, bg="#95a5a6", fg="white", font=("微软雅黑", 9), width=8).pack(side=tk.LEFT, padx=5)

        # 第三排：系统设置
        settings_frame = tk.LabelFrame(container, text=" ⚙️ 系统与云端配置 ", bg="#ffffff", pady=10, padx=15, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        
        set_box = tk.Frame(settings_frame, bg="#ffffff")
        set_box.pack(fill=tk.X, pady=5)
        
        tk.Label(set_box, text="自动上报间隔 (分钟):", bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.app.report_interval))
        tk.Spinbox(set_box, from_=5, to=1440, textvariable=self.interval_var, width=6, font=("Consolas", 10)).pack(side=tk.LEFT, padx=10)
        tk.Button(set_box, text="应用更改", command=self.update_report_interval, bg="#3498db", fg="white", font=("微软雅黑", 8)).pack(side=tk.LEFT)
        
        switch_box = tk.Frame(settings_frame, bg="#ffffff")
        switch_box.pack(fill=tk.X, pady=5)
        
        self.boot_var = tk.BooleanVar(value=self.app.boot_start)
        tk.Checkbutton(switch_box, text="Windows 开机自启动", variable=self.boot_var, command=self.on_boot_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))
        
        self.tray_var = tk.BooleanVar(value=self.app.min_to_tray)
        tk.Checkbutton(switch_box, text="关闭时最小化到托盘", variable=self.tray_var, command=self.on_tray_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))

        self.report_var = tk.BooleanVar(value=self.app.allow_report)
        tk.Checkbutton(switch_box, text="开启自动上报 (支持我们)", variable=self.report_var, command=self.on_report_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))

        self.collect_var = tk.BooleanVar(value=self.app.auto_collect)
        tk.Checkbutton(switch_box, text="自动收集新崩溃", variable=self.collect_var, command=self.on_collect_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        
        tk.Button(settings_frame, text="📖 查看手动上报指南", command=self.show_manual_guide, bg="#f5f6f7", fg="#2c3e50", font=("微软雅黑", 9)).pack(side=tk.RIGHT, pady=5)

        # 独立日志窗口
        log_frame = tk.LabelFrame(main_frame, text=" 工具执行日志 ", bg="#ffffff", padx=10, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.adv_log_area = tk.scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.adv_log_area.pack(fill=tk.BOTH, expand=True)

        # 重新绑定 plugin_manager 的日志输出
        self.plugin_manager.log = self.adv_log

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
        
        text = """🛠️ 魔兽崩溃恢复与预防引导

当地图频繁发生崩溃时，请尝试以下排查步骤：

1. 先拿到可信的崩溃线索：
   - 软件会自动监控魔兽崩溃日志与 .dmp 文件，解析崩溃地址并判断责任归属。
   - 也可以在“静态审计”页面手动选择日志文件进行诊断。

2. 处理内存泄露导致的崩溃：
   - 在“泄露定位&修复”页面执行定位，查看未销毁的点、单位组、矩形区域。
   - 降低地图内的特效密度，检查是否有每秒多次的大规模单位组枚举。

3. 针对退出地图时的崩溃：
   - 这类崩溃多由定时器、触发器或回调在退出后仍然执行引起。
   - 建议用泄露定位功能检查未清理的句柄，本工具不提供自动补丁。

4. 定位到具体脚本行号：
   - 安装 JassDebug 插件后，脚本报错时游戏会直接提示出错的函数与行号。

5. 环境与版本：
   - 不同游戏版本（1.24e / 1.27a / 1.28.5 等）的偏移不同，请确认日志中的版本与地图要求一致。
   - 对战平台或第三方插件会改变调用栈，诊断结果中会标注可疑模块。

如果问题依然存在，请将诊断报告通过“上报崩溃”提交给地图作者。"""
        content.insert(tk.END, text)
        content.config(state=tk.DISABLED)
        self.update_status("崩溃恢复引导已加载")

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
        
        text = """📖 软件功能使用与上报指南

欢迎使用魔兽崩溃分析工具，您可以按照以下指引进行操作：

1. 静态审计 (审计/提取) 页面：
   - 第一步：点击“浏览”选择您的魔兽目录和地图文件。
   - 第二步：点击“资源审计”检查模型和贴图，或点击“JASS 审计”检查脚本逻辑。
   - 第三步：如果发生崩溃，点击“诊断日志”自动匹配已知崩溃原因。

2. 本地调试 (实测模式) 页面：
   - 操作：先启动魔兽进入地图，回到本软件点击“开启实时监控”。
   - 查看：“引擎对象”标签页可实时观察单位、点、组的数量，辅助排查泄露。

3. 泄露定位&修复 页面：
   - 操作：选择地图后点击“执行泄露定位&修复”，软件将自动生成一个带有 '_leakfixed' 后缀的修复版地图。

4. 高级工具页面：
   - JassDebug：点击“安装插件”后，游戏崩溃时会直接弹出报错的脚本行号。

5. 如何上报崩溃：
   - 方式一（推荐）：在高级工具页开启“自动上报”，软件会随崩溃日志一起提交诊断结果。
   - 上报内容包含崩溃日志原文（其中可能出现 Windows 用户名、计算机名和本地文件路径）、
     地图名与崩溃地址分析结果。可在高级工具页随时关闭自动上报。
   - 方式二：在“静态审计”页面点击“上报崩溃”按钮进行手动提交。

感谢您为魔兽生态稳定性做出的贡献！"""
        content.insert(tk.END, text)
        content.config(state=tk.DISABLED)
        self.update_status("正在查看功能使用指南")
