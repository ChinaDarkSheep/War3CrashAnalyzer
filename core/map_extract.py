"""地图脚本提取：优先 w3x2lni 还原文件名，回退 MPQEditor + 动态 listfile。

w3x2lni（GPL-3.0）只作为外部程序调用，不随本项目分发。未配置或调用失败时，
继续使用原有的二进制扫描 + 本地字典方案，行为与 JASS 审计保持一致。
"""

import glob
import os
import re
import shutil
import subprocess
import tempfile

from core.constants import COMMON_DICT
from core.mpq_index import (
    recover_names,
    rename_placeholder_files,
    report_counts,
)

SCRIPT_NAMES = ("war3map.j", "scripts\\war3map.j", "war3map.lua", "scripts\\war3map.lua")
_PATH_PATTERN = re.compile(
    rb"[a-zA-Z0-9_\\]+\.(?:j|lua|w3u|w3a|w3h|w3t|w3b|w3d|w3q|wts)", re.I)


def _creation_flags():
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def find_w3x2lni(base_dir=None):
    """寻找 w2l.exe；只调用外部程序，不随项目分发。

    W3X2LNI_PATH 可以是 exe，也可以是解压后的 w3x2lni 目录。
    """
    env_path = os.environ.get("W3X2LNI_PATH")
    candidates = [env_path]
    if candidates[0] and os.path.isdir(candidates[0]):
        candidates[0] = os.path.join(candidates[0], "w2l.exe")
    if base_dir:
        candidates.extend([
            os.path.join(base_dir, "tools", "w2l.exe"),
            os.path.join(base_dir, "w2l.exe"),
            os.path.join(base_dir, "w3x2lni", "w2l.exe"),
        ])
        for pattern in (os.path.join(base_dir, "tools", "*", "w2l.exe"),
                        os.path.join(base_dir, "*", "w2l.exe")):
            candidates.extend(sorted(glob.glob(pattern), reverse=True))
    candidates.extend([
        r"C:\war3Dev\w3x2lni\w2l.exe",
        shutil.which("w2l"),
        shutil.which("w2l.exe"),
    ])
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def decode_output(data):
    """外部工具输出可能是 UTF-8 或 GBK；优先 UTF-8，失败后回退。"""
    if isinstance(data, str):
        return data
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return (data or b"").decode("utf-8", errors="replace")


def build_dynamic_listfile(map_file, temp_dir):
    """扫描地图二进制并结合本地字典，构建用于 MPQ 提取的 listfile。"""
    found_paths = set(COMMON_DICT)
    found_paths.update(SCRIPT_NAMES)

    listfiles_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "listfiles")
    if os.path.isdir(listfiles_dir):
        for name in os.listdir(listfiles_dir):
            if not name.endswith(".txt"):
                continue
            try:
                with open(os.path.join(listfiles_dir, name), "r",
                          encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if len(line) > 3:
                            found_paths.add(line)
            except OSError:
                pass

    try:
        with open(map_file, "rb") as f:
            chunk = f.read(30 * 1024 * 1024)
        for match in _PATH_PATTERN.finditer(chunk):
            path = match.group().decode("ascii", errors="ignore")
            if len(path) > 3:
                found_paths.add(path)
    except OSError:
        pass

    listfile_path = os.path.join(temp_dir, "auditor_listfile.txt")
    with open(listfile_path, "w", encoding="ascii", errors="ignore") as f:
        for path in sorted(found_paths):
            f.write(path + "\n")
    return listfile_path


def find_script(directory):
    """在提取目录中找主脚本：优先 war3map.j/lua，其次体积最大的 .j/.lua。"""
    candidates = []
    for root, _, filenames in os.walk(directory):
        for name in filenames:
            lower = name.lower()
            if not lower.endswith((".j", ".lua")):
                continue
            path = os.path.join(root, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size <= 100:
                continue
            candidates.append((path, size, lower))
    if not candidates:
        return None

    def rank(item):
        path, size, lower = item
        base = os.path.basename(path).lower()
        priority = 0 if base in ("war3map.j", "war3map.lua") else 1
        return (priority, -size)

    candidates.sort(key=rank)
    return candidates[0][0]


def write_listfile_from_dir(directory, listfile_path, map_root=None):
    """把 w3x2lni 还原出的真实文件名写成 MPQEditor 可用的 listfile。

    w3x2lni 的 lni 输出通常位于 map/ 子目录；map_root 指向脚本所在层时，
    写出的路径才与地图内部路径一致（war3map.j、scripts\\war3map.j 等）。
    """
    map_root = map_root or directory
    paths = set()
    for root, _, filenames in os.walk(directory):
        for name in filenames:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, map_root)
            if rel.startswith(".."):
                rel = os.path.relpath(full, directory)
            rel = rel.replace("/", "\\")
            if rel.lower().endswith((".w3x", ".w3m", ".log")):
                continue
            paths.add(rel)
    with open(listfile_path, "w", encoding="utf-8", errors="ignore") as f:
        for path in sorted(paths):
            f.write(path + "\n")
    return listfile_path


def extract_script_with_mpq(map_file, mpq_editor_path, output_dir, log=None):
    """原有策略：常用路径直提 -> /list 深度扫描 -> 取最大脚本。"""
    log = log or (lambda _msg: None)
    os.makedirs(output_dir, exist_ok=True)
    listfile = build_dynamic_listfile(map_file, output_dir)

    try:
        for name in SCRIPT_NAMES:
            target = os.path.join(output_dir, os.path.basename(name))
            if os.path.exists(target):
                os.remove(target)
            subprocess.run(
                [mpq_editor_path, "/extract", map_file, name, output_dir,
                 "/listfile", listfile],
                capture_output=True, creationflags=_creation_flags())
            if os.path.exists(target) and os.path.getsize(target) > 100:
                log(f"[+] 成功提取脚本: {name}")
                return {"script_path": target, "listfile": listfile,
                        "method": "MPQEditor", "output": ""}
    except OSError as exc:
        log(f"[-] MPQEditor 无法启动: {exc}")
        return {"script_path": None, "listfile": listfile,
                "method": "MPQEditor", "output": "",
                "error": f"MPQEditor 无法启动：{exc}"}

    log("[*] 常规路径提取失败，正在通过深度扫描识别混淆名...")
    try:
        result = subprocess.run(
            [mpq_editor_path, "/list", map_file, "/listfile", listfile],
            capture_output=True, timeout=30, creationflags=_creation_flags())
        output = decode_output(result.stdout)
        if result.returncode == 0 and output:
            scripts = [line.strip() for line in output.splitlines()
                       if line.strip().lower().endswith((".j", ".lua"))]
            extracted = []
            for script in scripts:
                subprocess.run(
                    [mpq_editor_path, "/extract", map_file, script, output_dir],
                    capture_output=True, creationflags=_creation_flags())
                path = os.path.join(output_dir, os.path.basename(script))
                if os.path.exists(path):
                    extracted.append((path, os.path.getsize(path)))
            if extracted:
                extracted.sort(key=lambda item: item[1], reverse=True)
                best = extracted[0][0]
                extension = os.path.splitext(best)[1].lower()
                final = os.path.join(output_dir, "war3map" + extension)
                if os.path.exists(final):
                    os.remove(final)
                shutil.move(best, final)
                log(f"[+] 深度扫描成功识别主脚本: "
                    f"{os.path.basename(best)} ({os.path.getsize(final)/1024:.1f} KB)")
                return {"script_path": final, "listfile": listfile,
                        "method": "MPQEditor", "output": output}
    except Exception as exc:
        log(f"[-] 深度扫描异常: {exc}")
        return {"script_path": None, "listfile": listfile,
                "method": "MPQEditor", "output": "", "error": str(exc)}

    return {"script_path": None, "listfile": listfile,
            "method": "MPQEditor", "output": ""}


def _recover_name_stats(map_file, out_dir, log):
    """补全 MPQEditor 占位文件名；失败只记录，不影响脚本提取。"""
    try:
        recovered = recover_names(map_file, out_dir)
    except Exception as exc:
        log(f"[-] 文件补名失败（不影响脚本分析）：{exc}")
        return {"error": str(exc)}
    if recovered.get("error"):
        log(f"[-] 文件补名失败：{recovered['error']}")
        return {"error": recovered["error"]}

    names = recovered.get("names") or {}
    counts = recovered.get("counts") or {}
    renamed = rename_placeholder_files(out_dir, names)
    detail = report_counts(counts)
    message = f"[+] 文件补名：{len(names)}/{recovered.get('blocks', 0)} 个文件"
    if detail:
        message += f"（{detail}）"
    if renamed:
        message += f"，已重命名 {renamed} 个占位文件"
    log(message)
    return {
        "named": len(names),
        "blocks": recovered.get("blocks", 0),
        "counts": counts,
        "renamed": renamed,
        "scanned": recovered.get("scanned", 0),
    }


def extract_dir_with_mpq(map_file, mpq_editor_path, work_dir, log=None):
    """把地图中能识别的文件展开成目录，供 w3x2lni 以目录模式转换。

    加密地图常删除 (listfile)，w3x2lni 会因此拒绝转换；先用字典展开目录，
    再交给 w3x2lni 即可绕过该限制。展开后用地图哈希表补全占位文件名。
    """
    log = log or (lambda _msg: None)
    os.makedirs(work_dir, exist_ok=True)
    out_dir = tempfile.mkdtemp(prefix="mpq_dir_", dir=work_dir)
    listfile = build_dynamic_listfile(map_file, work_dir)
    log("[*] 改用 MPQEditor 展开地图文件，再交给 w3x2lni 转换...")
    try:
        subprocess.run(
            [mpq_editor_path, "/extract", map_file, "*", out_dir,
             "/listfile", listfile],
            capture_output=True, timeout=300,
            creationflags=_creation_flags())
    except subprocess.TimeoutExpired:
        return {"dir": out_dir, "listfile": listfile, "script_path": None,
                "error": "MPQEditor 展开超时（300 秒）"}
    except OSError as exc:
        return {"dir": out_dir, "listfile": listfile, "script_path": None,
                "error": f"MPQEditor 无法启动：{exc}"}

    script = find_script(out_dir)
    count = sum(len(files) for _, _, files in os.walk(out_dir))
    if not script:
        return {"dir": out_dir, "listfile": listfile, "script_path": None,
                "error": "MPQEditor 未能展开出地图脚本"}
    log(f"[+] 已展开 {count} 个文件")
    name_stats = _recover_name_stats(map_file, out_dir, log)
    log("[*] 交给 w3x2lni 继续转换...")
    return {"dir": out_dir, "listfile": listfile, "script_path": script,
            "name_stats": name_stats}


def extract_with_w3x2lni(exe_path, map_file, work_dir, log=None):
    """调用 w2l.exe 以 lni 模式还原地图，得到真实文件名与脚本。"""
    log = log or (lambda _msg: None)
    os.makedirs(work_dir, exist_ok=True)
    out_dir = tempfile.mkdtemp(prefix="w3x2lni_", dir=work_dir)
    cmd = [exe_path, "lni", map_file, out_dir]
    log(f"[*] 调用 w3x2lni: {os.path.basename(exe_path)} lni <地图> <临时目录>")
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=180,
            cwd=os.path.dirname(os.path.abspath(exe_path)),
            creationflags=_creation_flags())
    except subprocess.TimeoutExpired:
        return {"script_path": None, "listfile": None, "method": "w3x2lni",
                "output": "", "error": "w3x2lni 执行超时（180 秒）"}
    except OSError as exc:
        return {"script_path": None, "listfile": None, "method": "w3x2lni",
                "output": "", "error": f"w3x2lni 无法启动：{exc}"}

    output = (decode_output(result.stdout) + decode_output(result.stderr)).strip()
    script = find_script(out_dir)
    if result.returncode != 0 or not script:
        reason = f"退出码 {result.returncode}" if result.returncode else "未找到脚本"
        return {"script_path": None, "listfile": None, "method": "w3x2lni",
                "output": output, "error": f"w3x2lni 转换失败：{reason}"}

    listfile = write_listfile_from_dir(
        out_dir, os.path.join(work_dir, "w3x2lni_listfile.txt"),
        map_root=os.path.dirname(script))
    log(f"[+] w3x2lni 还原成功：{os.path.basename(script)}")
    return {"script_path": script, "listfile": listfile,
            "method": "w3x2lni", "output": output, "extract_dir": out_dir}


def extract_script(map_file, mpq_editor_path, work_dir, w3x2lni_path=None, log=None):
    """统一入口：目录/脚本文件直接使用，其余优先 w3x2lni，失败回退 MPQEditor。"""
    log = log or (lambda _msg: None)
    if os.path.isdir(map_file):
        script = find_script(map_file)
        return {"script_path": script, "listfile": None,
                "method": "目录", "output": ""}
    if map_file.lower().endswith((".j", ".lua")):
        return {"script_path": map_file, "listfile": None,
                "method": "脚本文件", "output": ""}

    os.makedirs(work_dir, exist_ok=True)
    if w3x2lni_path and os.path.isfile(w3x2lni_path):
        result = extract_with_w3x2lni(w3x2lni_path, map_file, work_dir, log=log)
        if result.get("script_path"):
            return result
        log(f"[-] {result.get('error') or 'w3x2lni 未找到脚本'}，尝试目录中转。")
        if result.get("output"):
            log(f"    w3x2lni 输出：{result['output'][:300]}")

        expanded = extract_dir_with_mpq(
            map_file, mpq_editor_path, work_dir, log=log)
        if expanded.get("dir"):
            converted = extract_with_w3x2lni(
                w3x2lni_path, expanded["dir"], work_dir, log=log)
            if converted.get("script_path"):
                converted["method"] = "w3x2lni 目录中转"
                converted["name_stats"] = expanded.get("name_stats")
                log("[+] 目录中转成功，已完成 w3x2lni 还原。")
                return converted
            log(f"[-] 目录中转失败：{converted.get('error') or '未找到脚本'}，"
                "使用已展开的目录继续分析。")
            if expanded.get("script_path"):
                return {"script_path": expanded["script_path"],
                        "listfile": expanded.get("listfile"),
                        "method": "MPQEditor（目录展开）", "output": "",
                        "name_stats": expanded.get("name_stats")}
        elif expanded.get("error"):
            log(f"[-] {expanded['error']}")

    return extract_script_with_mpq(map_file, mpq_editor_path, work_dir, log=log)


def read_script_text(path):
    """war3map.j 常见 UTF-8(BOM) 与 GBK 编码，按顺序尝试。"""
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
