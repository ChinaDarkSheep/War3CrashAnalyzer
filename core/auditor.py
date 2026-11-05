import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import traceback
import hashlib
import json
import re
import shutil
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
from core.constants import COMMON_DICT
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
        if base_dir:
            db_path = os.path.join(base_dir, "history.db")
            self.history = HistoryTracker(db_path)
        else:
            self.history = None

    def _build_dynamic_listfile(self, map_file, temp_dir):
        """扫描地图二进制文件并结合本地字典，构建用于提取的 Listfile。"""
        path_pattern = re.compile(rb'[a-zA-Z0-9_\\]+\.(?:j|lua|w3u|w3a|w3h|w3t|w3b|w3d|w3q|wts)', re.I)
        found_paths = set(COMMON_DICT)
        found_paths.update({"war3map.j", "scripts\\war3map.j", "war3map.lua", "scripts\\war3map.lua"})
        
        # 1. 尝试从本地 listfiles 目录加载字典
        listfiles_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "listfiles")
        if os.path.exists(listfiles_dir):
            for f_name in os.listdir(listfiles_dir):
                if f_name.endswith(".txt"):
                    try:
                        with open(os.path.join(listfiles_dir, f_name), 'r', encoding='utf-8', errors='ignore') as lf:
                            for line in lf:
                                line = line.strip()
                                if len(line) > 3:
                                    found_paths.add(line)
                    except: pass

        # 2. 动态扫描二进制数据 (前 30MB)
        try:
            with open(map_file, 'rb') as f:
                chunk = f.read(30 * 1024 * 1024)
                for m in path_pattern.finditer(chunk):
                    try:
                        path = m.group().decode('ascii', errors='ignore')
                        if len(path) > 3:
                            found_paths.add(path)
                    except: pass
        except: pass
            
        listfile_path = os.path.join(temp_dir, "auditor_listfile.txt")
        with open(listfile_path, 'w', encoding='ascii', errors='ignore') as f:
            for p in sorted(found_paths):
                f.write(p + "\n")
        return listfile_path

    def _find_and_extract_jass_script(self, map_file, mpq_editor_path, output_dir):
        """
        增强型脚本提取逻辑：
        1. 尝试直接提取常用路径
        2. 动态扫描二进制构建 listfile 并通过 /list 提取
        3. 筛选体积最大的脚本文件
        """
        self.log("[*] 正在初始化增强型脚本提取...")
        
        # 1. 尝试提取关键路径 (配合 Listfile)
        listfile = self._build_dynamic_listfile(map_file, output_dir)
        common_names = ["war3map.j", "scripts\\war3map.j", "war3map.lua", "scripts\\war3map.lua"]
        
        for name in common_names:
            target_p = os.path.join(output_dir, os.path.basename(name))
            if os.path.exists(target_p): os.remove(target_p)
            
            cmd = [mpq_editor_path, "/extract", map_file, name, output_dir, "/listfile", listfile]
            subprocess.run(cmd, capture_output=True)
            
            if os.path.exists(target_p) and os.path.getsize(target_p) > 100:
                self.log(f"[+] 成功提取脚本: {name}")
                return target_p

        # 2. 深度扫描提取 (混淆名识别)
        self.log("[*] 常规路径提取失败，正在通过深度扫描识别混淆名...")
        list_cmd = [mpq_editor_path, "/list", map_file, "/listfile", listfile]
        
        try:
            result = subprocess.run(list_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=30)
            if result.returncode == 0 and result.stdout:
                files = result.stdout.strip().splitlines()
                jass_files = [f.strip() for f in files if f.strip().lower().endswith(('.j', '.lua'))]
                
                if jass_files:
                    extracted_scripts = []
                    for jf in jass_files:
                        safe_name = os.path.basename(jf)
                        subprocess.run([mpq_editor_path, "/extract", map_file, jf, output_dir], capture_output=True)
                        p = os.path.join(output_dir, safe_name)
                        if os.path.exists(p):
                            extracted_scripts.append((p, os.path.getsize(p)))
                    
                    if extracted_scripts:
                        extracted_scripts.sort(key=lambda x: x[1], reverse=True)
                        best_p = extracted_scripts[0][0]
                        ext = os.path.splitext(best_p)[1].lower()
                        final_p = os.path.join(output_dir, "war3map" + ext)
                        
                        if os.path.exists(final_p): os.remove(final_p)
                        shutil.move(best_p, final_p)
                        self.log(f"[+] 深度扫描成功识别主脚本: {os.path.basename(best_p)} ({os.path.getsize(final_p)/1024:.1f} KB)")
                        return final_p
        except Exception as e:
            self.log(f"[-] 深度扫描异常: {e}")

        self.log("[-] 提取失败：所有策略均无法找到脚本文件。")
        return None

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
        }

    def get_analysis_data(self, log_content):
        r = self.analyze_log_content(log_content)
        return (r["addr"], r["relative_offset"], r["analysis_text"], r["map_name"], r["module_name"])

    def analyze_log_file(self, log_path):
        """诊断单个日志（自动收集用）：分析文本并记录历史与指纹。"""
        content = read_log(log_path)
        result = self.analyze_log_content(content)
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
            latest_log = target_log["path"]
            base_name = os.path.splitext(latest_log)[0]
            dmp_file = base_name + ".dmp"
            
            analysis_summary = ""
            try:
                # 1. 优先分析 .dmp 文件 (二进制分析)；回溯建指纹时只读文本，避免启动过慢
                dmp_analysis_success = False
                if os.path.exists(dmp_file) and not backfill:
                    self.log(f"[*] 发现伴随 Dump 文件: {os.path.basename(dmp_file)}")
                    parser = MinidumpParser(dmp_file)
                    try:
                        if parser.parse():
                            dmp_analysis_success = True
                            if parser.exception:
                                code = parser.exception['code']
                                addr = parser.exception['address']
                                
                                # 兼容性查找：忽略大小写并统一格式
                                explanation = "未知异常代码"
                                for k, v in EXCEPTION_CODES.items():
                                    if k.lower() == code.lower():
                                        explanation = v
                                        break
                                        
                                self.log(f"[+] Dump 异常码: {code}")
                                self.log(f"    解释: {explanation}")
                                self.log(f"[+] Dump 崩溃地址: {addr}")
                                
                                # 定位崩溃模块，并用 dmp 内的文件版本查知识库
                                crash_mod = "Unknown"
                                target_addr = int(addr, 16)
                                for mod in parser.modules:
                                    if mod['base'] <= target_addr < (mod['base'] + mod['size']):
                                        crash_mod = mod['name']
                                        mod_version = normalize_version(mod.get('file_version'))
                                        offset = normalize_offset(hex(target_addr - mod['base']))
                                        self.log(f"[+] 崩溃发生于模块: {crash_mod} "
                                                 f"(相对偏移: {offset}, 文件版本: {mod.get('file_version') or '未知'})")
                                        analysis_summary += f"[{crash_mod}+{offset}] "
                                        for ver, entry in lookup(crash_mod, mod_version, offset):
                                            hit = describe(entry, ver, mod_version is not None)
                                            self.log(f"[+] 命中知识库: {hit}")
                                            analysis_summary += hit + " "
                                        break
                            
                            # 提取 war3map 相关字符串
                            scripts = parser.extract_strings(b'war3map', 8)
                            if scripts:
                                self.log(f"[+] 提取到 {len(scripts)} 条脚本相关线索:")
                                for s in scripts[:5]: # 只显示前5条
                                    self.log(f"    - {s}")
                    except Exception as de:
                        self.log(f"[-] Dump 分析异常: {de}")
                
                # 2. 传统文本日志分析 (逻辑降级/互补)
                content = read_log(latest_log)
                result = self.analyze_log_content(content)
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
                    analysis_summary = analysis

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
                    self.history.mark_diagnosed(target_log['name'], file_hash, target_log['mtime'], analysis_summary)
                    
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

    def desync_log_analysis(self, war3_path):
        self.log("\n" + "="*70)
        self.log("   🌐 网络同步日志分析 (Desync Analysis)")
        self.log("="*70)
        
        # 尝试从多个可能的位置读取 net.log
        possible_paths = [
            os.path.join(war3_path, "Logs", "net.log"),
            os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "Logs", "net.log"),
            os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Logs", "net.log")
        ]
        
        log_content = None
        for path in possible_paths:
            if os.path.exists(path):
                self.log(f"[*] 发现同步日志: {path}")
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        log_content = f.read()
                    break
                except: continue
        
        if not log_content:
            self.log("[-] 未在魔兽目录或文档目录找到 net.log。")
            self.log("[提示] 请确保在魔兽启动参数中开启了网络日志记录功能。")
            return

        self.log("[*] 正在扫描同步失效关键标记...")
        desync_markers = ["desync", "checksum mismatch", "mismatch", "sync error"]
        found = False
        
        lines = log_content.splitlines()
        for i, line in enumerate(reversed(lines)):
            if any(marker in line.lower() for marker in desync_markers):
                self.log(f"[发现] 同步失效记录 (倒数第 {i+1} 行):")
                self.log(f"      > {line.strip()}")
                found = True
                # 简单原因推测
                if "Random" in line:
                    self.log("[诊断] 风险点: 随机数种子不匹配，检查 GetRandomInt 调用。")
                elif "Handle" in line:
                    self.log("[诊断] 风险点: 句柄 ID 不一致，检查异步对象创建。")
                break
        
        if not found:
            self.log("[+] 日志分析完毕：未发现明显的同步失效(Desync)记录。")
        
        self.log("="*70)
