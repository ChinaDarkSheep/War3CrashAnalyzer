"""上传码查询对话框：凭 6 位码查看服务端诊断与维护者反馈。"""

import re
import threading
import tkinter as tk
from tkinter import scrolledtext

from core import uploader


FEEDBACK_COLORS = {
    "pending": ("#636e72", "#f1f2f6"),
    "reviewing": ("#1d6fa5", "#e0f2fe"),
    "resolved": ("#1e8449", "#dcfce7"),
    "need_info": ("#a16207", "#fef9c3"),
}


def _fmt_bytes(size):
    value = float(size or 0)
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.2f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value:.0f} B"


def _position(upload):
    module = upload.get("module")
    offset = upload.get("relative_offset")
    if module and offset:
        return f"{module}+{offset}"
    return offset or module or "未识别"


class UploadStatusDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("查询上传码状态")
        self.geometry("700x680")
        self.minsize(620, 520)
        self.transient(parent)
        self._busy = False

        self.code_var = tk.StringVar(
            value=(app.config or {}).get("last_upload_code", ""))

        self._build()
        self._configure_tags()
        if re.fullmatch(r"\d{6}", self.code_var.get().strip()):
            self.after(150, self._query)

    # ---------- 界面 ----------
    def _build(self):
        outer = tk.Frame(self, padx=14, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        query = tk.Frame(outer)
        query.pack(fill=tk.X)
        tk.Label(query, text="上传码：", font=("微软雅黑", 10, "bold")).pack(
            side=tk.LEFT)
        self.code_entry = tk.Entry(
            query, textvariable=self.code_var, width=10, justify=tk.CENTER,
            font=("Consolas", 15, "bold"))
        self.code_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.query_btn = tk.Button(
            query, text="查询", width=10, bg="#2980b9", fg="white",
            font=("微软雅黑", 9, "bold"), command=self._query)
        self.query_btn.pack(side=tk.LEFT)
        self.status_label = tk.Label(query, text="", fg="#7f8c8d", anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        self.code_entry.bind("<Return>", lambda _event: self._query())

        tk.Label(
            outer,
            text="上传码会在上传成功时自动记住；也可以手动输入群里收到的 6 位数字。",
            fg="#7f8c8d", anchor="w", justify=tk.LEFT).pack(fill=tk.X, pady=(6, 0))

        body_frame = tk.LabelFrame(outer, text=" 上传记录 ", padx=6, pady=6)
        body_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.body = scrolledtext.ScrolledText(
            body_frame, wrap=tk.WORD, font=("微软雅黑", 10), bg="#ffffff",
            state=tk.DISABLED, padx=8, pady=8)
        self.body.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="这里只显示服务端派生信息与维护者反馈，不会显示原始日志内容。",
            fg="#7f8c8d", anchor="w", justify=tk.LEFT).pack(
            fill=tk.X, pady=(6, 0))

        self._show_placeholder()

    def _configure_tags(self):
        self.body.tag_configure(
            "title", font=("Consolas", 16, "bold"), foreground="#2c3e50",
            spacing3=8)
        self.body.tag_configure(
            "section", font=("微软雅黑", 10, "bold"), foreground="#2c3e50",
            spacing1=12, spacing3=4)
        self.body.tag_configure("label", foreground="#7f8c8d")
        self.body.tag_configure("value", foreground="#2c3e50")
        self.body.tag_configure(
            "analysis", foreground="#34495e", lmargin1=4, lmargin2=4,
            spacing1=2)
        self.body.tag_configure("error", foreground="#c0392b")
        for status, (fg, bg) in FEEDBACK_COLORS.items():
            self.body.tag_configure(
                f"fb_{status}", foreground=fg, background=bg,
                font=("微软雅黑", 9, "bold"))

    def _clear(self):
        self.body.config(state=tk.NORMAL)
        self.body.delete("1.0", tk.END)

    def _finish(self):
        self.body.config(state=tk.DISABLED)

    def _write(self, text, tag=None):
        self.body.insert(tk.END, text, tag)

    def _set_status(self, message, color="#7f8c8d"):
        self.status_label.config(text=message, fg=color)

    def _show_placeholder(self):
        self._clear()
        self._write("输入 6 位上传码后点击“查询”\n", "title")
        self._write(
            "上传成功后，程序会自动把上传码复制到剪贴板并记住；"
            "打开本窗口即可看到维护者的复核进度与备注。", "label")
        self._finish()

    # ---------- 查询 ----------
    def _query(self):
        if self._busy:
            return
        code = self.code_var.get().strip()
        if not re.fullmatch(r"\d{6}", code):
            self._set_status("上传码应为 6 位数字", "#c0392b")
            return

        self._busy = True
        self.query_btn.config(state=tk.DISABLED, text="查询中…")
        self._set_status("正在查询…")

        def worker():
            try:
                payload = uploader.query_upload(code)
            except uploader.UploadError as exc:
                self._ui(self._failed, str(exc))
                return
            except Exception as exc:
                self._ui(self._failed, f"查询出错：{exc}")
                return
            self._ui(self._succeeded, payload)

        threading.Thread(target=worker, daemon=True).start()

    def _ui(self, func, *args):
        try:
            self.after(0, func, *args)
        except tk.TclError:
            pass

    def _failed(self, message):
        self._busy = False
        self.query_btn.config(state=tk.NORMAL, text="查询")
        self._set_status(message, "#c0392b")
        self._clear()
        self._write("查询失败\n", "title")
        self._write(message + "\n", "error")
        self._finish()

    def _succeeded(self, data):
        self._busy = False
        self.query_btn.config(state=tk.NORMAL, text="查询")
        self.code_var.set(str(data.get("code") or self.code_var.get().strip()))
        self._set_status("查询成功", "#1e8449")
        self._render(data)

    # ---------- 渲染 ----------
    def _render(self, data):
        self._clear()
        self._write(f"上传码 {data.get('code')}\n", "title")

        if data.get("raw_available"):
            self._write(
                f"原始文件保留中 · 保留至 {data.get('expires_at') or '未知'}\n",
                "label")
        else:
            self._write("原始文件已到期删除，仅保留派生信息。\n", "label")

        feedback = data.get("feedback") or {}
        status = feedback.get("status") if feedback.get("status") in FEEDBACK_COLORS else "pending"
        label = feedback.get("label") or "待处理"
        self._write("\n维护者反馈  ", "section")
        self._write(f" {label} ", f"fb_{status}")
        if feedback.get("updated_at"):
            self._write(f"  更新于 {feedback['updated_at']}", "label")
        else:
            self._write("  维护者尚未更新", "label")
        note = (feedback.get("note") or "").strip()
        self._write("\n" + (note or "暂无备注；如需补充材料，请用同一上传码联系维护者。") + "\n",
                    "value" if note else "label")

        rows = [
            ("上传时间", data.get("created_at") or "—"),
            ("游戏版本", data.get("game_version") or "未识别"),
            ("地图", data.get("map_name") or "未识别"),
            ("地图作者", data.get("map_author") or "未识别"),
            ("地图 MD5", data.get("map_hash") or "未识别"),
            ("崩溃位置", _position(data)),
            ("归属", data.get("attribution") or "未判定"),
            ("KK 会话", data.get("kk_session") or "未附平台日志"),
            ("文件数 / 大小",
             f"{data.get('file_count') or 0} 个 / {_fmt_bytes(data.get('total_bytes'))}"),
        ]
        if data.get("confidence") is not None:
            rows.append(("置信度", f"{round(float(data['confidence']) * 100)}%"))

        self._write("\n上传信息\n", "section")
        for name, value in rows:
            self._write(f"{name}：", "label")
            self._write(f"{value}\n", "value")

        analysis = (data.get("analysis") or "").strip()
        if analysis:
            self._write("\n初步诊断\n", "section")
            self._write(analysis + "\n", "analysis")

        summary = data.get("summary") or {}
        crash = summary.get("crash") if isinstance(summary, dict) else None
        if crash:
            self._write("\n崩溃记录\n", "section")
            self._write(f"服务端识别到 {crash.get('records', 0)} 次崩溃记录。\n",
                        "value")

        if data.get("server"):
            self._write(f"\n数据来源：{data['server']}\n", "label")

        self.body.see("1.0")
        self._finish()
