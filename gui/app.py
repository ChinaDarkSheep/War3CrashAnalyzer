import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import platform
import ctypes
import json
import threading
import winreg
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk
from core.reporter import Reporter
from core.fixer import Fixer
from gui.tabs.static_tab import StaticTab
from gui.tabs.local_tab import LocalTab
from gui.tabs.leak_fix_tab import LeakFixTab
from gui.tabs.adv_tab import AdvTab

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
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            self.exe_dir = self.base_dir
            
        self.mpq_editor_path = os.path.join(self.base_dir, "MPQEditor.exe")
        
        self.first_run = True
        self.allow_plugin = False
        self.allow_report = False
        self.report_interval = 30
        self.boot_start = False
        self.min_to_tray = True
        self.status_var = tk.StringVar(value="就绪 | 模块化重构版")
        self.report_area = None # Will be set by StaticTab
        self.config = {}

        # Initialize core components that depend on config
        self.reporter = Reporter(self.log, self.base_dir)
        self.load_config() # Load before UI setup to set variables
        
        if platform.system() == "Windows":
            try:
                myappid = 'darksheep.war3analyzer.1.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
                
        self.setup_ui()
        self.setup_tray()
        self.set_window_icon()

        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        if self.first_run or not self.war3_path.get():
            self.root.after(500, self.show_welcome_wizard)
        else:
            # 启动时执行一次静默批量诊断
            self.root.after(1000, self.startup_audit)

        self.stop_reporting = threading.Event()
        threading.Thread(target=self.reporter.periodic_report_worker, 
                         args=(self.stop_reporting, self), 
                         daemon=True).start()

    def startup_audit(self):
        if self.war3_path.get():
            self.log("[*] 正在执行启动项扫描...")
            threading.Thread(target=self.static_tab.auditor.analyze_last_crash, 
                             args=(self.war3_path.get(),), 
                             daemon=True).start()

    def setup_ui(self):
        # Header (Simplified for example)
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="魔兽RPG崩溃分析工具 v1.0.0", font=("Segoe UI", 14, "bold"), fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=20)

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.static_tab = StaticTab(self.notebook, self)
        self.notebook.add(self.static_tab, text=" 静态审计与诊断 ")

        self.local_tab = LocalTab(self.notebook, self)
        self.notebook.add(self.local_tab, text=" 本地调试 (实测模式) ")

        self.leak_fix_tab = LeakFixTab(self.notebook, self)
        self.notebook.add(self.leak_fix_tab, text=" 泄露定位&修复 ")

        self.adv_tab = AdvTab(self.notebook, self)
        self.notebook.add(self.adv_tab, text=" 高级工具 & 设置 ")

        # Status Bar
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, message):
        if self.report_area:
            self.report_area.insert(tk.END, message + "\n")
            self.report_area.see(tk.END)
        else:
            print(message)

    def report_crash_to_server(self):
        self.reporter.report_crash_to_server(self.war3_path.get(), self.map_path.get(), is_auto=False)

    def save_config(self):
        config = {
            "war3_path": self.war3_path.get(), 
            "map_path": self.map_path.get(),
            "first_run": self.first_run,
            "allow_plugin": self.allow_plugin,
            "allow_report": self.allow_report,
            "report_interval": self.report_interval,
            "boot_start": self.boot_start,
            "min_to_tray": self.min_to_tray
        }
        try:
            with open(os.path.join(self.exe_dir, CONFIG_FILE), 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            self.update_boot_start_registry()
        except Exception as e:
            self.log(f"[-] 保存配置失败: {e}")

    def load_config(self):
        config_path = os.path.join(self.exe_dir, CONFIG_FILE)
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                self.log(f"[-] 加载配置失败: {e}")
                
        self.config = config
        # Update components that use the config
        self.war3_path.set(config.get("war3_path", ""))
        self.map_path.set(config.get("map_path", ""))
        self.first_run = config.get("first_run", True)
        self.allow_plugin = config.get("allow_plugin", False)
        self.allow_report = config.get("allow_report", False)
        self.report_interval = config.get("report_interval", 30)
        self.boot_start = config.get("boot_start", False)
        self.min_to_tray = config.get("min_to_tray", True)
        
        # Re-initialize fixer with new key if it changed
        self.fixer = Fixer(self.log, self.config.get("api_key"))
        
        # Update the API key entry in the advanced tab if it exists
        if hasattr(self, 'adv_tab') and hasattr(self.adv_tab, 'api_key_entry'):
            try:
                self.adv_tab.api_key_entry.delete(0, tk.END)
                self.adv_tab.api_key_entry.insert(0, self.config.get("api_key", ""))
            except: 
                pass

    def update_boot_start_registry(self):
        if platform.system() != "Windows": return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if self.boot_start:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
                winreg.SetValueEx(key, "War3SuperAnalyzer", 0, winreg.REG_SZ, exe_path)
            else:
                try: winreg.DeleteValue(key, "War3SuperAnalyzer")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except: pass

    def set_window_icon(self):
        try:
            # 优先从 exe 目录或资源目录查找 icon.ico
            ico_path = os.path.join(self.exe_dir, "assets", "icon.ico")
            if not os.path.exists(ico_path):
                ico_path = os.path.join(self.base_dir, "assets", "icon.ico")
            
            if platform.system() == "Windows" and os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            else:
                png_path = ico_path.replace(".ico", ".png")
                if os.path.exists(png_path):
                    img = Image.open(png_path)
                    photo = ImageTk.PhotoImage(img)
                    self.root.iconphoto(True, photo)
                    self.root._icon_photo = photo
        except Exception as e:
            print(f"Failed to set window icon: {e}")

    def setup_tray(self):
        try:
            icon_path = os.path.join(self.exe_dir, "assets", "icon.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(self.base_dir, "assets", "icon.ico")
            
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                image = Image.new('RGB', (64, 64), color=(44, 62, 80))
        except:
            image = Image.new('RGB', (64, 64), color=(44, 62, 80))

        menu = (
            item('显示主界面', self.show_window),
            item('退出程序', self.quit_app)
        )
        self.tray_icon = pystray.Icon("War3SuperAnalyzer", image, "魔兽崩溃分析工具", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        self.root.after(0, self.root.focus_force)

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
            from tkinter import filedialog
            p = filedialog.askdirectory(title="选择魔兽争霸 III 安装根目录 (包含 war3.exe)")
            if p: temp_path.set(p.replace('/', '\\'))
            
        tk.Button(sel_frame, text="浏览...", command=browse_wizard).pack(side=tk.RIGHT)

        btn_frame = tk.Frame(wizard, bg="#ffffff")
        btn_frame.pack(side=tk.BOTTOM, pady=20)

        def on_agree():
            war3_dir = temp_path.get().strip()
            if not war3_dir or (not os.path.exists(os.path.join(war3_dir, "war3.exe")) and not os.path.exists(os.path.join(war3_dir, "Warcraft III.exe"))):
                messagebox.showwarning("目录无效", "请务必选择正确的魔兽争霸根目录！\n该目录下必须包含 war3.exe 或 Warcraft III.exe。")
                return

            self.war3_path.set(war3_dir)
            self.allow_plugin = True
            self.allow_report = True
            self.first_run = False
            self.save_config()
            self.log(f"[*] 已设置魔兽目录: {war3_dir}")
            self.log("[*] 用户已同意开启增强诊断功能。")
            wizard.destroy()
            self.adv_tab.install_jassdebug()

        def on_skip():
            self.allow_plugin = False
            self.allow_report = False
            self.first_run = False
            self.save_config()
            self.log("[*] 用户跳过了首次配置，可手动在界面操作。")
            wizard.destroy()

        tk.Button(btn_frame, text="✅ 确认并开启功能", command=on_agree, bg="#27ae60", fg="white", font=("微软雅黑", 10, "bold"), width=20).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="⏭️ 跳过 (手动配置)", command=on_skip, bg="#bdc3c7", fg="#2c3e50", font=("微软雅黑", 10), width=15).pack(side=tk.LEFT, padx=10)

    def quit_app(self, icon=None, item=None):
        self.stop_reporting.set()
        if hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except: pass
        
        # 使用 destroy() 销毁所有窗口，然后安全退出
        self.root.after(0, self._force_quit)

    def _force_quit(self):
        try:
            self.root.destroy()
        except: pass
        os._exit(0)

    def on_closing(self):
        msg = "您想如何处理程序？\n\n[是]：最小化到系统托盘 (继续自动上报)\n[否]：彻底退出程序 (停止所有功能)"
        res = messagebox.askyesnocancel("退出确认", msg)
        
        if res is True: # Minimize to tray
            self.root.withdraw()
            self.log("[*] 程序已最小化到系统托盘。")
        elif res is False: # Quit
            self.quit_app()
        # if res is None (Cancel), do nothing
