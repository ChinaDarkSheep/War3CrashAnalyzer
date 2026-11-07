import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import traceback
import hashlib
import json
import re
import time
from core.knowledge import (
    EXCEPTION_CODES,
    describe,
    get_disputed,
    lookup,
    lookup_any_module,
    normalize_offset,
    normalize_version,
)
from core.map_extract import (
    build_dynamic_listfile,
    extract_script_with_mpq,
)
from core.logtext import detect_host, diagnose_plain, read_log
from core.stack_parser import describe_stack, find_crash_frame, first_valid_frame, parse_stack_trace
from core.environment import analyze_environment
from core.diagnosis import build_conclusion
from core.fingerprint import build_fingerprint
from core.history import HistoryTracker
from engine.memory import get_module_base
from engine.dmp_parser import MinidumpParser

class Auditor:
    def __init__(self, log_func, update_status_func, base_dir=None):
        self.log = log_func
        self.update_status = update_status_func
        # 供界面追加“疑似泄露证据”使用；只保存最近一次结构化诊断结果。
        self.last_diagnosis = None
        if base_dir:
            db_path = os.path.join(base_dir, "history.db")
            self.history = HistoryTracker(db_path)
        else:
            self.history = None

    def _build_dynamic_listfile(self, map_file, temp_dir):
        """兼容入口：实际构建逻辑位于 core.map_extract。"""
        return build_dynamic_listfile(map_file, temp_dir)

    def _find_and_extract_jass_script(self, map_file, mpq_editor_path, output_dir):
        """兼容入口：实际提取逻辑位于 core.map_extract。"""
        self.log("[*] 正在初始化增强型脚本提取...")
        result = extract_script_with_mpq(
            map_file, mpq_editor_path, output_dir, log=self.log)
        if not result.get("script_path"):
            self.log("[-] 提取失败：所有策略均无法找到脚本文件。")
        return result.get("script_path")

    def deep_extract_worker(self, map_file, mpq_editor_path, base_dir, finish_callback=None):
        self.log("\n" + "="*70)
        self.log(f"   🚀 强力提取模式 (Deep Extraction)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            out_dir = os.path.join(base_dir, "extracted_" + os.path.basename(map_file).replace('.', '_'))
            os.makedirs(out_dir, exist_ok=True)
            
            # 1. 构建地图专属动态字典
            self.log("[*] 正在构建地图专属动态字典...")
            dyn_listfile = self._build_dynamic_listfile(map_file, out_dir)
            
            # 2. 执行 MPQEditor 提取命令 (使用 * 提取所有能识别的文件)
            self.log(f"[*] 执行 MPQEditor 全量提取命令...")
            cmd = [mpq_editor_path, "/extract", map_file, "*", out_dir, "/listfile", dyn_listfile]
            subprocess.run(cmd, capture_output=True, text=True)
            
            files_count = 0
            for root, _, filenames in os.walk(out_dir):
                files_count += len(filenames)
            
            self.log(f"[+] 提取完成！共获取 {files_count} 个文件。")
            self.log(f"[+] 保存目录: {out_dir}")
            self.update_status(f"提取完成: {files_count} 个文件")
            
        except Exception as e:
            self.log(f"[-] 提取异常: {e}")
        finally:
            if finish_callback: finish_callback()
            self.log("="*70)

    def audit_worker(self, map_file, mpq_editor_path, base_dir, finish_callback=None):
        self.log("\n" + "="*70)
        self.log(f"   🔍 资源审计模式 (Resource Audit)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            temp_dir = os.path.join(base_dir, "temp_audit")
            os.makedirs(temp_dir, exist_ok=True)
            
            # 1. 尝试提取关键物编文件
            self.log("[*] 正在分析地图资源引用...")
            key_files = ["war3map.w3u", "war3map.w3a", "war3map.w3h", "war3map.w3t"]
            found_issues = 0
            
            for f in key_files:
                cmd = [mpq_editor_path, "/extract", map_file, f, temp_dir]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.log(f"[+] 成功分析物编文件: {f}")
                else:
                    self.log(f"[-] 跳过不存在的文件: {f}")

            # 2. 检查模型路径长度 (真实扫描地图二进制)
            self.log("[*] 正在扫描模型路径长度有效性...")
            with open(map_file, 'rb') as f:
                content = f.read()
                paths = re.findall(rb'[a-zA-Z0-9_\\]+\.(?:mdx|blp)', content)
                for p in paths:
                    if len(p) > 160:
                        self.log(f"[!] 风险: 发现超长路径 ({len(p)} 字符): {p.decode(errors='ignore')}")
                        found_issues += 1

            # 3. 比对脚本引用与实际提取到的资源
            script_path = self._find_and_extract_jass_script(map_file, mpq_editor_path, temp_dir)
            if not script_path:
                self.log("[!] 未能提取脚本，跳过资源缺失比对。")
            else:
                with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                    script = f.read()

                refs = set()
                for raw in re.findall(r'[A-Za-z0-9_\\/]+\.(?:mdx|mdl|blp|tga)', script, re.I):
                    refs.add(raw.lower().replace('/', '\\').replace('\\\\', '\\'))

                extracted_dir = os.path.join(base_dir, "extracted_" + os.path.basename(map_file).replace('.', '_'))
                extracted = set()
                if os.path.isdir(extracted_dir):
                    for root, _, filenames in os.walk(extracted_dir):
                        for name in filenames:
                            rel = os.path.relpath(os.path.join(root, name), extracted_dir)
                            extracted.add(rel.lower().replace('/', '\\'))

                if not extracted:
                    self.log(f"[*] 脚本中共引用 {len(refs)} 个模型/贴图路径。")
                    self.log("[提示] 先执行“超级强力提取”，再次审计即可比对缺失文件。")
                else:
                    builtin_roots = ("replaceabletextures\\", "units\\", "abilities\\", "buildings\\",
                                     "doodads\\", "environment\\", "ui\\")
                    missing = sorted(p for p in refs
                                     if p not in extracted and not p.startswith(builtin_roots))
                    found_issues += len(missing)
                    if missing:
                        self.log(f"[!] 发现 {len(missing)} 个可能缺失的资源引用 (通常只影响视觉效果):")
                        for p in missing[:10]:
                            self.log(f"  - {p}")
                        if len(missing) > 10:
                            self.log(f"  ... 以及其他 {len(missing) - 10} 个")
                    else:
                        self.log("[+] 资源引用与提取文件一致，未发现缺失。")
            
            if found_issues == 0:
                self.log(f"[+] 审计完成！未发现严重资源错误。")
                self.update_status("审计完成: 未发现致命风险")
            else:
                self.log(f"[+] 审计完成！发现 {found_issues} 处潜在风险。")
                self.update_status(f"审计完成: 发现 {found_issues} 个风险点")
                
        except Exception as e:
            self.log(f"[-] 审计异常: {e}")
        finally:
            if finish_callback: finish_callback()
            self.log("="*70)

    def jass_audit_worker(self, map_file, mpq_editor_path, base_dir, finish_callback=None):
        self.log("\n" + "="*70)
        self.log(f"   📜 JASS 脚本审计模式 (JASS Audit)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            temp_dir = os.path.join(base_dir, "temp_jass")
            os.makedirs(temp_dir, exist_ok=True)
            
            script_path = self._find_and_extract_jass_script(map_file, mpq_editor_path, temp_dir)
            
            if not script_path:
                self.log("[-] 提取失败: 无法找到或提取 JASS 脚本。")
                self.update_status("JASS 审计失败: 未找到脚本")
                return

            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            self.log("[*] 正在扫描高危函数与同步风险...")
            
            issues = []
            if re.search(r"UnitRemoveAbility\s*\([^)]*['\"]AHer['\"]", content, re.I):
                issues.append("发现致命错误: UnitRemoveAbility(..., 'AHer') 会导致魔兽崩溃！")

            high_risk_null = ["GroupEnumUnitsInRange", "RemoveLocation", "DestroyGroup", "UnitRemoveAbility"]
            for fn in high_risk_null:
                if re.search(rf'{fn}\s*\(\s*null', content, re.I):
                    issues.append(f"发现 {fn}(null) 调用，部分游戏版本下会直接崩溃。")

            if "UnitDamageTarget" in content:
                self.log("[!] 发现 UnitDamageTarget 调用，请确认未在伤害事件回调中递归触发。")

            if "GetLocalPlayer" in content:
                self.log("[提示] 脚本中包含 GetLocalPlayer，请确保块内无同步对象创建。")
            
            loc_created = content.count("Location(")
            loc_destroyed = content.count("RemoveLocation(")
            if loc_created > loc_destroyed:
                issues.append(f"检测到潜在泄露: Location 创建 {loc_created} 次，仅销毁 {loc_destroyed} 次。")

            if "DzFrameCreate" in content or "DzFrameRegister" in content:
                self.log("[风险] 发现自定义 UI 帧操作，退出地图前需正确注销，否则可能导致退出崩溃。")
            if "DzFrameSetScript" in content:
                self.log("[提示] 发现 UI 脚本回调，若退出时崩溃请检查回调是否在退出后仍被触发。")

            for issue in issues:
                self.log(f"[!] {issue}")
            
            if not issues:
                self.log(f"[+] JASS 审计完成！未发现明显逻辑错误。")
                self.update_status("JASS 审计完成: 逻辑正常")
            else:
                self.log(f"[+] JASS 审计完成！发现 {len(issues)} 处潜在风险。")
                self.update_status(f"JASS 审计完成: 发现 {len(issues)} 个问题")
                
        except Exception as e:
            self.log(f"[-] JASS 审计异常: {e}")
        finally:
            if finish_callback: finish_callback()
            self.log("="*70)

    def analyze_log_content(self, log_content):
        """
        解析单份崩溃日志，返回结构化诊断结果。
        日志明文原因（内存不足/文件损坏）优先于模块偏移查表。
        """
        addr = "Unknown"
        relative_offset = None
        analysis_text = "无法从日志中提取有效崩溃地址"
        map_name = "Unknown"
        module_name = "Unknown"
        plain = None
        frames = []
        environment = None
        conclusion = None
        matches = []
        detail_text = ""
        log_version = None

        try:
            # 1. 匹配地址和模块 (增强型)
            # 兼容各种日志格式 (Crash.txt, Error.txt, Bug.txt)
            patterns = [
                r'occurred at (0x[0-9A-F]+)',
                r'at [0-9A-F]{4}:([0-9A-F]{8})',
                r"The instruction at '(0x[0-9A-F]+)'",
                r"The instruction at ([0-9A-F]{8})",
                r"Address:\s+(0x[0-9A-F]{8})",
            ]
            
            found_addr = None
            for p in patterns:
                m = re.search(p, log_content, re.IGNORECASE)
                if m:
                    found_addr = m.group(1).upper()
                    break
            
            if found_addr:
                addr = found_addr
            else:
                # 尝试从 Stack Trace 第一行提取 (针对 Error.txt)
                stack_start = log_content.find("Address  Frame    Logical addr  Module")
                if stack_start != -1:
                    lines = log_content[stack_start:].splitlines()
                    # 跳过标题行
                    for line in lines[1:]:
                        m = re.search(r'([0-9A-F]{8})\s+[0-9A-F]{8}\s+[0-9A-F]{4}:[0-9A-F]{8}\s+(.*)', line, re.IGNORECASE)
                        if m:
                            addr = m.group(1).upper()
                            break
            
            # 解析整段调用栈：既用于定位有效帧，也为后续环境/插件识别保留原始帧
            clean_addr = addr.replace("0X", "")[-8:]
            used_fallback_frame = False
            frames = parse_stack_trace(log_content)
            stack_summary = describe_stack(frames)

            def _frame_offset(frame):
                # 只有 .text（0001 节）的节内偏移加 0x1000 才是 RVA；
                # 其他节需要读目标模块的 PE 节表才能换算，此处宁可不猜。
                if frame["rva"] is None:
                    return None
                return normalize_offset("0x%08X" % frame["rva"])

            crash_frame = find_crash_frame(frames, addr)
            if crash_frame and crash_frame["module"].lower() not in ("<unknown>", "unknown", ""):
                relative_offset = _frame_offset(crash_frame)
                module_name = os.path.basename(crash_frame["module"])
            else:
                # 崩溃地址无效（如空函数指针调用）时，改用调用栈中第一个有效模块帧
                fallback = first_valid_frame(frames)
                if fallback:
                    relative_offset = _frame_offset(fallback)
                    module_name = os.path.basename(fallback["module"])
                    used_fallback_frame = addr != "Unknown"

            if relative_offset is None and addr != "Unknown" and not used_fallback_frame:
                # 降级方案：如果地址看起来像是一个相对偏移 (例如 < 0x05000000)
                try:
                    val = int(clean_addr, 16)
                    if 0 < val < 0x05000000:
                        relative_offset = normalize_offset(clean_addr)
                        exe_match = re.search(r'Exe:\s+(.*)', log_content, re.IGNORECASE)
                        if exe_match:
                            module_name = os.path.basename(exe_match.group(1).strip())
                except ValueError:
                    pass

            # 2. 提取地图名称 (增强型)
            # 寻找形如 Played Maps\Test\WorldEditTestMap.w3m 的行
            map_match = re.search(r'Played Maps\\(.*?)\.(w3x|w3m|w3n)', log_content, re.IGNORECASE)
            if map_match:
                full_name = map_match.group(1)
                suffix = map_match.group(2)
                if '\\' in full_name:
                    map_name = full_name.split('\\')[-1] + "." + suffix
                else:
                    map_name = full_name + "." + suffix
            
            # 备选方案：寻找 File: 字段；war3map.* 是地图内部数据文件，不能当作地图名
            if map_name == "Unknown":
                file_match = re.search(r'File:\s+(.*\.(?:w3x|w3m|w3n|w3a|w3u|w3h|w3t|w3d|w3q))', log_content, re.IGNORECASE)
                if file_match:
                    candidate = os.path.basename(file_match.group(1).strip())
                    if not candidate.lower().startswith("war3map."):
                        map_name = candidate

            if map_name == "Unknown" or map_name.lower() in [".w3m", ".w3x"]:
                alt_match = re.search(r'([^\\]+\.(?:w3x|w3m|w3n))', log_content, re.IGNORECASE)
                if alt_match:
                    alt_name = alt_match.group(1)
                    if "war3" not in alt_name.lower() and "exe" not in alt_name.lower() and "dll" not in alt_name.lower():
                        map_name = alt_name

            # 3. 日志明文原因
            plain = diagnose_plain(log_content)

            # 识别运行环境（平台插件 / 编辑器运行时 / 显卡驱动），用于责任归属；
            # 明文已明确指向地图文件损坏时，不让环境提示改口。
            exe_match = re.search(r"^(?:Exe|Program):\s*(.+)$", log_content, re.M | re.I)
            log_exe = exe_match.group(1).strip() if exe_match else None
            environment = analyze_environment(
                log_content, frames=frames, focus_module=module_name, exe=log_exe,
                allow_hint=not (plain and plain.get("attribution") == "地图"))

            if plain and plain["host"] == "editor":
                # 编辑器崩溃的 Storm.dll 偏移没有诊断价值，直接用统一结论
                conclusion = build_conclusion(
                    plain=plain, environment=environment, matches=None,
                    module_name=plain["exe"] or module_name, rva=None, addr=addr,
                    log_version=None, used_fallback=False, host="editor")
                analysis_text = conclusion["text"]
                if environment and environment["text"]:
                    analysis_text += "\n" + environment["text"]
                return {
                    "addr": addr,
                    "relative_offset": None,
                    "analysis_text": analysis_text,
                    "detail_text": (environment or {}).get("text") or "",
                    "map_name": map_name,
                    "module_name": plain["exe"] or module_name,
                    "reason": plain,
                    "stack": frames,
                    "environment": environment,
                    "conclusion": conclusion,
                    "fingerprint": None,
                    "version": None,
                }

            # 4. 匹配知识库：版本 + 精确 RVA，不做任何后缀/跨版本模糊匹配
            build_match = re.search(r'War3Build:\s*([0-9.]+)', log_content, re.IGNORECASE)
            build_raw = build_match.group(1) if build_match else None
            log_version = normalize_version(build_raw) if build_raw else None
            rva = normalize_offset(relative_offset)
            lookup_text = ""

            if rva:
                if module_name != "Unknown":
                    matches = [(module_name, ver, entry)
                               for ver, entry in lookup(module_name, log_version, rva)]
                else:
                    matches = lookup_any_module(log_version, rva)

                frame_note = ""
                if used_fallback_frame:
                    frame_note = ("崩溃指令地址无效（可能为空函数指针调用），"
                                  f"已改为分析调用栈首个有效帧 {module_name}+{rva}。")
                    if stack_summary:
                        frame_note += f"调用栈：{stack_summary}。"
                if matches:
                    lookup_text = " | ".join(
                        f"[{mod}] {describe(entry, ver, log_version is not None)}"
                        for mod, ver, entry in matches
                    )
                    disputed = get_disputed(matches[0][0], matches[0][1], rva)
                    if len(disputed) > 1:
                        others = "；".join(f"{d['source']}：{d['desc']}" for d in disputed[1:])
                        lookup_text += f"\n    注意：该地址另有不同说法 → {others}"
                    lookup_text = frame_note + lookup_text
                elif log_version:
                    lookup_text = frame_note + (f"该版本（{log_version}）知识库未收录偏移 {rva}，"
                                                f"崩溃模块：{module_name}")
                else:
                    lookup_text = frame_note + (f"未知偏移量 ({rva})，日志中未找到游戏版本，"
                                                f"崩溃模块：{module_name}")
            elif addr != "Unknown":
                lookup_text = f"日志中的地址 {addr} 不是模块内偏移，无法查表，崩溃模块：{module_name}"

            # 5. 栈指纹：版本 + 栈顶若干帧，用于跨地图聚合同一崩溃
            fingerprint = build_fingerprint(
                frames,
                version=log_version or build_raw,
                module_name=module_name if module_name != "Unknown" else None,
                rva=rva)

            # 6. 统一结论：一句话结论 + 责任归属 + 建议 + 置信度
            conclusion = build_conclusion(
                plain=plain, environment=environment, matches=matches,
                module_name=module_name, rva=rva, addr=addr,
                log_version=log_version, used_fallback=used_fallback_frame,
                host=detect_host(log_content)[0])

            details = []
            if lookup_text and (matches or "知识库未收录" in lookup_text or not plain):
                details.append(lookup_text)
            if environment and environment["text"]:
                details.append(environment["text"])

            detail_text = "\n".join(details)
            analysis_text = conclusion["text"]
            if detail_text:
                analysis_text += "\n" + detail_text
        except Exception as e:
            analysis_text = f"分析过程异常: {str(e)}"
            
        return {
            "addr": addr,
            "relative_offset": relative_offset,
            "analysis_text": analysis_text,
            "detail_text": detail_text,
            "map_name": map_name,
            "module_name": module_name,
            "reason": plain,
            "stack": frames,
            "environment": environment,
            "conclusion": conclusion,
            "fingerprint": fingerprint,
            "version": log_version,
        }

    def _analyze_dmp(self, dmp_file):
        """解析伴随 dump 并查表；返回结构化结果，失败返回 None。"""
        self.log(f"[*] 发现伴随 Dump 文件: {os.path.basename(dmp_file)}")
        parser = MinidumpParser(dmp_file)
        try:
            if not parser.parse():
                self.log("[-] Dump 解析失败。")
                return None
        except Exception as e:
            self.log(f"[-] Dump 分析异常: {e}")
            return None

        info = {
            "engine": parser.engine,
            "exception": parser.exception,
            "stack": parser.stack,
            "module": parser.crash_module,
            "rva": parser.crash_rva,
            "file_version": parser.crash_file_version,
            "version": None,
            "fallback": parser.crash_fallback,
            "analysis": "",
            "matches": [],
        }

        if parser.exception:
            code = parser.exception["code"]
            explanation = "未知异常代码"
            for key, value in EXCEPTION_CODES.items():
                if key.lower() == code.lower():
                    explanation = value
                    break
            self.log(f"[+] Dump 异常码: {code}")
            self.log(f"    解释: {explanation}")
            self.log(f"[+] Dump 崩溃地址: {parser.exception['address']}")

        if parser.crash_module and parser.crash_rva is not None:
            mod_version = (normalize_version(parser.crash_file_version)
                           if parser.crash_file_version else None)
            info["version"] = mod_version
            offset = normalize_offset(hex(parser.crash_rva))
            if parser.crash_fallback:
                self.log("[!] Dump 异常地址不在任何模块内，已改用栈顶帧定位。")
            self.log(f"[+] 崩溃发生于模块: {parser.crash_module} "
                     f"(相对偏移: {offset}, 文件版本: {parser.crash_file_version or '未知'})")
            info["analysis"] += f"[{parser.crash_module}+{offset}] "
            for ver, entry in lookup(parser.crash_module, mod_version, offset):
                hit = describe(entry, ver, mod_version is not None)
                self.log(f"[+] 命中知识库: {hit}")
                info["analysis"] += hit + " "
                info["matches"].append({"version": ver, "text": hit})
        elif parser.exception:
            self.log("[-] 无法从 Dump 定位崩溃模块。")

        if parser.stack:
            self.log(f"[+] Dump 调用栈（{len(parser.stack)} 帧）:")
            for frame in parser.stack[:8]:
                self.log(f"    {frame['module']}+0x{frame['rva']:08X}")
            summary = describe_stack(parser.stack)
            if summary:
                info["analysis"] += f"调用栈：{summary}"
        else:
            self.log("[-] Dump 未提供调用栈（可能缺少异常上下文）。")

        scripts = parser.extract_strings(b'war3map', 8)
        if scripts:
            self.log(f"[+] 提取到 {len(scripts)} 条脚本相关线索:")
            for value in scripts[:5]:
                self.log(f"    - {value}")

        info["analysis"] = info["analysis"].strip()
        return info

    def _merge_dmp(self, result, dmp):
        """把 dump 结果并入文本诊断：补版本、补栈、必要时重算指纹。"""
        if not dmp:
            result["dmp"] = None
            return result

        result["dmp"] = {
            "engine": dmp["engine"],
            "exception": dmp["exception"],
            "stack": dmp["stack"],
            "module": dmp["module"],
            "rva": ("0x%08X" % dmp["rva"]) if dmp["rva"] is not None else None,
            "file_version": dmp["file_version"],
            "version": dmp["version"],
            "fallback": dmp["fallback"],
            "analysis": dmp["analysis"],
        }

        if not result.get("stack") and dmp.get("stack"):
            result["stack"] = dmp["stack"]

        version = dmp.get("version")
        needs_fingerprint = (not result.get("fingerprint")
                             or (version and not result.get("version")))
        has_frames = bool(result.get("stack")) or bool(result["dmp"]["rva"])
        if version and needs_fingerprint and has_frames:
            module = result.get("module_name")
            if module == "Unknown":
                module = dmp.get("module")
            fingerprint = build_fingerprint(
                result["stack"], version=version,
                module_name=module, rva=result["dmp"]["rva"])
            if fingerprint:
                result["fingerprint"] = fingerprint
                result["version"] = version
        return result

    def analyze_log_file(self, log_path):
        """诊断单个日志（自动收集用）：分析文本并记录历史与指纹。"""
        content = read_log(log_path)
        result = self.analyze_log_content(content)
        dmp_path = os.path.splitext(log_path)[0] + ".dmp"
        dmp = self._analyze_dmp(dmp_path) if os.path.exists(dmp_path) else None
        result = self._merge_dmp(result, dmp)
        self.last_diagnosis = result
        if dmp and dmp.get("analysis"):
            result["analysis_text"] = (dmp["analysis"] + "\n"
                                       + result["analysis_text"]).strip()
        name = os.path.basename(log_path)
        stats = None
        if self.history:
            try:
                mtime = os.path.getmtime(log_path)
            except OSError:
                mtime = time.time()
            fingerprint = result.get("fingerprint")
            conclusion = result.get("conclusion") or {}
            if fingerprint:
                stats = self.history.record_fingerprint(
                    fingerprint, name, result.get("map_name"),
                    attribution=conclusion.get("attribution"),
                    confidence=conclusion.get("confidence"))
            file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            self.history.mark_diagnosed(
                name, file_hash, mtime, result["analysis_text"])
        result["fingerprint_stats"] = stats
        return result

    def analyze_last_crash(self, war3_path):
        if not war3_path or not os.path.exists(war3_path):
            return "[-] 未找到魔兽目录，无法读取日志。"
        
        log_dir = os.path.join(war3_path, "Errors")
        if not os.path.exists(log_dir):
            return "[-] Errors 目录不存在，未发现崩溃日志。"
            
        logs = [f for f in os.listdir(log_dir) if f.endswith(".txt")]
        if not logs:
            return "[-] 未发现崩溃日志文件。"
            
        # 统计信息
        self.log(f"[*] 扫描 Errors 目录: 发现 {len(logs)} 份日志文件")
        
        # 识别未诊断的日志
        log_info = []
        for f in logs:
            full_path = os.path.join(log_dir, f)
            try:
                mtime = os.path.getmtime(full_path)
                status = self.history.get_log_status(f) if self.history else None
                log_info.append({
                    "name": f,
                    "path": full_path,
                    "mtime": mtime,
                    "diagnosed": status["diagnosed"] if status else False,
                    "reported": status["reported"] if status else False
                })
            except: continue
        
        # 统计诊断状态
        diagnosed_count = sum(1 for l in log_info if l["diagnosed"])
        reported_count = sum(1 for l in log_info if l["reported"])
        self.log(f"[+] 统计: {diagnosed_count} 份已诊断, {reported_count} 份已上报")
        
        # 筛选未诊断的日志；首次启用指纹时回溯全部日志，避免统计从 0 开始
        undiagnosed = [l for l in log_info if not l["diagnosed"]]
        backfill = (bool(self.history) and diagnosed_count > 0
                    and self.history.fingerprint_sample_count() == 0)
        if backfill:
            target_logs = sorted(log_info, key=lambda x: x["mtime"])
            self.log(f"[*] 首次启用栈指纹，回溯诊断全部 {len(target_logs)} 份日志...")
        elif not undiagnosed:
            # 如果全诊断过了，就选最新的一个重新分析一遍
            target_logs = [max(log_info, key=lambda x: x["mtime"])]
            self.log(f"[*] 所有日志已诊断，重新分析最近一份: {target_logs[0]['name']}")
        else:
            # 排序，从旧到新处理
            undiagnosed.sort(key=lambda x: x["mtime"])
            target_logs = undiagnosed
            self.log(f"[*] 准备批量诊断 {len(target_logs)} 份未处理日志...")

        total = len(target_logs)
        fingerprint_stats = {}
        for idx, target_log in enumerate(target_logs):
            self.log(f"\n[*] [{idx+1}/{total}] 正在分析: {target_log['name']}")
            try:
                self._diagnose_log_entry(target_log, backfill, fingerprint_stats)
            except Exception as e:
                self.log(f"[-] [{idx+1}/{total}] 分析失败: {e}")
        
        if fingerprint_stats:
            self.log(f"\n[+] 本次诊断涉及 {len(fingerprint_stats)} 个栈指纹。")
            ranked = sorted(fingerprint_stats.values(),
                            key=lambda s: (-s["samples"], s["signature"]))
            repeated = [s for s in ranked if s["samples"] > 1]
            if repeated:
                self.log("[+] 重复崩溃聚类（累计出现多于 1 次）：")
                for s in repeated[:5]:
                    map_part = f"{s['maps']} 张地图" if s["maps"] else "地图未知"
                    self.log(f"    {s['signature']}  {s.get('version') or '版本未知'}  "
                             f"{s['samples']} 次 / {map_part}")

        return f"[+] 批量诊断完成，共处理 {total} 份日志。"

    def _diagnose_log_entry(self, target_log, backfill=False,
                            fingerprint_stats=None):
        """诊断单份日志并输出完整结论，记录指纹与历史。"""
        latest_log = target_log["path"]
        base_name = os.path.splitext(latest_log)[0]
        dmp_file = base_name + ".dmp"

        analysis_summary = ""
        # 1. 优先分析 .dmp 文件 (二进制分析)；回溯建指纹时只读文本，避免启动过慢
        dmp_info = None
        if os.path.exists(dmp_file) and not backfill:
            dmp_info = self._analyze_dmp(dmp_file)
        dmp_analysis_success = dmp_info is not None
        if dmp_info:
            analysis_summary = dmp_info["analysis"]

        # 2. 传统文本日志分析 (逻辑降级/互补)
        content = read_log(latest_log)
        result = self.analyze_log_content(content)
        result = self._merge_dmp(result, dmp_info)
        self.last_diagnosis = result
        addr = result["addr"]
        relative_offset = result["relative_offset"]
        analysis = result["analysis_text"]
        log_map_name = result["map_name"]
        log_mod_name = result["module_name"]
        conc = result.get("conclusion")
        detail_text = result.get("detail_text") or ""

        if log_map_name != "Unknown":
            self.log(f"[+] 从日志提取到地图: {log_map_name}")

        if log_mod_name != "Unknown" and not dmp_analysis_success:
            self.log(f"[+] 从日志定位到模块: {log_mod_name}")

        if addr != "Unknown" and not dmp_analysis_success:
            self.log(f"[+] 捕获到原始崩溃地址: {addr}")
            if relative_offset:
                self.log(f"[+] 成功还原相对偏移量: {relative_offset}")

        show_conclusion = bool(conc) and (
            not dmp_analysis_success or conc["attribution"] != "暂无法确定")
        if show_conclusion:
            self.log("")
            for line in conc["text"].splitlines():
                self.log("  " + line)
            self.update_status(
                f"诊断：{conc['attribution']} · 置信度 {int(conc['confidence'] * 100)}%")
            analysis_summary = (analysis_summary + "\n" + analysis
                                if analysis_summary else analysis)
        elif conc is None:
            self.log(f"[-] {analysis}")
            analysis_summary = (analysis_summary + "\n" + analysis
                                if analysis_summary else analysis)

        if detail_text:
            self.log("[!] 补充依据：")
            self.log(f"      {detail_text}")
            if not show_conclusion:
                analysis_summary = (analysis_summary + "\n" + detail_text
                                    if analysis_summary else detail_text)

        # 栈指纹：同一版本 + 相同栈顶帧视为同一崩溃，按日志去重计数
        fp = result.get("fingerprint")
        if fp and self.history:
            stats = self.history.record_fingerprint(
                fp, target_log["name"], log_map_name,
                attribution=(conc or {}).get("attribution"),
                confidence=(conc or {}).get("confidence"))
            if stats:
                if fingerprint_stats is not None:
                    fingerprint_stats[stats["signature"]] = stats
                label = fp["version"] or "版本未知"
                map_part = (f"涉及 {stats['maps']} 张地图"
                            if stats["maps"] else "地图未知")
                if stats["new"]:
                    self.log(f"[+] 栈指纹 {fp['signature']}（{label}，"
                             f"{fp['frame_count']} 帧）：累计第 "
                             f"{stats['samples']} 次，{map_part}")
                else:
                    self.log(f"[+] 栈指纹 {fp['signature']}（{label}，"
                             f"{fp['frame_count']} 帧）：本日志已计入，累计 "
                             f"{stats['samples']} 次，{map_part}")

        # 记录到历史库
        if self.history:
            file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            self.history.mark_diagnosed(
                target_log['name'], file_hash, target_log['mtime'],
                analysis_summary)

    def analyze_selected_log(self, log_path):
        """诊断用户指定的单份日志，返回给界面显示的结果行。"""
        if not log_path or not os.path.isfile(log_path):
            return "[-] 未找到所选日志文件。"
        name = os.path.basename(log_path)
        try:
            mtime = os.path.getmtime(log_path)
        except OSError:
            mtime = time.time()
        status = self.history.get_log_status(name) if self.history else None
        target_log = {
            "name": name,
            "path": log_path,
            "mtime": mtime,
            "diagnosed": status["diagnosed"] if status else False,
            "reported": status["reported"] if status else False,
        }
        self.log(f"\n[*] 正在分析所选日志: {name}")
        self.last_diagnosis = None
        try:
            self._diagnose_log_entry(target_log)
        except Exception as e:
            self.log(f"[-] 分析失败: {e}")
            return f"[-] 诊断失败: {e}"
        return f"[+] 已诊断: {name}"

    def generate_ai_slicing_report(self, map_file, mpq_editor_path, base_dir):
        """
        Extracts war3map.j and performs code slicing to identify risky functions for AI analysis.
        Generates a Markdown report.
        """
        self.log("\n" + "="*70)
        self.log(f"   🤖 AI 辅助修复预处理 (JASS Slicing)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        
        try:
            temp_dir = os.path.join(base_dir, "ai_slicing")
            os.makedirs(temp_dir, exist_ok=True)
            
            script_path = self._find_and_extract_jass_script(map_file, mpq_editor_path, temp_dir)
            if not script_path:
                self.log("[-] 提取失败: 无法找到 JASS 脚本。")
                return
            
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            self.log("[*] 正在分析脚本结构并提取高风险函数...")
            
            functions = []
            current_func = []
            in_func = False
            
            for line in lines:
                if line.strip().startswith("function ") or line.strip().startswith("constant function "):
                    in_func = True
                    current_func = [line]
                elif line.strip() == "endfunction":
                    current_func.append(line)
                    functions.append("".join(current_func))
                    in_func = False
                    current_func = []
                elif in_func:
                    current_func.append(line)
            
            # 筛选高风险函数：包含创建句柄但没有销毁逻辑的，或者逻辑复杂的
            risky_functions = []
            for func in functions:
                risk_score = 0
                if "Location(" in func and "RemoveLocation" not in func: risk_score += 5
                if "CreateGroup()" in func and "DestroyGroup" not in func: risk_score += 5
                if "CreateTimer()" in func and "DestroyTimer" not in func: risk_score += 5
                if "GetLocalPlayer()" in func: risk_score += 3
                if len(func.splitlines()) > 50: risk_score += 2 # 复杂度
                
                if risk_score >= 5:
                    risky_functions.append((func, risk_score))
            
            risky_functions.sort(key=lambda x: x[1], reverse=True)
            
            # 生成 Markdown 报告
            report_name = f"AI_Audit_{os.path.basename(map_file)}.md"
            report_path = os.path.join(base_dir, report_name)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"# JASS 脚本分析报告 (AI 辅助修复专用)\n\n")
                f.write(f"- **目标地图**: {os.path.basename(map_file)}\n")
                f.write(f"- **分析时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"- **发现风险函数**: {len(risky_functions)} 个\n\n")
                f.write(f"## 建议操作\n")
                f.write(f"请将以下代码块提交给 AI (如 ChatGPT/Claude/Trae)，并询问：\n")
                f.write(f"> \"这些 JASS 函数存在泄露或同步风险吗？请帮我修复它们。\"\n\n")
                
                for i, (func, score) in enumerate(risky_functions[:10]): # 只取前10个最危险的
                    f.write(f"### 风险函数 #{i+1} (风险评分: {score})\n")
                    f.write(f"```jass\n{func}\n```\n\n")
            
            self.log(f"[+] 报告已生成: {report_path}")
            self.log(f"[提示] 您可以直接使用该报告内容向 AI 发起修复请求，以节省 Token。")
            
        except Exception as e:
            self.log(f"[-] Slicing 异常: {e}")
        finally:
            self.log("="*70)
