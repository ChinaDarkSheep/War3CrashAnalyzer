"""玩家一键上传：采集最近崩溃与 KK 会话日志，复用服务端 /api/upload。

只上传崩溃日志、同名 dump 与最近一次平台会话日志；不上传地图、配置或
本机其它文件。上传前由界面明确告知内容，上传后返回 6 位上传码。
"""

import json
import os
import re
import stat
import urllib.error
import urllib.request
import uuid

from core.map_meta import read_map_meta

SERVER_UPLOAD_URLS = (
    "http://ca.darksheep.vip/api/upload",
    "http://43.163.75.93:2234/api/upload",
)
USER_AGENT = "War3CrashAnalyzer/1.1 (+https://github.com/ChinaDarkSheep/War3CrashAnalyzer)"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_ZONE = 40
MAX_KK_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".log", ".dmp", ".mdmp", ".bin"}

SESSION_PATTERN = re.compile(r"^\d{4}_\d{2}_\d{2} \d{2}_\d{2}_\d{2}\.\d{3}$")
CRASH_PRIMARY_NAMES = ("crash.txt", "error.txt", "war3crash.txt", "bug.txt")


def _is_primary(name):
    lowered = name.lower()
    return _ext(name) == ".txt" and any(
        lowered == primary or lowered.endswith(" " + primary)
        or lowered.endswith("_" + primary)
        for primary in CRASH_PRIMARY_NAMES)


class UploadError(Exception):
    """上传前的可读错误，界面直接展示 message。"""


def _is_file(path):
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def _ext(path):
    return os.path.splitext(path)[1].lower()


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def _walk(root):
    entries = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append((rel, full))
    entries.sort()
    return entries


def latest_crash_log(war3_path):
    """返回配置目录下最新的一份崩溃日志及同名 dump；没有则返回 None。"""
    war3_path = (war3_path or "").strip().strip('"')
    if not war3_path:
        return None
    errors_dir = os.path.join(war3_path, "Errors")
    if not os.path.isdir(errors_dir):
        return None
    candidates = []
    try:
        names = os.listdir(errors_dir)
    except OSError:
        return None
    for name in names:
        if not _is_primary(name):
            continue
        path = os.path.join(errors_dir, name)
        if not _is_file(path) or _size(path) == 0:
            continue
        try:
            candidates.append((os.path.getmtime(path), path))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    log_path = candidates[0][1]
    dmp_path = None
    stem = os.path.splitext(log_path)[0]
    for suffix in (".dmp", ".mdmp"):
        if _is_file(stem + suffix):
            dmp_path = stem + suffix
            break
    return {
        "log_path": log_path,
        "dmp_path": dmp_path,
        "name": os.path.basename(log_path),
        "size": _size(log_path),
        "modified": candidates[0][0],
    }


def collect_crash_files(log_path):
    """把一份崩溃日志与同名 dump 组织成服务端崩溃区的相对路径列表。"""
    log_path = (log_path or "").strip().strip('"')
    if not _is_file(log_path):
        raise UploadError("崩溃日志不存在或不可读取")
    name = os.path.basename(log_path)
    if not _is_primary(name):
        raise UploadError(
            "请选择命名为 Crash.txt / Error.txt / War3Crash.txt / Bug.txt 的崩溃日志")
    folder = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", os.path.splitext(name)[0])[:80] or "crash"
    files = [(f"{folder}/{name}", log_path)]
    stem = os.path.splitext(log_path)[0]
    for suffix in (".dmp", ".mdmp"):
        dmp = stem + suffix
        if _is_file(dmp):
            files.append((f"{folder}/{os.path.basename(dmp)}", dmp))
            break
    return files


def _process_kk_roots():
    roots = []
    try:
        import psutil
    except Exception:
        return roots
    for proc in psutil.process_iter(["exe"]):
        try:
            exe = (proc.info.get("exe") or "").replace("/", "\\")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        lowered = exe.lower()
        marker = "\\kkduizhan\\"
        index = lowered.find(marker)
        if index < 0:
            continue
        roots.append(exe[:index + len("\\kkduizhan")])
    return roots


def find_kk_log_dirs(extra=()):
    """探测 KK 平台日志目录；安装路径因人而异，探测失败时由用户手动选择。"""
    candidates = [item for item in (extra or ()) if item]
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if base:
            candidates.append(os.path.join(base, "kkduizhan", "log"))
    candidates.extend(os.path.join(root, "log") for root in _process_kk_roots())

    found = []
    seen = set()
    for path in candidates:
        path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(path):
            found.append(path)
    return found


def find_latest_kk_session(log_dir):
    """在 KK 的 log 目录下找最近一次会话（形如 2026_11_06 10_00_00.000）。"""
    if not log_dir or not os.path.isdir(log_dir):
        return None
    sessions = []
    try:
        names = os.listdir(log_dir)
    except OSError:
        return None
    for name in names:
        path = os.path.join(log_dir, name)
        if SESSION_PATTERN.fullmatch(name) and os.path.isdir(path):
            sessions.append((name, path))
    if not sessions:
        return None
    sessions.sort(reverse=True)
    for _, path in sessions:
        if any(os.path.basename(rel).lower() == "war3dll.log"
               for rel, _ in _walk(path)):
            return path
    return sessions[0][1]


def collect_kk_files(log_dir):
    """采集最近一次平台会话；只取白名单扩展名，并受体积与数量限制。"""
    log_dir = (log_dir or "").strip().strip('"')
    if not log_dir or not os.path.isdir(log_dir):
        raise UploadError("KK 日志目录不存在")
    session = find_latest_kk_session(log_dir)
    if session is None and not any(
            _is_file(os.path.join(log_dir, name))
            for name in ("platform.log", "downloader.log", "war3dll.log")):
        raise UploadError("该目录中没有找到 KK 平台日志（platform.log / downloader.log / war3dll.log）")

    files = []
    total = 0

    def add(path, rel):
        nonlocal total
        if len(files) >= MAX_FILES_PER_ZONE:
            return
        if _ext(path) not in ALLOWED_EXTENSIONS or not _is_file(path):
            return
        size = _size(path)
        if total + size > MAX_KK_BYTES:
            return
        if any(existing.lower() == rel.lower() for existing, _ in files):
            return
        files.append((rel, path))
        total += size

    for name in ("platform.log", "downloader.log"):
        direct = os.path.join(log_dir, name)
        if _is_file(direct):
            add(direct, name)

    if session:
        entries = _walk(session)
        entries.sort(key=lambda item: (
            os.path.basename(item[0]).lower() != "war3dll.log",
            -os.path.getmtime(item[1]) if _is_file(item[1]) else 0))
        for rel, full in entries:
            add(full, os.path.relpath(full, log_dir).replace(os.sep, "/"))
    else:
        for name in ("war3dll.log",):
            direct = os.path.join(log_dir, name)
            if _is_file(direct):
                add(direct, name)
        war3_root = os.path.join(log_dir, "war3")
        if os.path.isdir(war3_root):
            entries = _walk(war3_root)
            entries.sort(key=lambda item: -os.path.getmtime(item[1])
                         if _is_file(item[1]) else 0)
            for rel, full in entries:
                add(full, os.path.relpath(full, log_dir).replace(os.sep, "/"))

    if not files:
        raise UploadError("KK 日志目录中没有可上传的日志文件")
    return files


def _build_multipart(fields, files):
    boundary = "----War3Crash" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8"))
    for field, rel, path, data in files:
        chunks.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="upload.bin"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n".encode("utf-8"))
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


_KK_REL_MAP = re.compile(
    r"wa\(661\),\s*path:\s*([^\r\n]+?\.(?:w3x|w3m|w3n))", re.IGNORECASE)
_KK_ABS_MAP = re.compile(
    r"([A-Za-z]:\\[^\r\n<>|\"?*]+?\.(?:w3x|w3m|w3n))", re.IGNORECASE)
_MAP_META_CACHE = {}


def _decode_log(raw):
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _within(path, root):
    try:
        return os.path.commonpath(
            [os.path.abspath(path), os.path.abspath(root)]).lower() == \
            os.path.abspath(root).lower()
    except ValueError:
        return False


def _kk_map_candidates(kk_files):
    """从 KK 的 war3dll.log / downloader.log 收集地图相对与绝对路径。"""
    relatives, absolutes = [], []
    for rel, path in kk_files:
        if os.path.basename(rel).lower() not in ("war3dll.log", "downloader.log"):
            continue
        try:
            with open(path, "rb") as handle:
                text = _decode_log(handle.read(2 * 1024 * 1024))
        except OSError:
            continue
        relatives.extend(match.group(1).strip() for match in _KK_REL_MAP.finditer(text))
        absolutes.extend(match.group(1).strip() for match in _KK_ABS_MAP.finditer(text))
    return relatives, absolutes


def find_session_map(kk_files, war3_path):
    """定位本次 KK 会话使用的本地地图文件；只允许读取魔兽目录内的文件。"""
    war3_path = (war3_path or "").strip().strip('"')
    if not war3_path or not os.path.isdir(war3_path):
        return None
    relatives, absolutes = _kk_map_candidates(kk_files)

    for candidate in absolutes:
        candidate = candidate.strip().strip('"')
        if os.path.isfile(candidate) and _within(candidate, war3_path):
            return os.path.abspath(candidate)

    for relative in relatives:
        relative = relative.replace("/", "\\").lstrip("\\")
        candidate = os.path.join(war3_path, relative)
        if os.path.isfile(candidate) and _within(candidate, war3_path):
            return os.path.abspath(candidate)
    return None


def session_map_meta(kk_files, war3_path):
    """读取会话地图的名称与作者；失败或非本地可信路径时返回 None。"""
    map_path = find_session_map(kk_files, war3_path)
    if not map_path:
        return None
    try:
        stat = os.stat(map_path)
    except OSError:
        return None
    cache_key = (map_path.lower(), stat.st_mtime, stat.st_size)
    if cache_key not in _MAP_META_CACHE:
        _MAP_META_CACHE[cache_key] = read_map_meta(map_path)
    meta = _MAP_META_CACHE[cache_key]
    return dict(meta) if meta else None


def plan_upload(log_path, kk_dir=None, war3_path=None):
    """生成上传清单，供界面展示与体积校验。"""
    crash_files = collect_crash_files(log_path)
    kk_files = collect_kk_files(kk_dir) if kk_dir else []
    total = sum(_size(path) for _, path in crash_files + kk_files)
    if total > MAX_UPLOAD_BYTES:
        raise UploadError("待上传内容超过 50 MB，请只保留最近一次崩溃与会话日志")
    return {
        "crash_files": crash_files,
        "kk_files": kk_files,
        "crash_count": len(crash_files),
        "kk_count": len(kk_files),
        "total_bytes": total,
        "kk_session": os.path.basename(find_latest_kk_session(kk_dir)) if kk_dir else None,
        "map_meta": session_map_meta(kk_files, war3_path) if kk_files else None,
    }


def _post(url, body, content_type, timeout):
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": content_type, "User-Agent": USER_AGENT,
                 "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _status_url(upload_url, code):
    base = upload_url.rstrip("/")
    if base.endswith("/api/upload"):
        base = base[:-len("/api/upload")]
    return f"{base}/api/upload/{code}"


def query_upload(code, server_urls=None, timeout=10):
    """按 6 位上传码查询公开状态与维护者反馈。"""
    code = (code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise UploadError("上传码应为 6 位数字")
    urls = list(server_urls or SERVER_UPLOAD_URLS)
    last_error = None
    for upload_url in urls:
        request = urllib.request.Request(
            _status_url(upload_url, code), method="GET",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                     "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                data = json.loads(exc.read().decode("utf-8"))
                detail = data.get("message") or data.get("error") or ""
            except Exception:
                pass
            if exc.code == 429:
                raise UploadError(detail or "查询过于频繁，请稍后再试")
            last_error = UploadError(detail or f"查询失败（HTTP {exc.code}）")
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = UploadError(f"无法连接查询服务器：{exc}")
            continue
        if isinstance(payload, dict) and payload.get("code"):
            payload.setdefault("server", request.full_url)
            return payload
        last_error = UploadError("查询服务返回内容无法识别")
    raise last_error or UploadError("查询失败，请检查网络后重试")


def upload_logs(log_path, kk_dir=None, server_urls=None, timeout=60, log=None,
                war3_path=None):
    """上传最近崩溃与可选 KK 会话，返回服务端响应（含 6 位上传码）。"""
    notify = log or (lambda message: None)
    plan = plan_upload(log_path, kk_dir, war3_path)
    crash_files = plan["crash_files"]
    kk_files = plan["kk_files"]
    notify(f"[*] 已整理 {len(crash_files)} 个崩溃文件与 "
           f"{len(kk_files)} 个平台日志，共 {plan['total_bytes']} 字节")
    meta = plan.get("map_meta") or {}
    if meta.get("name") or meta.get("author"):
        notify(f"[*] 地图元数据：{meta.get('name') or '未知'}"
               f" / {meta.get('author') or '作者未知'}")

    files = []
    for rel, path in crash_files:
        files.append(("crash", rel, path, _read(path)))
    fields = {"crash_paths": json.dumps(
        [rel for rel, _ in crash_files], ensure_ascii=False)}
    map_meta = plan.get("map_meta") or {}
    if map_meta.get("name"):
        fields["map_name"] = map_meta["name"]
    if map_meta.get("author"):
        fields["map_author"] = map_meta["author"]
    if kk_files:
        for rel, path in kk_files:
            files.append(("kk", rel, path, _read(path)))
        fields["kk_paths"] = json.dumps(
            [rel for rel, _ in kk_files], ensure_ascii=False)

    body, content_type = _build_multipart(fields, files)
    urls = list(server_urls or SERVER_UPLOAD_URLS)
    last_error = None
    for url in urls:
        notify(f"[*] 正在连接 {url} …")
        try:
            payload = _post(url, body, content_type, timeout)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                data = json.loads(exc.read().decode("utf-8"))
                detail = data.get("message") or data.get("error") or ""
            except Exception:
                pass
            last_error = UploadError(detail or f"上传服务返回 HTTP {exc.code}")
            if exc.code in (400, 413, 429):
                raise last_error
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = UploadError(f"无法连接上传服务器：{exc}")
            continue
        if not isinstance(payload, dict) or not payload.get("code"):
            last_error = UploadError("上传服务返回内容无法识别")
            continue
        notify(f"[+] 服务端已接收，上传码 {payload['code']}")
        payload.setdefault("server", url)
        return payload
    raise last_error or UploadError("上传失败，请检查网络后重试")
