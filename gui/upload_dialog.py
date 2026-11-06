"""一键上传对话框：确认内容后把最近崩溃与 KK 会话日志交给维护者。"""

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from core import uploader


def _human_size(size):
    value = float(size or 0)
    for unit in ("B", "KB", "MB"):
        if value < 1024 or unit == "MB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} MB"


class UploadLogsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("上传崩溃日志给维护者")
        self.geometry("680x620")
        self.resizable(False, True)
        self.transient(parent)

        self.crash_info = None
        self._busy = False
        self._plan = None
        self.kk_enabled = tk.BooleanVar(value=False)
        self.kk_path = tk.StringVar()
        self.code_var = tk.StringVar(value="")

        self._build()
        self._load_latest()
        self._detect_kk()

    # ---------- 界面 ----------
    def _build(self):
        outer = tk.Frame(self, padx=12, pady=8)
        outer.pack(fill=tk.BOTH, expand=True)

        crash_frame = tk.LabelFrame(outer, text=" 1. 崩溃日志 ", padx=8, pady=6)
        crash_frame.pack(fill=tk.X)
        self.crash_label = tk.Label(crash_frame, text="正在查找…", anchor="w",
                                    justify=tk.LEFT, fg="#2c3e50")
        self.crash_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(crash_frame, text="更换日志", width=9,
                  command=self._browse_crash).pack(side=tk.RIGHT)

        kk_frame = tk.LabelFrame(outer, text=" 2. KK 平台日志（可选） ",
                                 padx=8, pady=6)
        kk_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Checkbutton(
            kk_frame, text="附加 KK 平台最近一次会话日志",
            variable=self.kk_enabled, command=self._refresh_plan,
            anchor="w").pack(fill=tk.X)
        row = tk.Frame(kk_frame)
        row.pack(fill=tk.X, pady=(4, 0))
        tk.Entry(row, textvariable=self.kk_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="浏览", width=7,
                  command=self._browse_kk).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(row, text="自动查找", width=8,
                  command=self._detect_kk).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Label(
            kk_frame,
            text="KK 安装路径因人而异，常见位置是 kkduizhan\\log；"
                 "若未自动识别，请从平台快捷方式打开安装目录后选择其中的 log 文件夹。",
            fg="#7f8c8d", anchor="w", justify=tk.LEFT, wraplength=620).pack(
            fill=tk.X, pady=(4, 0))

        privacy = tk.LabelFrame(outer, text=" 上传内容说明 ", padx=8, pady=4)
        privacy.pack(fill=tk.X, pady=(8, 0))
        tk.Label(
            privacy,
            text="上传：崩溃日志文本、同名 .dmp（如有）、所选 KK 会话日志。\n"
                 "这些日志可能包含 Windows 用户名、计算机名、本地路径或平台昵称。\n"
                 "不会上传：地图文件、配置、历史库或其它本机文件。\n"
                 "原始日志由服务端私有保存 14 天后自动删除；上传成功会返回 6 位上传码，"
                 "可发给维护者在群里核对。",
            fg="#555555", anchor="w", justify=tk.LEFT, wraplength=620).pack(
            fill=tk.X)

        self.plan_label = tk.Label(outer, text="", fg="#16a085", anchor="w",
                                   justify=tk.LEFT, wraplength=640)
        self.plan_label.pack(fill=tk.X, pady=(6, 0))

        log_frame = tk.LabelFrame(outer, text=" 上传进度 ", padx=4, pady=4)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        result = tk.Frame(outer)
        result.pack(fill=tk.X, pady=(8, 0))
        tk.Label(result, text="上传码：", font=("微软雅黑", 10, "bold")).pack(
            side=tk.LEFT)
        tk.Entry(result, textvariable=self.code_var, width=10, state="readonly",
                 font=("Consolas", 14, "bold"), justify=tk.CENTER).pack(
            side=tk.LEFT)
        self.copy_btn = tk.Button(result, text="复制上传码", width=10,
                                  state=tk.DISABLED, command=self._copy_code)
        self.copy_btn.pack(side=tk.LEFT, padx=(6, 0))

        buttons = tk.Frame(outer)
        buttons.pack(fill=tk.X, pady=(8, 0))
        self.upload_btn = tk.Button(
            buttons, text="开始上传", width=14, bg="#2980b9", fg="white",
            font=("微软雅黑", 9, "bold"), command=self._start_upload)
        self.upload_btn.pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(buttons, text="关闭", width=8,
                  command=self._close).pack(side=tk.RIGHT)

    # ---------- 数据 ----------
    def _load_latest(self):
        self.crash_info = uploader.latest_crash_log(self.app.war3_path.get())
        if not self.crash_info:
            self.crash_label.config(
                text="未在魔兽目录的 Errors 中找到崩溃日志，请点击“更换日志”手动选择。",
                fg="#c0392b")
            return
        info = self.crash_info
        modified = time.strftime("%Y-%m-%d %H:%M:%S",
                                 time.localtime(info["modified"]))
        dmp = "含同名 dmp" if info["dmp_path"] else "无同名 dmp"
        self.crash_label.config(
            text=f"{info['name']}（{_human_size(info['size'])}，{modified}，{dmp}）",
            fg="#2c3e50")

    def _detect_kk(self):
        configured = (self.app.config or {}).get("kk_log_path") or ""
        current = self.kk_path.get().strip()
        candidates = [item for item in (current, configured) if item]
        dirs = uploader.find_kk_log_dirs(candidates)
        if dirs:
            self.kk_path.set(dirs[0])
            self.kk_enabled.set(True)
            self._append_log(f"[*] 已识别 KK 日志目录: {dirs[0]}")
        else:
            self.kk_enabled.set(False)
            self._append_log("[!] 未自动识别 KK 日志目录；如需要请手动选择。")
        self._refresh_plan()

    def _browse_crash(self):
        path = filedialog.askopenfilename(
            title="选择崩溃日志",
            filetypes=[("崩溃日志", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            files = uploader.collect_crash_files(path)
        except uploader.UploadError as exc:
            messagebox.showwarning("无法使用该文件", str(exc), parent=self)
            return
        self.crash_info = {
            "log_path": path,
            "dmp_path": files[1][1] if len(files) > 1 else None,
            "name": os.path.basename(path),
            "size": os.path.getsize(path),
            "modified": os.path.getmtime(path),
        }
        modified = time.strftime("%Y-%m-%d %H:%M:%S",
                                 time.localtime(self.crash_info["modified"]))
        dmp = "含同名 dmp" if self.crash_info["dmp_path"] else "无同名 dmp"
        self.crash_label.config(
            text=f"{self.crash_info['name']}（{_human_size(self.crash_info['size'])}，"
                 f"{modified}，{dmp}）", fg="#2c3e50")
        self._refresh_plan()

    def _browse_kk(self):
        initial = self.kk_path.get().strip() or None
        path = filedialog.askdirectory(title="选择 KK 平台 log 目录",
                                       initialdir=initial)
        if not path:
            return
        self.kk_path.set(path.replace("/", "\\"))
        self.kk_enabled.set(True)
        self._remember_kk()
        self._refresh_plan()

    def _remember_kk(self):
        path = self.kk_path.get().strip()
        if path:
            self.app.config["kk_log_path"] = path
            try:
                self.app.save_config()
            except Exception:
                pass

    def _kk_dir(self):
        if not self.kk_enabled.get():
            return None
        path = self.kk_path.get().strip().strip('"')
        if not path or not os.path.isdir(path):
            raise uploader.UploadError("请选择有效的 KK 日志目录，或取消勾选平台日志")
        return path

    def _refresh_plan(self):
        self._plan = None
        if not self.crash_info:
            self.plan_label.config(text="请先选择崩溃日志。", fg="#c0392b")
            return
        try:
            plan = uploader.plan_upload(
                self.crash_info["log_path"], self._kk_dir(),
                self.app.war3_path.get())
        except uploader.UploadError as exc:
            self.plan_label.config(text=f"待上传内容不可用：{exc}", fg="#c0392b")
            return
        self._plan = plan
        kk_part = (f"，平台日志 {plan['kk_count']} 个"
                   f"（会话 {plan['kk_session']}）" if plan["kk_count"] else "")
        meta = plan.get("map_meta") or {}
        map_part = ""
        if meta.get("name") or meta.get("author"):
            map_part = (f"；地图 {meta.get('name') or '未知'}"
                        f"（作者 {meta.get('author') or '未知'}）")
        self.plan_label.config(
            text=f"将上传 {plan['crash_count']} 个崩溃文件{kk_part}，"
                 f"共 {_human_size(plan['total_bytes'])}{map_part}。",
            fg="#16a085")

    # ---------- 上传 ----------
    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log_threadsafe(self, message):
        try:
            self.after(0, self._append_log, message)
        except Exception:
            pass

    def _start_upload(self):
        if self._busy:
            return
        if not self.crash_info:
            messagebox.showwarning("缺少崩溃日志", "请先选择要上传的崩溃日志。",
                                   parent=self)
            return
        try:
            kk_dir = self._kk_dir()
            plan = uploader.plan_upload(
                self.crash_info["log_path"], kk_dir, self.app.war3_path.get())
        except uploader.UploadError as exc:
            messagebox.showwarning("无法上传", str(exc), parent=self)
            return

        kk_text = (f"平台日志 {plan['kk_count']} 个（最近会话）"
                   if plan["kk_count"] else "不附加平台日志")
        meta = plan.get("map_meta") or {}
        map_text = ""
        if meta.get("name") or meta.get("author"):
            map_text = (f"• 地图：{meta.get('name') or '未知'}"
                        f"（作者 {meta.get('author') or '未知'}）\n")
        confirm = (
            f"即将上传：\n"
            f"• 崩溃日志 {plan['crash_count']} 个\n"
            f"• {kk_text}\n"
            f"{map_text}"
            f"• 合计 {_human_size(plan['total_bytes'])}\n\n"
            "不会上传地图文件，仅读取地图名与作者随日志一起提交。\n"
            "原始日志在服务端私有保存 14 天后删除。\n\n"
            "确定现在上传吗？")
        if not messagebox.askyesno("确认上传", confirm, parent=self):
            return

        self._busy = True
        self.upload_btn.config(state=tk.DISABLED, text="正在上传…")
        self.copy_btn.config(state=tk.DISABLED)
        self.code_var.set("")
        self._append_log(f"[*] 开始上传，共 {_human_size(plan['total_bytes'])}…")

        def worker():
            try:
                payload = uploader.upload_logs(
                    self.crash_info["log_path"], kk_dir,
                    log=self._log_threadsafe,
                    war3_path=self.app.war3_path.get())
            except uploader.UploadError as exc:
                self.after(0, self._failed, str(exc))
                return
            except Exception as exc:
                self.after(0, self._failed, f"上传过程出错：{exc}")
                return
            if kk_dir:
                self._remember_kk()
            self.after(0, self._succeeded, payload)

        threading.Thread(target=worker, daemon=True).start()

    def _failed(self, message):
        self._busy = False
        self.upload_btn.config(state=tk.NORMAL, text="重新上传")
        self._append_log(f"[-] {message}")
        messagebox.showerror("上传失败", message, parent=self)

    def _succeeded(self, payload):
        self._busy = False
        self.upload_btn.config(state=tk.NORMAL, text="再次上传")
        code = str(payload.get("code") or "")
        self.code_var.set(code)
        self.copy_btn.config(state=tk.NORMAL)
        if code:
            self.app.config["last_upload_code"] = code
            try:
                self.app.save_config()
            except Exception:
                pass
        if payload.get("duplicate"):
            self._append_log("[*] 相同内容此前已上传，返回原上传码。")
        self._append_log(f"[+] 上传成功，上传码 {code}"
                         f"（有效期至 {payload.get('expires_at')}）")
        self._copy_code()
        messagebox.showinfo(
            "上传成功",
            f"上传码：{code}\n\n"
            f"原始日志保留至：{payload.get('expires_at')}\n"
            "上传码已复制到剪贴板，可以发给维护者在群里核对。",
            parent=self)

    def _copy_code(self):
        code = self.code_var.get().strip()
        if not code:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(code)
        except Exception:
            pass

    def _close(self):
        if self._busy and not messagebox.askyesno(
                "正在上传", "上传尚未完成，确定关闭窗口吗？", parent=self):
            return
        self.destroy()
