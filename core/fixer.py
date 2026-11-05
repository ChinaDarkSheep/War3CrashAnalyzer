import os
import shutil
import subprocess
import traceback
import re
from core.constants import (
    SET_RE, LEAK_CATEGORY, ALL_FUNCS_SORTED, COMMON_DICT, ALL_LEAK_TYPES,
    CALL_RE, BOOLEXPR_FUNCS, MATCHING_FUNCS, NO_AUTO_DESTROY
)

class Fixer:
    def __init__(self, log_func):
        self.log = log_func
        self.leak_counter = 0

    def _build_dynamic_jass_listfile(self, map_file, temp_dir):
        """扫描地图二进制文件并结合本地字典，构建用于提取脚本的 Listfile。"""
        # 匹配可能的脚本路径模式
        path_pattern = re.compile(rb'[a-zA-Z0-9_\\]+\.(?:j|lua)', re.I)
        found_paths = {"war3map.j", "scripts\\war3map.j", "war3map.lua", "scripts\\war3map.lua"}
        
        # 1. 尝试从本地 listfiles 目录加载字典
        listfiles_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "listfiles")
        if os.path.exists(listfiles_dir):
            for f_name in os.listdir(listfiles_dir):
                if f_name.endswith(".txt"):
                    try:
                        with open(os.path.join(listfiles_dir, f_name), 'r', encoding='utf-8', errors='ignore') as lf:
                            for line in lf:
                                line = line.strip()
                                if line.lower().endswith(('.j', '.lua')):
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
        except Exception as e:
            self.log(f"[!] 动态扫描异常: {e}")
            
        listfile_path = os.path.join(temp_dir, "fixer_listfile.txt")
        with open(listfile_path, 'w', encoding='ascii', errors='ignore') as f:
            for p in sorted(found_paths):
                f.write(p + "\n")
        return listfile_path

    def _extract_script(self, map_file, mpq_editor_path, temp_dir):
        """通用提取脚本逻辑。"""
        self.log("[*] 正在从地图中提取脚本文件...")
        script_path = None
        listfile = self._build_dynamic_jass_listfile(map_file, temp_dir)
        
        common_names = ["war3map.j", "scripts\\war3map.j", "war3map.lua", "scripts\\war3map.lua"]
        for name in common_names:
            target_p = os.path.join(temp_dir, os.path.basename(name))
            if os.path.exists(target_p): os.remove(target_p)
            cmd = [mpq_editor_path, "/extract", map_file, name, temp_dir, "/listfile", listfile]
            subprocess.run(cmd, capture_output=True)
            if os.path.exists(target_p) and os.path.getsize(target_p) > 100:
                script_path = target_p
                self.log(f"[+] 成功提取脚本: {name}")
                break

        if not script_path:
            self.log("[*] 正在通过深度扫描筛选主脚本...")
            list_cmd = [mpq_editor_path, "/list", map_file, "/listfile", listfile]
            try:
                result = subprocess.run(list_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=20)
                if result.returncode == 0:
                    files = result.stdout.strip().splitlines()
                    jass_files = [f.strip() for f in files if f.strip().lower().endswith(('.j', '.lua'))]
                    if jass_files:
                        best_script = None
                        max_size = -1
                        for jf in jass_files:
                            subprocess.run([mpq_editor_path, "/extract", map_file, jf, temp_dir], capture_output=True)
                            p = os.path.join(temp_dir, os.path.basename(jf))
                            if os.path.exists(p):
                                sz = os.path.getsize(p)
                                if sz > max_size:
                                    max_size = sz
                                    best_script = p
                        if best_script:
                            ext = os.path.splitext(best_script)[1].lower()
                            script_path = os.path.join(temp_dir, "war3map" + ext)
                            if os.path.exists(script_path): os.remove(script_path)
                            shutil.move(best_script, script_path)
                            self.log(f"[+] 识别到主脚本: {os.path.basename(best_script)}")
            except: pass
        return script_path

    def leak_fix_worker(self, map_file, mpq_editor_path, base_dir, fix_stats_func, finish_callback, options=None):
        if options is None:
            options = {"fix_point": True, "fix_group": True, "fix_rect": True, "optimize_jass": True}
            
        self.log("\n" + "="*70)
        self.log(f"   🛠️ 泄露定位&修复模式 (v1.0)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            temp_dir = os.path.join(base_dir, "temp_fix")
            os.makedirs(temp_dir, exist_ok=True)
            
            script_path = self._extract_script(map_file, mpq_editor_path, temp_dir)
            if not script_path or not os.path.exists(script_path) or os.path.getsize(script_path) == 0:
                self.log("[-] 提取脚本失败，可能地图已加密或脚本文件名不匹配。")
                return

            # 如果是 Lua 脚本，目前 Fixer 只支持 JASS 基础修复，提醒用户
            is_lua = script_path.endswith(".lua")
            if is_lua:
                self.log("[!] 检测到 Lua 脚本。当前基础修复仅支持 JASS，AI 报告仍将尝试生成。")

            # 2. 读取脚本
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_text = f.read()
            
            # 3. 生成诊断报告
            report_text = self.generate_ai_report(original_text, options)
            report_path = os.path.join(temp_dir, "leak_diagnostic_report.md")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            self.log(f"[+] 诊断报告已生成: {report_path}")
            self.log("[提示] 你可以将此报告提交给 AI 以获得更深度的逻辑修复建议。")

            # 4. 执行基础修复
            self.log("[*] 正在分析并执行泄露定位&修复...")
            self.leak_counter = 0
            fixed_text, nfuncs = self.transform_script(original_text, options)
            
            # 5. 写回修复后的脚本
            fixed_script_path = os.path.join(temp_dir, "war3map.fixed.j")
            with open(fixed_script_path, 'w', encoding='utf-8') as f:
                f.write(fixed_text)
            
            # 6. 创建新地图并导入修复后的脚本
            out_path = os.path.splitext(map_file)[0] + "_leakfixed" + os.path.splitext(map_file)[1]
            shutil.copy2(map_file, out_path)
            
            self.log(f"[*] 正在将修复后的脚本导入新地图...")
            cmd_add = [mpq_editor_path, "/add", out_path, fixed_script_path, "war3map.j"]
            subprocess.run(cmd_add, capture_output=True, text=True)
            
            self.log(f"[+] 基础修复完成！")
            self.log(f"[+] 原始函数: {nfuncs} 个")
            self.log(f"[+] 成功定位并修复泄露: {self.leak_counter} 处")
            self.log(f"[+] 输出地图: {out_path}")
            
            fix_stats_func(f"基础修复完成 (发现 {self.leak_counter} 处)。建议查看诊断报告以进行高级修复。")
            
        except Exception as e:
            self.log(f"[-] 修复异常: {e}")
            self.log(traceback.format_exc())
        finally:
            finish_callback()
            self.log("="*70)

    def leak_locate_worker(self, map_file, mpq_editor_path, base_dir, finish_callback, options=None):
        """仅定位泄露而不修复的异步 Worker。"""
        if options is None:
            options = {"fix_point": True, "fix_group": True, "fix_rect": True}

        self.log("\n" + "="*70)
        self.log(f"   🔍 泄露定位模式 (v1.0)")
        self.log(f"   目标: {os.path.basename(map_file)}")
        self.log("="*70)
        try:
            temp_dir = os.path.join(base_dir, "temp_locate")
            os.makedirs(temp_dir, exist_ok=True)
            
            script_path = self._extract_script(map_file, mpq_editor_path, temp_dir)
            if not script_path:
                self.log("[-] 提取脚本失败。")
                return

            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            self.log("[*] 正在分析脚本泄露点...")
            leaks = self.locate_leaks(content, options)
            
            if not leaks:
                self.log("[+] 未发现明显的句柄泄露风险。")
            else:
                self.log(f"[+] 发现 {len(leaks)} 处潜在泄露。")
                for i, leak in enumerate(leaks):
                    self.log(f"  {i+1}. [第 {leak['line']} 行] 类型: {leak['type']}")
                    self.log(f"     原因: {leak['reason']}")
            
            if options.get("gen_report", True):
                report_path = os.path.join(base_dir, f"Leak_Locate_{os.path.basename(map_file)}.md")
                self._generate_locate_report(leaks, report_path, map_file)
                self.log(f"[+] 详细定位报告已生成: {report_path}")

        except Exception as e:
            self.log(f"[-] 定位异常: {e}")
        finally:
            finish_callback()
            self.log("="*70)

    def locate_leaks(self, text, options):
        """核心定位逻辑：返回泄露信息列表，包含局部变量泄露和匿名内联泄露。"""
        text = text.replace('\r\n', '\n')
        lines = text.split('\n')
        func_bounds = self._find_function_blocks(lines)
        
        leaks = []
        for start, end, fname in func_bounds:
            func_lines = lines[start:end+1]
            func_text = '\n'.join(func_lines)
            body = func_lines[1:-1]
            
            # 1. 扫描局部变量泄露 (未销毁的 Local 变量)
            idx = 0
            while idx < len(body) and re.match(r'^\s*local\s', body[idx]):
                idx += 1
            
            locals_part = body[:idx]
            for i, line in enumerate(locals_part):
                m = re.match(r'^\s*local\s+(\w+)\s+(\w+)', line)
                if m:
                    vtype, vname = m.group(1), m.group(2)
                    
                    if vtype not in ALL_LEAK_TYPES: continue
                    
                    # 检查是否禁用了该类型的定位
                    if not self._category_enabled(vtype, options): continue

                    destroyer, _ = ALL_LEAK_TYPES[vtype]
                    
                    if destroyer and f"{destroyer}({vname})" not in func_text:
                        leaks.append({
                            "line": start + i + 2,
                            "function": fname,
                            "variable": vname,
                            "type": vtype,
                            "reason": f"局部变量 `{vname}` ({vtype}) 在函数结束前未调用 `{destroyer}` 销毁。",
                            "suggestion": f"在函数返回前添加 `call {destroyer}({vname})` 并设置 `set {vname} = null`。"
                        })

            # 2. 扫描内联匿名泄露 (例如 call Func(GetUnitLoc(u)))
            # 思路借鉴自“排泄处理”项目：寻找作为参数传递但未赋值给变量的创建函数调用
            for i, line in enumerate(body):
                # 排除注释行
                if line.strip().startswith("//"): continue
                
                # 匹配所有已知的创建函数
                for vtype, (destroyer, creators) in ALL_LEAK_TYPES.items():
                    if not self._category_enabled(vtype, options): continue
                    for creator in creators:
                        if creator in NO_AUTO_DESTROY: continue
                        # 寻找 creator(...) 形式的匹配
                        pattern = re.compile(re.escape(creator) + r'\s*\(', re.I)
                        for match in pattern.finditer(line):
                            # 判定条件：如果这个调用不是紧跟在 'set var =' 之后，或者它被包裹在另一个调用中
                            is_inline = False
                            line_stripped = line.strip()
                            
                            if line_stripped.startswith("call "):
                                is_inline = True
                            elif line_stripped.startswith("set "):
                                eq_idx = line.find("=")
                                if eq_idx != -1:
                                    right_side = line[eq_idx+1:].strip()
                                    if not right_side.startswith(creator) or line.count(creator) > 1:
                                        is_inline = True
                            elif any(line_stripped.startswith(k) for k in ["if ", "elseif ", "loop", "return "]):
                                is_inline = True
                                
                            if is_inline:
                                leaks.append({
                                    "line": start + i + 2,
                                    "function": fname,
                                    "variable": "Anonymous (内联匿名)",
                                    "type": vtype,
                                    "reason": f"内联调用 `{creator}(...)` 产生了匿名 `{vtype}` 对象，无法被手动销毁。",
                                    "suggestion": f"建议先将 `{creator}(...)` 的结果赋值给一个局部变量，使用后再调用 `{destroyer}` 销毁。"
                                })
                            
        return leaks

    def _generate_locate_report(self, leaks, output_path, map_name):
        import datetime
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 泄露定位报告: {os.path.basename(map_name)}\n\n")
            f.write(f"- **总计风险**: {len(leaks)} 处\n")
            f.write(f"- **生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if not leaks:
                f.write("## 扫描结果\n未发现明显泄露点。\n")
                return

            f.write("| 行号 | 函数名 | 变量名 | 类型 | 判定原因 | 修复建议 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for leak in leaks:
                f.write(f"| {leak['line']} | `{leak['function']}` | `{leak['variable']}` | {leak['type']} | {leak['reason']} | {leak['suggestion']} |\n")
            
            f.write("\n\n---\n*报告由 War3CrashAnalyzer 泄露定位引擎生成*")

    def generate_ai_report(self, script_text, options):
        """扫描脚本并生成一份紧凑的 AI 修复上下文报告，节省 tokens。"""
        self.log("[*] 正在生成 AI 诊断报告 (预处理)...")
        lines = script_text.replace('\r\n', '\n').split('\n')
        func_bounds = self._find_function_blocks(lines)
        
        report = []
        report.append("# Warcraft III JASS Leak Diagnostic Report")
        report.append("This report contains suspicious functions extracted from the map script.\n")
        
        cases_found = 0
        for start, end, fname in func_bounds:
            func_code = '\n'.join(lines[start:end+1])
            is_suspicious = False
            detected_leaks = []
            
            # 启发式检测：使用 constants.py 中的 LEAK_CATEGORY
            for creator_func, (ltype, destroyer) in LEAK_CATEGORY.items():
                if creator_func in NO_AUTO_DESTROY: continue
                # 检查选项开关
                if not self._category_enabled(ltype, options): continue
                
                # 如果函数里用了创建函数，但没用销毁函数
                if f"{creator_func}(" in func_code and destroyer not in func_code:
                    is_suspicious = True
                    detected_leaks.append(f"{ltype} (via {creator_func})")
            
            # 复杂逻辑检测
            if func_code.count('return') > 1 or 'TriggerSleepAction' in func_code:
                is_suspicious = True
            
            if is_suspicious:
                cases_found += 1
                report.append(f"## Case {cases_found}: Function `{fname}`")
                report.append(f"- **Issue**: Potential leak or complex logic detected.")
                if detected_leaks:
                    report.append(f"- **Specifics**: {', '.join(set(detected_leaks))}")
                report.append(f"- **Context**: Lines {start+1} - {end+1}")
                report.append("\n```jass")
                report.append(func_code)
                report.append("```\n")
        
        self.log(f"[+] 预处理诊断完成，提取了 {cases_found} 个高风险函数片段。")
        return "\n".join(report)

    def transform_script(self, text, options):
        text = text.replace('\r\n', '\n')
        lines = text.split('\n')
        func_bounds = self._find_function_blocks(lines)
        
        if options.get('optimize_jass', True):
            shared_vars = self._find_shared_scratch_vars(lines, func_bounds)
        else:
            shared_vars = set()
        
        out = []
        nfuncs = 0
        last_end = -1
        for (start, end, fname) in func_bounds:
            out.extend(lines[last_end + 1:start])
            func_block = '\n'.join(lines[start:end + 1])
            fixed = self.transform_function_block(func_block, fname, shared_vars, options)
            out.append(fixed)
            nfuncs += 1
            last_end = end
        out.extend(lines[last_end + 1:])
        return '\n'.join(out), nfuncs

    def _find_function_blocks(self, lines):
        bounds = []
        for i, line in enumerate(lines):
            if re.match(r'^function\s', line):
                start = i
                j = i + 1
                while j < len(lines) and not re.match(r'^endfunction\s*$', lines[j]):
                    j += 1
                fname_m = re.match(r'^function\s+(\S+)', line)
                bounds.append((start, j, fname_m.group(1) if fname_m else "?"))
        return bounds

    def _find_shared_scratch_vars(self, lines, func_bounds):
        from collections import defaultdict
        var_funcs = defaultdict(set)
        for (fstart, fend, fname) in func_bounds:
            for i in range(fstart + 1, fend):
                m = SET_RE.match(lines[i])
                if m and not m.group(2).startswith('gg_'):
                    var_funcs[m.group(2)].add(fname)
        return {v for v, funcs in var_funcs.items() if len(funcs) > 1}

    @staticmethod
    def _category_enabled(kind, options):
        if kind == "location": return options.get("fix_point", True)
        if kind == "group": return options.get("fix_group", True)
        if kind == "rect": return options.get("fix_rect", True)
        return True

    def transform_function_block(self, func_text, func_name, shared_vars, options):
        lines = func_text.split('\n')
        if len(lines) < 2: return func_text
        
        header, trailer, body = lines[0], lines[-1], lines[1:-1]
        
        idx = 0
        while idx < len(body) and re.match(r'^\s*local\s', body[idx]):
            idx += 1
        
        locals_part = body[:idx]
        actual_body = body[idx:]

        local_vars = []
        for line in locals_part:
            m = re.match(r'^\s*local\s+(location|group|rect|unit)\s+(\w+)', line)
            if m:
                local_vars.append((m.group(1), m.group(2)))

        cleanup_code = []
        for vtype, vname in local_vars:
            if not self._category_enabled(vtype, options): continue
            
            destroy_func = {
                "location": "RemoveLocation",
                "group": "DestroyGroup",
                "rect": "RemoveRect"
            }.get(vtype)
            
            if destroy_func and f"{destroy_func}({vname})" not in func_text:
                cleanup_code.append(f"    call {destroy_func}({vname})")
                cleanup_code.append(f"    set {vname} = null")
                self.leak_counter += 1

        # 跟踪 `set var = Creator(...)` 的变量，在使用结束后销毁
        depths = self._nesting_depths(actual_body)
        destroy_after = {}
        assigned_creators = {}
        for i, line in enumerate(actual_body):
            m = SET_RE.match(line)
            if not m or m.group(2).startswith('gg_'):
                continue
            var, rhs = m.group(2), m.group(4).rstrip()
            cm = CALL_RE.match(rhs)
            if not cm or cm.start() != 0 or self._find_matching_paren(rhs, cm.end() - 1) != len(rhs) - 1:
                continue
            creator = cm.group(1)
            kind, destroyfn = LEAK_CATEGORY[creator]
            if creator in NO_AUTO_DESTROY or not self._category_enabled(kind, options):
                continue
            assigned_creators[i] = (var, creator, rhs)
            if var in shared_vars:
                continue
            last_use = -1
            already_cleaned = False
            clean_re = re.compile(rf'\b{destroyfn}\s*\(\s*{re.escape(var)}\s*\)')
            j = i + 1
            while j < len(actual_body):
                if re.match(rf'^\s*set\s+{re.escape(var)}\s*=', actual_body[j]): break
                if clean_re.search(actual_body[j]): already_cleaned = True; break
                if re.search(rf'\b{re.escape(var)}\b', actual_body[j]): last_use = j
                j += 1
            if not already_cleaned and last_use != -1 and depths[last_use] == depths[i]:
                destroy_after.setdefault(last_use, []).append((destroyfn, var))

        new_locals, out = [], []
        for i, line in enumerate(actual_body):
            if i in assigned_creators:
                var, creator, call = assigned_creators[i]
                newline, pre, post = self.hoist_all_calls(call, new_locals, options, True)
                out.extend(pre)
                out.append(line.replace(call, newline, 1) if newline != call else line)
                out.extend(post)
            else:
                newline, pre, post = self.hoist_all_calls(line, new_locals, options)
                out.extend(pre); out.append(newline); out.extend(post)
            if i in destroy_after:
                for dfn, v in destroy_after[i]:
                    out.append(f"    call {dfn}({v})")
                    self.leak_counter += 1

        final_body = []
        inserted = False
        for line in out:
            if "return" in line and not inserted:
                final_body.extend(cleanup_code)
                inserted = True
            final_body.append(line)
        
        if not inserted:
            final_body.extend(cleanup_code)

        return '\n'.join([header] + locals_part + new_locals + final_body + [trailer])

    def _nesting_depths(self, lines):
        depth = [0] * len(lines)
        d = 0
        for i, line in enumerate(lines):
            if re.match(r'^\s*(endif|endloop)\s*$', line): d -= 1
            depth[i] = d
            if re.match(r'^\s*if\s.*\bthen\s*$', line) or re.match(r'^\s*loop\s*$', line): d += 1
        return depth

    def _find_matching_paren(self, s, open_idx):
        depth, in_str = 0, False
        for i in range(open_idx, len(s)):
            if in_str:
                if s[i] == '\\': i += 1
                elif s[i] == '"': in_str = False
            else:
                if s[i] == '"': in_str = True
                elif s[i] == '(': depth += 1
                elif s[i] == ')':
                    depth -= 1
                    if depth == 0: return i
        return -1

    def hoist_all_calls(self, line, new_locals, options, nested_only=False):
        """把内联的句柄创建调用提升为局部变量，并在语句后销毁。"""
        newline, pre, post = line, [], []
        indent = re.match(r'^(\s*)', line).group(1)
        while True:
            spans = []
            for m in CALL_RE.finditer(newline):
                close = self._find_matching_paren(newline, m.end() - 1)
                if close != -1: spans.append((m.start(), close, m.group(1)))
            if not spans: break
            leaf = None
            for s, e, name in spans:
                if name in NO_AUTO_DESTROY: continue
                kind, dfn = LEAK_CATEGORY[name]
                if not self._category_enabled(kind, options): continue
                if nested_only and s == 0 and e == len(newline) - 1: continue
                if any(s < s2 and e2 < e for s2, e2, n2 in spans if (s, e) != (s2, e2)): continue
                parent = None
                for s2, e2, n2 in spans:
                    if s2 <= s and e <= e2 and (s, e) != (s2, e2):
                        if parent is None or (e2 - s2) < (parent[1] - parent[0]): parent = (s2, e2, n2)
                # 外层已经是销毁函数时不再提升，避免重复销毁
                if parent is not None and parent[2] == dfn: continue
                if re.search(rf'\b{re.escape(dfn)}\s*\(\s*$', newline[:s]): continue
                if name in BOOLEXPR_FUNCS:
                    if parent is None or parent[2] not in MATCHING_FUNCS: continue
                leaf = (s, e, name); break
            if not leaf: break
            s, e, name = leaf
            kind, dfn = LEAK_CATEGORY[name]
            v = f"leakfix_{kind[:3]}_{self.leak_counter + 1}"
            self.leak_counter += 1
            new_locals.append(f"    local {kind} {v}")
            pre.append(f"{indent}set {v} = {newline[s:e + 1]}")
            post.append(f"{indent}call {dfn}({v})")
            newline = newline[:s] + v + newline[e + 1:]
        return newline, pre, post
