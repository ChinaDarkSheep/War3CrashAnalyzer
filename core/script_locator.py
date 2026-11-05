"""作者定位：把崩溃指纹映射到地图脚本中的可疑 API 调用行。

输入可以是诊断包（zip/JSON）或服务端聚合指纹；输出是脚本中相关调用的
行号、列号与片段，并可附带 pjass 语法检查结果。所有分析在本机完成。
"""

import json
import os
import re
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.knowledge import lookup, lookup_any_module, normalize_version
from core.map_extract import extract_script, read_script_text
from core.mpq_index import report_counts
from core.pjass import run_pjass

API_FAMILIES = (
    {
        "label": "单位组枚举",
        "keywords": (r"GroupEnum", r"单位组枚举", r"组句柄"),
        "apis": (
            "GroupEnumUnitsInRange", "GroupEnumUnitsInRangeCounted",
            "GroupEnumUnitsInRangeOfLoc", "GroupEnumUnitsInRangeOfLocCounted",
            "GroupEnumUnitsInRect", "GroupEnumUnitsInRectCounted",
            "GroupEnumUnitsOfPlayer", "GroupEnumUnitsOfType",
            "GroupEnumUnitsOfTypeCounted", "GroupEnumUnitsSelected",
        ),
    },
    {
        "label": "计时器",
        "keywords": (r"Timer", r"定时器", r"计时器"),
        "apis": (
            "TimerStart", "GetExpiredTimer", "TimerGetElapsed",
            "TimerGetRemaining", "TimerGetTimeout", "DestroyTimer",
            "PauseTimer",
        ),
    },
    {
        "label": "整数转换",
        "keywords": (r"I2\*", r"I2S", r"I2R", r"I2B", r"I2C"),
        "apis": ("I2S", "I2R", "I2B", "I2C"),
    },
    {
        "label": "动态执行",
        "keywords": (r"ExecuteFunc", r"ExecuteFunction"),
        "apis": ("ExecuteFunc",),
    },
    {
        "label": "句柄释放",
        "keywords": (r"Handle", r"句柄", r"排泄", r"泄漏"),
        "apis": (
            "DestroyGroup", "DestroyTimer", "DestroyTrigger", "DestroyEffect",
            "DestroyUnit", "RemoveUnit", "DestroyTextTag", "DestroyLightning",
        ),
    },
)


def derive_hints(text):
    """从知识库描述、作者标注或诊断结论中识别可疑 API 家族。"""
    text = (text or "").lower()
    hints = []
    if not text:
        return hints
    for family in API_FAMILIES:
        if any(re.search(keyword.lower(), text) for keyword in family["keywords"]):
            for api in family["apis"]:
                if api not in hints:
                    hints.append(api)
    return hints


def parse_hints(text):
    """作者输入：逗号/空格分隔，支持 GroupEnum* 通配。"""
    selectors = []
    for item in re.split(r"[,，;；\s]+", text or ""):
        item = item.strip()
        if item and item not in selectors:
            selectors.append(item)
    return selectors[:50]


def selector_pattern(selector):
    selector = (selector or "").strip().rstrip("(").strip()
    if not selector:
        return None
    pattern = re.escape(selector).replace(r"\*", r"\w*")
    return re.compile(r"\b" + pattern + r"\w*\s*\(", re.I)


def mask_code(text, language="jass"):
    """把注释与字符串替换为空格，保留行号/列号，避免误报。"""
    out = []
    index = 0
    length = len(text)
    quote = None
    line_comment = False
    block_comment = False
    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""
        if line_comment:
            if char == "\n":
                out.append("\n")
                line_comment = False
            else:
                out.append("\t" if char == "\t" else " ")
            index += 1
            continue
        if block_comment:
            if language == "lua" and text.startswith("]]", index):
                out.extend("  ")
                index += 2
                block_comment = False
                continue
            out.append("\n" if char == "\n" else ("\t" if char == "\t" else " "))
            index += 1
            continue
        if quote:
            if char == "\\" and nxt:
                out.extend("  ")
                index += 2
                continue
            if char == quote:
                quote = None
            out.append("\n" if char == "\n" else ("\t" if char == "\t" else " "))
            index += 1
            continue

        if language == "lua" and text.startswith("--[[", index):
            out.extend("    ")
            index += 4
            block_comment = True
            continue
        if language == "lua" and text.startswith("--", index):
            out.extend("  ")
            index += 2
            line_comment = True
            continue
        if language == "jass" and text.startswith("//", index):
            out.extend("  ")
            index += 2
            line_comment = True
            continue
        if char in ('"', "'") and (language == "lua" or char == '"'):
            quote = char
            out.append(" ")
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out).split("\n")


def locate_calls(text, selectors, language="jass", limit_per=200):
    """返回按选择器分组的调用点。selectors 为空时返回空列表。"""
    original_lines = (text or "").split("\n")
    masked_lines = mask_code(text or "", language)
    groups = []
    total = 0
    for selector in selectors:
        pattern = selector_pattern(selector)
        if not pattern:
            continue
        matches = []
        count = 0
        for line_no, masked in enumerate(masked_lines, 1):
            for match in pattern.finditer(masked):
                count += 1
                if len(matches) >= limit_per:
                    continue
                original = original_lines[line_no - 1] if line_no <= len(original_lines) else ""
                snippet = original.strip()
                if len(snippet) > 240:
                    snippet = snippet[:237] + "..."
                matches.append({
                    "line": line_no,
                    "column": match.start() + 1,
                    "name": match.group(0).strip(),
                    "snippet": snippet,
                })
        groups.append({
            "selector": selector,
            "count": count,
            "truncated": count > limit_per,
            "matches": matches,
        })
        total += count
    return {"total": total, "groups": groups}


def _first(*values):
    for value in values:
        if value not in (None, "", 0):
            return value
    return None


def normalize_fingerprint(data):
    """兼容诊断包、云端聚合详情、单条指纹和纯聚合对象。"""
    if not isinstance(data, dict):
        raise ValueError("指纹数据必须是 JSON 对象")
    aggregate = data.get("aggregate") if isinstance(data.get("aggregate"), dict) else None
    root = data.get("diagnosis") if isinstance(data.get("diagnosis"), dict) else data
    fingerprint = root.get("fingerprint") if isinstance(root.get("fingerprint"), dict) else {}
    if aggregate is None and "relative_offset" in root and "module" in root:
        aggregate = root
    aggregate = aggregate or {}
    map_info = data.get("map") if isinstance(data.get("map"), dict) else {}
    version_info = data.get("version") if isinstance(data.get("version"), dict) else {}
    conclusion = root.get("conclusion") if isinstance(root.get("conclusion"), dict) else {}

    signature = _first(aggregate.get("signature"), fingerprint.get("signature"),
                       root.get("signature"))
    module = _first(aggregate.get("module"), fingerprint.get("module"),
                    root.get("module"))
    rva = _first(aggregate.get("relative_offset"), fingerprint.get("rva"),
                 root.get("relative_offset"), root.get("rva"))
    version = _first(aggregate.get("game_version"), version_info.get("normalized"),
                     fingerprint.get("version"), root.get("version"))
    map_name = _first(aggregate.get("map_name"), map_info.get("name"),
                      root.get("map_name"))
    map_hash = _first(aggregate.get("map_hash"), map_info.get("md5"))
    annotation = _first(aggregate.get("annotation"), root.get("annotation"))
    description = _first(conclusion.get("summary"), root.get("plain_reason"),
                         root.get("analysis_text"))
    if not signature and not (module and rva):
        raise ValueError("未在数据中找到指纹或崩溃位置")
    return {
        "signature": str(signature).upper() if signature else None,
        "module": module,
        "relative_offset": rva,
        "version": version,
        "map_name": map_name,
        "map_hash": map_hash,
        "annotation": annotation,
        "description": description,
    }


def load_fingerprint_file(path):
    max_size = 4 * 1024 * 1024
    if not path or not os.path.isfile(path):
        raise ValueError("诊断包或 JSON 文件不存在")
    if zipfile.is_zipfile(path) and path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            target = "diagnosis.json" if "diagnosis.json" in names else None
            if target is None:
                target = next((name for name in names
                               if name.lower().endswith(".json")), None)
            if target is None:
                raise ValueError("压缩包内没有 diagnosis.json")
            info = archive.getinfo(target)
            if info.file_size > max_size:
                raise ValueError("诊断 JSON 超过 4 MB")
            raw = archive.read(target)
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"诊断 JSON 无法解析：{exc}") from exc
        return normalize_fingerprint(data)

    if os.path.getsize(path) > max_size:
        raise ValueError("JSON 文件超过 4 MB")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise ValueError(f"JSON 文件无法解析：{exc}") from exc
    return normalize_fingerprint(data)


def fetch_cloud_fingerprint(base_url, signature, timeout=10):
    signature = (signature or "").strip().upper()
    if not re.fullmatch(r"[0-9A-F]{12}", signature):
        raise ValueError("指纹必须是 12 位十六进制")
    parsed = urlparse((base_url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("服务端地址必须是 http(s):// 开头")
    url = f"{base_url.rstrip('/')}/api/aggregate/{signature}"
    request = Request(url, headers={"User-Agent": "War3CrashAnalyzer/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    except HTTPError as exc:
        raise ValueError(f"云端返回 HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"无法连接云端：{exc.reason}") from exc
    except OSError as exc:
        raise ValueError(f"云端请求失败：{exc}") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("云端响应超过 4 MB")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"云端响应不是有效 JSON：{exc}") from exc
    return normalize_fingerprint(data)


def knowledge_for(fingerprint):
    module = fingerprint.get("module")
    version = fingerprint.get("version")
    version = normalize_version(version) or version
    rva = fingerprint.get("relative_offset")
    if not rva:
        return None
    matches = []
    if module:
        matches = [(module, ver, entry)
                   for ver, entry in lookup(module, version, rva)]
    if not matches:
        matches = lookup_any_module(version, rva)
    if not matches:
        return None
    module_name, version_key, entry = max(
        matches, key=lambda item: item[2].get("confidence") or 0)
    return {
        "module": module_name,
        "version": version_key,
        "rva": rva,
        "entry": entry,
        "desc": entry.get("desc") or "",
    }


def default_hints(fingerprint, knowledge=None):
    knowledge = knowledge or knowledge_for(fingerprint)
    hints = []
    if knowledge and isinstance(knowledge["entry"].get("apis"), list):
        hints.extend(knowledge["entry"]["apis"])
    for text in (
        (knowledge or {}).get("desc"),
        fingerprint.get("annotation"),
        fingerprint.get("description"),
    ):
        for hint in derive_hints(text):
            if hint not in hints:
                hints.append(hint)
    return hints


def locate_script(script_path, selectors, pjass_path=None, syntax_only=True):
    text = read_script_text(script_path)
    language = "lua" if script_path.lower().endswith(".lua") else "jass"
    calls = locate_calls(text, selectors, language=language)
    pjass_result = None
    if language == "jass":
        pjass_result = run_pjass(
            script_path, pjass_path=pjass_path, syntax_only=syntax_only)
    return {
        "script_path": script_path,
        "script_name": os.path.basename(script_path),
        "language": language,
        "calls": calls,
        "pjass": pjass_result,
    }


def locate_map(map_file, selectors, work_dir, mpq_editor_path,
               w3x2lni_path=None, pjass_path=None, syntax_only=True, log=None):
    extraction = extract_script(
        map_file, mpq_editor_path, work_dir,
        w3x2lni_path=w3x2lni_path, log=log)
    script_path = extraction.get("script_path")
    if not script_path:
        return {"error": "未能从地图中提取脚本", "extraction": extraction}
    listfile = extraction.get("listfile")
    method = extraction.get("method") or ""
    if method.startswith("w3x2lni") and listfile and os.path.isfile(listfile):
        try:
            with open(listfile, "r", encoding="utf-8", errors="ignore") as f:
                extraction["listfile_count"] = sum(
                    1 for line in f if line.strip())
        except OSError:
            pass
    located = locate_script(
        script_path, selectors, pjass_path=pjass_path, syntax_only=syntax_only)
    located["extraction"] = extraction
    return located


def build_report(result, fingerprint=None):
    """生成可直接粘贴给作者的报告文本，不含本机绝对路径。"""
    fingerprint = fingerprint or result.get("fingerprint") or {}
    lines = ["【崩溃指纹定位报告】"]
    map_name = fingerprint.get("map_name")
    if map_name:
        lines.append(f"地图：{map_name}")
    if fingerprint.get("signature"):
        version = fingerprint.get("version")
        suffix = f"（{version}）" if version else ""
        lines.append(f"指纹：{fingerprint['signature']}{suffix}")
    if fingerprint.get("module") and fingerprint.get("relative_offset"):
        lines.append(f"崩溃位置：{fingerprint['module']}+{fingerprint['relative_offset']}")

    knowledge = result.get("knowledge")
    if knowledge:
        lines.append(f"知识库：{knowledge['desc']}（版本 {knowledge['version']}）")
    if fingerprint.get("annotation"):
        lines.append(f"作者标注：{fingerprint['annotation']}")

    hints = result.get("hints") or []
    lines.append(f"定位 API：{', '.join(hints) if hints else '未指定'}")
    if result.get("error"):
        lines.append(f"结果：{result['error']}")
        extraction = result.get("extraction") or {}
        if extraction.get("method"):
            lines.append(f"提取方式：{extraction['method']}")
        return "\n".join(lines)

    extraction = result.get("extraction") or {}
    method = extraction.get("method") or "未知"
    if extraction.get("listfile_count") and method.startswith("w3x2lni"):
        method += f"，listfile {extraction['listfile_count']} 条"
    lines.append(f"脚本：{result.get('script_name')}（{method}）")
    name_stats = extraction.get("name_stats") or {}
    if name_stats.get("named") and name_stats.get("blocks"):
        detail = report_counts(name_stats.get("counts") or {})
        line = (f"资源名识别：{name_stats['named']}/{name_stats['blocks']}"
                f" 个文件")
        if detail:
            line += f"（{detail}）"
        if name_stats.get("renamed"):
            line += f"，已重命名 {name_stats['renamed']} 个占位文件"
        lines.append(line)
    calls = result.get("calls") or {}
    lines.append(f"命中：{calls.get('total', 0)} 处")
    for group in calls.get("groups", []):
        if not group["count"]:
            continue
        suffix = "，仅显示前 200 处" if group.get("truncated") else ""
        lines.append(f"[{group['selector']}] {group['count']} 处{suffix}")
        for match in group["matches"]:
            lines.append(f"  L{match['line']}:{match['column']}  {match['snippet']}")
    if calls.get("total", 0) == 0:
        lines.append("  未找到相关 API 调用，请检查定位 API 是否填写正确。")

    pjass_result = result.get("pjass")
    if pjass_result is None:
        lines.append("pjass：Lua 脚本不适用")
    elif not pjass_result.get("available"):
        lines.append(f"pjass：{pjass_result.get('message')}")
    elif pjass_result.get("crashed"):
        lines.append("pjass：语法检查未完成")
        if pjass_result.get("message"):
            lines.append(f"  {pjass_result['message']}")
    elif pjass_result.get("ok"):
        ignored = pjass_result.get("ignored") or 0
        chunked = pjass_result.get("chunked")
        if ignored and chunked:
            suffix = f"，各段累计忽略 {ignored} 个语义/未声明提示"
        elif ignored:
            suffix = f"，已忽略 {ignored} 个语义/未声明提示"
        else:
            suffix = ""
        if chunked:
            lines.append(
                f"pjass：语法检查通过（大脚本分 "
                f"{pjass_result.get('chunks', 0)} 段检查{suffix}）")
        else:
            lines.append(f"pjass：语法检查通过{suffix}")
    else:
        errors = pjass_result.get("errors") or []
        if not errors:
            lines.append(
                f"pjass：语法检查未通过（退出码 "
                f"{pjass_result.get('returncode')}，未解析到错误行）")
        else:
            lines.append(f"pjass：发现 {len(errors)} 个语法错误")
            for error in errors[:20]:
                column = f":{error['column']}" if error.get("column") else ""
                lines.append(f"  L{error['line']}{column}  {error['message']}")
            if len(errors) > 20:
                lines.append("  ……其余错误见界面输出")
    return "\n".join(lines)
