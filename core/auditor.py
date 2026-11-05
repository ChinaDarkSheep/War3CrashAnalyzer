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
from core.knowledge import CRASH_KNOWLEDGE, EXCEPTION_CODES
from core.constants import COMMON_DICT
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
                # 寻找可能的 .mdx 或 .blp 路径
                paths = re.findall(rb'[a-zA-Z0-9_\\]+\.(?:mdx|blp)', content)
                for p in paths:
                    if len(p) > 160:
                        self.log(f"[!] 风险: 发现超长路径 ({len(p)} 字符): {p.decode(errors='ignore')}")
                        found_issues += 1
            
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
            
            # 真实扫描逻辑
            issues = []
            if "UnitRemoveAbility" in content and "'AHer'" in content:
                issues.append("发现致命错误: UnitRemoveAbility(..., 'AHer') 会导致魔兽崩溃！")
            
            if "GetLocalPlayer" in content:
                self.log("[提示] 脚本中包含 GetLocalPlayer，请确保块内无同步对象创建。")
            
            # 统计泄露
            loc_created = content.count("Location(")
            loc_destroyed = content.count("RemoveLocation(")
            if loc_created > loc_destroyed:
                issues.append(f"检测到潜在泄露: Location 创建 {loc_created} 次，仅销毁 {loc_destroyed} 次。")

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

    def get_analysis_data(self, log_content):
        """
        Pure data analysis function without logging to UI
        Returns: (addr, relative_offset, analysis_text, map_name, module_name)
        """
        addr = "Unknown"
        relative_offset = None
        analysis_text = "无法从日志中提取有效崩溃地址"
        map_name = "Unknown"
        module_name = "Unknown"

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
            
            # 尝试从 Stack Trace 中提取模块和相对偏移
            clean_addr = addr.replace("0X", "")
            if len(clean_addr) > 8: clean_addr = clean_addr[-8:] # 取后8位
            
            stack_pattern = rf'{clean_addr}\s+[0-9A-F]{{8}}\s+([0-9A-F]{{4}}):([0-9A-F]{{8}})\s+(.*)'
            stack_match = re.search(stack_pattern, log_content, re.IGNORECASE)
            
            if stack_match:
                section = stack_match.group(1)
                inner_offset = stack_match.group(2)
                # 转换 0001:XXXX 为 RVA (通常 +0x1000)
                if section == "0001":
                    try:
                        rva = int(inner_offset, 16) + 0x1000
                        relative_offset = "0x" + hex(rva)[2:].upper().zfill(8)
                    except:
                        relative_offset = "0x" + inner_offset.upper()
                else:
                    relative_offset = "0x" + inner_offset.upper()
                    
                full_mod_path = stack_match.group(3).strip()
                module_name = os.path.basename(full_mod_path)
            else:
                # 降级方案：如果地址看起来像是一个相对偏移 (例如 < 0x05000000)
                if addr != "Unknown":
                    try:
                        val = int(clean_addr, 16)
                        if val < 0x05000000:
                            relative_offset = "0x" + clean_addr.zfill(8)
                            exe_match = re.search(r'Exe:\s+(.*)', log_content, re.IGNORECASE)
                            if exe_match:
                                module_name = os.path.basename(exe_match.group(1).strip())
                    except: pass

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
            
            # 备选方案：寻找 File: war3map.w3a 等
            if map_name == "Unknown":
                file_match = re.search(r'File:\s+(.*\.(?:w3x|w3m|w3n|w3a|w3u|w3h|w3t|w3d|w3q))', log_content, re.IGNORECASE)
                if file_match:
                    map_name = os.path.basename(file_match.group(1).strip())

            if map_name == "Unknown" or map_name.lower() in [".w3m", ".w3x"]:
                alt_match = re.search(r'([^\\]+\.(?:w3x|w3m|w3n))', log_content, re.IGNORECASE)
                if alt_match:
                    alt_name = alt_match.group(1)
                    if "war3" not in alt_name.lower() and "exe" not in alt_name.lower() and "dll" not in alt_name.lower():
                        map_name = alt_name

            # 3. 匹配知识库 (适配新结构)
            search_target = relative_offset if relative_offset else (addr if addr.startswith("0X") else "0x" + addr)
            search_target = search_target.upper().replace("0X", "0x") # 统一为 0xXXXX 格式
            
            found = False
            # 优先匹配已知模块
            target_modules = [module_name] if module_name != "Unknown" else ["Game.dll", "WorldEditKKWE.exe", "Storm.dll"]
            
            for mod_key in target_modules:
                # 模糊匹配模块名 (忽略大小写)
                matched_mod = None
                for k in CRASH_KNOWLEDGE.keys():
                    if k.lower() == mod_key.lower():
                        matched_mod = k
                        break
                
                if matched_mod:
                    mod_data = CRASH_KNOWLEDGE[matched_mod]
                    for ver, ver_data in mod_data.items():
                        if search_target in ver_data['offsets']:
                            analysis_text = f"[{matched_mod} ({ver})] {ver_data['offsets'][search_target]}"
                            found = True
                            break
                    if found: break
            
            # 增强匹配：如果还是没找到，尝试后缀匹配 (针对 Game.dll 的 ASLR/多版本情况)
            if not found:
                # 只针对 Game.dll 的高频偏移量进行后缀匹配 (后 5 位)
                suffix = search_target[-5:] if len(search_target) >= 5 else None
                if suffix:
                    game_data = CRASH_KNOWLEDGE.get("Game.dll", {})
                    for ver, ver_data in game_data.items():
                        for off, desc in ver_data['offsets'].items():
                            if off.endswith(suffix):
                                analysis_text = f"[Game.dll ({ver}) 疑似匹配] {desc}"
                                found = True
                                break
                        if found: break

            if not found:
                # 如果没找到，但在其他模块中找到了相同的偏移量，也提示一下
                for mod_key, mod_data in CRASH_KNOWLEDGE.items():
                    for ver, ver_data in mod_data.items():
                        if search_target in ver_data['offsets']:
                            analysis_text = f"[{mod_key} ({ver})] {ver_data['offsets'][search_target]}"
                            found = True
                            break
                    if found: break

            if not found and addr != "Unknown":
                analysis_text = f"未知偏移量 ({search_target})，可能发生在 {module_name}"
        except Exception as e:
            analysis_text = f"分析过程异常: {str(e)}"
            
        return addr, relative_offset, analysis_text, map_name, module_name

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
        
        # 筛选未诊断的日志
        undiagnosed = [l for l in log_info if not l["diagnosed"]]
        if not undiagnosed:
            # 如果全诊断过了，就选最新的一个重新分析一遍
            target_logs = [max(log_info, key=lambda x: x["mtime"])]
            self.log(f"[*] 所有日志已诊断，重新分析最近一份: {target_logs[0]['name']}")
        else:
            # 排序，从旧到新处理
            undiagnosed.sort(key=lambda x: x["mtime"])
            target_logs = undiagnosed
            self.log(f"[*] 准备批量诊断 {len(target_logs)} 份未处理日志...")

        total = len(target_logs)
        for idx, target_log in enumerate(target_logs):
            self.log(f"\n[*] [{idx+1}/{total}] 正在分析: {target_log['name']}")
            latest_log = target_log["path"]
            base_name = os.path.splitext(latest_log)[0]
            dmp_file = base_name + ".dmp"
            
            analysis_summary = ""
            try:
                # 1. 优先分析 .dmp 文件 (二进制分析)
                dmp_analysis_success = False
                if os.path.exists(dmp_file):
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
                                
                                # 定位崩溃模块
                                crash_mod = "Unknown"
                                target_addr = int(addr, 16)
                                for mod in parser.modules:
                                    if mod['base'] <= target_addr < (mod['base'] + mod['size']):
                                        crash_mod = mod['name']
                                        offset = hex(target_addr - mod['base']).upper()
                                        self.log(f"[+] 崩溃发生于模块: {crash_mod} (相对偏移: {offset})")
                                        analysis_summary += f"[{crash_mod}+{offset}] "
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
                with open(latest_log, 'r', encoding='gbk', errors='ignore') as f:
                    content = f.read()
                
                addr, relative_offset, analysis, log_map_name, log_mod_name = self.get_analysis_data(content)
                
                if log_map_name != "Unknown":
                    self.log(f"[+] 从日志提取到地图: {log_map_name}")
                
                if log_mod_name != "Unknown" and not dmp_analysis_success:
                    self.log(f"[+] 从日志定位到模块: {log_mod_name}")

                if addr != "Unknown":
                    if not dmp_analysis_success:
                        self.log(f"[+] 捕获到原始崩溃地址: {addr}")
                        if relative_offset:
                            self.log(f"[+] 成功还原相对偏移量: {relative_offset}")
                    
                    if "未知偏移量" not in analysis and "无法从日志" not in analysis:
                        self.log(f"\n[!!!] 匹配到已知崩溃知识库内容:")
                        self.log(f"      {analysis}")
                        analysis_summary += analysis
                    else:
                        if not dmp_analysis_success:
                            self.log(f"\n[?] {analysis}")
                else:
                    if not dmp_analysis_success:
                        self.log("[-] 日志中未找到明确的崩溃偏移量。")
                
                # 记录到历史库
                if self.history:
                    file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    self.history.mark_diagnosed(target_log['name'], file_hash, target_log['mtime'], analysis_summary)
                    
            except Exception as e:
                self.log(f"[-] [{idx+1}/{total}] 分析失败: {e}")
        
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
