"""本地崩溃历史：查看指纹聚类、重复次数、样本日志与诊断记录。"""

import datetime
import os
import tkinter as tk
from tkinter import scrolledtext, ttk

from core.history import HistoryTracker
from core.knowledge import describe, lookup


def _fmt_timestamp(value):
    if value in (None, ""):
        return "—"
    try:
        return datetime.datetime.fromtimestamp(float(value)).strftime(
            "%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(value)


def _fmt_db_time(value):
    if value in (None, ""):
        return "—"
    return str(value)[:16]


def _position(module, rva):
    if module and rva:
        return f"{module}+{rva}"
    return module or rva or "—"


class CrashHistoryDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("崩溃历史与重复崩溃")
        self.geometry("980x720")
        self.minsize(860, 560)
        self.transient(parent)

        db_path = os.path.join(app.data_dir, "history.db")
        self.db_path = db_path
        self.history = HistoryTracker(db_path) if os.path.exists(db_path) else None
        self.fp_rows = {}
        self.log_rows = {}

        self.search_var = tk.StringVar()
        self.repeated_only = tk.BooleanVar(value=False)
        self.summary_var = tk.StringVar(value="")

        self._build()
        self.refresh()

    def _build(self):
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        ttk.Label(header, textvariable=self.summary_var,
                  font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=self.db_path, foreground="#7f8c8d").pack(
            side=tk.RIGHT)

        filters = ttk.Frame(outer)
        filters.pack(fill=tk.X, pady=(8, 4))
        ttk.Label(filters, text="筛选:").pack(side=tk.LEFT)
        entry = ttk.Entry(filters, textvariable=self.search_var, width=32)
        entry.pack(side=tk.LEFT, padx=(4, 8))
        entry.bind("<Return>", lambda event: self.refresh())
        ttk.Checkbutton(filters, text="指纹仅看重复（≥2 次）",
                        variable=self.repeated_only,
                        command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(filters, text="刷新", width=8,
                   command=self.refresh).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(filters, text="清空筛选", width=9,
                   command=self._clear_search).pack(side=tk.RIGHT)
        ttk.Label(filters, text="支持指纹、版本、模块、偏移、归属、日志名",
                  foreground="#7f8c8d").pack(side=tk.LEFT, padx=(8, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self._build_fingerprint_tab()
        self._build_log_tab()

        ttk.Label(
            outer,
            text="历史库只保存在本机，包含崩溃日志名、地图名、指纹与诊断结论；"
                 "不会因为查看历史而上送任何数据。",
            foreground="#7f8c8d").pack(fill=tk.X, pady=(6, 0))

    def _build_fingerprint_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text=" 重复崩溃指纹 ")

        pane = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(pane)
        pane.add(tree_frame, weight=3)

        columns = ("signature", "version", "position", "attribution",
                   "samples", "maps", "last_seen")
        self.fp_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "signature": ("指纹", 110),
            "version": ("版本", 65),
            "position": ("崩溃位置", 170),
            "attribution": ("归属", 130),
            "samples": ("次数", 55),
            "maps": ("地图数", 60),
            "last_seen": ("最近出现", 135),
        }
        for key, (label, width) in headings.items():
            self.fp_tree.heading(key, text=label)
            self.fp_tree.column(key, width=width, anchor=tk.W,
                                stretch=(key in ("position", "attribution")))
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                               command=self.fp_tree.yview)
        self.fp_tree.configure(yscrollcommand=scroll.set)
        self.fp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.fp_tree.bind("<<TreeviewSelect>>", self._on_fingerprint_select)

        detail = ttk.PanedWindow(pane, orient=tk.VERTICAL)
        pane.add(detail, weight=3)

        info_frame = ttk.LabelFrame(detail, text=" 调用栈与知识库 ", padding=4)
        detail.add(info_frame, weight=3)
        self.fp_info = scrolledtext.ScrolledText(
            info_frame, font=("Consolas", 9), wrap=tk.WORD, height=9,
            state=tk.DISABLED)
        self.fp_info.pack(fill=tk.BOTH, expand=True)

        samples_frame = ttk.LabelFrame(detail, text=" 样本日志 ", padding=4)
        detail.add(samples_frame, weight=2)
        sample_columns = ("log_name", "map_name", "seen_at")
        self.sample_tree = ttk.Treeview(
            samples_frame, columns=sample_columns, show="headings",
            selectmode="browse")
        for key, label, width in (("log_name", "日志", 300),
                                  ("map_name", "地图", 310),
                                  ("seen_at", "记录时间", 145)):
            self.sample_tree.heading(key, text=label)
            self.sample_tree.column(key, width=width, anchor=tk.W,
                                    stretch=(key == "log_name"))
        sample_scroll = ttk.Scrollbar(samples_frame, orient=tk.VERTICAL,
                                      command=self.sample_tree.yview)
        self.sample_tree.configure(yscrollcommand=sample_scroll.set)
        self.sample_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sample_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_log_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text=" 诊断日志 ")

        pane = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(pane)
        pane.add(tree_frame, weight=2)

        columns = ("filename", "status", "log_time", "summary")
        self.log_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse")
        for key, label, width, stretch in (
                ("filename", "日志", 300, False),
                ("status", "状态", 110, False),
                ("log_time", "日志时间", 135, False),
                ("summary", "诊断摘要", 380, True)):
            self.log_tree.heading(key, text=label)
            self.log_tree.column(key, width=width, anchor=tk.W,
                                 stretch=stretch)
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                               command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scroll.set)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.bind("<<TreeviewSelect>>", self._on_log_select)

        detail_frame = ttk.LabelFrame(pane, text=" 诊断详情 ", padding=4)
        pane.add(detail_frame, weight=3)
        self.log_detail = scrolledtext.ScrolledText(
            detail_frame, font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        self.log_detail.pack(fill=tk.BOTH, expand=True)

    def _clear_search(self):
        self.search_var.set("")
        self.refresh()

    def refresh(self):
        query = self.search_var.get().strip()
        if not self.history:
            self.summary_var.set("历史库尚未生成")
            self._set_text(self.fp_info, "完成一次崩溃日志诊断后，这里会显示重复崩溃统计。")
            self._set_text(self.log_detail, "暂无诊断记录。")
            self.fp_rows = {}
            self.log_rows = {}
            self._fill_fingerprints([])
            self._fill_logs([])
            return

        summary = self.history.summary()
        self.summary_var.set(
            f"本机历史：{summary['logs']} 份诊断日志 · "
            f"{summary['fingerprints']} 组指纹 · {summary['repeated']} 组重复崩溃")

        fingerprints = self.history.list_fingerprints(
            limit=500, query=query,
            repeated_only=self.repeated_only.get())
        self._fill_fingerprints(fingerprints)

        logs = self.history.list_logs(limit=500, query=query)
        self._fill_logs(logs)

        if fingerprints:
            first = fingerprints[0]["signature"]
            if self.fp_tree.exists(first):
                self.fp_tree.selection_set(first)
                self.fp_tree.focus(first)
                self._on_fingerprint_select()
        else:
            hint = "没有匹配的指纹记录。"
            if self.repeated_only.get():
                hint += "当前勾选了“仅看重复”，可取消后重试。"
            self._set_text(self.fp_info, hint)
            self.sample_tree.delete(*self.sample_tree.get_children())

        if not logs:
            self._set_text(self.log_detail, "没有匹配的诊断日志。")

    def _fill_fingerprints(self, rows):
        self.fp_tree.delete(*self.fp_tree.get_children())
        self.fp_rows = {row["signature"]: row for row in rows}
        for row in rows:
            self.fp_tree.insert("", tk.END, iid=row["signature"], values=(
                row["signature"],
                row.get("version") or "—",
                _position(row.get("module"), row.get("rva")),
                row.get("attribution") or "未判定",
                row.get("samples") or 0,
                row.get("map_count") or 0,
                _fmt_db_time(row.get("last_seen")),
            ))

    def _fill_logs(self, rows):
        self.log_tree.delete(*self.log_tree.get_children())
        self.log_rows = {row["filename"]: row for row in rows}
        for row in rows:
            status = "已诊断" if row.get("diagnosed") else "未诊断"
            if row.get("reported"):
                status += "·已上报"
            summary = " ".join(
                (row.get("summary") or "").split())[:80] or "—"
            log_time = (_fmt_timestamp(row.get("last_modified"))
                        if row.get("last_modified")
                        else _fmt_db_time(row.get("timestamp")))
            self.log_tree.insert("", tk.END, iid=row["filename"], values=(
                row["filename"], status, log_time, summary))

    def _on_fingerprint_select(self, event=None):
        selection = self.fp_tree.selection()
        if not selection:
            return
        row = self.fp_rows.get(selection[0])
        if not row:
            return
        self._set_text(self.fp_info, self._fingerprint_text(row))
        samples = self.history.fingerprint_samples(row["signature"])
        self.sample_tree.delete(*self.sample_tree.get_children())
        for sample in samples:
            self.sample_tree.insert("", tk.END, values=(
                sample.get("log_name") or "—",
                sample.get("map_name") or "—",
                _fmt_db_time(sample.get("seen_at")),
            ))

    def _fingerprint_text(self, row):
        lines = [
            f"指纹：{row['signature']}",
            f"版本：{row.get('version') or '未知'}    "
            f"崩溃位置：{_position(row.get('module'), row.get('rva'))}",
            f"归属：{row.get('attribution') or '未判定'}    "
            f"累计：{row.get('samples') or 0} 次 / "
            f"{row.get('map_count') or 0} 张地图",
            f"首次：{_fmt_db_time(row.get('first_seen'))}    "
            f"最近：{_fmt_db_time(row.get('last_seen'))}",
            "",
        ]
        try:
            entries = lookup(row.get("module"), row.get("version"),
                             row.get("rva"))
        except Exception:
            entries = []
        if entries:
            for version, entry in entries:
                lines.append(f"知识库：{describe(entry, version)}")
        else:
            lines.append("知识库：未收录该模块内偏移。")
        lines.append("")
        lines.append("调用栈（栈顶到调用方）：")
        frames = row.get("frames") or []
        if frames:
            for index, frame in enumerate(frames, 1):
                lines.append(f"  {index}. {frame}")
        else:
            lines.append("  （无调用栈记录）")
        return "\n".join(lines)

    def _on_log_select(self, event=None):
        selection = self.log_tree.selection()
        if not selection:
            return
        filename = selection[0]
        detail = self.history.get_log(filename) if self.history else None
        if not detail:
            self._set_text(self.log_detail, "读取诊断记录失败。")
            return
        lines = [
            f"日志：{filename}",
            f"诊断时间：{_fmt_db_time(detail.get('timestamp'))}",
            f"状态：{'已诊断' if detail.get('diagnosed') else '未诊断'}"
            f"{' · 已上报' if detail.get('reported') else ''}",
            f"文件哈希：{detail.get('file_hash') or '—'}",
            "",
            detail.get("analysis_result") or "（无诊断结论）",
        ]
        self._set_text(self.log_detail, "\n".join(lines))

    @staticmethod
    def _set_text(widget, text):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)
