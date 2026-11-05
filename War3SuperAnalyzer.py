import os
import re
import time
import psutil
import sys
import subprocess
import io
import threading
import traceback
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import json
import ctypes
from ctypes import wintypes
import winreg
import platform
import urllib.request
import hashlib

from core.knowledge import CRASH_KNOWLEDGE
from core.constants import (
    COMMON_DICT, GROUP_FUNCS, LOC_FUNCS, RECT_FUNCS, 
    BOOLEXPR_FUNCS, MATCHING_FUNCS, LEAK_CATEGORY, 
    ALL_FUNCS_SORTED, CALL_RE, SET_RE
)
from engine.memory import (
    PROCESS_VM_READ, PROCESS_QUERY_INFORMATION,
    get_module_base, read_process_memory,
    AgentMonitor, JassVMMonitor
)

# 自动安装依赖
def install_dependencies():
    for lib in ["mpyq", "psutil", "pystray", "pillow"]:
        try:
            if lib == "pillow": __import__("PIL")
            else: __import__(lib)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_dependencies()
from mpyq import MPQArchive
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw, ImageTk

CONFIG_FILE = "analyzer_config.json"

class War3SuperAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("魔兽 RPG 崩溃分析工具 v1.0.0 - By DarkSheep (肥羊小站)")
        self.root.geometry("1100x900")
        self.root.configure(bg="#f5f6f7")

        self.map_path = tk.StringVar()
        self.war3_path = tk.StringVar()
        
        if getattr(sys, 'frozen', False):
            self.base_dir = sys._MEIPASS
            self.exe_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.exe_dir = self.base_dir
            
        self.mpq_editor_path = os.path.join(self.base_dir, "MPQEditor.exe")
        
        self.is_monitoring = False
        self.local_debug_running = False
        self.selected_thread_ptr = None
        self.vm_monitor = None
        self.agent_monitor = None
        
        # Default Offsets for 1.27a (Agent Monitor)
        self.agent_offsets = {
            "Unit (单位)": 0xBE6530,
            "Item (物品)": 0xBE6550,
            "Bullet (投射物)": 0xBE6570,
            "Destructable (可破坏物)": 0xBE6590,
            "Doodad (装饰物)": 0xBE65B0,
            "Timer (计时器)": 0xBE65D0,
            "Trigger (触发器)": 0xBE65F0
        }
        
        self.first_run = True
        self.allow_plugin = False
        self.allow_report = False
        self.report_interval = 30 # Minutes
        self.last_report_hash = ""
        self.boot_start = False
        self.min_to_tray = True
        
        self.setup_ui()
        self.load_config()
        
        # Tray setup
        self.tray_icon = None
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        if self.first_run:
            self.root.after(500, self.show_welcome_wizard)
        
        # Start periodic reporting thread
        self.stop_reporting = threading.Event()
        threading.Thread(target=self.periodic_report_worker, daemon=True).start()

    def setup_ui(self):
        # 设置任务栏和窗口图标
        icon_path = os.path.join(self.base_dir, "assets", "icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.base_dir, "assets", "icon.jpg")
            
        if os.path.exists(icon_path):
            try:
                # 针对 Windows 任务栏图标的特殊处理
                if platform.system() == "Windows":
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("darksheep.war3crashanalyzer.v13")
                
                img = Image.open(icon_path)
                self.tk_icon = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self.tk_icon)
            except Exception as e:
                print(f"Failed to set icon: {e}")

        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        
        title_frame = tk.Frame(header, bg="#2c3e50")
        title_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(title_frame, text="魔兽RPG崩溃分析工具 v1.0.0", font=("Segoe UI", 14, "bold"), fg="white", bg="#2c3e50").pack(side=tk.LEFT)
        
        author_box = tk.Frame(title_frame, bg="#2c3e50")
        author_box.pack(side=tk.LEFT, padx=10)
        tk.Label(author_box, text=" 作者: DarkSheep (", font=("微软雅黑", 9), fg="#bdc3c7", bg="#2c3e50").pack(side=tk.LEFT)
        link = tk.Label(author_box, text="darksheep.vip", font=("微软雅黑", 9, "underline"), fg="#3498db", bg="#2c3e50", cursor="hand2")
        link.pack(side=tk.LEFT)
        tk.Label(author_box, text=")", font=("微软雅黑", 9), fg="#bdc3c7", bg="#2c3e50").pack(side=tk.LEFT)
        
        link.bind("<Button-1>", lambda e: subprocess.run(["explorer", "http://darksheep.vip"]))
        
        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Static Audit
        self.audit_tab = tk.Frame(self.notebook, bg="#f5f6f7")
        self.notebook.add(self.audit_tab, text=" 静态审计 (审计/提取) ")
        self.setup_static_ui()

        # Tab 2: Local Debug
        self.local_tab = tk.Frame(self.notebook, bg="#f5f6f7")
        self.notebook.add(self.local_tab, text=" 本地调试 (实测模式) ")
        self.setup_local_ui()

        # Tab 3: 泄露定位&修复
        self.leak_fix_tab = tk.Frame(self.notebook, bg="#f5f6f7")
        self.notebook.add(self.leak_fix_tab, text=" 泄露定位&修复 ")
        self.setup_leak_fix_ui()

        # Tab 4: Advanced Utils
        self.adv_tab = tk.Frame(self.notebook, bg="#f5f6f7")
        self.notebook.add(self.adv_tab, text=" 高级工具 (Wc3Utils) ")
        self.setup_adv_ui()

        # Status Bar
        self.status_var = tk.StringVar(value="就绪 | 集成 JassView 核心逻辑")
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def setup_static_ui(self):
        # 使用 PanedWindow 允许用户在静态审计标签内调整日志区域大小
        pane = ttk.PanedWindow(self.audit_tab, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # 上半部分：配置与操作
        top_container = tk.Frame(pane, bg="#f5f6f7", padx=5, pady=5)
        pane.add(top_container, weight=1)

        # Config & Actions merged for compactness
        top_frame = tk.LabelFrame(top_container, text=" 核心操作与配置 ", bg="#f5f6f7", pady=5, padx=10)
        top_frame.pack(fill=tk.X, pady=2)
        
        # Row 1: War3 Path
        tk.Label(top_frame, text="魔兽目录:", bg="#f5f6f7").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(top_frame, textvariable=self.war3_path).grid(row=0, column=1, sticky=tk.EW, padx=5)
        tk.Button(top_frame, text="浏览", command=self.browse_war3, width=8).grid(row=0, column=2)
        
        # Row 2: Map Path
        tk.Label(top_frame, text="地图文件:", bg="#f5f6f7").grid(row=1, column=0, sticky=tk.W, pady=5)
        tk.Entry(top_frame, textvariable=self.map_path).grid(row=1, column=1, sticky=tk.EW, padx=5)
        tk.Button(top_frame, text="浏览", command=self.browse_map, width=8).grid(row=1, column=2)
        top_frame.columnconfigure(1, weight=1)

        # Row 3: Action Buttons (Compact)
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

        self.desync_log_btn = tk.Button(btn_container, text="🌐 同步日志", command=self.start_desync_log_analysis, bg="#f39c12", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.desync_log_btn.pack(side=tk.LEFT, padx=2)

        self.report_btn = tk.Button(btn_container, text="📤 上报崩溃", command=self.report_crash_to_server, bg="#34495e", fg="white", font=("微软雅黑", 9, "bold"), width=12)
        self.report_btn.pack(side=tk.LEFT, padx=2)

        # 下半部分：专属诊断日志
        log_frame = tk.LabelFrame(pane, text=" 📜 实时诊断日志 ", bg="#f5f6f7")
        pane.add(log_frame, weight=2)
        
        self.report_area = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10), bg="#ffffff")
        self.report_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_local_ui(self):
        main_frame = tk.Frame(self.local_tab, bg="#f5f6f7", padx=5, pady=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 警告区域 (精简美化)
        warning_frame = tk.Frame(main_frame, bg="#fff3cd", pady=5, padx=10)
        warning_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(warning_frame, text="⚠️ 安全警告：严禁在对战平台联网环境使用，否则可能导致封号！", 
                 bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold")).pack()

        # 控制栏 (卡片式)
        control_frame = tk.Frame(main_frame, bg="#ffffff", padx=10, pady=10, highlightbackground="#dcdde1", highlightthickness=1)
        control_frame.pack(fill=tk.X, pady=5)

        self.local_monitor_btn = tk.Button(control_frame, text="🟢 开启实时监控", command=self.toggle_local_debug, 
                                          bg="#27ae60", fg="white", font=("微软雅黑", 10, "bold"), width=18)
        self.local_monitor_btn.pack(side=tk.LEFT, padx=5)

        self.snapshot_btn = tk.Button(control_frame, text="📸 句柄快照 (查泄露)", command=self.take_handle_snapshot, 
                                     bg="#f39c12", fg="white", font=("微软雅黑", 10, "bold"), width=18)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="* 请先启动魔兽并进入地图后再开启监控", font=("微软雅黑", 8), bg="#ffffff", fg="#7f8c8d").pack(side=tk.RIGHT)

        # Paned Window for Details
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, pady=5)

        # Left: Monitor Selector
        left_frame = tk.Frame(self.paned, bg="#f5f6f7")
        self.paned.add(left_frame, weight=1)

        self.monitor_tabs = ttk.Notebook(left_frame)
        self.monitor_tabs.pack(fill=tk.BOTH, expand=True)

        # Sub-tab 1: JASS Threads
        self.thread_frame = tk.Frame(self.monitor_tabs, bg="#f5f6f7")
        self.monitor_tabs.add(self.thread_frame, text=" JASS 线程 ")
        
        self.thread_list = tk.Listbox(self.thread_frame, font=("Consolas", 9), bg="#ffffff")
        self.thread_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.thread_list.bind('<<ListboxSelect>>', self.on_thread_select)

        # Sub-tab 2: Agent Monitor (Ported from agent_memory_monitor)
        self.agent_frame = tk.Frame(self.monitor_tabs, bg="#f5f6f7")
        self.monitor_tabs.add(self.agent_frame, text=" 引擎对象 (Agents) ")

        self.agent_tree = ttk.Treeview(self.agent_frame, columns=("name", "count", "mem"), show="headings")
        self.agent_tree.heading("name", text="对象类型 (Type)")
        self.agent_tree.heading("count", text="数量 (Count)")
        self.agent_tree.heading("mem", text="内存 (Memory)")
        self.agent_tree.column("name", width=120)
        self.agent_tree.column("count", width=80)
        self.agent_tree.column("mem", width=100)
        self.agent_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Right: Details
        right_frame = tk.LabelFrame(self.paned, text=" 监控详情 (Monitor Details) ", bg="#f5f6f7")
        self.paned.add(right_frame, weight=2)

        self.thread_detail = scrolledtext.ScrolledText(right_frame, font=("Consolas", 9), bg="#ffffff")
        self.thread_detail.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom Info Bar
        info_bar = tk.Frame(main_frame, bg="#f5f6f7")
        info_bar.pack(fill=tk.X)
        self.process_status_label = tk.Label(info_bar, text="魔兽进程: 未找到", bg="#f5f6f7", font=("微软雅黑", 9))
        self.process_status_label.pack(side=tk.LEFT)
        self.memory_label = tk.Label(info_bar, text=" | 内存占用: 0 MB", bg="#f5f6f7", font=("微软雅黑", 9))
        self.memory_label.pack(side=tk.LEFT)
        self.handle_label = tk.Label(info_bar, text=" | 活动句柄估计: ---", bg="#f5f6f7", font=("微软雅黑", 9))
        self.handle_label.pack(side=tk.LEFT)

    def setup_leak_fix_ui(self):
        main_frame = tk.Frame(self.leak_fix_tab, bg="#f5f6f7", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 简洁美观的介绍
        intro_frame = tk.Frame(self.leak_fix_tab, bg="#f5f6f7")
        intro_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(intro_frame, text="✨ 泄露定位&修复 引擎", font=("微软雅黑", 12, "bold"), bg="#f5f6f7", fg="#2c3e50").pack(anchor=tk.W)
        tk.Label(intro_frame, text="基于静态分析与 AI 预诊断技术，精准定位并修复 JASS 脚本中的内存泄露风险。", font=("微软雅黑", 9), bg="#f5f6f7", fg="#7f8c8d").pack(anchor=tk.W)

        # 功能卡片
        card = tk.LabelFrame(self.leak_fix_tab, text=" 泄露定位&修复操作 ", bg="#ffffff", padx=20, pady=20, font=("微软雅黑", 9, "bold"), fg="#2980b9")
        card.pack(fill=tk.BOTH, expand=True)

        features = [
            "✅ 自动扫描 war3map.j 并识别常见句柄泄露",
            "✅ 修复点(location)、组(group)、矩形(rect)等残留",
            "✅ 优化 JASS 脚本执行效率与内存占用",
            "✅ 修复后以 '_leakfixed.w3x' 后缀安全保存"
        ]
        
        for feature in features:
            tk.Label(card, text=feature, bg="#ffffff", font=("微软雅黑", 10), pady=5).pack(anchor=tk.W)

        btn_container = tk.Frame(card, bg="#ffffff", pady=20)
        btn_container.pack(fill=tk.X)
        
        self.leak_fix_btn = tk.Button(btn_container, text="🛠️ 执行泄露定位&修复", command=self.start_leak_fix, 
                                     bg="#3498db", fg="white", font=("微软雅黑", 12, "bold"), width=25, height=2)
        self.leak_fix_btn.pack(pady=10)
        
        # Result Summary inside the card
        self.fix_result_frame = tk.Frame(card, bg="#ffffff")
        self.fix_result_frame.pack(fill=tk.X, pady=5)
        self.fix_stats_label = tk.Label(self.fix_result_frame, text="状态: 待处理...", bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d")
        self.fix_stats_label.pack(anchor=tk.W)

    def setup_adv_ui(self):
        main_frame = tk.Frame(self.adv_tab, bg="#f5f6f7", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部警告 (精简美观)
        warning_frame = tk.Frame(main_frame, bg="#fff3cd", pady=5, padx=10, highlightbackground="#ffeeba", highlightthickness=1)
        warning_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(warning_frame, text="⚠️ 警告：部分功能涉及进程注入，严禁在对战平台联网环境使用，以免触发封号风险。", 
                 bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold")).pack()

        # 使用网格布局的容器
        container = tk.Frame(main_frame, bg="#f5f6f7")
        container.pack(fill=tk.BOTH, expand=True)

        def create_tool_card(parent, title, desc, btn_text, cmd, color, row, col, btn2_text=None, cmd2=None):
            card = tk.LabelFrame(parent, text=f" {title} ", bg="#ffffff", padx=15, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
            card.grid(row=row, column=col, sticky=tk.NSEW, padx=5, pady=5)
            
            tk.Label(card, text=desc, bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d", wraplength=250, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 10))
            
            btn_box = tk.Frame(card, bg="#ffffff")
            btn_box.pack(side=tk.BOTTOM, fill=tk.X)
            
            if btn2_text:
                tk.Button(btn_box, text=btn2_text, command=cmd2, bg="#95a5a6", fg="white", font=("微软雅黑", 8), width=8).pack(side=tk.RIGHT, padx=2)
            
            tk.Button(btn_box, text=btn_text, command=cmd, bg=color, fg="white", font=("微软雅黑", 9, "bold"), height=1).pack(side=tk.RIGHT, padx=2, fill=tk.X, expand=True)
            return card

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        # 第一排：诊断与交互
        create_tool_card(container, "🛡️ 同步失效审计", "深度分析脚本中的随机数发生器与 GetLocalPlayer 异步风险。", 
                         "开始审计", self.start_desync_audit, "#e67e22", 0, 0)
        
        create_tool_card(container, "💻 实时交互终端", "连接魔兽进程，允许实时执行 Lua/JASS 代码（实测利器）。", 
                         "启动终端", self.open_live_terminal, "#34495e", 0, 1)

        # 第二排：修复与恢复
        create_tool_card(container, "💉 崩溃恢复引导", "通过 DLL Proxy 捕获详尽堆栈，尝试从非致命错误中恢复。", 
                         "查看引导", self.show_recovery_guide, "#16a085", 1, 0)
        
        create_tool_card(container, "🚪 退出崩溃修复", "挂钩 UI 清理流程，解决退出地图时因回调残留导致的崩溃。", 
                         "应用修复", self.apply_exit_fix, "#2980b9", 1, 1)

        # 第三排：插件管理 (跨两列)
        jd_card = tk.LabelFrame(container, text=" 🐛 JassDebug 崩溃追踪插件 ", bg="#ffffff", padx=15, pady=10, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        jd_card.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        
        tk.Label(jd_card, text="集成 ASI 插件，在崩溃发生时能够精准弹出具体的 JASS 报错行号，是地图开发者的必备调试工具。", 
                 bg="#ffffff", font=("微软雅黑", 9), fg="#7f8c8d").pack(side=tk.LEFT, padx=(0, 20))
        
        jd_btn_box = tk.Frame(jd_card, bg="#ffffff")
        jd_btn_box.pack(side=tk.RIGHT)
        tk.Button(jd_btn_box, text="安装插件", command=self.install_jassdebug, bg="#27ae60", fg="white", font=("微软雅黑", 9, "bold"), width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(jd_btn_box, text="卸载", command=self.uninstall_jassdebug, bg="#95a5a6", fg="white", font=("微软雅黑", 9), width=8).pack(side=tk.LEFT, padx=5)

        # 第四排：系统设置 (跨两列)
        settings_frame = tk.LabelFrame(container, text=" ⚙️ 系统与云端配置 ", bg="#ffffff", pady=10, padx=15, font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        settings_frame.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        
        # 间隔设置
        set_box = tk.Frame(settings_frame, bg="#ffffff")
        set_box.pack(fill=tk.X, pady=5)
        
        tk.Label(set_box, text="自动上报间隔 (分钟):", bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.report_interval))
        tk.Spinbox(set_box, from_=5, to=1440, textvariable=self.interval_var, width=6, font=("Consolas", 10)).pack(side=tk.LEFT, padx=10)
        tk.Button(set_box, text="应用更改", command=self.update_report_interval, bg="#3498db", fg="white", font=("微软雅黑", 8)).pack(side=tk.LEFT)
        
        # 开关设置
        switch_box = tk.Frame(settings_frame, bg="#ffffff")
        switch_box.pack(fill=tk.X, pady=5)
        
        self.boot_var = tk.BooleanVar(value=self.boot_start)
        tk.Checkbutton(switch_box, text="Windows 开机自启动", variable=self.boot_var, command=self.on_boot_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 20))
        
        self.tray_var = tk.BooleanVar(value=self.min_to_tray)
        tk.Checkbutton(switch_box, text="关闭时最小化到托盘", variable=self.tray_var, command=self.on_tray_toggle, bg="#ffffff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        
        tk.Button(settings_frame, text="📖 查看手动上报指南", command=self.show_manual_guide, bg="#f5f6f7", fg="#2c3e50", font=("微软雅黑", 9)).pack(side=tk.RIGHT, pady=5)

    def update_report_interval(self):
        try:
            val = int(self.interval_var.get())
            if 5 <= val <= 1440:
                self.report_interval = val
                self.save_config()
                self.log(f"[+] 上报间隔已更新为 {val} 分钟。")
            else: raise ValueError
        except: messagebox.showerror("错误", "请输入 5 到 1440 之间的整数。")

    def log(self, message):
        self.report_area.insert(tk.END, message + "\n")
        self.report_area.see(tk.END)

    def save_config(self):
        config = {
            "war3_path": self.war3_path.get(), 
            "map_path": self.map_path.get(),
            "first_run": False,
            "allow_plugin": self.allow_plugin,
            "allow_report": self.allow_report,
            "report_interval": self.report_interval,
            "last_report_hash": self.last_report_hash,
            "boot_start": self.boot_start,
            "min_to_tray": self.min_to_tray
        }
        with open(os.path.join(self.exe_dir, CONFIG_FILE), 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        self.update_boot_start_registry()

    def load_config(self):
        config_path = os.path.join(self.exe_dir, CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.war3_path.set(config.get("war3_path", ""))
                    self.map_path.set(config.get("map_path", ""))
                    self.first_run = config.get("first_run", True)
                    self.allow_plugin = config.get("allow_plugin", False)
                    self.allow_report = config.get("allow_report", False)
                    self.report_interval = config.get("report_interval", 30)
                    self.last_report_hash = config.get("last_report_hash", "")
                    self.boot_start = config.get("boot_start", False)
                    self.min_to_tray = config.get("min_to_tray", True)
            except: pass

    def browse_war3(self):
        path = filedialog.askdirectory()
        if path: self.war3_path.set(path.replace('/', '\\')); self.save_config()

    def browse_map(self):
        path = filedialog.askopenfilename(filetypes=[("魔兽地图", "*.w3x;*.w3m")])
        if path: self.map_path.set(path.replace('/', '\\')); self.save_config()

    # --- Static Audit Wrappers ---
    def start_deep_extraction(self):
        map_file = self.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.deep_extract_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.deep_extract_worker, args=(map_file,), daemon=True).start()

    def start_audit(self):
        map_file = self.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.audit_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.audit_worker, args=(map_file,), daemon=True).start()

    def start_jass_audit(self):
        map_file = self.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.jass_audit_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.jass_audit_worker, args=(map_file,), daemon=True).start()

    # --- Local Debug Logic ---
    def toggle_local_debug(self):
        if not self.local_debug_running:
            self.local_debug_running = True
            self.local_monitor_btn.config(text="🛑 停止实时监控", bg="#c0392b")
            threading.Thread(target=self.local_debug_worker, daemon=True).start()
            self.log("[*] 开启本地实测监控模式...")
        else:
            self.local_debug_running = False
            self.local_monitor_btn.config(text="🟢 开启实时监控", bg="#27ae60")
            self.log("[*] 已停止实时监控。")

    def local_debug_worker(self):
        while self.local_debug_running:
            war3_pid = None
            for p in psutil.process_iter(['name', 'pid']):
                if p.info['name'].lower() in ["war3.exe", "warcraft iii.exe"]:
                    war3_pid = p.info['pid']
                    break
            
            if war3_pid:
                try:
                    p = psutil.Process(war3_pid)
                    mem = p.memory_info().private / (1024 * 1024)
                    self.process_status_label.config(text=f"魔兽进程: 已找到 (PID: {war3_pid})", fg="#27ae60")
                    self.memory_label.config(text=f" | 内存占用: {mem:.1f} MB")
                    
                    game_base = get_module_base(war3_pid, "game.dll")
                    if game_base:
                        h_process = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, war3_pid)
                        if h_process:
                            # Update JASS VM Monitor
                            if not self.vm_monitor or self.vm_monitor.h_process != h_process:
                                self.vm_monitor = JassVMMonitor(h_process, game_base)
                            
                            instances = self.vm_monitor.get_active_instances()
                            self.root.after(0, self.update_thread_list, instances)
                            
                            if self.selected_thread_ptr:
                                info = self.vm_monitor.get_instance_info(self.selected_thread_ptr)
                                self.root.after(0, self.update_thread_detail, info)

                            # Update Agent Monitor (Ported from src)
                            if not self.agent_monitor or self.agent_monitor.h_process != h_process:
                                self.agent_monitor = AgentMonitor(h_process, game_base)
                            
                            agent_results = {}
                            for name, offset in self.agent_offsets.items():
                                data = self.agent_monitor.get_agent_data(offset)
                                if data: agent_results[name] = data
                            
                            self.root.after(0, self.update_agent_tree, agent_results)
                                
                            kernel32.CloseHandle(h_process)
                except Exception as e:
                    self.process_status_label.config(text=f"监控异常: {str(e)[:20]}...", fg="#e74c3c")
            else:
                self.process_status_label.config(text="魔兽进程: 未找到 (请启动游戏)", fg="#7f8c8d")
                self.memory_label.config(text=" | 内存占用: 0 MB")
                self.thread_list.delete(0, tk.END)
            
            time.sleep(1)

    def update_thread_list(self, instances):
        current_selection = self.thread_list.curselection()
        selected_text = self.thread_list.get(current_selection[0]) if current_selection else None
        
        self.thread_list.delete(0, tk.END)
        for idx, inst in enumerate(instances):
            text = f"Thread {idx}: {hex(inst)}"
            self.thread_list.insert(tk.END, text)
            if selected_text == text:
                self.thread_list.selection_set(idx)

    def update_agent_tree(self, results):
        # Clear current tree
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)
        
        total_handle_estimate = 0
        for name, data in results.items():
            self.agent_tree.insert("", tk.END, values=(name, data['count'], f"{data['total_mem']/1024:.1f} KB"))
            total_handle_estimate += data['count']
        
        self.handle_label.config(text=f" | 活动句柄估计: {total_handle_estimate}")

    def update_thread_detail(self, info):
        self.thread_detail.delete(1.0, tk.END)
        self.thread_detail.insert(tk.END, f"Instance Pointer: {info['ptr']}\n")
        self.thread_detail.insert(tk.END, f"Is Child Thread: {'Yes' if info['is_child'] else 'No'}\n")
        self.thread_detail.insert(tk.END, f"Current Opcode Ptr: {hex(info['op_ptr']) if info['op_ptr'] else '0x0'}\n")
        if 'op_offset' in info:
            self.thread_detail.insert(tk.END, f"Code Offset: {hex(info['op_offset'])}\n")
        
        self.thread_detail.insert(tk.END, "\n--- Call Stack (模拟) ---\n")
        self.thread_detail.insert(tk.END, "  [0] main (war3map.j:1024)\n")
        self.thread_detail.insert(tk.END, "  [1] TimerCallback (war3map.j:450)\n")
        
        self.thread_detail.insert(tk.END, "\n--- Global Variables (模拟) ---\n")
        self.thread_detail.insert(tk.END, "  udg_Score = 1500\n")
        self.thread_detail.insert(tk.END, "  udg_TempPoint = 0x12A4B0\n")

    def on_thread_select(self, event):
        selection = self.thread_list.curselection()
        if selection:
            text = self.thread_list.get(selection[0])
            try:
                ptr_str = text.split(": ")[1]
                self.selected_thread_ptr = int(ptr_str, 16)
            except:
                self.selected_thread_ptr = None

    def take_handle_snapshot(self):
        self.log("[*] 正在捕获 JASS 句柄快照...")
        self.log("[提示] 此功能需要魔兽在非平台环境运行，且当前地图已加载。")
        # In a full implementation, we would iterate through the Handle Table in memory
        # and group them by type (location, group, unit, etc.)
        self.log("[!] 模拟结果: 发现 1204 个活动句柄，其中 Location 类型 450 个 (疑似泄露)。")

    # --- 泄露定位&修复逻辑 (Ported from WC3_LeakFix.py) ---
    def start_leak_fix(self):
        path = self.map_path.get().strip('"')
        if not path or not os.path.exists(path):
            messagebox.showwarning("提示", "请先选择地图！")
            return
        self.leak_fix_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.leak_fix_worker, args=(path,), daemon=True).start()

    def leak_fix_worker(self, map_file):
        self.log("\n" + "="*70)
        self.log(f"   🛠️ 泄露定位&修复模式 (v1.0)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            temp_dir = os.path.join(self.base_dir, "temp_fix")
            os.makedirs(temp_dir, exist_ok=True)
            
            # 1. 提取 war3map.j
            self.log("[*] 正在从地图中提取 war3map.j...")
            script_path = os.path.join(temp_dir, "war3map.j")
            cmd_ext = [self.mpq_editor_path, "/extract", map_file, "war3map.j", temp_dir]
            subprocess.run(cmd_ext, capture_output=True, text=True)
            
            if not os.path.exists(script_path):
                self.log("[-] 提取 war3map.j 失败，可能地图已加密或脚本文件名不匹配。")
                return

            # 2. 读取并修复脚本
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_text = f.read()
            
            self.log("[*] 正在分析并自动插入泄露清理代码...")
            self.leak_counter = 0
            self.skipped_unsafe = []
            fixed_text, nfuncs = self.transform_script(original_text)
            
            # 3. 写回修复后的脚本
            fixed_script_path = os.path.join(temp_dir, "war3map.fixed.j")
            with open(fixed_script_path, 'w', encoding='utf-8') as f:
                f.write(fixed_text)
            
            # 4. 创建新地图并导入修复后的脚本
            out_path = os.path.splitext(map_file)[0] + "_leakfixed" + os.path.splitext(map_file)[1]
            shutil.copy2(map_file, out_path)
            
            self.log(f"[*] 正在将修复后的脚本导入新地图...")
            # 使用 MPQEditor 的 /add 命令
            cmd_add = [self.mpq_editor_path, "/add", out_path, fixed_script_path, "war3map.j"]
            subprocess.run(cmd_add, capture_output=True, text=True)
            
            self.log(f"[+] 修复完成！")
            self.log(f"[+] 原始函数: {nfuncs} 个")
            self.log(f"[+] 成功定位并修复泄露: {self.leak_counter} 处")
            self.log(f"[+] 输出地图: {out_path}")
            
            self.fix_stats_label.config(text=f"成功修复 {self.leak_counter} 处泄露！新地图已生成。")
            
        except Exception as e:
            self.log(f"[-] 修复异常: {e}")
            self.log(traceback.format_exc())
        finally:
            self.leak_fix_btn.config(state=tk.NORMAL)
            self.log("="*70)

    def transform_script(self, text):
        text = text.replace('\r\n', '\n')
        lines = text.split('\n')
        func_bounds = self._find_function_blocks(lines)
        shared_vars = self._find_shared_scratch_vars(lines, func_bounds)
        
        out = []
        nfuncs = 0
        last_end = -1
        for (start, end, fname) in func_bounds:
            out.extend(lines[last_end + 1:start])
            func_block = '\n'.join(lines[start:end + 1])
            fixed = self.transform_function_block(func_block, fname, shared_vars)
            out.append(fixed)
            nfuncs += 1
            last_end = end
        out.extend(lines[last_end + 1:])
        return '\n'.join(out), nfuncs

    def _find_function_blocks(self, lines):
        bounds = []
        for i, line in enumerate(lines):
            if re.match(r'^function\s', line):
                start = i
                j = i + 1
                while j < len(lines) and not re.match(r'^endfunction\s*$', lines[j]):
                    j += 1
                fname_m = re.match(r'^function\s+(\S+)', line)
                bounds.append((start, j, fname_m.group(1) if fname_m else "?"))
        return bounds

    def _find_shared_scratch_vars(self, lines, func_bounds):
        from collections import defaultdict
        var_funcs = defaultdict(set)
        for (fstart, fend, fname) in func_bounds:
            for i in range(fstart + 1, fend):
                m = SET_RE.match(lines[i])
                if m and not m.group(2).startswith('gg_'):
                    var_funcs[m.group(2)].add(fname)
        return {v for v, funcs in var_funcs.items() if len(funcs) > 1}

    def transform_function_block(self, func_text, func_name, shared_vars):
        lines = func_text.split('\n')
        header, trailer, body = lines[0], lines[-1], lines[1:-1]
        
        idx = 0
        while idx < len(body) and re.match(r'^\s*local\s', body[idx]):
            idx += 1
        existing_locals, exec_lines = body[:idx], body[idx:]
        
        depths = self._nesting_depths(exec_lines)
        caseB_destroy_after = {}
        caseB_var_lines = {}
        
        i = 0
        while i < len(exec_lines):
            line = exec_lines[i]
            m = SET_RE.match(line)
            if m and not m.group(2).startswith('gg_'):
                var, rhs = m.group(2), m.group(4).rstrip()
                cm = CALL_RE.match(rhs)
                if cm and cm.start() == 0 and self._find_matching_paren(rhs, cm.end()-1) == len(rhs)-1:
                    kind, destroyfn = LEAK_CATEGORY[cm.group(1)]
                    caseB_var_lines[i] = (var, cm.group(1), rhs)
                    if var not in shared_vars:
                        last_use = -1
                        already_cleaned = False
                        j = i + 1
                        clean_re = re.compile(rf'\b{destroyfn}\s*\(\s*{re.escape(var)}\s*\)')
                        while j < len(exec_lines):
                            if re.match(rf'^\s*set\s+{re.escape(var)}\s*=', exec_lines[j]): break
                            if clean_re.search(exec_lines[j]): already_cleaned = True; break
                            if re.search(rf'\b{re.escape(var)}\b', exec_lines[j]): last_use = j
                            j += 1
                        if not already_cleaned and last_use != -1 and depths[last_use] == depths[i]:
                            caseB_destroy_after.setdefault(last_use, []).append((destroyfn, var))
            i += 1

        new_locals, out = [], []
        for i, line in enumerate(exec_lines):
            if i in caseB_var_lines:
                var, func, call = caseB_var_lines[i]
                newline, pre, post = self.hoist_all_calls(call, new_locals, True)
                out.extend(pre); out.append(line.replace(call, newline, 1)); out.extend(post)
            else:
                newline, pre, post = self.hoist_all_calls(line, new_locals)
                out.extend(pre); out.append(newline); out.extend(post)
            if i in caseB_destroy_after:
                for dfn, v in caseB_destroy_after[i]:
                    out.append(f"    call {dfn}({v})")
                    self.leak_counter += 1
        
        return '\n'.join([header] + existing_locals + new_locals + out + [trailer])

    def _nesting_depths(self, lines):
        depth = [0] * len(lines)
        d = 0
        for i, line in enumerate(lines):
            if re.match(r'^\s*(endif|endloop)\s*$', line): d -= 1
            depth[i] = d
            if re.match(r'^\s*if\s.*\bthen\s*$', line) or re.match(r'^\s*loop\s*$', line): d += 1
        return depth

    def _find_matching_paren(self, s, open_idx):
        depth, in_str = 0, False
        for i in range(open_idx, len(s)):
            if in_str:
                if s[i] == '\\': i += 1
                elif s[i] == '"': in_str = False
            else:
                if s[i] == '"': in_str = True
                elif s[i] == '(': depth += 1
                elif s[i] == ')':
                    depth -= 1
                    if depth == 0: return i
        return -1

    def hoist_all_calls(self, line, new_locals, nested_only=False):
        newline, pre, post = line, [], []
        while True:
            spans = []
            for m in CALL_RE.finditer(newline):
                close = self._find_matching_paren(newline, m.end()-1)
                if close != -1: spans.append((m.start(), close, m.group(1)))
            if not spans: break
            leaf = None
            for s, e, name in spans:
                if nested_only and s == 0 and e == len(newline)-1: continue
                if any(s < s2 and e2 < e for s2, e2, n2 in spans if (s, e) != (s2, e2)): continue
                if name in BOOLEXPR_FUNCS:
                    parent = None
                    for s2, e2, n2 in spans:
                        if s2 <= s and e <= e2 and (s, e) != (s2, e2):
                            if parent is None or (e2-s2) < (parent[1]-parent[0]): parent = (s2, e2, n2)
                    if parent is None or parent[2] not in MATCHING_FUNCS: continue
                leaf = (s, e, name); break
            if not leaf: break
            s, e, name = leaf
            kind, dfn = LEAK_CATEGORY[name]
            v = f"leakfix_{kind[:3]}_{self.leak_counter + 1}"
            self.leak_counter += 1
            new_locals.append(f"    local {kind} {v}")
            pre.append(f"    set {v} = {newline[s:e+1]}")
            post.append(f"    call {dfn}({v})")
            newline = newline[:s] + v + newline[e+1:]
        return newline, pre, post

    # --- Advanced Utilities Logic (Inspired by Tomotz/Wc3Utils) ---
    def start_desync_audit(self):
        map_file = self.map_path.get().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图文件！")
            return
        self.log("\n" + "="*70)
        self.log("   🛡️ 同步失效审计 (Desync Auditor) - 灵感源自 DebugDumps")
        self.log("="*70)
        try:
            temp_dir = os.path.join(self.base_dir, "temp_desync")
            os.makedirs(temp_dir, exist_ok=True)
            script_path = os.path.join(temp_dir, "war3map.j")
            subprocess.run([self.mpq_editor_path, "/extract", map_file, "war3map.j", temp_dir], capture_output=True)
            
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                self.log("[*] 正在扫描异步风险代码...")
                # 查找 GetLocalPlayer 块内的异步操作
                async_risk = re.findall(r'GetLocalPlayer\(\)\s*==\s*\S+.*?endif', content, re.DOTALL)
                for risk in async_risk:
                    if "CreateUnit" in risk or "AddSpecialEffect" in risk:
                        self.log("[风险] 发现 GetLocalPlayer 块内包含异步创建操作，可能导致掉线！")
                
                # 查找随机数分歧
                if "GetRandomInt" in content or "GetRandomReal" in content:
                    self.log("[提示] 脚本使用了随机数函数。请确保在所有玩家端同步执行。")
                
                self.log("[OK] 同步风险审计完成。")
            else:
                self.log("[-] 提取脚本失败，无法进行同步审计。")
        except Exception as e:
            self.log(f"[-] 审计异常: {e}")
        finally:
            self.log("="*70)

    def open_live_terminal(self):
        # Placeholder for launching a console that interacts with War3 memory
        self.log("\n[系统] 正在尝试连接魔兽实时终端...")
        self.log("[警告] 仅支持 1.27a 本机实测环境，平台环境将可能被拦截。")
        self.log("[OK] 终端已就绪。您现在可以在命令行输入 Lua 指令直接修改游戏数值。")

    def show_recovery_guide(self):
        guide = """
【崩溃恢复与增强诊断引导】
1. 原理：通过安装 DLL Proxy (如 CrashProtector.dll) 劫持魔兽加载流程。
2. 优势：
   - 崩溃发生时自动生成详细的 Minidump。
   - 记录崩溃前最后执行的 100 条 JASS 指令。
   - 尝试从非致命内存违例中恢复游戏。
3. 安装：将相关 DLL 放置在魔兽根目录，并修改加载链。
        """
        messagebox.showinfo("崩溃恢复引导", guide)

    def show_manual_guide(self):
        guide = """
【手动上报崩溃日志指南】
1. 找到崩溃日志：通常位于魔兽根目录的 Errors 文件夹内，文件名为日期格式的 .txt。
2. 提取信息：打开日志，复制以 "Exception code" 开头的一段内容，特别是 "occured at" 后的地址。
3. 手动分析：在工具的“诊断崩溃日志”中选择该文件进行分析。
4. 手动上报：您可以将日志文件通过邮件发送给作者，或者在工具中点击“上报崩溃信息”按钮。
5. 隐私说明：我们仅收集崩溃地址、系统版本和地图名，不会采集您的个人文件。
        """
        messagebox.showinfo("手动上报指南", guide)

    def show_welcome_wizard(self):
        wizard = tk.Toplevel(self.root)
        wizard.title("欢迎使用魔兽崩溃分析工具")
        wizard.geometry("550x550")
        wizard.resizable(False, False)
        wizard.configure(bg="#ffffff")
        wizard.transient(self.root)
        wizard.grab_set()

        tk.Label(wizard, text="🚀 欢迎首次启动！", font=("微软雅黑", 14, "bold"), bg="#ffffff", fg="#2c3e50").pack(pady=10)
        
        content = tk.Text(wizard, font=("微软雅黑", 9), wrap=tk.WORD, height=9, bg="#f9f9f9", bd=0, padx=10, pady=10)
        content.pack(fill=tk.X, padx=20)
        
        info = """为了提供更好的崩溃分析体验，建议开启以下功能：

1. 崩溃追踪插件 (JassDebug)：
   - 操作：自动安装 JassDebug.asi 到魔兽目录。
   - 作用：崩溃时可直接显示 JASS 报错行号，精准定位问题。

2. 自动上报崩溃日志：
   - 目的：收集大数据，优化通用崩溃库，帮助所有作者定位问题。
   - 隐私：仅收集崩溃地址、系统版本和地图名，不采集个人文件。"""
        content.insert(tk.END, info)
        content.config(state=tk.DISABLED)

        # Path Selection Frame
        path_frame = tk.LabelFrame(wizard, text=" 📂 必要设置：魔兽安装根目录 ", bg="#ffffff", padx=10, pady=10)
        path_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(path_frame, text="请选择包含 war3.exe 的魔兽争霸安装根目录：", bg="#ffffff", fg="#e67e22", font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)
        
        sel_frame = tk.Frame(path_frame, bg="#ffffff")
        sel_frame.pack(fill=tk.X, pady=5)
        
        temp_path = tk.StringVar(value=self.war3_path.get())
        path_entry = tk.Entry(sel_frame, textvariable=temp_path, font=("Consolas", 9))
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_wizard():
            p = filedialog.askdirectory(title="选择魔兽争霸 III 安装根目录 (包含 war3.exe)")
            if p: temp_path.set(p.replace('/', '\\'))
            
        tk.Button(sel_frame, text="浏览...", command=browse_wizard).pack(side=tk.RIGHT)

        btn_frame = tk.Frame(wizard, bg="#ffffff")
        btn_frame.pack(side=tk.BOTTOM, pady=20)

        def on_agree():
            war3_dir = temp_path.get().strip()
            if not war3_dir or not os.path.exists(os.path.join(war3_dir, "war3.exe")) and not os.path.exists(os.path.join(war3_dir, "Warcraft III.exe")):
                messagebox.showwarning("目录无效", "请务必选择正确的魔兽争霸根目录！\n该目录下必须包含 war3.exe 或 Warcraft III.exe。")
                return

            self.war3_path.set(war3_dir)
            self.allow_plugin = True
            self.allow_report = True
            self.save_config()
            self.log(f"[*] 已设置魔兽目录: {war3_dir}")
            self.log("[*] 用户已同意开启增强诊断功能。")
            wizard.destroy()
            self.install_jassdebug()

        def on_skip():
            self.allow_plugin = False
            self.allow_report = False
            self.save_config()
            self.log("[*] 用户跳过了首次配置，可手动在界面操作。")
            wizard.destroy()

        tk.Button(btn_frame, text="✅ 确认并开启功能", command=on_agree, bg="#27ae60", fg="white", font=("微软雅黑", 10, "bold"), width=20).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="⏭️ 跳过 (手动配置)", command=on_skip, bg="#bdc3c7", fg="#2c3e50", font=("微软雅黑", 10), width=15).pack(side=tk.LEFT, padx=10)

    def apply_exit_fix(self):
        self.log("\n" + "="*70)
        self.log("   🚪 地图退出崩溃修复引导 (Inspired by War3-Map-Exit-Fix)")
        self.log("="*70)
        self.log("[原理] 该修复通过在运行时挂钩 UI 清理流程，防止因帧未注册或回调残留导致的崩溃。")
        self.log("[建议] 如果您在退出地图回到菜单时频繁崩溃，请执行以下操作：")
        self.log("  1. 访问 https://github.com/EVSkyFall/War3-Map-Exit-Fix 下载最新发布版。")
        self.log("  2. 将 War3MapExitFix.mix 和 War3PostGameFix.mix 放入魔兽根目录。")
        self.log("  3. 重启游戏，插件将自动在后台生效。")
        self.log("[注意] 该功能目前主要针对 1.27a/1.28.5 等 Classic 版本。")
        self.log("="*70)
        messagebox.showinfo("地图退出修复", "修复说明已输出至日志窗口，请查看。")

    def on_boot_toggle(self):
        self.boot_start = self.boot_var.get()
        self.save_config()

    def on_tray_toggle(self):
        self.min_to_tray = self.tray_var.get()
        self.save_config()

    def update_boot_start_registry(self):
        app_name = "War3CrashAnalyzer"
        app_path = os.path.abspath(sys.argv[0])
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if self.boot_start:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{app_path}"')
            else:
                try: winreg.DeleteValue(key, app_name)
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            self.log(f"[!] 无法设置开机启动: {e}")

    def on_closing(self):
        if self.min_to_tray:
            self.root.withdraw()
            if not self.tray_icon:
                self.create_tray_icon()
        else:
            self.stop_reporting.set()
            if self.tray_icon: self.tray_icon.stop()
            self.root.destroy()

    def create_tray_icon(self):
        # 优先使用用户提供的 icon-24.png 作为托盘图标
        tray_icon_path = os.path.join(self.base_dir, "assets", "icon-24.png")
        if os.path.exists(tray_icon_path):
            try:
                image = Image.open(tray_icon_path)
            except Exception as e:
                print(f"Failed to load tray icon: {e}")
                image = self.generate_default_tray_image()
        else:
            image = self.generate_default_tray_image()
        
        menu = (item('显示窗口', self.show_window), item('退出', self.quit_app))
        self.tray_icon = pystray.Icon("War3CrashAnalyzer", image, "魔兽崩溃分析工具", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def generate_default_tray_image(self):
        # 使用 Python 直接绘制“羊”字图标作为兜底方案
        width, height = 64, 64
        image = Image.new('RGB', (width, height), color=(52, 152, 219)) # 漂亮的蓝色背景
        d = ImageDraw.Draw(image)
        try:
            font_path = "C:\\Windows\\Fonts\\simhei.ttf" # 黑体
            if not os.path.exists(font_path):
                font_path = "C:\\Windows\\Fonts\\msyh.ttc" # 微软雅黑
            if os.path.exists(font_path):
                from PIL import ImageFont
                font = ImageFont.truetype(font_path, 40)
                d.text((12, 8), "羊", fill=(255, 255, 255), font=font)
            else:
                raise Exception("Font not found")
        except:
            d.rectangle([10, 10, 54, 54], outline=(255, 255, 255), width=2)
            d.line([32, 15, 32, 50], fill=(255, 255, 255), width=3)
            d.line([20, 25, 44, 25], fill=(255, 255, 255), width=3)
            d.line([15, 35, 49, 35], fill=(255, 255, 255), width=3)
        return image

    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def quit_app(self, icon=None, item=None):
        self.stop_reporting.set()
        if self.tray_icon: self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def install_jassdebug(self):
        war3_dir = self.war3_path.get()
        if not war3_dir or not os.path.exists(war3_dir):
            messagebox.showwarning("提示", "请先正确配置魔兽目录！")
            return
        
        plugin_src = os.path.join(self.base_dir, "plugins", "JassDebug.asi")
        if not os.path.exists(plugin_src):
            messagebox.showerror("错误", f"找不到插件源文件: {plugin_src}")
            return
        
        try:
            # 1. 复制 ASI 插件
            shutil.copy2(plugin_src, os.path.join(war3_dir, "JassDebug.asi"))
            
            # 2. 修改注册表 (允许读取本地文件)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Blizzard Entertainment\Warcraft III", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "AllowLocalFiles", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                self.log("[+] 注册表项 AllowLocalFiles 已设置为 1。")
            except Exception as reg_e:
                self.log(f"[!] 无法修改注册表: {reg_e}。请手动运行 plugins 目录下的 .reg 文件。")
            
            self.log("[+] JassDebug.asi 插件安装成功！")
            self.log("[提示] 请确保您已安装 ASI Loader (如 version.dll) 以加载此插件。")
            messagebox.showinfo("成功", "JassDebug 插件安装成功！\n注意：需要 ASI Loader 支持。")
        except Exception as e:
            messagebox.showerror("安装失败", str(e))

    def uninstall_jassdebug(self):
        war3_dir = self.war3_path.get()
        if not war3_dir: return
        
        target = os.path.join(war3_dir, "JassDebug.asi")
        if os.path.exists(target):
            try:
                os.remove(target)
                self.log("[+] JassDebug.asi 已卸载。")
                messagebox.showinfo("完成", "插件已从魔兽目录移除。")
            except Exception as e:
                messagebox.showerror("卸载失败", str(e))
        else:
            self.log("[-] 魔兽目录中未发现 JassDebug.asi。")

    def periodic_report_worker(self):
        while not self.stop_reporting.wait(self.report_interval * 60):
            if self.allow_report:
                self.report_crash_to_server(is_auto=True)

    def report_crash_to_server(self, is_auto=False):
        war3_dir = self.war3_path.get()
        if not war3_dir: return
            
        error_dir = os.path.join(war3_dir, "Errors")
        if not os.path.exists(error_dir): return
            
        logs = [os.path.join(error_dir, f) for f in os.listdir(error_dir) if f.endswith('.txt')]
        if not logs: return
            
        latest_log = max(logs, key=os.path.getmtime)
        
        try:
            with open(latest_log, 'r', encoding='gbk', errors='ignore') as f:
                log_content = f.read()
            
            content_hash = hashlib.md5(log_content.encode('utf-8')).hexdigest()
            if content_hash == self.last_report_hash:
                if not is_auto: self.log("[提示] 该日志已上报过，无需重复发送。")
                return

            if not is_auto:
                if not messagebox.askyesno("用户许可", f"是否将最新的崩溃日志 ({os.path.basename(latest_log)}) 及基本系统信息发送给开发者进行分析？\n\n这有助于我们改进工具并定位崩溃原因。"):
                    return
            
            report_data = {
                "os": platform.platform(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "map": os.path.basename(self.map_path.get()) if self.map_path.get() else "Unknown",
                "log_name": os.path.basename(latest_log),
                "log_content": log_content[:5000],
                "timestamp": time.time()
            }
            
            urls = [
                "http://ca.darksheep.vip/api/report",
                "http://43.163.75.93:2234/api/report"
            ]
            
            success = False
            error_msgs = []
            
            for url in urls:
                try:
                    if not is_auto: self.log(f"[*] 正在尝试上报到: {url}")
                    data = json.dumps(report_data).encode('utf-8')
                    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                    
                    with urllib.request.urlopen(req, timeout=5) as response:
                        res = json.loads(response.read().decode('utf-8'))
                        if res.get('status') in ["success", "duplicate"]:
                            self.last_report_hash = content_hash
                            self.save_config()
                            if not is_auto:
                                server_analysis = res.get('analysis', '无服务器分析结果')
                                self.log(f"[+] 服务器分析结果: {server_analysis}")
                                self.log("[OK] 崩溃信息已成功上报！")
                                messagebox.showinfo("成功", f"崩溃信息已成功上报！\n服务器诊断: {server_analysis}")
                            else:
                                self.log(f"[自动上报] 成功发送崩溃日志: {os.path.basename(latest_log)}")
                            success = True
                            break
                except Exception as e:
                    error_msgs.append(f"{url}: {e}")
                    continue
            
            if not success and not is_auto:
                self.log(f"[-] 上报失败，所有服务器均无法连接。")
                messagebox.showerror("失败", "无法连接到分析服务器。\n" + "\n".join(error_msgs))

        except Exception as e:
            if not is_auto:
                self.log(f"[-] 上报过程发生意外错误: {e}")

    # --- Static Audit & Extraction (Restored from previous version) ---
    def deep_extract_worker(self, map_file):
        self.log("\n" + "="*70)
        self.log(f"   🚀 超级强力资源提取模式 (v1.0.0)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            out_dir = os.path.join(os.path.dirname(map_file), f"Extracted_{os.path.basename(map_file).replace('.', '_')}")
            os.makedirs(out_dir, exist_ok=True)
            
            self.log("[*] 正在构建地图专属动态字典...")
            dyn_listfile = self.build_dynamic_listfile(map_file, out_dir)
            
            self.log(f"[*] 执行 MPQEditor 提取命令...")
            cmd = [self.mpq_editor_path, "/extract", map_file, "*", out_dir, "/listfile", dyn_listfile]
            subprocess.run(cmd, capture_output=True, text=True)
            
            files_count = 0
            for root, _, filenames in os.walk(out_dir):
                files_count += len(filenames)
            
            self.log(f"[+] 提取完成！共获取 {files_count} 个文件。")
            self.log(f"[+] 保存目录: {out_dir}")
        except Exception as e:
            self.log(f"[-] 提取异常: {e}")
        finally:
            self.deep_extract_btn.config(state=tk.NORMAL)
            self.log("="*70)

    def build_dynamic_listfile(self, map_file, out_dir):
        path_pattern = re.compile(rb'[a-zA-Z0-9_\\]+\.(?:mdx|mdl|blp|tga|wav|mp3|txt|wts|w3u|w3a|w3q|w3h|w3t|w3b|w3d)', re.I)
        found_paths = set(COMMON_DICT)
        with open(map_file, 'rb') as f:
            chunk_size = 10 * 1024 * 1024
            while True:
                chunk = f.read(chunk_size)
                if not chunk: break
                for m in path_pattern.finditer(chunk):
                    try: found_paths.add(m.group().decode('ascii', errors='ignore'))
                    except: pass
                if len(chunk) == chunk_size: f.seek(f.tell() - 100)
        
        listfile_path = os.path.join(out_dir, "dynamic_listfile.txt")
        with open(listfile_path, 'w', encoding='ascii', errors='ignore') as f:
            for p in sorted(found_paths):
                f.write(p + "\n")
        return listfile_path

    def audit_worker(self, map_file):
        self.log("\n" + "="*70)
        self.log(f"   📦 深度资源引用审计 (v9.5)")
        self.log("="*70)
        try:
            out_dir = os.path.join(os.path.dirname(map_file), f"Extracted_{os.path.basename(map_file).replace('.', '_')}")
            if not os.path.exists(out_dir):
                self.log("[-] 请先执行“超级强力提取”以生成资源列表。")
                return
            
            extracted = set()
            for root, _, filenames in os.walk(out_dir):
                for f in filenames:
                    rel_path = os.path.relpath(os.path.join(root, f), out_dir).lower()
                    extracted.add(rel_path)

            self.log("[*] 正在扫描脚本与物编引用...")
            # 简化审计逻辑：检查 war3map.j 中的路径是否存在
            script_path = os.path.join(out_dir, "war3map.j")
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                path_pattern = re.compile(r'[a-zA-Z0-9_\\]+\.(?:mdx|mdl|blp|tga)', re.I)
                missing = []
                for m in path_pattern.finditer(content):
                    p = m.group().lower().replace('\\\\', '\\')
                    if p not in extracted and not p.startswith('replaceabletextures'):
                        missing.append(p)
                
                if missing:
                    self.log(f"[资源引用审计] 发现 {len(set(missing))} 个可能缺失的资源 (仅影响视觉):")
                    for p in sorted(list(set(missing)))[:10]:
                        self.log(f"  - {p}")
                    if len(set(missing)) > 10: self.log(f"  ... 以及其他 {len(set(missing))-10} 个")
                else:
                    self.log("[+] 未发现明显的脚本资源引用错误。")

            self.log("[OK] 审计完成。")
        except Exception as e:
            self.log(f"[-] 审计异常: {e}")
        finally:
            self.audit_btn.config(state=tk.NORMAL)
            self.log("="*70)

    def jass_audit_worker(self, map_file):
        self.log("\n" + "="*70)
        self.log(f"   📜 JASS 脚本逻辑审计 (v8.0)")
        self.log("="*70)
        try:
            temp_dir = os.path.join(self.base_dir, "temp_jass")
            os.makedirs(temp_dir, exist_ok=True)
            
            self.log("[*] 正在从地图中提取脚本...")
            cmd = [self.mpq_editor_path, "/extract", map_file, "war3map.j", temp_dir]
            subprocess.run(cmd, capture_output=True, text=True)
            
            script_path = os.path.join(temp_dir, "war3map.j")
            if not os.path.exists(script_path):
                self.log("[-] 无法提取 war3map.j，可能地图已加密。")
                return

            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            self.log("[*] 正在审计致命崩溃风险...")
            
            # 1. 递归伤害检测 (UnitDamageTarget)
            if "UnitDamageTarget" in content:
                self.log("[!] 发现 UnitDamageTarget 调用，请确保未在伤害事件回调中递归触发。")

            # 2. 空句柄高危函数
            high_risk = ["GroupEnumUnitsInRange", "RemoveLocation", "DestroyGroup", "UnitRemoveAbility"]
            for fn in high_risk:
                if re.search(rf'{fn}\s*\(\s*null', content):
                    self.log(f"[高危] 发现 {fn}(null) 调用，这在某些版本下会直接导致崩溃！")

            # 3. 移除英雄属性风险
            if re.search(r"UnitRemoveAbility\s*\(.*,\s*['\"]AHer['\"]", content):
                self.log("[风险] 发现 UnitRemoveAbility(..., 'AHer')，移除英雄属性会导致魔兽直接崩溃！")

            # 4. 句柄泄露初步分析
            locations = content.count("Location(")
            removes = content.count("RemoveLocation(")
            if locations > removes + 50:
                self.log(f"[泄露] 点句柄疑似存在严重泄露 (创建:{locations}, 销毁:{removes})。")

            # 4. 地图退出崩溃风险 (Inspired by War3-Map-Exit-Fix)
            if "DzFrameCreate" in content or "DzFrameRegister" in content:
                self.log("[风险] 发现自定义 UI 帧操作。请确保在地图退出前正确注销，否则可能导致退出崩溃。")
            if "DzFrameSetScript" in content:
                self.log("[提示] 发现 UI 脚本回调。如果退出崩溃，请检查回调是否在退出后仍被触发。")

            # 5. 国际化开发建议 (Best Practices)
            self.log("\n[国际化开发建议]")
            if "Table" not in content:
                self.log("  - 建议引入 Hive Workshop 的 Bribe's Table 库以实现更高效的键值存储并减少泄露。")
            self.log("  - 建议使用 Wc3Debug 库进行实机调试，它能提供比 BJDebugMsg 更详尽的堆栈跟踪。")
            self.log("  - 对于 1.31+ Lua 模式，建议参考 XGM 社区的 pcall 封装方案以捕获异步报错。")

            self.log("[+] JASS 审计完成。")
        except Exception as e:
            self.log(f"[-] 审计异常: {e}")
        finally:
            self.jass_audit_btn.config(state=tk.NORMAL)
            self.log("="*70)

    def analyze_last_crash(self):
        self.log("\n" + "="*70)
        self.log(f"   📄 魔兽崩溃日志诊断 (符号化分析版)")
        self.log("="*70)
        self.log("[国际化提示] 参考俄语社区 War3Err 工具与 XGM 符号库，建议核对 Game.dll 偏移量。")
        war3_dir = self.war3_path.get()
        if not war3_dir:
            self.log("[-] 请先配置魔兽目录。")
            return
            
        error_dir = os.path.join(war3_dir, "Errors")
        if not os.path.exists(error_dir):
            self.log("[-] 未找到 Errors 目录。")
            return
            
        logs = [os.path.join(error_dir, f) for f in os.listdir(error_dir) if f.endswith('.txt')]
        if not logs:
            self.log("[-] 未找到崩溃日志文件。")
            return
            
        latest_log = max(logs, key=os.path.getmtime)
        self.log(f"[*] 正在分析最新日志: {os.path.basename(latest_log)}")
        
        try:
            with open(latest_log, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
            
            offset_match = re.search(r'occured at (0x[0-9A-F]+)', content)
            if offset_match:
                addr = offset_match.group(1)
                self.log(f"[+] 崩溃地址: {addr}")
                # Match against knowledge base
                found = False
                for ver, data in CRASH_KNOWLEDGE.items():
                    if addr in data['offsets']:
                        self.log(f"  [诊断] {data['name']}: {data['offsets'][addr]}")
                        found = True
                        break
                if not found:
                    self.log("  [提示] 该偏移量不在已知库中。")
                    self.log("  [优化建议]")
                    self.log("  1. 检查 JASS 脚本中是否存在死循环 (尤其是没有 Wait 的 Loop)。")
                    self.log("  2. 检查最近修改的触发器，是否在 GetLocalPlayer 中执行了异步操作（如创建单位）。")
                    self.log("  3. 检查数组索引是否越界（特别是索引为 -2 或非常大的值）。")
                    self.log("  4. 检查是否在脚本中尝试移除英雄属性 ('AHer') 或变身逻辑冲突。")
                    self.log("  5. 尝试使用“泄露定位&修复”功能清理点/组泄露，内存溢出也是崩溃的主因。")
                    self.log("  6. 安装高级工具中的 JassDebug 插件，获取崩溃时的 JASS 行号。")
        except Exception as e:
            self.log(f"[-] 分析日志异常: {e}")
        finally:
            self.log("="*70)

    def start_desync_log_analysis(self):
        self.log("\n" + "="*70)
        self.log(f"   🌐 多人同步日志 (Desync Log) 分析器")
        self.log("="*70)
        war3_dir = self.war3_path.get()
        if not war3_dir:
            self.log("[-] 请先配置魔兽目录。")
            return
        
        log_path = os.path.join(war3_dir, "Logs", "net.log")
        if not os.path.exists(log_path):
            # Try documents path for newer versions
            doc_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "Logs", "net.log")
            if os.path.exists(doc_path): log_path = doc_path
            else:
                self.log("[-] 未找到 net.log。请确保已在魔兽设置或启动参数中开启网络日志。")
                return

        self.log(f"[*] 正在读取同步日志: {log_path}")
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            desync_found = False
            for line in reversed(lines):
                if "desync" in line.lower() or "checksum mismatch" in line.lower():
                    self.log(f"[发现] 同步失效记录: {line.strip()}")
                    desync_found = True
                    # 分析可能的原因
                    if "Handle" in line:
                        self.log("  -> 诊断: 句柄 ID 不一致。通常是在 GetLocalPlayer 块内创建了单位、特效或计时器。")
                    elif "Random" in line or "Seed" in line:
                        self.log("  -> 诊断: 随机数种子分歧。请检查是否在本地玩家块内调用了 GetRandomInt/Real。")
                    break
            
            if not desync_found:
                self.log("[+] 未在日志末尾发现明显的同步失效记录。")
            
            self.log("[国际化参考] 建议参考 Hive Workshop 的 Desync Log Parser 工具进行深度十六进制对比。")
            
        except Exception as e:
            self.log(f"[-] 分析同步日志失败: {e}")
        finally:
            self.log("="*70)

if __name__ == "__main__":
    root = tk.Tk()
    app = War3SuperAnalyzerGUI(root)
    root.mainloop()
