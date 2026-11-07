"""P6 掉线风险页。

只读展示静态异步风险扫描结果：进入页面不扫描，扫描不修改地图，
不提供任何自动修复或写回入口。
"""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core.desync_risk import RULES, render_markdown, scan_text, summary_text
from core.map_script import MapScript
from gui.tabs.base import BaseTab

_COLUMNS = (
    ("severity", "级别", 58, tk.CENTER),
    ("rule", "规则", 62, tk.CENTER),
    ("title", "风险类型", 150, tk.W),
    ("function", "函数", 170, tk.W),
    ("line", "行", 56, tk.CENTER),
    ("evidence", "证据", 420, tk.W),
)


def _safe_stem(name):
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" .")
    return cleaned or "desync_report"


class DesyncRiskTab(BaseTab):
    def setup_ui(self):
        self.map_script = None
        self.report = None
        self._rows = {}
        self._busy = False

        main = tk.Frame(self, bg="#f5f6f7", padx=12, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        title_row = tk.Frame(main, bg="#f5f6f7")
        title_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            title_row, text="掉线风险", font=("微软雅黑", 12, "bold"),
            bg="#f5f6f7", fg="#2c3e50").pack(side=tk.LEFT)
        tk.Label(
            title_row, text="静态检查多人同步风险；只报告，不修改地图。",
            font=("微软雅黑", 9), bg="#f5f6f7", fg="#7f8c8d").pack(
                side=tk.LEFT, padx=(10, 0))

        toolbar = tk.Frame(main, bg="#f5f6f7")
        toolbar.pack(fill=tk.X, pady=(0, 6))
        tk.Label(toolbar, text="地图：", bg="#f5f6f7", fg="#2c3e50",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Entry(toolbar, textvariable=self.app.map_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(toolbar, text="选择地图", command=self.browse_map,
                  width=9).pack(side=tk.LEFT, padx=(6, 0))
        self.scan_btn = tk.Button(
            toolbar, text="开始扫描", command=self.start_scan,
            bg="#8e44ad", fg="white", font=("微软雅黑", 9, "bold"), width=10)
        self.scan_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.export_btn = tk.Button(
            toolbar, text="导出 Markdown", command=self.export_report,
            width=14, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.summary_var = tk.StringVar(
            value="尚未扫描：选择地图后点击「开始扫描」。")
        tk.Label(
            main, textvariable=self.summary_var, bg="#f5f6f7", fg="#2c3e50",
            font=("微软雅黑", 9), justify=tk.LEFT, anchor=tk.W).pack(
                fill=tk.X, pady=(0, 6))

        vertical = tk.PanedWindow(
            main, orient=tk.VERTICAL, sashwidth=6, sashrelief=tk.RAISED,
            bg="#d0d7de")
        vertical.pack(fill=tk.BOTH, expand=True)

        tree_box = tk.Frame(vertical, bg="#ffffff")
        vertical.add(tree_box, minsize=180, height=320)
        self.tree = ttk.Treeview(
            tree_box, columns=[column[0] for column in _COLUMNS],
            show="headings", selectmode="browse")
        for key, heading, width, anchor in _COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(
                key, width=width, anchor=anchor,
                stretch=key in ("title", "function", "evidence"))
        self.tree.tag_configure("高", foreground="#c0392b")
        self.tree.tag_configure("中", foreground="#b9770e")
        self.tree.tag_configure("低", foreground="#7f8c8d")
        y_scroll = ttk.Scrollbar(
            tree_box, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(
            tree_box, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree_box.grid_rowconfigure(0, weight=1)
        tree_box.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail_frame = tk.LabelFrame(
            vertical, text=" 风险详情 ", bg="#ffffff", padx=6, pady=6,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        vertical.add(detail_frame, minsize=150, height=220)
        self.detail_text = scrolledtext.ScrolledText(
            detail_frame, font=("Consolas", 9), bg="#fbfcfd", wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self._set_detail(
            "选择地图后点击「开始扫描」。\n\n"
            "本页只做静态检查：不提取后写回、不生成补丁、不修改地图。")

        tk.Label(
            main,
            text="规则：D1 本地分支改同步状态 / D2 本地分支枚举单位组 / "
                 "D3 本地随机 / D4 本地写全局 / D5 本地输入分支；"
                 "L1-L4 为 Lua 风险。纯视觉本地操作不会报告。",
            bg="#f5f6f7", fg="#7f8c8d", font=("微软雅黑", 8),
            justify=tk.LEFT, anchor=tk.W, wraplength=1040).pack(
                fill=tk.X, pady=(6, 0))

    # ------------------------------------------------------------ 地图与扫描
    def browse_map(self):
        path = filedialog.askopenfilename(
            title="选择地图或脚本",
            filetypes=[
                ("魔兽地图", "*.w3x *.w3m *.w3n"),
                ("JASS / Lua 脚本", "*.j *.lua"),
                ("所有文件", "*.*"),
            ])
        if not path:
            return
        self.app.map_path.set(os.path.normpath(path))
        self._reset_results()

    def _reset_results(self):
        self.map_script = None
        self.report = None
        self._rows.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.summary_var.set("尚未扫描：点击「开始扫描」。")
        self._set_detail(
            "选择地图后点击「开始扫描」。\n\n"
            "本页只做静态检查：不提取后写回、不生成补丁、不修改地图。")
        self._update_action_state()

    def start_scan(self):
        if self._busy:
            return
        path = self.app.map_path.get().strip().strip('"')
        if not path or not os.path.exists(path):
            messagebox.showwarning("提示", "请先选择地图或脚本文件。")
            return

        self._reset_results()
        self._busy = True
        self.summary_var.set("正在扫描...")
        self._update_action_state()
        work_dir = os.path.join(self.app.data_dir, "leak_work")

        def worker():
            try:
                map_script = MapScript.load(
                    path, work_dir,
                    mpq_editor_path=getattr(self.app, "mpq_editor_path", None))
                report = scan_text(map_script.text, map_script.language)
                self.app.root.after(
                    0, self._scan_done, map_script, report)
            except Exception as exc:  # noqa: BLE001 - 扫描失败要回显原因
                self.app.root.after(0, self._scan_failed, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self, map_script, report):
        self.map_script = map_script
        self.report = report
        self._rows.clear()

        for finding in report.findings:
            item = self.tree.insert(
                "", tk.END,
                values=(
                    finding.severity, finding.rule_id, finding.title,
                    finding.function or "-", finding.line, finding.evidence),
                tags=(finding.severity,))
            self._rows[item] = finding

        self.summary_var.set(
            f"{summary_text(report)} 脚本 {report.total_lines} 行 · "
            f"解析覆盖率 {report.coverage:.1%} · "
            f"跳过 {report.parse_errors} 处 · 语言 {report.language}")
        self._busy = False
        self._update_action_state()
        if report.findings:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self._on_select()
        else:
            self._set_detail(
                "未发现静态异步风险。\n\n"
                "这表示脚本中没有命中当前规则的高置信写法，"
                "不代表地图一定不会掉线。")
        if getattr(self.app, "status_var", None) is not None:
            self.app.status_var.set("掉线风险扫描完成")

    def _scan_failed(self, error):
        self._busy = False
        self._update_action_state()
        self.summary_var.set("扫描失败：请检查文件是否可读取。")
        self._set_detail(f"扫描失败：\n{error}")
        messagebox.showerror("扫描失败", error)

    # -------------------------------------------------------------- 结果展示
    def _on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        finding = self._rows.get(selection[0])
        if finding is None:
            return
        self._set_detail(self._format_detail(finding))

    @staticmethod
    def _format_detail(finding):
        severity, title = RULES.get(
            finding.rule_id, (finding.severity, finding.title))
        return "\n".join([
            f"【{severity}】{finding.rule_id} {title}",
            f"位置：{finding.function or '（Lua 顶层）'} "
            f"第 {finding.line} 行",
            "",
            f"证据：{finding.evidence or '（空行）'}",
            f"说明：{finding.detail}",
            "",
            "提示：静态规则只说明这里值得人工复核，"
            "不证明地图一定掉线；本页不会修改脚本。",
        ])

    def _set_detail(self, text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.config(state=tk.DISABLED)

    # ---------------------------------------------------------------- 导出
    def export_report(self):
        if self.report is None or self._busy:
            messagebox.showinfo("提示", "请先完成一次扫描。")
            return
        out_dir = os.path.join(self.app.data_dir, "desync_reports")
        os.makedirs(out_dir, exist_ok=True)
        source = (
            self.map_script.source_path if self.map_script else "地图")
        stem = _safe_stem(source)
        path = os.path.join(out_dir, f"{stem}_desync.md")
        text = render_markdown(
            self.report,
            map_name=os.path.basename(source),
            script_path=(self.map_script.internal_path or "")
            if self.map_script else "",
            encoding=self.map_script.encoding if self.map_script else "",
            sha256=(self.map_script.source_sha256 or "")
            if self.map_script else "")
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        messagebox.showinfo("报告已导出", f"已生成 Markdown 报告：\n{path}")

    def _update_action_state(self):
        self.scan_btn.config(
            state=tk.DISABLED if self._busy else tk.NORMAL)
        self.export_btn.config(
            state=tk.NORMAL if (self.report is not None and not self._busy)
            else tk.DISABLED)
