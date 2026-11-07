import os
import shutil
import subprocess
import traceback
import re
from core.constants import (
    SET_RE, LEAK_CATEGORY, ALL_FUNCS_SORTED, COMMON_DICT, ALL_LEAK_TYPES,
    CALL_RE, CALL_NAME_RE, BOOLEXPR_FUNCS, MATCHING_FUNCS, NO_AUTO_DESTROY,
    SHARED_HANDLE_CREATORS, AUTO_FIX_TYPES, OWNERSHIP_SINK_FUNCS
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
            body = lines[start + 1:end]
            masked = [self._mask_code(line) for line in body]

            local_names = set()
            for line in masked:
                m = re.match(r'^\s*local\s+\w+\s+(\w+)', line)
                if m:
                    local_names.add(m.group(1))

            # 1. 扫描局部变量泄露 (未销毁的 Local 变量)
            idx = 0
            while idx < len(body) and re.match(r'^\s*local\s', masked[idx]):
                idx += 1

            for i in range(idx):
                m = re.match(
                    r'^\s*local\s+(\w+)\s+(\w+)\s*(?:=\s*(.*))?$', masked[i]
                )
                if not m:
                    continue
                vtype, vname = m.group(1), m.group(2)
                if vtype not in ALL_LEAK_TYPES:
                    continue
                if not self._category_enabled(vtype, options):
                    continue

                creator = self._creator_at_start(m.group(3) or '')
                if not creator:
                    creator = self._creator_from_assignment(masked, vname)
                if creator not in ALL_LEAK_TYPES[vtype][1]:
                    # 没有创建过对象，或只创建了共享句柄
                    continue

                destroyer = ALL_LEAK_TYPES[vtype][0]
                if self._has_destroy(masked, destroyer, vname):
                    continue

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
            gui_managed_groups = any(
                re.match(r'^\s*set\s+bj_wantDestroyGroup\s*=\s*true\b', line)
                for line in masked
            )
            for i, line in enumerate(masked):
                stripped = line.strip()
                if not stripped or stripped.startswith("local "):
                    continue
                if re.match(r'^\s*return\b', line):
                    # return 出去的对象所有权已经转移
                    continue

                for span in self._call_spans(line):
                    s, e, creator = span
                    kind, destroyer = LEAK_CATEGORY.get(creator, (None, None))
                    if kind not in ALL_LEAK_TYPES:
                        continue
                    if not self._category_enabled(kind, options):
                        continue
                    if creator in SHARED_HANDLE_CREATORS:
                        continue
                    if kind == "group" and gui_managed_groups:
                        continue

                    parent = self._parent_call(line, span)
                    if parent is not None:
                        if parent[2] == destroyer:
                            continue
                        if parent[2] in OWNERSHIP_SINK_FUNCS:
                            continue

                    if stripped.startswith("set "):
                        sm = SET_RE.match(line)
                        if sm and self._creator_at_start(sm.group(4)):
                            # 命名赋值交给局部变量扫描，全局变量视为所有权转移
                            continue

                    leaks.append({
                        "line": start + i + 2,
                        "function": fname,
                        "variable": "Anonymous (内联匿名)",
                        "type": kind,
                        "reason": f"内联调用 `{creator}(...)` 产生了匿名 `{kind}` 对象，无法被手动销毁。",
                        "suggestion": f"建议先将 `{creator}(...)` 的结果赋值给一个局部变量，使用后再调用 `{destroyer}` 销毁。"
                    })

        return leaks

    @staticmethod
    def _mask_code(line):
        """把字符串字面量与 // 注释替换为等长空白，保留列位置。"""
        chars = list(line)
        i = 0
        in_string = False
        while i < len(chars):
            ch = chars[i]
            if in_string:
                if ch == '\\' and i + 1 < len(chars):
                    chars[i] = chars[i + 1] = ' '
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                chars[i] = ' '
                i += 1
                continue
            if ch == '"':
                chars[i] = ' '
                in_string = True
                i += 1
                continue
            if ch == '/' and i + 1 < len(chars) and chars[i + 1] == '/':
                for j in range(i, len(chars)):
                    chars[j] = ' '
                break
            i += 1
        return ''.join(chars)

    def _creator_at_start(self, rhs):
        """rhs 整体是一个已知创建调用时返回函数名。"""
        rhs = rhs.strip()
        if not rhs:
            return None
        m = CALL_NAME_RE.match(rhs)
        if not m or m.start() != 0:
            return None
        if self._find_matching_paren(rhs, m.end() - 1) != len(rhs) - 1:
            return None
        return m.group(1)

    def _creator_from_assignment(self, masked_lines, var):
        """查找 `set var = Creator(...)` 中实际创建对象的函数名。"""
        pattern = re.compile(rf'^\s*set\s+{re.escape(var)}\s*=\s*(.*)$')
        for line in masked_lines:
            m = pattern.match(line)
            if m:
                creator = self._creator_at_start(m.group(1))
                if creator:
                    return creator
        return None

    @staticmethod
    def _has_destroy(masked_lines, destroyer, var):
        pattern = re.compile(
            rf'\b{re.escape(destroyer)}\s*\(\s*{re.escape(var)}\s*\)'
        )
        return any(pattern.search(line) for line in masked_lines)

    @staticmethod
    def _call_spans(line):
        spans = []
        for m in CALL_NAME_RE.finditer(line):
            close = Fixer._find_matching_paren(line, m.end() - 1)
            if close != -1:
                spans.append((m.start(), close, m.group(1)))
        return spans

    @staticmethod
    def _parent_call(line, span):
        """返回包裹 span 的最小调用，没有则返回 None。"""
        s, e, _ = span
        parent = None
        for candidate in Fixer._call_spans(line):
            cs, ce, _ = candidate
            if cs < s and e < ce:
                if parent is None or (ce - cs) < (parent[1] - parent[0]):
                    parent = candidate
        return parent

    def _variable_escapes(self, masked_lines, var, local_names):
        """变量所有权被转移时返回 True。"""
        name = re.escape(var)
        for line in masked_lines:
            if re.match(rf'^\s*return\s+{name}\s*$', line):
                return True
            m = SET_RE.match(line)
            if m and m.group(4).strip() == var:
                target = m.group(2)
                if target not in local_names:
                    return True
            if re.match(r'^\s*set\s+[A-Za-z_]\w*\s*\[', line):
                if re.search(rf'=\s*{name}\s*$', line):
                    return True
            if re.search(rf'\bSave\w*Handle\s*\([^)]*\b{name}\b', line):
                return True
        return False

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
                used = re.search(rf'\b{re.escape(creator_func)}\s*\(', func_code)
                destroyed = re.search(rf'\b{re.escape(destroyer)}\s*\(', func_code)
                if used and not destroyed:
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

    @staticmethod
    def _auto_fix_enabled(kind, creator, options):
        """自动修复白名单：只处理点、单位组、新建玩家组。"""
        if not creator or kind not in AUTO_FIX_TYPES:
            return False
        if creator in NO_AUTO_DESTROY or creator in SHARED_HANDLE_CREATORS:
            return False
        if kind == "location": return options.get("fix_point", True)
        if kind == "group": return options.get("fix_group", True)
        if kind == "force": return options.get("fix_force", True)
        return False

    def transform_function_block(self, func_text, func_name, shared_vars, options):
        lines = func_text.split('\n')
        if len(lines) < 2: return func_text

        header, trailer, body = lines[0], lines[-1], lines[1:-1]
        masked = [self._mask_code(line) for line in body]

        idx = 0
        while idx < len(body) and re.match(r'^\s*local\s', masked[idx]):
            idx += 1

        locals_part = body[:idx]
        actual_body = body[idx:]
        actual_masked = masked[idx:]

        local_names = set()
        local_vars = []
        for line in masked[:idx]:
            m = re.match(
                r'^\s*local\s+(\w+)\s+(\w+)\s*(?:=\s*(.*))?$', line
            )
            if not m:
                continue
            vtype, vname = m.group(1), m.group(2)
            local_names.add(vname)
            if vtype in ALL_LEAK_TYPES:
                creator = self._creator_at_start(m.group(3) or '')
                local_vars.append((vtype, vname, creator))

        # GUI 单位组由 bj_wantDestroyGroup 管理，自动销毁会重复清理
        block_options = dict(options)
        if any(
            re.match(r'^\s*set\s+bj_wantDestroyGroup\s*=\s*true\b', line)
            for line in masked
        ):
            block_options["fix_group"] = False

        returns = [
            i for i, line in enumerate(actual_masked)
            if re.match(r'^\s*return\b', line)
        ]
        depths = self._nesting_depths(actual_masked)
        # 多出口或嵌套 return 的清理位置无法静态确定，先只报告不修改
        tail_cleanup_allowed = not returns or (
            len(returns) == 1 and depths[returns[0]] == 0
        )
        body_text = '\n'.join(actual_masked)
        reassigned = {
            m.group(1)
            for m in re.finditer(
                r'^\s*set\s+([A-Za-z_]\w*)\s*=', body_text, re.MULTILINE
            )
        }

        cleanup_code = []
        for vtype, vname, creator in local_vars:
            if not self._auto_fix_enabled(vtype, creator, block_options):
                continue
            if vname in shared_vars or vname in reassigned:
                continue
            destroy_func = ALL_LEAK_TYPES[vtype][0]
            if self._has_destroy(actual_masked, destroy_func, vname):
                continue
            if self._variable_escapes(actual_masked, vname, local_names):
                continue
            if not tail_cleanup_allowed:
                continue
            cleanup_code.append(f"    call {destroy_func}({vname})")
            cleanup_code.append(f"    set {vname} = null")
            self.leak_counter += 1

        # 跟踪 `set var = Creator(...)` 的变量，在使用结束后销毁
        declared_with_creator = {
            vname for _, vname, creator in local_vars if creator
        }
        destroy_after = {}
        assigned_creators = {}
        for i, line in enumerate(actual_masked):
            m = SET_RE.match(line)
            if not m:
                continue
            var, rhs = m.group(2), m.group(4).rstrip()
            if var not in local_names or var in shared_vars:
                continue
            if var in declared_with_creator:
                continue
            cm = CALL_RE.match(rhs)
            if not cm or cm.start() != 0 or self._find_matching_paren(rhs, cm.end() - 1) != len(rhs) - 1:
                continue
            creator = cm.group(1)
            kind, destroyfn = LEAK_CATEGORY[creator]
            if not self._auto_fix_enabled(kind, creator, block_options):
                continue
            assigned_creators[i] = (var, creator, rhs)
            if self._variable_escapes(actual_masked, var, local_names):
                continue
            last_use = -1
            already_cleaned = False
            clean_re = re.compile(rf'\b{destroyfn}\s*\(\s*{re.escape(var)}\s*\)')
            j = i + 1
            while j < len(actual_masked):
                if re.match(rf'^\s*set\s+{re.escape(var)}\s*=', actual_masked[j]): break
                if clean_re.search(actual_masked[j]): already_cleaned = True; break
                if re.search(rf'\b{re.escape(var)}\b', actual_masked[j]): last_use = j
                j += 1
            if not already_cleaned and last_use != -1 and depths[last_use] == depths[i]:
                destroy_after.setdefault(last_use, []).append((destroyfn, var))

        new_locals, out = [], []
        for i, line in enumerate(actual_body):
            if i in assigned_creators:
                var, creator, call = assigned_creators[i]
                newline, pre, post = self.hoist_all_calls(
                    call, new_locals, block_options, True
                )
                out.extend(pre)
                out.append(line.replace(call, newline, 1) if newline != call else line)
                out.extend(post)
            else:
                newline, pre, post = self.hoist_all_calls(
                    line, new_locals, block_options
                )
                out.extend(pre); out.append(newline); out.extend(post)
            if i in destroy_after:
                for dfn, v in destroy_after[i]:
                    out.append(f"    call {dfn}({v})")
                    self.leak_counter += 1

        final_body = []
        inserted = False
        for line in out:
            if cleanup_code and not inserted and re.match(
                r'^\s*return\b', self._mask_code(line)
            ):
                final_body.extend(cleanup_code)
                inserted = True
            final_body.append(line)

        if cleanup_code and not inserted:
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

    @staticmethod
    def _find_matching_paren(s, open_idx):
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
        masked = self._mask_code(newline)

        # return 出去的对象所有权转移，不能追加销毁
        if re.match(r'^\s*return\b', masked):
            return line, [], []
        # `set var = Creator(...)` 是命名赋值，由调用方决定所有权
        assign = SET_RE.match(masked)
        if assign and self._creator_at_start(assign.group(4)):
            return line, [], []

        while True:
            spans = [
                span for span in self._call_spans(masked)
                if span[2] in LEAK_CATEGORY
            ]
            if not spans: break
            leaf = None
            for s, e, name in spans:
                kind, dfn = LEAK_CATEGORY[name]
                if not self._auto_fix_enabled(kind, name, options): continue
                if nested_only and s == 0 and e == len(masked) - 1: continue
                if any(s < s2 and e2 < e for s2, e2, n2 in spans if (s, e) != (s2, e2)): continue
                parent = self._parent_call(masked, (s, e, name))
                # 外层已经是销毁函数时不再提升，避免重复销毁
                if parent is not None and parent[2] == dfn: continue
                if parent is not None and parent[2] in OWNERSHIP_SINK_FUNCS: continue
                if re.search(rf'\b{re.escape(dfn)}\s*\(\s*$', masked[:s]): continue
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
            masked = self._mask_code(newline)
        return newline, pre, post
