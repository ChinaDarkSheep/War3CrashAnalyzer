"""作者工具：导入诊断包或云端指纹，定位地图脚本中的相关 API 调用。"""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core.map_extract import find_w3x2lni
from core.pjass import find_pjass
from core.script_locator import (
    build_report,
    default_hints,
    fetch_cloud_fingerprint,
    knowledge_for,
    load_fingerprint_file,
    locate_map,
    parse_hints,
)

DEFAULT_SERVER = "http://43.163.75.93:2234"


class FingerprintLocatorDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("崩溃指纹定位 - 作者工具")
        self.geometry("980x780")
        self.transient(parent)
        self.fingerprint = None
        self.knowledge = None
        self.last_report = ""
        self._messages = queue.Queue()

        self.map_path = tk.StringVar(value=self.app.map_path.get())
        self.source_path = tk.StringVar()
        self.server_url = tk.StringVar(value=DEFAULT_SERVER)
        self.signature = tk.StringVar()
        self.hints = tk.StringVar()
        tool_base = (getattr(self.app, "exe_dir", None)
                     or getattr(self.app, "base_dir", None))
        self.pjass_path = tk.StringVar(value=find_pjass(tool_base) or "")
        self.w3x2lni_path = tk.StringVar(value=find_w3x2lni(tool_base) or "")

        self._build_ui()
        self.after(100, self._drain_messages)

    def _drain_messages(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            while True:
                message = self._messages.get_nowait()
                if message[0] == "log":
                    self._append(message[1])
                elif message[0] == "finish":
                    self._finish(message[1], message[2])
        except queue.Empty:
            pass
        try:
            self.after(100, self._drain_messages)
        except tk.TclError:
            pass

    def _build_ui(self):
        body = ttk.Frame(self, padding=8)
        body.pack(fill=tk.BOTH, expand=True)

        map_frame = ttk.LabelFrame(body, text=" 1. 地图 ", padding=6)
        map_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(map_frame, text="地图文件:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(map_frame, textvariable=self.map_path).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(map_frame, text="浏览", width=8,
                   command=self._browse_map).grid(row=0, column=2)
        map_frame.columnconfigure(1, weight=1)

        source_frame = ttk.LabelFrame(body, text=" 2. 故障来源 ", padding=6)
        source_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(source_frame, text="诊断包/JSON:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(source_frame, textvariable=self.source_path).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(source_frame, text="浏览", width=8,
                   command=self._browse_source).grid(row=0, column=2)
        ttk.Button(source_frame, text="读取", width=8,
                   command=self._load_source).grid(row=0, column=3, padx=(4, 0))

        ttk.Label(source_frame, text="云端指纹:").grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(source_frame, textvariable=self.signature, width=18).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=(6, 0))
        ttk.Label(source_frame, text="服务端:").grid(
            row=1, column=2, sticky=tk.E, pady=(6, 0))
        ttk.Entry(source_frame, textvariable=self.server_url).grid(
            row=1, column=3, sticky=tk.EW, padx=(4, 4), pady=(6, 0))
        ttk.Button(source_frame, text="获取", width=8,
                   command=self._fetch_cloud).grid(row=1, column=4, pady=(6, 0))
        source_frame.columnconfigure(1, weight=1)
        source_frame.columnconfigure(3, weight=1)

        self.fp_info = ttk.Label(
            source_frame, text="未导入故障信息；也可直接填写下方 API 手动定位。",
            foreground="#555555", justify=tk.LEFT, wraplength=900)
        self.fp_info.grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))

        locate_frame = ttk.LabelFrame(body, text=" 3. 定位与语法检查 ", padding=6)
        locate_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(locate_frame, text="定位 API:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(locate_frame, textvariable=self.hints).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Label(locate_frame, text="逗号分隔；GroupEnum* 表示前缀",
                  foreground="#666666").grid(
            row=0, column=2, columnspan=2, sticky=tk.W)

        ttk.Label(locate_frame, text="pjass:").grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(locate_frame, textvariable=self.pjass_path).grid(
            row=1, column=1, sticky=tk.EW, padx=5, pady=(6, 0))
        ttk.Button(locate_frame, text="浏览", width=8,
                   command=self._browse_pjass).grid(row=1, column=2, pady=(6, 0))
        ttk.Label(locate_frame, text="仅语法检查，无需 common.j",
                  foreground="#666666").grid(
            row=1, column=3, sticky=tk.W, padx=(6, 0), pady=(6, 0))

        ttk.Label(locate_frame, text="w3x2lni:").grid(
            row=2, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(locate_frame, textvariable=self.w3x2lni_path).grid(
            row=2, column=1, sticky=tk.EW, padx=5, pady=(6, 0))
        ttk.Button(locate_frame, text="浏览", width=8,
                   command=self._browse_w3x2lni).grid(row=2, column=2, pady=(6, 0))
        ttk.Label(locate_frame, text="可选；未配置时回退 MPQEditor",
                  foreground="#666666").grid(
            row=2, column=3, sticky=tk.W, padx=(6, 0), pady=(6, 0))

        actions = ttk.Frame(locate_frame)
        actions.grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=(8, 0))
        self.start_btn = ttk.Button(actions, text="开始定位",
                                    command=self._start)
        self.start_btn.pack(side=tk.LEFT)
        ttk.Button(actions, text="导出报告",
                   command=self._export_report).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="清空结果",
                   command=self._clear).pack(side=tk.LEFT)
        locate_frame.columnconfigure(1, weight=1)

        result_frame = ttk.LabelFrame(body, text=" 4. 结果 ", padding=4)
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.result_text = scrolledtext.ScrolledText(
            result_frame, font=("Consolas", 10), wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.config(state=tk.DISABLED)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(body, textvariable=self.status_var,
                  foreground="#444444").pack(fill=tk.X, pady=(6, 0))

    def _browse_map(self):
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("魔兽地图", "*.w3x *.w3m *.w3n"),
                       ("JASS/Lua 脚本", "*.j *.lua"),
                       ("所有文件", "*.*")])
        if path:
            self.map_path.set(path)

    def _browse_source(self):
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("诊断包或 JSON", "*.zip *.json"),
                       ("所有文件", "*.*")])
        if path:
            self.source_path.set(path)

    def _browse_pjass(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("pjass", "pjass.exe"), ("所有文件", "*.*")])
        if path:
            self.pjass_path.set(path)

    def _browse_w3x2lni(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("w2l", "w2l.exe"),
                                    ("所有文件", "*.*")])
        if path:
            self.w3x2lni_path.set(path)

    def _load_source(self):
        try:
            fingerprint = load_fingerprint_file(self.source_path.get().strip())
        except ValueError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        self._apply_fingerprint(fingerprint, "诊断包/JSON")

    def _fetch_cloud(self):
        try:
            fingerprint = fetch_cloud_fingerprint(
                self.server_url.get().strip(), self.signature.get().strip())
        except ValueError as exc:
            messagebox.showerror("获取失败", str(exc), parent=self)
            return
        self._apply_fingerprint(fingerprint, "云端指纹")

    def _apply_fingerprint(self, fingerprint, source):
        self.fingerprint = fingerprint
        self.knowledge = knowledge_for(fingerprint)
        hints = default_hints(fingerprint, self.knowledge)
        self.hints.set(", ".join(hints))
        self._validate_hints()

        lines = [f"来源：{source}"]
        if fingerprint.get("signature"):
            version = f"（{fingerprint.get('version')}）" if fingerprint.get("version") else ""
            lines.append(f"指纹：{fingerprint['signature']}{version}")
        if fingerprint.get("module") and fingerprint.get("relative_offset"):
            lines.append(f"崩溃位置：{fingerprint['module']}+{fingerprint['relative_offset']}")
        if fingerprint.get("map_name"):
            lines.append(f"地图：{fingerprint['map_name']}")
        if self.knowledge:
            entry = self.knowledge["entry"]
            confidence = int(round((entry.get("confidence") or 0) * 100))
            verified = "已验证" if entry.get("verified") else "未验证"
            lines.append(
                f"知识库：{self.knowledge['desc']}"
                f"（{self.knowledge['version']}，置信度 {confidence}%，{verified}）")
        if fingerprint.get("annotation"):
            lines.append(f"作者标注：{fingerprint['annotation']}")
        if not hints:
            lines.append("未从该指纹推导出 API，请手动填写定位 API。")
        self.fp_info.config(text="\n".join(lines))
        if fingerprint.get("signature"):
            self.signature.set(fingerprint["signature"])
        self.status_var.set("已导入故障信息，可以开始定位")

    def _validate_hints(self):
        selectors = parse_hints(self.hints.get())
        return selectors

    def _start(self):
        map_file = self.map_path.get().strip().strip('"')
        if not map_file or not os.path.exists(map_file):
            messagebox.showwarning("提示", "请先选择地图或脚本文件。", parent=self)
            return
        selectors = self._validate_hints()
        if not selectors:
            if not messagebox.askyesno(
                    "未填写定位 API",
                    "没有定位 API，只会做脚本提取和 pjass 检查。是否继续？",
                    parent=self):
                return
        self.start_btn.config(state=tk.DISABLED)
        self.status_var.set("正在提取脚本并分析，请稍候...")
        self._set_result("")

        fingerprint = self.fingerprint
        knowledge = self.knowledge
        pjass_path = self.pjass_path.get().strip() or None
        w3x2lni_path = self.w3x2lni_path.get().strip() or None
        work_dir = os.path.join(self.app.data_dir, "temp_locator")
        mpq_editor = self.app.mpq_editor_path

        def worker():
            try:
                result = locate_map(
                    map_file, selectors, work_dir, mpq_editor,
                    w3x2lni_path=w3x2lni_path,
                    pjass_path=pjass_path,
                    syntax_only=True,
                    log=self._thread_log)
                result["fingerprint"] = fingerprint or {}
                result["knowledge"] = knowledge
                result["hints"] = selectors
                report = build_report(result, fingerprint)
            except Exception as exc:
                report = f"定位失败：{exc}"
                result = {"error": str(exc)}
            self._messages.put(("finish", result, report))

        threading.Thread(target=worker, daemon=True).start()

    def _thread_log(self, message):
        self._messages.put(("log", message))

    def _finish(self, result, report):
        self.start_btn.config(state=tk.NORMAL)
        self.last_report = report
        self._append(report)
        if result.get("error"):
            self.status_var.set(f"定位未完成：{result['error']}")
        else:
            total = (result.get("calls") or {}).get("total", 0)
            self.status_var.set(f"定位完成：命中 {total} 处")

    def _set_result(self, text):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        if text:
            self.result_text.insert(tk.END, text)
        self.result_text.config(state=tk.DISABLED)

    def _append(self, text):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, text + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)

    def _export_report(self):
        if not self.last_report:
            messagebox.showinfo("提示", "还没有可导出的结果。", parent=self)
            return
        signature = (self.fingerprint or {}).get("signature") or "手动定位"
        default_name = f"指纹定位_{signature}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            parent=self, title="保存定位报告", defaultextension=".txt",
            initialfile=default_name, filetypes=[("文本文件", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(self.last_report + "\n")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        self.status_var.set(f"报告已保存：{os.path.basename(path)}")

    def _clear(self):
        self.last_report = ""
        self._set_result("")
        self.status_var.set("已清空结果")
