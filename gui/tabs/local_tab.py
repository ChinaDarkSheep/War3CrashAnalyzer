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
        self.thread_list.bind('<<ListboxSelect>>', self.on_thread_select)

        # Sub-tab 2: Agent Monitor
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
        self.handle_label = tk.Label(info_bar, text=" | 活动句柄估计: ---", bg="#f5f6f7", font=("微软雅黑", 9))
        self.handle_label.pack(side=tk.LEFT)

        # State
        self.local_debug_running = False
        self.selected_thread_ptr = None
        self.vm_monitor = None
        self.agent_monitor = None
        self.agent_offsets = {
            "Group (单位组)": 0x00,
            "Location (点)": 0x20,
            "Unit (单位)": 0x40,
            "Item (物品)": 0x60,
            "Bullet (投射物)": 0x80,
            "Destructable (可破坏物)": 0xA0,
            "Doodad (装饰物)": 0xC0,
            "Timer (计时器)": 0xE0,
            "Trigger (触发器)": 0x100,
        }
        
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
            self.log_local("[*] 正在全内存扫描真实的 HandleTable 和 JassEnv ...")
            
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
            self.agent_monitor = AgentMonitor(h_process, game_base, game_size)
            
            # 记录偏移量探测结果到日志
            if self.vm_monitor.GAME_WAR3:
                self.app.root.after(0, self.log_local, f"[*] 已自动适配 GameWar3 偏移: {hex(self.vm_monitor.GAME_WAR3 - game_base)}")
            
            # 尝试通过启发式强制读取 JassEnv 以输出绝对地址
            env_addr = self.vm_monitor.get_jass_env()
            if env_addr:
                self.app.root.after(0, self.log_local, f"[+] 成功定位 JassEnv (线程池): {hex(env_addr)}")
            else:
                self.app.root.after(0, self.log_local, "[-] 警告: 未能通过雷达扫描定位到 JassEnv。")
            
            ht_info = self.vm_monitor.get_jass_handles_info()
            if ht_info:
                self.app.root.after(0, self.log_local, f"[+] 成功定位 HandleTable, 当前活跃数: {ht_info['active']}")
            else:
                self.app.root.after(0, self.log_local, "[-] 警告: 未能通过雷达扫描定位到 HandleTable。")
                
            if self.agent_monitor.generator_base:
                self.app.root.after(0, self.log_local, f"[*] 成功定位 AgentGenerator: {hex(self.agent_monitor.generator_base)}")
            else:
                self.app.root.after(0, self.log_local, "[-] 警告: 未找到 AgentGenerator 基址，引擎对象将无法显示。")
            
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
                    
                    # 2. 读取 JASS 线程
                    instances = self.vm_monitor.get_active_instances()
                    if not instances and time.time() % 10 < 1:
                        self.log_local("[!] 未探测到活跃 JASS 线程，请确保已进入地图并正在运行脚本。")
                    self.app.root.after(0, self.update_thread_list, instances)
                    
                    # 3. 如果有选中的线程，更新详情
                    if self.selected_thread_ptr:
                        info = self.vm_monitor.get_instance_info(self.selected_thread_ptr)
                        self.app.root.after(0, self.update_thread_detail, info)
                    
                    # 4. 读取引擎对象 (Agents)
                    agent_results = {}
                    base = self.agent_monitor.generator_base
                    if base:
                        for name, relative_off in self.agent_offsets.items():
                            data = self.agent_monitor.get_agent_data(base + relative_off)
                            if data:
                                agent_results[name] = data
                    else:
                        # 兼容直接从 generator_base 失败的情况，有些版本是绝对地址
                        for name, offset in self.agent_offsets.items():
                            if offset > 0x100000: # 这意味着它可能是旧的绝对地址
                                data = self.agent_monitor.get_agent_data(offset)
                                if data:
                                    agent_results[name] = data
                    
                    self.current_agent_results = agent_results
                    
                    # 5. 读取全局句柄
                    handles_info = self.vm_monitor.get_jass_handles_info()
                    self.current_handles_info = handles_info
                    
                    # 6. 更新 UI 树
                    self.app.root.after(0, self.update_agent_tree, agent_results, handles_info)
                    
                    # 如果有选中的 Agent，更新详情
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

    def update_thread_list(self, instances):
        current_selection = self.thread_list.curselection()
        selected_text = self.thread_list.get(current_selection[0]) if current_selection else None
        
        self.thread_list.delete(0, tk.END)
        for idx, inst in enumerate(instances):
            info = self.vm_monitor.get_instance_info(inst)
            call_stack = info.get('call_stack', [])
            
            # 将生硬的十六进制转化为易读的中文状态
            if not call_stack and not info['op_ptr']:
                status = "[空闲]"
                color = "#27ae60"  # 绿色
            else:
                status = "[挂起/阻塞]"
                color = "#e74c3c"  # 红色
                
            text = f"线程 {idx} {status} (ID:{hex(inst)[-4:]})"
            self.thread_list.insert(tk.END, text)
            self.thread_list.itemconfig(idx, {'fg': color})
            
            # 用隐藏属性绑定真实的指针
            if not hasattr(self, 'thread_ptr_map'):
                self.thread_ptr_map = {}
            self.thread_ptr_map[text] = inst
            
            if selected_text == text:
                self.thread_list.selection_set(idx)

    def update_agent_tree(self, results, handles_info):
        # 保存当前选中项的 ID
        selected_items = self.agent_tree.selection()
        selected_name = self.agent_tree.item(selected_items[0])['values'][0] if selected_items else None

        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)
        
        total_agent_mem = 0
        for name, data in results.items():
            mem_mb = data['total_mem'] / (1024 * 1024)
            total_agent_mem += mem_mb
            item_id = self.agent_tree.insert("", tk.END, values=(name, f"{data['active']} / {data['count']}", f"{mem_mb:.2f} MB"))
            if selected_name == name:
                self.agent_tree.selection_set(item_id)
        
        if handles_info:
            self.handle_label.config(text=f" | 活动句柄数: {handles_info['active']} (总计: {handles_info['total']})")
        else:
            self.handle_label.config(text=" | 活动句柄数: <无法读取>")
            
        # 在内存占用标签后增加 Agent 总内存显示
        self.memory_label.config(text=f" | 内存占用: {self.last_process_mem:.1f} MB (引擎对象: {total_agent_mem:.2f} MB)")

    def update_thread_detail(self, info):
        self.thread_detail.delete(1.0, tk.END)
        
        # 配置颜色标签
        self.thread_detail.tag_config('label', foreground='#34495e', font=('Microsoft YaHei', 10, 'bold'))
        self.thread_detail.tag_config('value', foreground='#2c3e50', font=('Consolas', 10))
        self.thread_detail.tag_config('hex', foreground='#2980b9', font=('Consolas', 10, 'bold'))
        self.thread_detail.tag_config('stack_title', foreground='#8e44ad', font=('Microsoft YaHei', 10, 'bold'))
        self.thread_detail.tag_config('idle', foreground='#27ae60', font=('Consolas', 10))
        self.thread_detail.tag_config('warning', foreground='#e67e22', font=('Consolas', 10))
        self.thread_detail.tag_config('error', foreground='#e74c3c', font=('Consolas', 10, 'bold'))
        self.thread_detail.tag_config('tip', foreground='#7f8c8d', font=('微软雅黑', 9))
        self.thread_detail.tag_config('header', foreground='#ffffff', background='#34495e', font=('微软雅黑', 10, 'bold'))
        
        self.thread_detail.insert(tk.END, " 线程运行时状态详情 (JASS Thread Runtime) \n", 'header')
        self.thread_detail.insert(tk.END, "\n")
        
        def insert_kv(label, value, value_tag='value'):
            self.thread_detail.insert(tk.END, f" ➤ {label}: ", 'label')
            self.thread_detail.insert(tk.END, f"{value}\n", value_tag)
            
        insert_kv("实例指针 (Instance)", info['ptr'], 'hex')
        insert_kv("是否子线程 (Child)", '是 (Yes)' if info['is_child'] else '否 (No)')
        
        op_ptr_val = hex(info['op_ptr']) if info['op_ptr'] else '0x0'
        insert_kv("当前指令指针 (Opcode)", op_ptr_val, 'hex')
        
        if 'op_offset' in info:
            insert_kv("代码偏移量 (Offset)", hex(info['op_offset']), 'hex')
        
        self.thread_detail.insert(tk.END, "\n 📜 调用栈 (Call Stack) \n", 'stack_title')
        
        call_stack = info.get('call_stack', [])
        offsets = info.get('call_stack_offsets', [])
        
        if not call_stack:
            self.thread_detail.insert(tk.END, "   [状态: 空闲 / Empty]\n", 'idle')
        else:
            for i, addr in enumerate(reversed(call_stack)):
                idx = len(call_stack) - 1 - i
                offset_str = ""
                if idx < len(offsets):
                    offset_str = f" (偏移: {hex(offsets[idx])})"
                self.thread_detail.insert(tk.END, f"   [层级 {i}] 返回地址: {hex(addr)}{offset_str}\n", 'warning')
            
            # Print current frame at the top
            offset_str = ""
            if 'op_offset' in info:
                offset_str = f" (偏移: {hex(info['op_offset'])})"
            self.thread_detail.insert(tk.END, f"   [当前] 执行位置: {op_ptr_val}{offset_str} ⬅\n", 'error')
            
        # --- 诊断提示 ---
        self.thread_detail.insert(tk.END, "\n" + "-"*40 + "\n")
        self.thread_detail.insert(tk.END, "💡 诊断建议 (Diagnosis):\n", 'label')
        if not call_stack and not info['op_ptr']:
            self.thread_detail.insert(tk.END, "当前线程处于休眠或空闲状态。这是正常的，意味着脚本当前没有挂起的等待任务。\n", 'tip')
        else:
            self.thread_detail.insert(tk.END, "检测到活跃指令或挂起的调用栈。如果偏移量长期不变，可能存在死循环或超长等待(TriggerSleepAction)。\n", 'tip')

    def on_thread_select(self, event):
        selection = self.thread_list.curselection()
        if selection:
            text = self.thread_list.get(selection[0])
            if hasattr(self, 'thread_ptr_map') and text in self.thread_ptr_map:
                self.selected_thread_ptr = self.thread_ptr_map[text]
                self.selected_agent_name = None
            else:
                self.selected_thread_ptr = None

    def on_agent_select(self, event):
        selection = self.agent_tree.selection()
        if selection:
            item = self.agent_tree.item(selection[0])
            self.selected_agent_name = item['values'][0]
            # 清除 Thread 选中状态
            self.selected_thread_ptr = None
            self.update_agent_detail()

    def update_agent_detail(self):
        if not hasattr(self, 'selected_agent_name') or not self.selected_agent_name:
            return
            
        name = self.selected_agent_name
        data = self.current_agent_results.get(name)
        
        self.thread_detail.delete(1.0, tk.END)
        self.thread_detail.insert(tk.END, f"--- 对象详情: {name} ---\n\n")
        if data:
            self.thread_detail.insert(tk.END, f"活动数量 (Active): {data['active']}\n")
            self.thread_detail.insert(tk.END, f"总计分配 (Total): {data['count']}\n")
            self.thread_detail.insert(tk.END, f"单对象大小: {data['size']} Bytes\n")
            self.thread_detail.insert(tk.END, f"总内存占用: {data['total_mem']/(1024*1024):.2f} MB\n\n")
            self.thread_detail.insert(tk.END, f"内存偏移量 (Offset): {hex(self.agent_offsets.get(name, 0))}\n")
            self.thread_detail.insert(tk.END, "\n[提示] 魔兽争霸 3 的对象池是按需分配的。\n如果数量激增且不下降，通常意味着脚本中漏掉了销毁函数（如 RemoveLocation）。")
        else:
            self.thread_detail.insert(tk.END, "暂无数据。请确保魔兽已启动并加载地图。")

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
