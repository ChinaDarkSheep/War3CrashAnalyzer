import os
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import psutil
from gui.tabs.base import BaseTab
from engine.memory import kernel32, PROCESS_VM_READ, PROCESS_QUERY_INFORMATION, get_module_info, get_module_base, JassVMMonitor, AgentMonitor

class LocalTab(BaseTab):
    def setup_ui(self):
        main_frame = tk.Frame(self, bg="#f5f6f7", padx=5, pady=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 警告区域
        warning_frame = tk.Frame(main_frame, bg="#fff3cd", pady=5, padx=10)
        warning_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(warning_frame, text="⚠️ 安全警告：严禁在对战平台联网环境使用，否则可能导致封号！", 
                 bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold")).pack()

        # 控制栏
        control_frame = tk.Frame(main_frame, bg="#ffffff", padx=10, pady=10, highlightbackground="#dcdde1", highlightthickness=1)
        control_frame.pack(fill=tk.X, pady=5)

        self.local_monitor_btn = tk.Button(control_frame, text="🟢 开启实时监控", command=self.toggle_local_debug, 
                                          bg="#27ae60", fg="white", font=("微软雅黑", 10, "bold"), width=18)
        self.local_monitor_btn.pack(side=tk.LEFT, padx=5)

        self.snapshot_btn = tk.Button(control_frame, text="📸 句柄快照 (查泄露)", command=self.take_handle_snapshot, 
                                     bg="#f39c12", fg="white", font=("微软雅黑", 10, "bold"), width=18)
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = tk.Button(control_frame, text="🔄 重置基准", command=self.reset_baseline, 
                                   bg="#95a5a6", fg="white", font=("微软雅黑", 10, "bold"), width=12)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
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

        # Sub-tab 2: Agent Monitor
        self.agent_frame = tk.Frame(self.monitor_tabs, bg="#f5f6f7")
        self.monitor_tabs.add(self.agent_frame, text=" 引擎对象 (Agents) ")

        self.agent_tree = ttk.Treeview(self.agent_frame, columns=("name", "count", "cls"), show="headings")
        self.agent_tree.heading("name", text="对象类型 (Type)")
        self.agent_tree.heading("count", text="活动数量 (Count)")
        self.agent_tree.heading("cls", text="引擎类名 (Class)")
        self.agent_tree.column("name", width=160)
        self.agent_tree.column("count", width=80)
        self.agent_tree.column("cls", width=140)
        self.agent_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.agent_tree.bind('<<TreeviewSelect>>', self.on_agent_select)

        # Right: Details
        right_frame = tk.LabelFrame(self.paned, text=" 监控详情 (Monitor Details) ", bg="#f5f6f7")
        self.paned.add(right_frame, weight=2)

        detail_header = tk.Frame(right_frame, bg="#f5f6f7")
        detail_header.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Button(detail_header, text="🧹 清空详情", command=self.clear_details,
                  font=("微软雅黑", 8), bg="#dcdde1").pack(side=tk.RIGHT)

        self.thread_detail = scrolledtext.ScrolledText(right_frame, font=("Consolas", 9), bg="#ffffff")
        self.thread_detail.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom Info Bar
        info_bar = tk.Frame(main_frame, bg="#f5f6f7")
        info_bar.pack(fill=tk.X)
        self.process_status_label = tk.Label(info_bar, text="魔兽进程: 未找到", bg="#f5f6f7", font=("微软雅黑", 9))
        self.process_status_label.pack(side=tk.LEFT)
        self.memory_label = tk.Label(info_bar, text=" | 内存占用: 0 MB", bg="#f5f6f7", font=("微软雅黑", 9))
        self.memory_label.pack(side=tk.LEFT)
        self.handle_label = tk.Label(info_bar, text=" | 活动句柄: ---", bg="#f5f6f7", font=("微软雅黑", 9))
        self.handle_label.pack(side=tk.LEFT)

        # State
        self.local_debug_running = False
        self.vm_monitor = None
        self.agent_monitor = None

        self.last_agent_counts = {}
        self.last_total_handles = 0
        self.last_process_mem = 0
        self.current_agent_results = {}
        self.current_handles_info = None
        self.selected_agent_name = None

    def toggle_local_debug(self):
        if not self.local_debug_running:
            # 启动监控前先检测进程是否存在
            war3_pid = None
            possible_names = ["war3.exe", "warcraft iii.exe", "war3_127.exe", "frozen throne.exe"]
            for p in psutil.process_iter(['name', 'pid']):
                try:
                    if p.info['name'] and p.info['name'].lower() in possible_names:
                        war3_pid = p.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not war3_pid:
                messagebox.showwarning("魔兽未运行", "未检测到魔兽争霸进程！\n\n请确保：\n1. 已启动魔兽并进入地图\n2. 进程名是 war3.exe 或 warcraft iii.exe\n3. 如果使用了对战平台，请先启动游戏再开启监控。")
                return

            self.local_debug_running = True
            self.local_monitor_btn.config(text="🛑 停止实时监控", bg="#c0392b")
            self.thread_detail.delete(1.0, tk.END)
            self.log_local("[*] 正在寻找 war3.exe 进程...")
            self.log_local(f"[*] 目标 PID: {war3_pid}")
            self.log_local("[*] 正在读取 1.27a 的 CGameWar3 / 句柄表 ...")
            
            threading.Thread(target=self.local_debug_worker, daemon=True).start()
            self.update_status("正在初始化监控...")
        else:
            self.local_debug_running = False
            self.on_monitor_stopped()
            self.log_local("[*] 监控已停止。")

    def local_debug_worker(self):
        war3_pid = None
        possible_names = ["war3.exe", "warcraft iii.exe", "war3_127.exe", "frozen throne.exe"]
        for p in psutil.process_iter(['name', 'pid']):
            try:
                if p.info['name'] and p.info['name'].lower() in possible_names:
                    war3_pid = p.info['pid']
                    break
            except: continue
        
        if not war3_pid:
            self.app.root.after(0, lambda: self.log_local("[-] 错误: 监控线程启动后丢失进程句柄。"))
            self.app.root.after(0, self.on_monitor_stopped)
            return

        h_process = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, war3_pid)
        if not h_process:
            self.app.root.after(0, lambda: messagebox.showerror("权限不足", "无法读取魔兽内存！\n\n请尝试以【管理员身份】运行本程序。"))
            self.app.root.after(0, self.on_monitor_stopped)
            return

        try:
            game_base, game_size = get_module_info(war3_pid, "game.dll")
            if not game_base:
                self.app.root.after(0, lambda: self.log_local("[-] 错误: 无法在进程中定位 game.dll。"))
                self.app.root.after(0, lambda: self.process_status_label.config(text="魔兽进程: 无法定位 game.dll", fg="#e74c3c"))
                self.app.root.after(0, self.on_monitor_stopped)
                return

            self.vm_monitor = JassVMMonitor(h_process, game_base, game_size)
            self.agent_monitor = AgentMonitor(h_process, game_base, game_size, self.vm_monitor)

            if self.vm_monitor.GAME_WAR3:
                self.app.root.after(0, self.log_local,
                                    f"[*] CGameWar3: {hex(self.vm_monitor.GAME_WAR3)}"
                                    f" (RVA {hex(self.vm_monitor.GAME_WAR3 - game_base)})")
                self.app.root.after(0, self.log_local,
                                    f"[*] CGameState: {hex(self.vm_monitor.GAME_STATE)}")
            else:
                self.app.root.after(0, self.log_local,
                                    "[-] 未读到 CGameWar3 锚点。实时监控目前只适配 1.27a (1.27.0.52240)，"
                                    "请确认游戏版本与权限。")

            ht_info = self.vm_monitor.get_jass_handles_info()
            if ht_info:
                self.app.root.after(0, self.log_local,
                                    f"[+] 句柄表: 活动 {ht_info['active']} / 容量 {ht_info['total']}"
                                    f" (表地址 {hex(ht_info['table'])})")
            else:
                self.app.root.after(0, self.log_local, "[-] 未能读取句柄表，引擎对象将无法显示。")

            self.app.root.after(0, self.mark_threads_unsupported)
            self.app.root.after(0, lambda: self.update_status("实时监控运行中"))
            p_process = psutil.Process(war3_pid)

            while self.local_debug_running:
                try:
                    # 检查进程是否还活着
                    if not p_process.is_running():
                        break

                    # 1. 更新基础信息
                    mem = p_process.memory_info().private / (1024 * 1024)
                    self.app.root.after(0, self.update_basic_info, war3_pid, mem)

                    # 2. 读取句柄表与对象类型统计
                    handles_info = self.vm_monitor.get_jass_handles_info()
                    agent_results = self.agent_monitor.get_object_counts() if handles_info else {}
                    self.current_handles_info = handles_info
                    self.current_agent_results = agent_results

                    # 3. 更新 UI 树
                    self.app.root.after(0, self.update_agent_tree, agent_results, handles_info)

                    # 如果有选中的对象类型，更新详情
                    if self.selected_agent_name:
                        self.app.root.after(0, self.update_agent_detail)

                except Exception as e:
                    print(f"Monitor loop error: {e}")

                time.sleep(1)

        finally:
            kernel32.CloseHandle(h_process)
            self.local_debug_running = False
            self.app.root.after(0, self.on_monitor_stopped)

    def update_basic_info(self, pid, mem):
        self.last_process_mem = mem
        self.process_status_label.config(text=f"魔兽进程: 已找到 (PID: {pid})", fg="#27ae60")
        self.memory_label.config(text=f" | 内存占用: {mem:.1f} MB")

    def on_monitor_stopped(self):
        self.process_status_label.config(text="魔兽进程: 已停止", fg="#7f8c8d")
        self.memory_label.config(text=" | 内存占用: 0 MB")
        self.local_monitor_btn.config(text="🟢 开启实时监控", bg="#27ae60")

    def mark_threads_unsupported(self):
        self.thread_list.delete(0, tk.END)
        self.thread_list.insert(tk.END, "1.27a 暂不支持读取 JASS 线程列表")
        self.thread_list.itemconfig(0, {'fg': '#7f8c8d'})
        self.thread_list.insert(tk.END, "已定位句柄表，可在“引擎对象”查看实时对象数")
        self.thread_list.itemconfig(1, {'fg': '#7f8c8d'})

    def update_agent_tree(self, results, handles_info):
        selected_items = self.agent_tree.selection()
        selected_name = self.agent_tree.item(selected_items[0])['values'][0] if selected_items else None

        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)

        for name, data in results.items():
            item_id = self.agent_tree.insert("", tk.END,
                                             values=(name, data['count'], data.get('class', '')))
            if selected_name == name:
                self.agent_tree.selection_set(item_id)

        if handles_info:
            self.handle_label.config(text=f" | 活动句柄数: {handles_info['active']} (总计: {handles_info['total']})")
        else:
            self.handle_label.config(text=" | 活动句柄数: <无法读取>")

    def on_agent_select(self, event):
        selection = self.agent_tree.selection()
        if selection:
            item = self.agent_tree.item(selection[0])
            self.selected_agent_name = item['values'][0]
            self.update_agent_detail()

    def update_agent_detail(self):
        if not self.selected_agent_name:
            return

        name = self.selected_agent_name
        data = self.current_agent_results.get(name)

        self.thread_detail.delete(1.0, tk.END)
        self.thread_detail.insert(tk.END, f"--- 对象详情: {name} ---\n\n")
        if data:
            self.thread_detail.insert(tk.END, f"活动数量 (Active): {data['count']}\n")
            self.thread_detail.insert(tk.END, f"引擎类名 (Class): {data.get('class') or '未识别'}\n\n")
            self.thread_detail.insert(
                tk.END,
                "[说明] 数量来自实时句柄表统计，表示当前仍被 JASS 引用的对象数。\n"
                "该数字持续上涨且不回落，通常意味着脚本漏调销毁函数"
                "（如 RemoveLocation / RemoveUnit / DestroyGroup）。")
        else:
            self.thread_detail.insert(tk.END, "暂无数据。请确保魔兽已启动并加载地图，且该对象类型当前存在。")

    def log_local(self, message):
        """专门用于本地调试详情窗口的日志输出"""
        self.thread_detail.insert(tk.END, message + "\n")
        self.thread_detail.see(tk.END)

    def reset_baseline(self):
        # 即使 handles_info 为空，也允许重置 Agent 基准
        if not self.local_debug_running:
            messagebox.showinfo("提示", "请先开启监控。")
            return
            
        if self.current_handles_info:
            self.last_total_handles = self.current_handles_info['active']
        
        self.last_agent_counts = {k: v['count'] for k, v in self.current_agent_results.items()}
        self.log_local("[*] 句柄快照基准已重置。")
        messagebox.showinfo("重置成功", "已将当前状态设为对比基准。")

    def clear_details(self):
        self.thread_detail.delete(1.0, tk.END)
        self.log_local("[*] 已清空详情日志窗口。")

    def take_handle_snapshot(self):
        if not self.local_debug_running:
            messagebox.showwarning("错误", "请先启动实时监控！")
            return

        self.log_local("\n====== 📸 句柄快照分析 ======")
        self.update_status("正在捕获句柄快照...")
        
        # 1. 分析全局句柄
        if self.current_handles_info:
            cur_handles = self.current_handles_info['active']
            delta_handles = cur_handles - self.last_total_handles
            trend = f"+{delta_handles}" if delta_handles >= 0 else str(delta_handles)
            self.log_local(f"活动句柄总数: {cur_handles} (变化: {trend})")
            if delta_handles > 100:
                self.log_local("⚠️ 警告: 句柄总数激增！")
            self.last_total_handles = cur_handles
        else:
            self.log_local("活动句柄总数: <无法读取>")
        
        # 2. 分析引擎对象 (Agents)
        self.log_local("--- 对象变化 (Agents) ---")
        for name, data in self.current_agent_results.items():
            cur_count = data['count']
            last_count = self.last_agent_counts.get(name, 0)
            delta_count = cur_count - last_count
            
            if delta_count != 0:
                trend = f"+{delta_count}" if delta_count >= 0 else str(delta_count)
                warning = " ⚠️(疑似泄露)" if delta_count > 20 else ""
                self.log_local(f" - {name}: {cur_count} ({trend}){warning}")
            
            self.last_agent_counts[name] = cur_count
        
        self.log_local("==========================\n")
        self.update_status("句柄快照捕获完毕")
