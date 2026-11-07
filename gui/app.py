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
from core.watcher import CrashLogWatcher
from gui.tabs.static_tab import StaticTab
from gui.tabs.records_tab import RecordsTab
from gui.tabs.health_tab import HealthTab
from gui.tabs.adv_tab import AdvTab

CONFIG_FILE = "analyzer_config.json"

class War3SuperAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("魔兽 RPG 崩溃分析工具 v1.1.0 - By DarkSheep (肥羊小站)")
        self.root.geometry("1100x840")
        self.root.minsize(1000, 680)
        self.root.configure(bg="#f5f6f7")

        self.map_path = tk.StringVar()
        self.war3_path = tk.StringVar()
        
        if getattr(sys, 'frozen', False):
            self.base_dir = sys._MEIPASS          # 只读资源目录
            self.exe_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            self.exe_dir = self.base_dir
        # 可写数据目录：冻结后 _MEIPASS 退出即删，历史库/报告必须落在 exe 同级
        self.data_dir = self.exe_dir
            
        self.mpq_editor_path = os.path.join(self.base_dir, "MPQEditor.exe")
        
        self.first_run = True
        self.allow_plugin = False
        self.allow_report = False
        self.report_interval = 30
        self.boot_start = False
        self.min_to_tray = True
        self.auto_collect = True
        self.status_var = tk.StringVar(value="就绪 | 模块化重构版")
        self.report_area = None # Will be set by StaticTab
        self.config = {}

        # Initialize core components that depend on config
        self.reporter = Reporter(self.log, self.data_dir)
        self.load_config() # Load before UI setup to set variables
        
        if platform.system() == "Windows":
            try:
                myappid = 'darksheep.war3analyzer.1.1'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
                
        self.setup_ui()
        self.setup_tray()
        self.set_window_icon()

        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        if self.first_run or not self.war3_path.get():
            self.root.after(500, self.show_welcome_wizard)

        self.stop_reporting = threading.Event()
        threading.Thread(target=self.reporter.periodic_report_worker, 
                         args=(self.stop_reporting, self), 
                         daemon=True).start()

        self.start_crash_watcher()

    def start_crash_watcher(self):
        self.stop_watcher = threading.Event()
        self.crash_watcher = CrashLogWatcher(
            get_war3_path=lambda: self.war3_path.get().strip('"'),
            get_enabled=lambda: self.auto_collect,
            on_new_log=self.handle_new_crash,
            log=self._watch_log)
        threading.Thread(target=self.crash_watcher.run,
                         args=(self.stop_watcher,), daemon=True).start()

    def _watch_log(self, message):
        try:
            self.root.after(0, self.log, message)
        except Exception:
            pass

    def handle_new_crash(self, log_path):
        try:
            result = self.static_tab.auditor.analyze_log_file(log_path)
        except Exception as e:
            self._watch_log(f"[-] 自动诊断失败: {os.path.basename(log_path)}: {e}")
            return
        try:
            self.root.after(0, lambda: self.show_new_crash(log_path, result))
        except Exception:
            pass

    def show_new_crash(self, log_path, result):
        conclusion = result.get("conclusion") or {}
        attribution = conclusion.get("attribution") or "暂无法确定"
        confidence = int(round((conclusion.get("confidence") or 0) * 100))
        summary = conclusion.get("summary") or "未能定位具体原因"
        map_name = result.get("map_name")
        map_text = map_name if map_name and map_name != "Unknown" else "地图未知"

        self.log("")
        self.log(f"[自动收集] 检测到新崩溃: {os.path.basename(log_path)}")
        if conclusion.get("text"):
            for line in conclusion["text"].splitlines():
                self.log("  " + line)
        else:
            self.log(f"  {summary}")
        detail = result.get("detail_text")
        if detail:
            self.log(f"  补充依据：{detail}")

        fingerprint = result.get("fingerprint")
        stats = result.get("fingerprint_stats")
        if fingerprint:
            count = stats["samples"] if stats else 1
            maps = stats["maps"] if stats else 0
            map_part = f"涉及 {maps} 张地图" if maps else "地图未知"
            self.log(f"  栈指纹 {fingerprint['signature']}"
                     f"（{fingerprint['version']}）：累计 {count} 次，{map_part}")

        self.update_status(f"自动诊断：{attribution} · 置信度 {confidence}%")
        notice = f"{map_text} · {attribution} · {confidence}%\n{summary[:70]}"
        try:
            self.tray_icon.notify(notice, "检测到新的魔兽崩溃")
        except Exception:
            pass

    def setup_ui(self):
        # Header (Simplified for example)
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="魔兽RPG崩溃分析工具 v1.1.0", font=("Segoe UI", 14, "bold"), fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=20)

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.static_tab = StaticTab(self.notebook, self)
        self.notebook.add(self.static_tab, text=" 崩溃诊断 ")

        self.records_tab = RecordsTab(self.notebook, self)
        self.notebook.add(self.records_tab, text=" 崩溃记录 ")

        self.health_tab = HealthTab(self.notebook, self)
        self.notebook.add(self.health_tab, text=" 地图体检 ")

        self.adv_tab = AdvTab(self.notebook, self)
        self.notebook.add(self.adv_tab, text=" 高级与设置 ")

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

    def open_upload_dialog(self, preferred_log=None):
        from gui.upload_dialog import UploadLogsDialog
        dialog = getattr(self, "upload_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            if preferred_log:
                dialog.set_crash_log(preferred_log)
            dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            return dialog
        self.upload_dialog = UploadLogsDialog(self.root, self, preferred_log)
        return self.upload_dialog

    def open_upload_status_dialog(self):
        from gui.upload_status_dialog import UploadStatusDialog
        dialog = getattr(self, "upload_status_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            return dialog
        self.upload_status_dialog = UploadStatusDialog(self.root, self)
        return self.upload_status_dialog

    def upload_latest_crash(self, icon=None, item=None):
        self.show_window()
        self.root.after(100, self.open_upload_dialog)

    def save_config(self):
        config = {
            "war3_path": self.war3_path.get(), 
            "map_path": self.map_path.get(),
            "first_run": self.first_run,
            "allow_plugin": self.allow_plugin,
            "allow_report": self.allow_report,
            "report_interval": self.report_interval,
            "boot_start": self.boot_start,
            "min_to_tray": self.min_to_tray,
            "auto_collect": self.auto_collect,
            "kk_log_path": self.config.get("kk_log_path", ""),
            "last_upload_code": self.config.get("last_upload_code", "")
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
        self.auto_collect = config.get("auto_collect", True)

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
            item('上传最近崩溃日志', self.upload_latest_crash),
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
   - 作用：本地客户端崩溃时弹出 JASS 语句、函数链与代码偏移；
     可在「高级与设置 → 插件与上报」点击“解析弹窗”读取并解析。

2. 自动上报崩溃日志：
   - 目的：收集大数据，优化通用崩溃库，帮助所有作者定位问题。
   - 隐私：会上传崩溃日志的文本内容（其中可能包含 Windows 用户名、计算机名和本地路径）、
     系统版本与地图名。如不希望上传，可在「高级与设置」中关闭自动上报。"""
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
        if hasattr(self, 'stop_watcher'):
            self.stop_watcher.set()
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
        if self.min_to_tray:
            self.root.withdraw()
            self.log("[*] 程序已最小化到系统托盘。")
            return

        if messagebox.askyesno("退出确认", "确定要彻底退出程序吗？\n退出后将停止自动上报等后台功能。"):
            self.quit_app()
