"""JassDebug 弹窗解析对话框：只读读取或粘贴“调试输出”文本。"""

import tkinter as tk
from tkinter import messagebox, scrolledtext

from core import jassdebug


class JassDebugDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("JassDebug 弹窗解析")
        self.geometry("820x700")
        self.minsize(700, 560)
        self.transient(parent)
        self._report = ""

        self._build()
        self._configure_tags()
        self.after(200, self._auto_read)

    def _build(self):
        outer = tk.Frame(self, padx=14, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        warning = tk.Label(
            outer,
            text="⚠️ 仅限本地客户端调试使用；严禁在 KK / 网易等联网对战平台开启 JassDebug。",
            bg="#fff3cd", fg="#856404", font=("微软雅黑", 9, "bold"),
            padx=8, pady=5, anchor="w")
        warning.pack(fill=tk.X, pady=(0, 8))

        toolbar = tk.Frame(outer)
        toolbar.pack(fill=tk.X)
        tk.Button(toolbar, text="读取当前弹窗", command=self._read_popup,
                  bg="#2980b9", fg="white", font=("微软雅黑", 9, "bold"),
                  width=13).pack(side=tk.LEFT)
        tk.Button(toolbar, text="粘贴剪贴板", command=self._paste,
                  bg="#16a085", fg="white", font=("微软雅黑", 9),
                  width=12).pack(side=tk.LEFT, padx=6)
        tk.Button(toolbar, text="解析", command=self._parse,
                  bg="#27ae60", fg="white", font=("微软雅黑", 9, "bold"),
                  width=8).pack(side=tk.LEFT)
        tk.Button(toolbar, text="复制结论", command=self._copy,
                  bg="#8e44ad", fg="white", font=("微软雅黑", 9),
                  width=10).pack(side=tk.RIGHT)
        tk.Button(toolbar, text="清空", command=self._clear,
                  bg="#95a5a6", fg="white", font=("微软雅黑", 9),
                  width=8).pack(side=tk.RIGHT, padx=6)
        self.status_label = tk.Label(
            outer, text="", fg="#7f8c8d", anchor="w")
        self.status_label.pack(fill=tk.X, pady=(6, 0))

        input_frame = tk.LabelFrame(
            outer, text=" 弹窗文字（可粘贴截图中的文字） ", padx=6, pady=6)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.input = scrolledtext.ScrolledText(
            input_frame, height=9, wrap=tk.WORD, font=("微软雅黑", 9),
            undo=True)
        self.input.pack(fill=tk.BOTH, expand=True)

        result_frame = tk.LabelFrame(
            outer, text=" 解析结果 ", padx=6, pady=6)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.result = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=("微软雅黑", 10), bg="#ffffff",
            state=tk.DISABLED, padx=8, pady=8)
        self.result.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="JASS 代码偏移由地图编译结果决定，重新编译后会变化；请用同一版本地图核对。",
            fg="#7f8c8d", anchor="w").pack(fill=tk.X, pady=(6, 0))

    def _configure_tags(self):
        self.result.tag_configure(
            "title", font=("微软雅黑", 12, "bold"), foreground="#2c3e50",
            spacing3=8)
        self.result.tag_configure(
            "section", font=("微软雅黑", 9, "bold"), foreground="#2c3e50",
            spacing1=10, spacing3=4)
        self.result.tag_configure("label", foreground="#7f8c8d")
        self.result.tag_configure("value", foreground="#2c3e50")
        self.result.tag_configure(
            "conclusion", foreground="#1d6fa5", font=("微软雅黑", 9, "bold"),
            spacing3=4)
        self.result.tag_configure("error", foreground="#c0392b")

    def _status(self, message, color="#7f8c8d"):
        self.status_label.config(text=message, fg=color)

    def _show_result(self, writer):
        self.result.config(state=tk.NORMAL)
        self.result.delete("1.0", tk.END)
        writer()
        self.result.config(state=tk.DISABLED)

    def _auto_read(self):
        self._read_popup(silent=True)

    def _read_popup(self, silent=False):
        text = jassdebug.read_popup_text()
        if not text:
            if not silent:
                messagebox.showinfo(
                    "未找到弹窗",
                    "未找到标题为“调试输出”的弹窗。\n"
                    "请保持崩溃弹窗打开后重试，或把弹窗文字粘贴到上方输入框。",
                    parent=self)
            self._status("未找到“调试输出”弹窗，可粘贴文字后解析")
            return
        self.input.delete("1.0", tk.END)
        self.input.insert("1.0", text)
        self._status("已读取当前弹窗文字", "#1e8449")
        self._parse()

    def _paste(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            self._status("剪贴板中没有文本", "#c0392b")
            return
        self.input.delete("1.0", tk.END)
        self.input.insert("1.0", text)
        self._status("已粘贴剪贴板文字")

    def _clear(self):
        self.input.delete("1.0", tk.END)
        self._report = ""
        self._show_result(lambda: None)
        self._status("已清空")

    def _parse(self):
        text = self.input.get("1.0", tk.END).strip()
        if not text:
            self._status("请先读取弹窗或粘贴弹窗文字", "#c0392b")
            return
        parsed = jassdebug.parse_popup(text)
        if not parsed:
            self._report = ""
            self._show_result(lambda: self._write_parse_error())
            self._status("未识别到 JassDebug 弹窗内容", "#c0392b")
            return
        conclusion = jassdebug.build_conclusion(parsed)
        self._render(parsed, conclusion)
        self._status("解析完成", "#1e8449")

    def _write_parse_error(self):
        self.result.insert(tk.END, "无法识别这段文字\n", "title")
        self.result.insert(
            tk.END,
            "没有找到“当前JASS语句地址为”“当前语句所属函数为”或"
            "“JASS代码起始地址为”等字段。\n"
            "请确认复制的是标题为“调试输出”的弹窗全文。", "error")

    def _render(self, parsed, conclusion):
        rows = [
            ("当前语句地址", parsed.get("statement_addr")),
            ("语句内容", parsed.get("statement_content")),
            ("所属函数", parsed.get("function")),
            ("上级函数链", " → ".join(parsed.get("parents") or [])),
            ("JASS 起始地址", parsed.get("code_base")),
        ]
        offset = parsed.get("code_offset")
        decimal = parsed.get("code_offset_decimal")
        rows.append((
            "JASS 代码偏移",
            f"{offset}（十进制 {decimal}）" if offset and decimal is not None else offset))

        def writer():
            self.result.insert(tk.END, "JassDebug 弹窗解析\n", "title")
            for line in conclusion["text"].splitlines():
                self.result.insert(tk.END, line + "\n", "conclusion")
            self.result.insert(tk.END, "\n详细信息\n", "section")
            for name, value in rows:
                self.result.insert(tk.END, f"{name}：", "label")
                self.result.insert(tk.END, f"{value or '—'}\n", "value")
            self.result.insert(tk.END, "\n调用链\n", "section")
            chain = parsed.get("call_chain") or []
            self.result.insert(
                tk.END, " → ".join(chain) if chain else "—", "value")

        self._show_result(writer)
        self._report = conclusion["text"]
        if parsed.get("call_chain"):
            self._report += "\n调用链：" + " → ".join(parsed["call_chain"])

    def _copy(self):
        if not self._report:
            self._status("还没有可复制的解析结果", "#c0392b")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._report)
        except tk.TclError:
            self._status("复制失败，请手动选择文本", "#c0392b")
            return
        self._status("解析结果已复制到剪贴板", "#1e8449")
