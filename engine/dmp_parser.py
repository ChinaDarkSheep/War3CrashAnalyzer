"""Minidump 解析：模块版本、异常上下文与调用栈。

优先使用 skelsec/minidump 读取模块表与异常流，再用 EBP/RBP 链回溯
32 位/64 位调用栈；依赖缺失或解析失败时回退到内置的轻量解析器。
"""

import os
import struct

try:
    import enum as _enum

    import minidump.constants as _md_constants
    import minidump.directory as _md_directory
    import minidump.minidumpfile as _md_file_module
    from minidump.minidumpfile import MinidumpFile as _MinidumpFile
    from minidump.streams.ContextStream import CONTEXT as _CONTEXT
    from minidump.streams.ContextStream import WOW64_CONTEXT as _WOW64_CONTEXT
    from minidump.streams.SystemInfoStream import PROCESSOR_ARCHITECTURE as _ARCH

    _HAS_MINIDUMP = True
except ImportError:
    _HAS_MINIDUMP = False


def _install_stream_type_patch():
    """让库忽略未知流类型（真实日志里存在 0x1000 自定义流）。"""
    tolerant = _enum.IntEnum(
        "TolerantStreamType",
        {member.name: member.value for member in _md_constants.MINIDUMP_STREAM_TYPE},
        module=__name__,
    )

    def _missing(cls, value):
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = "Unknown_%d" % value
        member._value_ = value
        return member

    tolerant._missing_ = classmethod(_missing)
    _md_directory.MINIDUMP_STREAM_TYPE = tolerant
    _md_file_module.MINIDUMP_STREAM_TYPE = tolerant


if _HAS_MINIDUMP:
    _install_stream_type_patch()


_ARCH_NAMES = {
    "INTEL": "x86",
    "AMD64": "x64",
    "ARM": "ARM",
    "IA64": "Itanium",
    "AARCH64": "ARM64",
}


class MinidumpParser:
    """解析 Windows Minidump（.dmp）。

    对外字段与旧实现兼容：modules / exception / sys_info / extract_strings()；
    新增 stack / crash_module / crash_rva / crash_file_version。
    """

    ThreadListStream = 3
    ModuleListStream = 4
    MemoryListStream = 5
    ExceptionStream = 6
    SystemInfoStream = 7
    Memory64ListStream = 9

    MAX_FRAMES = 48

    def __init__(self, file_path):
        self.file_path = file_path
        self.modules = []
        self.exception = None
        self.exception_address = 0
        self.exception_code = 0
        self.thread_id = None
        self.sys_info = None
        self.stack = []
        self.crash_module = None
        self.crash_rva = None
        self.crash_file_version = None
        self.crash_fallback = False
        self.engine = None

    def _reset(self):
        self.modules = []
        self.exception = None
        self.exception_address = 0
        self.exception_code = 0
        self.thread_id = None
        self.sys_info = None
        self.stack = []
        self.crash_module = None
        self.crash_rva = None
        self.crash_file_version = None
        self.crash_fallback = False

    def parse(self):
        if not os.path.exists(self.file_path):
            return False

        if _HAS_MINIDUMP:
            try:
                if self._parse_with_library():
                    self.engine = "minidump"
                    return True
            except Exception:
                pass

        self._reset()
        if self._parse_legacy():
            self.engine = "legacy"
            return True
        return False

    # ---------- minidump 库实现 ----------

    def _parse_with_library(self):
        self._reset()
        # 库在缺少内存段时会用 root logger 打印 PEB 解析异常，
        # 对诊断无意义，解析期间静音。
        import logging
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            minidump_file = _MinidumpFile.parse(self.file_path)
        finally:
            logging.disable(previous)
        try:
            if not minidump_file.sysinfo or not minidump_file.modules:
                return False

            arch = _ARCH_NAMES.get(
                getattr(minidump_file.sysinfo.ProcessorArchitecture, "name", ""), "Unknown")
            self.sys_info = {
                "arch": arch,
                "level": getattr(minidump_file.sysinfo, "ProcessorLevel", None),
            }

            for module in minidump_file.modules.modules:
                self.modules.append({
                    "name": os.path.basename(module.name),
                    "path": module.name,
                    "base": module.baseaddress,
                    "size": module.size,
                    "file_version": _fixed_file_version(module.versioninfo),
                    "timestamp": module.timestamp,
                })

            self._parse_exception(minidump_file)
            self._resolve_crash_frame()
            return True
        finally:
            try:
                minidump_file.file_handle.close()
            except Exception:
                pass

    def _parse_exception(self, minidump_file):
        records = (minidump_file.exception.exception_records
                   if minidump_file.exception else [])
        if not records:
            return

        record = records[0]
        exc = record.ExceptionRecord
        code = getattr(exc, "ExceptionCode_raw", None)
        if code is None:
            code = getattr(getattr(exc, "ExceptionCode", None), "value", 0)
        addr = int(getattr(exc, "ExceptionAddress", 0) or 0)

        self.thread_id = record.ThreadId
        self.exception_code = int(code or 0)
        self.exception_address = addr
        self.exception = {
            "thread_id": "0x%X" % (record.ThreadId or 0),
            "code": "0x%08X" % self.exception_code,
            "address": "0x%08X" % addr,
        }

        context = self._read_exception_context(minidump_file, record)
        if context is not None:
            self.stack = self._unwind(minidump_file, context, addr)

    def _read_exception_context(self, minidump_file, record):
        rva = getattr(getattr(record, "ThreadContext", None), "Rva", None)
        if not rva:
            return None
        arch = (self.sys_info or {}).get("arch")
        if arch not in ("x86", "x64"):
            return None

        handle = minidump_file.file_handle
        position = handle.tell()
        try:
            handle.seek(rva)
            if arch == "x64":
                return _CONTEXT.parse(handle)
            return _WOW64_CONTEXT.parse(handle)
        except Exception:
            return None
        finally:
            try:
                handle.seek(position)
            except Exception:
                pass

    def _unwind(self, minidump_file, context, exception_address):
        if not (minidump_file.memory_segments or minidump_file.memory_segments_64):
            return []
        try:
            reader = minidump_file.get_reader()
        except Exception:
            return []

        ptr_size = 8 if (self.sys_info or {}).get("arch") in ("x64", "ARM64") else 4
        frames = []

        def add(address):
            module = self._module_at(address)
            if not module:
                return
            frames.append({
                "address": "%X" % address,
                "frame": "",
                "section": None,
                "offset": None,
                "module": module["name"],
                "rva": address - module["base"],
            })

        add(exception_address)

        if ptr_size == 8:
            current = getattr(context, "Rbp", 0)
        else:
            current = getattr(context, "Ebp", 0)

        seen = set()
        while current and current not in seen and len(frames) < self.MAX_FRAMES:
            if current % ptr_size:
                break
            seen.add(current)
            try:
                return_address = int.from_bytes(
                    reader.read(current + ptr_size, ptr_size), "little")
                next_frame = int.from_bytes(reader.read(current, ptr_size), "little")
            except Exception:
                break

            add(return_address)
            if not next_frame or next_frame <= current:
                break
            current = next_frame

        deduped = []
        for frame in frames:
            if (deduped and frame["module"] == deduped[-1]["module"]
                    and frame["rva"] == deduped[-1]["rva"]):
                continue
            deduped.append(frame)
        return deduped

    def _module_at(self, address):
        if not address:
            return None
        for module in self.modules:
            if module["base"] <= address < module["base"] + module["size"]:
                return module
        return None

    def _resolve_crash_frame(self):
        module = self._module_at(self.exception_address)
        if module:
            self.crash_module = module["name"]
            self.crash_rva = self.exception_address - module["base"]
            self.crash_file_version = module["file_version"]
            return

        for frame in self.stack:
            if frame.get("rva") is None:
                continue
            module = self._find_module_by_name(frame["module"])
            if module:
                self.crash_module = module["name"]
                self.crash_rva = frame["rva"]
                self.crash_file_version = module["file_version"]
                self.crash_fallback = bool(self.exception_address)
                return

    def _find_module_by_name(self, name):
        for module in self.modules:
            if module["name"].lower() == (name or "").lower():
                return module
        return None

    # ---------- 回退实现（依赖缺失或库解析失败） ----------

    def _parse_legacy(self):
        with open(self.file_path, 'rb') as f:
            data = f.read(32)
            if len(data) < 32:
                return False
            if data[0:4] != b'MDMP':
                return False

            header_struct = struct.unpack('<IIIIIIQ', data)
            stream_count = header_struct[2]
            stream_dir_rva = header_struct[3]

            f.seek(stream_dir_rva)
            streams = {}
            for _ in range(stream_count):
                stream_type, size, rva = struct.unpack('<III', f.read(12))
                streams[stream_type] = {'size': size, 'rva': rva}

            if self.SystemInfoStream in streams:
                s = streams[self.SystemInfoStream]
                f.seek(s['rva'])
                arch, level, _ = struct.unpack('<HHH', f.read(6))
                arch_map = {0: 'x86', 5: 'ARM', 6: 'Itanium', 9: 'x64', 12: 'ARM64'}
                self.sys_info = {'arch': arch_map.get(arch, 'Unknown'), 'level': level}

            if self.ExceptionStream in streams:
                s = streams[self.ExceptionStream]
                f.seek(s['rva'])
                data = f.read(36)
                if len(data) == 36:
                    thread_id, _, code, _, _, addr, _ = struct.unpack('<IIIIQQI', data)
                    self.thread_id = thread_id
                    self.exception_code = code
                    self.exception_address = addr
                    self.exception = {
                        'thread_id': f"0x{thread_id:X}",
                        'code': f"0x{code:08X}",
                        'address': f"0x{addr:08X}",
                    }

            if self.ModuleListStream in streams:
                s = streams[self.ModuleListStream]
                f.seek(s['rva'])
                num_modules = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_modules):
                    m_data = f.read(108)
                    if len(m_data) < 108:
                        break
                    base, size, _, timestamp, name_rva = struct.unpack('<QIIII', m_data[:24])
                    file_version = None
                    ms, ls = struct.unpack('<II', m_data[32:40])
                    if ms or ls:
                        file_version = (f"{ms >> 16}.{ms & 0xFFFF}."
                                        f"{ls >> 16}.{ls & 0xFFFF}")

                    curr_pos = f.tell()
                    f.seek(name_rva)
                    name_len = struct.unpack('<I', f.read(4))[0]
                    name = f.read(name_len).decode('utf-16', errors='ignore').strip('\x00')
                    f.seek(curr_pos)

                    self.modules.append({
                        'name': os.path.basename(name),
                        'path': name,
                        'base': base,
                        'size': size,
                        'file_version': file_version,
                        'timestamp': timestamp,
                    })

        self._resolve_crash_frame()
        return True

    def extract_strings(self, pattern=b'war3map', min_len=4):
        results = []
        if not os.path.exists(self.file_path):
            return results

        with open(self.file_path, 'rb') as f:
            content = f.read()
        start = 0
        while True:
            idx = content.find(pattern, start)
            if idx == -1:
                break
            end = idx
            while end < len(content) and 32 <= content[end] <= 126:
                end += 1
            value = content[idx:end].decode('ascii', errors='ignore')
            if len(value) >= min_len and value not in results:
                results.append(value)
            start = idx + 1
        return results


def _fixed_file_version(info):
    if not info:
        return None
    ms = getattr(info, "dwFileVersionMS", 0) or 0
    ls = getattr(info, "dwFileVersionLS", 0) or 0
    if not (ms or ls):
        return None
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
