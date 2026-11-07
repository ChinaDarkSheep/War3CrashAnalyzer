"""P5.5 泄露定位&修复界面。

交互边界：

- 进入页面不扫描、不提取地图，只有点击「开始扫描」才读图；
- 默认只勾选 A 级可自动修复项，应用前必须预览 diff；
- B 级只导出补丁，C 级只报告；
- 写回永远落到 ``*_leakfixed`` 副本，原图保持不变，可撤销上一写回。
"""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core.leak_catalog import coverage_statement
from core.leak_fixer import build_fix_plan, write_fix_plan
from core.leak_report import build_leak_report, write_leak_report
from core.map_script import MapScript
from core.pjass import find_pjass
from gui.tabs.base import BaseTab

_TREE_COLUMNS = (
    ("sel", "选", 42, tk.CENTER),
    ("severity", "严重度", 58, tk.CENTER),
    ("rule", "规则", 58, tk.CENTER),
    ("function", "函数", 160, tk.W),
    ("line", "行", 52, tk.CENTER),
    ("type", "类型", 78, tk.CENTER),
    ("variable", "变量", 110, tk.W),
    ("confidence", "置信度", 62, tk.CENTER),
    ("level", "级别", 46, tk.CENTER),
    ("handling", "处理", 82, tk.CENTER),
)


def _safe_stem(name):
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" .")
    return cleaned or "leak_report"


def _validation_line(validation):
    status = (validation or {}).get("status", "unchecked")
    if status == "ok":
        return "pjass 语法检查通过（0 错误）"
    if status == "failed":
        errors = (validation or {}).get("errors") or []
        return f"pjass 校验未通过（{len(errors)} 个错误）"
    return "未校验：未找到 pjass 或本次未执行"


class LeakFixTab(BaseTab):
    def setup_ui(self):
        self.map_script = None
        self.plan = None
        self.report = None
        self._rows = {}
        self._checked = set()
        self._busy = False
        self._applied = False
        self._undo_script = None
        self._last_output_dir = None
        self._pjass_path = find_pjass(getattr(self.app, "base_dir", None))

        main = tk.Frame(self, bg="#f5f6f7", padx=12, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        title_row = tk.Frame(main, bg="#f5f6f7")
        title_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            title_row, text="泄露定位&修复", font=("微软雅黑", 12, "bold"),
            bg="#f5f6f7", fg="#2c3e50").pack(side=tk.LEFT)
        tk.Label(
            title_row,
            text="默认只定位；修复只写 *_leakfixed 副本，原图保持不变。",
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
            bg="#2980b9", fg="white", font=("微软雅黑", 9, "bold"), width=10)
        self.scan_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.report_btn = tk.Button(
            toolbar, text="导出统一报告", command=self.export_report, width=12)
        self.report_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.undo_btn = tk.Button(
            toolbar, text="撤销上次写回", command=self.undo_last_write, width=12)
        self.undo_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.summary_var = tk.StringVar(value="尚未扫描：选择地图后点击「开始扫描」。")
        tk.Label(
            main, textvariable=self.summary_var, bg="#f5f6f7", fg="#2c3e50",
            font=("微软雅黑", 9), justify=tk.LEFT, anchor=tk.W).pack(
                fill=tk.X, pady=(0, 6))

        vertical = tk.PanedWindow(
            main, orient=tk.VERTICAL, sashwidth=6, sashrelief=tk.RAISED,
            bg="#d0d7de")
        vertical.pack(fill=tk.BOTH, expand=True)

        result_frame = tk.Frame(vertical, bg="#ffffff")
        vertical.add(result_frame, minsize=180, height=300)

        tree_box = tk.Frame(result_frame, bg="#ffffff")
        tree_box.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_box, columns=[column[0] for column in _TREE_COLUMNS],
            show="headings", selectmode="browse")
        for key, heading, width, anchor in _TREE_COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(
                key, width=width, anchor=anchor,
                stretch=key in ("function", "variable"))
        self.tree.tag_configure("A", foreground="#1e8449")
        self.tree.tag_configure("B", foreground="#b9770e")
        self.tree.tag_configure("C", foreground="#7f8c8d")
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
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        lower = tk.PanedWindow(
            vertical, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED,
            bg="#d0d7de")
        vertical.add(lower, minsize=150, height=260)

        detail_frame = tk.LabelFrame(
            lower, text=" 证据 / 上下文 / diff ", bg="#ffffff", padx=6, pady=6,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        lower.add(detail_frame, minsize=360)
        self.detail_text = scrolledtext.ScrolledText(
            detail_frame, font=("Consolas", 9), bg="#fbfcfd", wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self._set_detail(
            "选择地图后点击「开始扫描」。\n\n"
            "进入本页不会自动扫描或修改地图；扫描只读取脚本，"
            "修复会在确认 diff 后写入 *_leakfixed 副本。")

        log_frame = tk.LabelFrame(
            lower, text=" 执行日志 / 进度 ", bg="#ffffff", padx=6, pady=6,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        lower.add(log_frame, minsize=300)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 9), bg="#ffffff")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        action_bar = tk.Frame(main, bg="#f5f6f7")
        action_bar.pack(fill=tk.X, pady=(6, 4))
        self.apply_btn = tk.Button(
            action_bar, text="应用选中修复", command=self.apply_selected,
            bg="#27ae60", fg="white", font=("微软雅黑", 10, "bold"), width=14)
        self.apply_btn.pack(side=tk.LEFT)
        self.patch_btn = tk.Button(
            action_bar, text="仅导出补丁", command=self.export_patch, width=12)
        self.patch_btn.pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            action_bar, text="全选 A 级", command=self.select_all_a,
            width=10).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            action_bar, text="清空选择", command=self.clear_selection,
            width=10).pack(side=tk.LEFT, padx=(6, 0))
        self.open_btn = tk.Button(
            action_bar, text="打开输出目录", command=self.open_output_dir,
            width=12)
        self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.progress = ttk.Progressbar(
            action_bar, mode="indeterminate", length=150)
        self.progress.pack(side=tk.RIGHT)
        self.status_var = tk.StringVar(value="空闲")
        tk.Label(
            action_bar, textvariable=self.status_var, bg="#f5f6f7",
            fg="#7f8c8d", font=("微软雅黑", 9)).pack(
                side=tk.RIGHT, padx=(0, 8))

        coverage = tk.LabelFrame(
            main, text=" 覆盖范围 ", bg="#ffffff", padx=8, pady=4,
            font=("微软雅黑", 9, "bold"), fg="#2c3e50")
        coverage.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            coverage, text=coverage_statement(), bg="#ffffff", fg="#566573",
            font=("微软雅黑", 8), justify=tk.LEFT, anchor=tk.W,
            wraplength=1040).pack(fill=tk.X)

        self._update_action_state()

    # ------------------------------------------------------------------ 日志
    def _append_log(self, message):
        try:
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        except tk.TclError:
            return
        if getattr(self.app, "status_var", None) is not None:
            try:
                self.app.status_var.set(message)
            except tk.TclError:
                pass

    def _thread_log(self, message):
        try:
            self.app.root.after(0, self._append_log, message)
        except Exception:
            pass

    def _set_detail(self, text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.config(state=tk.DISABLED)

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
        self._append_log(f"[*] 已选择: {path}")

    def _reset_results(self):
        self.map_script = None
        self.plan = None
        self.report = None
        self._rows.clear()
        self._checked.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._applied = False
        self._undo_script = None
        self.summary_var.set("尚未扫描：点击「开始扫描」。")
        self.status_var.set("空闲")
        self._set_detail(
            "选择地图后点击「开始扫描」。\n\n"
            "进入本页不会自动扫描或修改地图；扫描只读取脚本，"
            "修复会在确认 diff 后写入 *_leakfixed 副本。")
        self._update_action_state()

    def start_scan(self):
        if self._busy:
            return
        path = self.app.map_path.get().strip().strip('"')
        if not path or not os.path.exists(path):
            messagebox.showwarning("提示", "请先选择地图或脚本文件。")
            return

        self._reset_results()
        self._set_busy(True, "正在扫描...")
        self._append_log("")
        self._append_log("=" * 60)
        self._append_log(f"[*] 开始扫描: {path}")
        self._append_log("[*] 进入本页不会自动扫描；本次由用户手动触发。")

        work_dir = os.path.join(self.app.data_dir, "leak_work")

        def worker():
            try:
                self._thread_log("[*] 正在提取地图脚本...")
                map_script = MapScript.load(
                    path, work_dir,
                    mpq_editor_path=getattr(self.app, "mpq_editor_path", None),
                    log=self._thread_log)
                internal = map_script.internal_path or map_script.script_path
                line_count = len(map_script.text.splitlines())
                self._thread_log(
                    f"[*] 脚本: {internal}（{map_script.method}"
                    f"，{map_script.language}，{map_script.encoding}，"
                    f"{line_count} 行）")
                if not map_script.writable and map_script.readonly_reason:
                    self._thread_log(f"[!] 只读：{map_script.readonly_reason}")

                self._thread_log("[*] 正在做静态语义分析与规则分类...")
                plan = build_fix_plan(
                    map_script.text, language=map_script.language)
                self._thread_log(
                    f"[*] 分析完成：{len(plan.matches)} 个创建点，"
                    f"{len(plan.auto_edits)} 条自动编辑，"
                    f"{len(plan.patch_edits)} 条补丁，"
                    f"{len(plan.notes)} 条人工提示。")
                if plan.parse_errors:
                    self._thread_log(f"[!] 容错解析跳过 {plan.parse_errors} 处。")

                self._thread_log("[*] 正在生成统一报告与可疑函数片段...")
                report = build_leak_report(
                    plan,
                    map_name=os.path.basename(map_script.source_path),
                    script_internal_path=map_script.internal_path or "",
                    encoding=map_script.encoding,
                    source_sha256=map_script.source_sha256 or "")
                self.app.root.after(
                    0, self._scan_done, map_script, plan, report)
            except Exception as exc:  # noqa: BLE001 - 扫描失败要回显原因
                self.app.root.after(0, self._scan_failed, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self, map_script, plan, report):
        self.map_script = map_script
        self.plan = plan
        self.report = report
        self._applied = False
        self._undo_script = None
        self._rows.clear()
        self._checked.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in report["rows"]:
            item = self.tree.insert(
                "", tk.END,
                values=(
                    "☐", row["severity"], row["rule_id"] or "-",
                    row["function"], row["line"], row["handle_type"],
                    row["variable"] or "-",
                    f"{int(round(row['confidence'] * 100))}%",
                    row["level"], self._handling(row)),
                tags=(row["level"],))
            self._rows[item] = row
            if row["level"] == "A" and row["auto"]:
                self._checked.add(row["key"])

        self._refresh_marks()
        self.summary_var.set(self._summary_text(report))
        self.status_var.set("扫描完成")
        if plan.readonly:
            self._append_log(f"[!] {plan.readonly_reason or '当前输入只读'}")
        self._append_log(
            f"[+] 扫描完成：{len(report['rows'])} 条结果，"
            f"默认勾选 {len(self._checked)} 条 A 级自动修复项。")
        if report["summary"]["global_skipped"]:
            self._append_log(
                f"[*] 全局变量持有的普通句柄 "
                f"{report['summary']['global_skipped']} 条，按设计不列为泄露。")
        self._append_log(f"[*] {_validation_line(report.get('validation'))}")
        self._set_busy(False, "扫描完成")
        self._select_first_row()

    def _scan_failed(self, error):
        self._set_busy(False, "扫描失败")
        self.summary_var.set("扫描失败：请查看执行日志。")
        self._append_log(f"[-] 扫描失败: {error}")
        messagebox.showerror("扫描失败", error)

    def _select_first_row(self):
        children = self.tree.get_children()
        if not children:
            self._set_detail("扫描完成：没有发现可报告的问题。")
            return
        self.tree.selection_set(children[0])
        self.tree.focus(children[0])
        self._on_tree_select()

    # -------------------------------------------------------------- 结果展示
    @staticmethod
    def _handling(row):
        if row["auxiliary"]:
            return "辅助置空"
        if row["auto"]:
            return "自动修复"
        if row["patch"]:
            return "补丁预览"
        return "只报告"

    def _mark(self, row):
        if not (row["auto"] or row["patch"]):
            return "—"
        return "☑" if row["key"] in self._checked else "☐"

    def _summary_text(self, report):
        summary = report["summary"]
        levels = summary["by_level"]
        rows = report["rows"]
        auto_rows = sum(1 for row in rows if row["auto"])
        patch_rows = sum(1 for row in rows if row["patch"])
        first = (
            f"共 {len(rows)} 条记录 · 泄露 {summary['findings']} 条 · "
            f"A {levels.get('A', 0)} / B {levels.get('B', 0)} / "
            f"C {levels.get('C', 0)} · 自动 {auto_rows} / "
            f"补丁 {patch_rows} / 提示 {summary['notices']}")
        second = (
            f"幂等 {'通过' if summary['idempotent'] else '未通过'} · "
            f"解析错误 {summary['parse_errors']} 行 · "
            f"{_validation_line(report.get('validation'))}")
        if summary["readonly"]:
            second += f" · 只读：{summary['readonly_reason']}"
        if summary["global_skipped"]:
            second += f" · 全局句柄跳过 {summary['global_skipped']} 条"
        return first + "\n" + second

    def _on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        item = self.tree.identify_row(event.y)
        row = self._rows.get(item)
        if row is None:
            return
        if not (row["auto"] or row["patch"]):
            self._append_log(
                f"[*] {row['rule_id'] or '未分类'} 只报告，没有可应用编辑。")
            return
        key = row["key"]
        if key in self._checked:
            self._checked.discard(key)
        else:
            self._checked.add(key)
        self.tree.set(item, "sel", self._mark(row))
        self._update_action_state()

    def _on_tree_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        row = self._rows.get(selection[0])
        if row is None:
            return
        self._set_detail(self._format_detail(row))

    def _format_detail(self, row):
        parts = [
            f"【{row['level']} 级 · {row['severity']}】"
            f"{row['rule_id'] or '未分类'} {row['title']}",
            f"位置：{row['function']} 第 {row['line']} 行"
            + (f" 第 {row['column']} 列" if row.get("column") else ""),
            "对象：" + row["handle_type"]
            + (f" `{row['variable']}`" if row["variable"] else "（内联）"),
            f"创建：`{row['creator']}` · 置信度 "
            f"{int(round(row['confidence'] * 100))}%",
            f"状态：{row['status']} · 处理：{self._handling(row)}",
            "",
            f"证据：{row['evidence']}",
            f"建议：{row['suggestion']}",
        ]
        if row["reasons"]:
            parts.append("判定依据：" + "；".join(row["reasons"]))
        parts.extend(["", "原始上下文：", row["context"] or "（无）"])
        diff = ""
        if self.plan is not None and (row["auto"] or row["patch"]):
            try:
                diff = self.plan.diff(
                    include_patch=True, keys={row["key"]})
            except Exception as exc:  # noqa: BLE001 - 预览失败不影响其他行
                diff = f"（生成 diff 失败：{exc}）"
        parts.extend(["", "本条 diff：", diff or "本条目没有生成编辑（只报告）。"])
        return "\n".join(parts)

    # ---------------------------------------------------------------- 选择
    def select_all_a(self):
        for row in self._rows.values():
            if row["level"] == "A" and row["auto"]:
                self._checked.add(row["key"])
        self._refresh_marks()

    def clear_selection(self):
        self._checked.clear()
        self._refresh_marks()

    def _refresh_marks(self):
        for item, row in self._rows.items():
            self.tree.set(item, "sel", self._mark(row))
        self._update_action_state()

    # ---------------------------------------------------------------- 写回
    def _editable_checked_keys(self, *, include_patch):
        return {
            row["key"]
            for row in self._rows.values()
            if row["key"] in self._checked
            and (row["auto"] or (include_patch and row["patch"]))
        }

    def apply_selected(self):
        if self._busy or self.plan is None or self.map_script is None:
            return
        if self.plan.readonly or self.map_script.language == "lua":
            messagebox.showwarning(
                "只读", self.plan.readonly_reason or "Lua 脚本只读，不写入地图。")
            return
        auto_keys = self._editable_checked_keys(include_patch=False)
        if not auto_keys:
            messagebox.showinfo(
                "没有可自动修复项",
                "请勾选 A 级可自动修复项。\nB 级补丁请使用「仅导出补丁」。")
            return
        diff = self.plan.diff(include_patch=False, keys=auto_keys)
        if not diff:
            messagebox.showinfo("提示", "选中项没有生成可应用的编辑。")
            return
        if not self._confirm_diff(diff, auto_keys):
            return

        self._set_busy(True, "正在应用修复...")
        self._append_log("")
        self._append_log(f"[*] 准备应用 {len(auto_keys)} 条自动修复。")

        def worker():
            try:
                result = write_fix_plan(
                    self.plan, self.map_script, selection=auto_keys,
                    pjass_path=self._pjass_path, validate=True)
            except Exception as exc:  # noqa: BLE001 - 写回异常要回显
                result = {
                    "written": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "validation": {"status": "unchecked"},
                }
            self.app.root.after(0, self._apply_done, result)

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_diff(self, diff, keys):
        dialog = tk.Toplevel(self)
        dialog.title("确认应用修复")
        dialog.geometry("900x600")
        dialog.transient(self.winfo_toplevel())
        dialog.configure(bg="#ffffff")

        tk.Label(
            dialog,
            text=(f"将应用 {len(keys)} 条修复。原图不会被修改，"
                  "输出写入 *_leakfixed 副本；写入前会做 pjass 语法校验。"),
            bg="#ffffff", fg="#2c3e50", font=("微软雅黑", 9),
            justify=tk.LEFT, anchor=tk.W).pack(fill=tk.X, padx=12, pady=(10, 6))

        text = scrolledtext.ScrolledText(
            dialog, font=("Consolas", 9), bg="#fbfcfd")
        text.pack(fill=tk.BOTH, expand=True, padx=12)
        text.insert(tk.END, diff)
        text.config(state=tk.DISABLED)

        result = {"ok": False}
        buttons = tk.Frame(dialog, bg="#ffffff")
        buttons.pack(fill=tk.X, padx=12, pady=10)

        def confirm():
            result["ok"] = True
            dialog.destroy()

        tk.Button(
            buttons, text="确认应用", command=confirm, bg="#27ae60",
            fg="white", font=("微软雅黑", 10, "bold"), width=12).pack(
                side=tk.RIGHT)
        tk.Button(
            buttons, text="取消", command=dialog.destroy, width=10).pack(
                side=tk.RIGHT, padx=(0, 8))
        dialog.grab_set()
        self.wait_window(dialog)
        return result["ok"]

    def _apply_done(self, result):
        validation = result.get("validation") or {"status": "unchecked"}
        if self.report is not None:
            self.report["validation"] = validation
            self.summary_var.set(self._summary_text(self.report))
        self._append_log(f"[*] {_validation_line(validation)}")
        for error in (validation.get("errors") or [])[:5]:
            self._append_log(
                f"    {error.get('line')}:{error.get('column')} "
                f"{error.get('message')}")
        if result.get("written"):
            self._applied = True
            self._undo_script = self.map_script
            output = result.get("output_path") or ""
            self._last_output_dir = (
                os.path.dirname(output) if output else self.app.data_dir)
            verification = result.get("verification") or {}
            if verification.get("verified"):
                self._append_log("[+] 写回后重新提取校验通过。")
            self._append_log(f"[+] 已写入副本: {output}")
            if result.get("backup_path"):
                self._append_log(
                    f"[*] 已备份上一次副本: {result['backup_path']}")
            self._append_log("[*] 如需继续修改，请重新扫描输出副本。")
            self.status_var.set("修复完成")
            messagebox.showinfo(
                "修复完成",
                "已写入地图副本：\n"
                f"{output}\n\n原图未被修改，可使用「撤销上次写回」恢复。")
        else:
            error = result.get("error") or "未写入地图"
            self._append_log(f"[-] 修复未完成: {error}")
            self.status_var.set("修复未完成")
            messagebox.showwarning("修复未完成", error)
        self._set_busy(
            False, "修复完成" if result.get("written") else "修复未完成")

    def undo_last_write(self):
        if self._busy or self._undo_script is None:
            return
        try:
            undone = self._undo_script.undo()
        except Exception as exc:  # noqa: BLE001 - 撤销失败要回显
            self._append_log(f"[-] 撤销失败: {exc}")
            messagebox.showerror("撤销失败", str(exc))
            return
        if undone:
            self._append_log("[+] 已撤销上一次写回（恢复备份或删除本次输出）。")
            self.status_var.set("已撤销写回")
            self._undo_script = None
            self._applied = False
        else:
            self._append_log("[-] 没有可撤销的写回记录。")
        self._update_action_state()

    # -------------------------------------------------------------- 导出
    def export_report(self):
        if self.report is None or self._busy:
            messagebox.showinfo("提示", "请先完成一次扫描。")
            return
        out_dir = os.path.join(self.app.data_dir, "leak_reports")
        base_name = (
            os.path.basename(self.map_script.source_path)
            if self.map_script else self.report["meta"]["map_name"])
        try:
            paths = write_leak_report(
                self.report, out_dir, base_name=base_name)
        except Exception as exc:  # noqa: BLE001 - 导出失败要回显
            self._append_log(f"[-] 导出报告失败: {exc}")
            messagebox.showerror("导出失败", str(exc))
            return
        self._last_output_dir = out_dir
        self._append_log("[+] 统一报告已导出：")
        for kind, path in paths.items():
            self._append_log(f"    {kind}: {path}")
        self.status_var.set("报告已导出")
        self._update_action_state()
        messagebox.showinfo(
            "报告已导出",
            "已生成 Markdown / JSON / CSV 三份报告：\n" + out_dir)

    def export_patch(self):
        if self.plan is None or self._busy:
            messagebox.showinfo("提示", "请先完成一次扫描。")
            return
        keys = self._editable_checked_keys(include_patch=True)
        if not keys:
            messagebox.showinfo("提示", "请先勾选需要导出的条目。")
            return
        diff = self.plan.diff(include_patch=True, keys=keys)
        if not diff:
            messagebox.showinfo("提示", "选中项没有生成可导出的编辑。")
            return
        out_dir = os.path.join(self.app.data_dir, "leak_reports")
        os.makedirs(out_dir, exist_ok=True)
        stem = _safe_stem(
            self.map_script.source_path if self.map_script else "leak")
        path = os.path.join(out_dir, f"{stem}_leakfix.patch")
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(diff)
        except OSError as exc:
            self._append_log(f"[-] 导出补丁失败: {exc}")
            messagebox.showerror("导出失败", str(exc))
            return
        self._last_output_dir = out_dir
        self._append_log(f"[+] 补丁已导出: {path}")
        self.status_var.set("补丁已导出")
        self._update_action_state()
        messagebox.showinfo(
            "补丁已导出",
            "只生成了 diff 文件，没有修改任何地图：\n" + path)

    def open_output_dir(self):
        path = self._last_output_dir or self.app.data_dir
        if not path or not os.path.isdir(path):
            messagebox.showinfo("提示", "还没有可打开的输出目录。")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                self._append_log(f"[*] 输出目录: {path}")
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))

    # -------------------------------------------------------------- 状态
    def _set_busy(self, busy, label=None):
        self._busy = busy
        if busy:
            self.progress.start(12)
            self.status_var.set(label or "处理中...")
        else:
            self.progress.stop()
            if label:
                self.status_var.set(label)
        self._update_action_state()

    def _update_action_state(self):
        busy = self._busy
        has_plan = self.plan is not None
        editable = has_plan and not self.plan.readonly and not self._applied
        checked_rows = [
            row for row in self._rows.values()
            if row["key"] in self._checked]
        has_auto = any(row["auto"] for row in checked_rows)
        has_editable = any(row["auto"] or row["patch"] for row in checked_rows)
        self.scan_btn.config(state=tk.DISABLED if busy else tk.NORMAL)
        self.report_btn.config(
            state=tk.NORMAL if (self.report is not None and not busy)
            else tk.DISABLED)
        self.apply_btn.config(
            state=tk.NORMAL if (editable and has_auto and not busy)
            else tk.DISABLED)
        self.patch_btn.config(
            state=tk.NORMAL if (
                has_plan and not self.plan.readonly
                and has_editable and not busy)
            else tk.DISABLED)
        self.undo_btn.config(
            state=tk.NORMAL if (self._undo_script is not None and not busy)
            else tk.DISABLED)
        self.open_btn.config(
            state=tk.NORMAL if (self._last_output_dir and not busy)
            else tk.DISABLED)
