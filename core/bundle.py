"""诊断包导出：日志 + dmp + 诊断 JSON + 可粘贴摘要。

诊断包用于把一次崩溃完整转交地图作者或平台客服。压缩包内不写入
本机绝对路径，摘要文本可直接粘贴到 QQ 群。
"""

import hashlib
import json
import os
import re
import time
import zipfile

from core.knowledge import normalize_version
from core.logtext import read_log
from core.stack_parser import describe_stack

SCHEMA_VERSION = 1


def md5_file(path, chunk_size=1024 * 1024):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _file_info(path, with_hash=True):
    name = os.path.basename(path)
    try:
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
    except OSError:
        return {"name": name}
    info = {
        "name": name,
        "size": size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
    }
    if with_hash:
        try:
            info["md5"] = md5_file(path)
        except OSError:
            info["md5"] = None
    return info


def _plain_stack(frames):
    """去掉本机绝对路径与栈帧地址，只保留可复现的模块与偏移。"""
    stack = []
    for frame in frames or []:
        module = (frame.get("module") or "").replace("/", "\\").rsplit("\\", 1)[-1]
        stack.append({
            "module": module,
            "rva": frame.get("rva"),
            "section": frame.get("section"),
            "offset": frame.get("offset"),
        })
    return stack


def _plugin_list(environment):
    plugins = []
    for category, items in ((environment or {}).get("findings") or {}).items():
        for item in items or []:
            plugins.append({
                "category": category,
                "label": item.get("label"),
                "module": item.get("module"),
            })
    return plugins


def _plain_dmp(dmp):
    """压缩 dump 信息，保留查表所需的版本/模块/偏移，去掉本机路径。"""
    if not dmp:
        return None
    return {
        "engine": dmp.get("engine"),
        "exception": dmp.get("exception"),
        "module": dmp.get("module"),
        "rva": dmp.get("rva"),
        "file_version": dmp.get("file_version"),
        "version": dmp.get("version"),
        "fallback": dmp.get("fallback"),
        "stack": _plain_stack(dmp.get("stack")),
    }


def build_bundle(log_path, diagnosis, map_path=None):
    """组装诊断包数据；diagnosis 为 Auditor.analyze_log_content 的结果。"""
    diagnosis = diagnosis or {}
    content = read_log(log_path)
    build_match = re.search(r'War3Build:\s*([0-9.]+)', content, re.I)
    build_raw = build_match.group(1) if build_match else None

    log_map_name = diagnosis.get("map_name") or "Unknown"
    map_info = {}
    if map_path and os.path.exists(map_path):
        map_info = _file_info(map_path)
    map_info["name"] = map_info.get("name") or log_map_name
    map_info["log_map_name"] = log_map_name

    environment = diagnosis.get("environment") or {}
    conclusion = diagnosis.get("conclusion") or {}
    fingerprint = diagnosis.get("fingerprint") or {}

    dmp_path = os.path.splitext(log_path)[0] + ".dmp"
    files = {"log": _file_info(log_path)}
    if os.path.exists(dmp_path):
        files["dmp"] = _file_info(dmp_path, with_hash=False)

    game_version = normalize_version(build_raw) if build_raw else None
    if not game_version:
        game_version = diagnosis.get("version")

    bundle = {
        "schema": SCHEMA_VERSION,
        "tool": "War3CrashAnalyzer",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": {
            "normalized": game_version,
            "raw": build_raw,
        },
        "map": map_info,
        "plugins": _plugin_list(environment),
        "files": files,
        "diagnosis": {
            "conclusion": conclusion,
            "analysis_text": diagnosis.get("analysis_text") or "",
            "detail_text": diagnosis.get("detail_text") or "",
            "plain_reason": diagnosis.get("reason"),
            "addr": diagnosis.get("addr"),
            "module": diagnosis.get("module_name"),
            "relative_offset": diagnosis.get("relative_offset"),
            "map_name": log_map_name,
            "stack": _plain_stack(diagnosis.get("stack")),
            "environment": {
                "focus_category": environment.get("focus_category"),
                "focus_label": environment.get("focus_label"),
                "attribution_hint": environment.get("attribution_hint"),
                "platform_in_stack": environment.get("platform_in_stack"),
                "platform_modules": [item.get("module") for item in
                                     (environment.get("platform_evidence") or [])],
                "advice": environment.get("advice"),
                "text": environment.get("text") or "",
            },
            "fingerprint": fingerprint,
            "fingerprint_stats": diagnosis.get("fingerprint_stats"),
            "dmp": _plain_dmp(diagnosis.get("dmp")),
        },
    }
    return bundle


def build_summary_text(bundle):
    """生成可直接粘贴到 QQ 群的纯文本摘要。"""
    diagnosis = bundle.get("diagnosis") or {}
    conclusion = diagnosis.get("conclusion") or {}
    map_info = bundle.get("map") or {}
    version = bundle.get("version") or {}

    lines = ["【魔兽崩溃诊断报告】"]
    lines.append(f"地图：{map_info.get('name') or diagnosis.get('map_name') or '未知'}")
    if map_info.get("md5"):
        lines.append(f"地图 MD5：{map_info['md5']}")
    game_version = version.get("normalized") or version.get("raw")
    if game_version:
        lines.append(f"游戏版本：{game_version}")

    dmp = diagnosis.get("dmp") or {}
    if dmp.get("module") and dmp.get("rva"):
        detail = f"Dump：{dmp['module']}+{dmp['rva']}"
        if dmp.get("file_version"):
            detail += f"（文件版本 {dmp['file_version']}）"
        lines.append(detail)

    if conclusion:
        confidence = int(round((conclusion.get("confidence") or 0) * 100))
        lines.append(f"归属：{conclusion.get('attribution')}（置信度 {confidence}%）")
        lines.append(f"结论：{conclusion.get('summary')}")
        lines.append(f"建议：{conclusion.get('suggestion')}")
    else:
        lines.append("结论：未能生成统一结论")

    fingerprint = diagnosis.get("fingerprint") or {}
    if fingerprint.get("signature"):
        lines.append(f"栈指纹：{fingerprint['signature']}（{fingerprint.get('version')}）")

    stack_text = describe_stack(diagnosis.get("stack"))
    if stack_text:
        lines.append(f"调用栈：{stack_text}")

    env_text = (diagnosis.get("environment") or {}).get("text")
    if env_text:
        lines.append(f"环境：{env_text}")

    plugins = bundle.get("plugins") or []
    if plugins:
        shown = "、".join(f"{p.get('label')}（{p.get('module')}）"
                          for p in plugins[:8])
        lines.append(f"插件/环境模块：{shown}")

    log_file = (bundle.get("files") or {}).get("log") or {}
    if log_file.get("name"):
        lines.append(f"日志：{log_file['name']}")
    return "\n".join(lines)


def default_bundle_name(map_name):
    base = os.path.splitext(os.path.basename(map_name or ""))[0] or "崩溃"
    base = re.sub(r'[\\/:*?"<>|]+', "_", base)[:40]
    return f"War3诊断包_{base}_{time.strftime('%Y%m%d_%H%M%S')}.zip"


def export_bundle(log_path, diagnosis, output_path, map_path=None):
    """写入 zip，返回 (bundle, summary_text)。"""
    bundle = build_bundle(log_path, diagnosis, map_path)
    summary = build_summary_text(bundle)
    log_name = bundle["files"]["log"]["name"]
    dmp_name = (bundle["files"].get("dmp") or {}).get("name")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnosis.json",
                    json.dumps(bundle, ensure_ascii=False, indent=2))
        zf.writestr("summary.txt", summary.encode("utf-8-sig"))
        zf.write(log_path, arcname=log_name)
        if dmp_name:
            zf.write(os.path.join(os.path.dirname(log_path), dmp_name),
                     arcname=dmp_name)
    return bundle, summary
