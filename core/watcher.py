"""监听魔兽崩溃日志目录，发现新日志后触发诊断回调。

监听范围：
- 配置的魔兽目录下的 Errors
- 与该目录同级的其它魔兽副本（对战平台常各自带一份游戏）
- 正在运行的 war3 / Frozen Throne 进程所在目录（定期刷新）

日志只有在大小与修改时间连续两次扫描保持不变、且写入已结束一段时间后
才会触发，避免读到只写了一半的文件。
"""

import os
import time


_GAME_EXES = ("war3.exe", "warcraft iii.exe", "frozen throne.exe")
_GAME_PROCESSES = frozenset(_GAME_EXES)


def _has_game_exe(path):
    return any(os.path.exists(os.path.join(path, exe)) for exe in _GAME_EXES)


def _errors_dir(root):
    path = os.path.join(root, "Errors")
    return path if os.path.isdir(path) else None


def running_game_roots():
    """返回当前运行的魔兽进程所在目录，用于发现平台自带的游戏副本。"""
    roots = []
    try:
        import psutil
    except Exception:
        return roots
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name not in _GAME_PROCESSES:
                continue
            exe = proc.info.get("exe")
            if exe:
                roots.append(os.path.dirname(exe))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return roots


def discover_error_dirs(war3_path, extra_roots=()):
    """汇总所有待监听的 Errors 目录，按真实路径去重。"""
    roots = []
    if war3_path:
        roots.append(war3_path)
    if war3_path:
        parent = os.path.dirname(os.path.normpath(war3_path))
        try:
            for name in os.listdir(parent):
                candidate = os.path.join(parent, name)
                if not os.path.isdir(candidate) or not _has_game_exe(candidate):
                    continue
                if os.path.normcase(os.path.normpath(candidate)) == \
                        os.path.normcase(os.path.normpath(war3_path)):
                    continue
                roots.append(candidate)
        except OSError:
            pass
    roots.extend(extra_roots or ())

    dirs = []
    seen = set()
    for root in roots:
        path = _errors_dir(root)
        if not path:
            continue
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        dirs.append(path)
    return dirs


class CrashLogWatcher:
    def __init__(self, get_war3_path, get_enabled, on_new_log,
                 log=None, interval=3.0, settle=2.0, rescan=30.0):
        self.get_war3_path = get_war3_path
        self.get_enabled = get_enabled
        self.on_new_log = on_new_log
        self.log = log or (lambda message: None)
        self.interval = interval
        self.settle = settle
        self.rescan = rescan

        self._war3_path = None
        self._dirs = []
        self._dirs_at = 0.0
        self._baselined = set()
        self._known = {}
        self._pending = {}

    def _baseline(self, directory):
        try:
            names = os.listdir(directory)
        except OSError:
            return
        for name in names:
            if not name.lower().endswith(".txt"):
                continue
            path = os.path.join(directory, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            self._known[path] = (stat.st_size, stat.st_mtime)

    def _refresh_dirs(self, war3_path):
        now = time.time()
        normalized = os.path.normpath(war3_path) if war3_path else None
        if (normalized == self._war3_path
                and now - self._dirs_at < self.rescan):
            return
        self._war3_path = normalized
        self._dirs_at = now
        dirs = discover_error_dirs(war3_path, running_game_roots())
        if dirs != self._dirs:
            self._dirs = dirs
            if dirs:
                self.log(f"[*] 自动收集监听 {len(dirs)} 个 Errors 目录")
        for directory in dirs:
            if directory in self._baselined:
                continue
            self._baselined.add(directory)
            self._baseline(directory)

    def scan_once(self, war3_path):
        """扫描一轮，返回已经稳定下来的新日志路径。"""
        self._refresh_dirs(war3_path)
        now = time.time()
        new_logs = []
        for directory in self._dirs:
            try:
                names = os.listdir(directory)
            except OSError:
                continue
            for name in names:
                if not name.lower().endswith(".txt"):
                    continue
                path = os.path.join(directory, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if stat.st_size == 0:
                    continue
                signature = (stat.st_size, stat.st_mtime)
                if self._known.get(path) == signature:
                    self._pending.pop(path, None)
                    continue
                if now - stat.st_mtime < self.settle:
                    continue
                if self._pending.get(path) != signature:
                    self._pending[path] = signature
                    continue
                self._pending.pop(path, None)
                self._known[path] = signature
                new_logs.append(path)
        return new_logs

    def run(self, stop_event):
        while not stop_event.wait(self.interval):
            if not self.get_enabled():
                continue
            war3_path = self.get_war3_path()
            if not war3_path:
                continue
            try:
                for path in self.scan_once(war3_path):
                    self.on_new_log(path)
            except Exception as e:
                self.log(f"[-] 自动收集异常: {e}")
