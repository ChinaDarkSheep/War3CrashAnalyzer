"""pjass 外部调用：对地图脚本做语法检查并解析为结构化错误。

pjass（BSD-2-Clause）以外部进程调用。默认使用 +nosemanticerror，
这样不需要 common.j / Blizzard.j 也能发现缩进、关键字、括号等语法问题；
未声明函数等语义问题不会淹没真正的语法错误。
"""

import os
import re
import shutil
import subprocess
import tempfile

from core.map_extract import decode_output, read_script_text

_ERROR_LINE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?:\s*(?P<col>\d+):)?\s*(?P<msg>.+)$")
_FUNCTION_LINE = re.compile(
    r"(?m)^[ \t]*function[ \t]+\w+[ \t]+takes\b")
_CRASH_EXIT = 0xC0000000
_CHUNK_SIZES = (1000, 300, 80)


def _is_crash(returncode):
    """pjass 在超大脚本上可能直接内存访问冲突退出（0xC0000005）。"""
    return returncode is not None and (
        returncode < 0 or returncode >= _CRASH_EXIT)


def find_pjass(base_dir=None):
    candidates = [
        os.environ.get("WAR3_PJASS"),
        os.environ.get("PJASS_PATH"),
        os.path.join(base_dir, "tools", "pjass.exe") if base_dir else None,
        os.path.join(base_dir, "pjass.exe") if base_dir else None,
        r"C:\war3Dev\pjass.exe",
        shutil.which("pjass"),
        shutil.which("pjass.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def parse_pjass_output(text, script_path=None):
    """把 pjass 的 file:line[:col]: message 输出解析为错误列表。"""
    script_name = os.path.basename(script_path or "").lower()
    errors = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("Parse successful", "Parse failed",
                            "errors ignored")) or "errors total" in line:
            continue
        match = _ERROR_LINE.match(line)
        if not match:
            continue
        file_name = match.group("file").strip()
        if file_name.lower() in ("<total>", "<stdin>"):
            continue
        if script_name and os.path.basename(file_name).lower() != script_name:
            continue
        try:
            line_no = int(match.group("line"))
        except ValueError:
            continue
        column = match.group("col")
        errors.append({
            "file": file_name,
            "line": line_no,
            "column": int(column) if column and column.isdigit() else None,
            "message": match.group("msg").strip(),
        })
    return errors


def _run_command(command, timeout):
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        return None, f"pjass 执行超时（{timeout} 秒）"
    except OSError as exc:
        return None, f"pjass 无法启动：{exc}"
    return result, None


def _chunked_check(script_path, base_command, timeout, syntax_only):
    """pjass 崩溃后按函数边界分段重试，避免超大脚本整份解析失败。"""
    text = read_script_text(script_path)
    starts = [match.start() for match in _FUNCTION_LINE.finditer(text)]
    if len(starts) < 2:
        return None

    prefix = text[:starts[0]]
    prefix_lines = prefix.count("\n")
    line_at = []
    line_no = 1
    previous = 0
    for start in starts:
        line_no += text.count("\n", previous, start)
        line_at.append(line_no)
        previous = start

    temp_dir = tempfile.mkdtemp(prefix="pjass_chunks_")
    try:
        for chunk_size in _CHUNK_SIZES:
            errors = []
            seen = set()
            ignored = 0
            outputs = []
            chunk_count = 0
            crashed = False
            for begin in range(0, len(starts), chunk_size):
                end = min(begin + chunk_size, len(starts))
                tail = starts[end] if end < len(starts) else len(text)
                body = prefix + text[starts[begin]:tail]
                chunk_path = os.path.join(
                    temp_dir, f"chunk_{begin}_{end}.j")
                with open(chunk_path, "w", encoding="utf-8",
                          errors="ignore") as f:
                    f.write(body)
                chunk_count += 1
                result, error = _run_command(
                    base_command + [chunk_path], timeout)
                if error:
                    return {
                        "available": True, "ok": False, "crashed": True,
                        "errors": [], "output": "", "message": error,
                        "chunked": True, "chunks": chunk_count,
                        "syntax_only": syntax_only,
                    }
                output = (decode_output(result.stdout)
                          + decode_output(result.stderr)).strip()
                if output:
                    outputs.append(output)
                if _is_crash(result.returncode):
                    crashed = True
                    break
                parsed = parse_pjass_output(output, chunk_path)
                offset = line_at[begin] - (prefix_lines + 1)
                for item in parsed:
                    item = dict(item)
                    item["file"] = os.path.basename(script_path)
                    if item["line"] > prefix_lines:
                        item["line"] += offset
                    key = (item["line"], item["column"], item["message"])
                    if key not in seen:
                        seen.add(key)
                        errors.append(item)
                match = re.search(r"(\d+) errors ignored", output)
                if match:
                    ignored += int(match.group(1))

            if not crashed:
                return {
                    "available": True, "ok": not errors, "crashed": False,
                    "errors": errors, "output": "\n".join(outputs)[:4000],
                    "message": "", "returncode": 0, "ignored": ignored,
                    "syntax_only": syntax_only, "chunked": True,
                    "chunks": chunk_count, "chunk_size": chunk_size,
                }
        return {
            "available": True, "ok": False, "crashed": True,
            "errors": [], "output": "\n".join(outputs)[:4000],
            "message": "pjass 分析超大脚本时崩溃（0xC0000005），分段检查仍未完成",
            "chunked": True, "chunks": chunk_count,
            "syntax_only": syntax_only,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_pjass(script_path, pjass_path=None, syntax_only=True,
              includes=None, timeout=120):
    if not pjass_path:
        pjass_path = find_pjass()
    if not pjass_path or not os.path.isfile(pjass_path):
        return {
            "available": False,
            "ok": None,
            "errors": [],
            "output": "",
            "message": "未找到 pjass.exe，请设置路径或放到 tools/pjass.exe",
            "syntax_only": syntax_only,
        }
    if not script_path or not os.path.isfile(script_path):
        return {
            "available": True,
            "ok": False,
            "errors": [],
            "output": "",
            "message": "脚本文件不存在",
            "syntax_only": syntax_only,
        }

    base_command = [pjass_path]
    if syntax_only:
        base_command.append("+nosemanticerror")
    base_command.extend(includes or [])

    result, error = _run_command(base_command + [script_path], timeout)
    if error:
        return {
            "available": True,
            "ok": False,
            "errors": [],
            "output": "",
            "message": error,
            "syntax_only": syntax_only,
        }

    output = (decode_output(result.stdout) + decode_output(result.stderr)).strip()
    if _is_crash(result.returncode):
        chunked = _chunked_check(
            script_path, base_command, timeout, syntax_only)
        if chunked is not None:
            chunked["pjass_path"] = pjass_path
            return chunked
        return {
            "available": True,
            "ok": False,
            "crashed": True,
            "errors": [],
            "output": output,
            "message": "pjass 分析该脚本时崩溃（0xC0000005），未能完成语法检查",
            "returncode": result.returncode,
            "ignored": 0,
            "syntax_only": syntax_only,
            "pjass_path": pjass_path,
        }

    errors = parse_pjass_output(output, script_path)
    ignored = 0
    match = re.search(r"(\d+) errors ignored", output)
    if match:
        ignored = int(match.group(1))
    return {
        "available": True,
        "ok": result.returncode == 0 and not errors,
        "crashed": False,
        "errors": errors,
        "output": output,
        "message": "",
        "returncode": result.returncode,
        "ignored": ignored,
        "syntax_only": syntax_only,
        "pjass_path": pjass_path,
        "chunked": False,
    }
