import os
import threading
import time
import hashlib
import urllib.request
import json
import platform
from tkinter import messagebox
from core.auditor import Auditor
from core.history import HistoryTracker
from core.logtext import read_log

class Reporter:
    def __init__(self, log_func, base_dir=None):
        self.log = log_func
        if base_dir:
            db_path = os.path.join(base_dir, "history.db")
            self.history = HistoryTracker(db_path)
        else:
            self.history = None
        
        # 创建一个不输出到 UI 的静默分析器
        self.silent_auditor = Auditor(lambda x: None, lambda x: None, base_dir)

    def report_crash_to_server(self, war3_dir, map_path, is_auto=False):
        if not war3_dir:
            if not is_auto:
                self.log("[-] 上报失败：未配置魔兽目录。")
                messagebox.showwarning("提示", "请先在设置或主界面配置魔兽安装目录！")
            return
            
        error_dir = os.path.join(war3_dir, "Errors")
        if not os.path.exists(error_dir):
            if not is_auto:
                self.log("[-] 上报失败：未在魔兽目录找到 Errors 文件夹。")
                messagebox.showinfo("提示", "未找到任何崩溃日志记录。")
            return
            
        logs = [f for f in os.listdir(error_dir) if f.endswith('.txt')]
        if not logs:
            if not is_auto:
                self.log("[-] 上报失败：Errors 文件夹内无日志文件。")
                messagebox.showinfo("提示", "未找到任何崩溃日志文件 (.txt)。")
            return
            
        # 筛选未上报的日志
        unreported_logs = []
        for f in logs:
            status = self.history.get_log_status(f) if self.history else None
            if not status or not status.get("reported", False):
                unreported_logs.append(f)
        
        if not unreported_logs:
            if not is_auto:
                self.log("[提示] 所有崩溃日志均已上报过。")
                messagebox.showinfo("提示", "所有崩溃日志均已上报过。")
            return

        # 排序，优先上报最新的
        unreported_logs.sort(key=lambda x: os.path.getmtime(os.path.join(error_dir, x)), reverse=True)
        
        total = len(unreported_logs)
        self.log(f"[*] 发现 {total} 份未上报日志，准备开始批量上报...")
        
        if not is_auto:
            if not messagebox.askyesno("用户许可", f"发现 {total} 份未上报的崩溃日志，是否将它们及基本系统信息发送给开发者进行分析？\n\n这有助于我们改进工具并定位崩溃原因。"):
                return

        success_count = 0
        for i, target_log_name in enumerate(unreported_logs):
            self.log(f"[*] [{i+1}/{total}] 正在上报: {target_log_name}...")
            latest_log = os.path.join(error_dir, target_log_name)
            
            try:
                log_content = read_log(latest_log)
                
                content_hash = hashlib.md5(log_content.encode('utf-8')).hexdigest()
                
                # 本地预分析（get_analysis_data 返回 5 元组：addr, relative_offset, analysis_text, map_name, module_name）
                addr, rel_offset, analysis, log_map_name, log_mod_name = self.silent_auditor.get_analysis_data(log_content)
                
                # 优先使用从日志里提取的地图名，如果没有再使用界面上的
                final_map_name = log_map_name if log_map_name != "Unknown" else (os.path.basename(map_path) if map_path else "Unknown")
                
                report_data = {
                    "os": platform.platform(),
                    "processor": platform.processor(),
                    "python_version": platform.python_version(),
                    "map": final_map_name,
                    "log_name": os.path.basename(latest_log),
                    "log_content": log_content[:5000],
                    "crash_address": rel_offset if rel_offset else addr,
                    "analysis_result": analysis,
                    "timestamp": time.time(),
                    "content_hash": content_hash
                }
                
                urls = [
                    "http://ca.darksheep.vip/api/report",
                    "http://43.163.75.93:2234/api/report"
                ]
                
                log_success = False
                for url in urls:
                    try:
                        data = json.dumps(report_data).encode('utf-8')
                        req = urllib.request.Request(
                            url, 
                            data=data, 
                            headers={
                                'Content-Type': 'application/json',
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) War3SuperAnalyzer/13.0'
                            }
                        )
                        
                        with urllib.request.urlopen(req, timeout=10) as response:
                            res = json.loads(response.read().decode('utf-8'))
                            if res.get('status') in ["success", "duplicate"]:
                                if self.history:
                                    self.history.mark_reported(target_log_name, content_hash)
                                log_success = True
                                break
                    except Exception:
                        continue
                
                if log_success:
                    success_count += 1
                    # 避免请求过快
                    if i < total - 1:
                        time.sleep(0.5)
                else:
                    self.log(f"[-] [{i+1}/{total}] 上报失败。")

            except Exception as e:
                self.log(f"[-] [{i+1}/{total}] 发生错误: {e}")

        self.log(f"[+] 批量上报完成: 成功 {success_count} / {total}")
        if not is_auto and success_count > 0:
            messagebox.showinfo("完成", f"已成功上报 {success_count} 份崩溃日志！")

    def periodic_report_worker(self, stop_event, app):
        while not stop_event.is_set():
            if app.allow_report:
                war3_path = app.war3_path.get()
                map_path = app.map_path.get()
                self.report_crash_to_server(war3_path, map_path, is_auto=True)
            
            # Wait for interval
            for _ in range(app.report_interval * 60):
                if stop_event.is_set(): break
                time.sleep(1)
