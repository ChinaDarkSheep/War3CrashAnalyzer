import struct
import os

class MinidumpParser:
    """
    A lightweight parser for Windows Minidump (.dmp) files.
    Reference: https://docs.microsoft.com/en-us/windows/win32/api/minidumpapiset/
    """
    
    # Stream Types
    ThreadListStream = 3
    ModuleListStream = 4
    MemoryListStream = 5
    ExceptionStream = 6
    SystemInfoStream = 7
    Memory64ListStream = 9
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = None
        self.streams = {}
        self.modules = []
        self.exception = None
        self.sys_info = None

    def parse(self):
        if not os.path.exists(self.file_path):
            return False
            
        with open(self.file_path, 'rb') as f:
            # 1. Parse Header (32 bytes)
            # Signature(4), Version(4), StreamCount(4), StreamDirectoryRva(4), CheckSum(4), TimeDateStamp(4), Flags(8)
            data = f.read(32)
            if len(data) < 32: return False
            
            sig = data[0:4]
            if sig != b'MDMP':
                return False
                
            header_struct = struct.unpack('<IIIIIIQ', data)
            stream_count = header_struct[2]
            stream_dir_rva = header_struct[3]
            
            # 2. Parse Stream Directory
            f.seek(stream_dir_rva)
            for _ in range(stream_count):
                stream_type, size, rva = struct.unpack('<III', f.read(12))
                self.streams[stream_type] = {'size': size, 'rva': rva}
            
            # 3. Parse System Info
            if self.SystemInfoStream in self.streams:
                s = self.streams[self.SystemInfoStream]
                f.seek(s['rva'])
                # ProcessorArch(2), ProcessorLevel(2), ProcessorRevision(2), ...
                arch, level, rev = struct.unpack('<HHH', f.read(6))
                arch_map = {0: 'x86', 5: 'ARM', 6: 'Itanium', 9: 'x64', 12: 'ARM64'}
                self.sys_info = {'arch': arch_map.get(arch, 'Unknown'), 'level': level}
            
            # 4. Parse Exception Stream
            if self.ExceptionStream in self.streams:
                s = self.streams[self.ExceptionStream]
                f.seek(s['rva'])
                # Exception Stream Structure:
                # ThreadId(4), __alignment(4), ExceptionCode(4), ExceptionFlags(4), 
                # ExceptionRecord(8), ExceptionAddress(8), NumberParameters(4)
                # Total: 4+4+4+4+8+8+4 = 36 bytes
                data = f.read(36)
                if len(data) == 36:
                    thread_id, _, code, flags, record, addr, num_params = struct.unpack('<IIIIQQI', data)
                    self.exception = {
                        'thread_id': f"0x{thread_id:X}",
                        'code': f"0x{code:08X}",
                        'address': f"0x{addr:08X}"
                    }
            
            # 5. Parse Module List
            if self.ModuleListStream in self.streams:
                s = self.streams[self.ModuleListStream]
                f.seek(s['rva'])
                num_modules = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_modules):
                    # Base(8), Size(4), CheckSum(4), TimeDateStamp(4), NameRva(4), VersionInfo(48), CVRecord(8), MiscRecord(8)
                    m_data = f.read(108) # 64-bit module entry size
                    base, size, _, _, name_rva = struct.unpack('<QIIII', m_data[:24])
                    
                    # Read name
                    curr_pos = f.tell()
                    f.seek(name_rva)
                    name_len = struct.unpack('<I', f.read(4))[0]
                    name = f.read(name_len).decode('utf-16', errors='ignore').strip('\x00')
                    f.seek(curr_pos)
                    
                    self.modules.append({
                        'name': os.path.basename(name),
                        'path': name,
                        'base': base,
                        'size': size
                    })
                    
        return True

    def extract_strings(self, pattern=b'war3map', min_len=4):
        """
        Extract interesting strings from the dump file.
        """
        results = []
        if not os.path.exists(self.file_path): return results
        
        with open(self.file_path, 'rb') as f:
            # We scan the whole file for the pattern as a simple heuristic
            content = f.read()
            start = 0
            while True:
                idx = content.find(pattern, start)
                if idx == -1: break
                
                # Extract surrounding bytes until a null terminator or non-printable
                end = idx
                while end < len(content) and 32 <= content[end] <= 126:
                    end += 1
                
                s = content[idx:end].decode('ascii', errors='ignore')
                if len(s) >= min_len and s not in results:
                    results.append(s)
                start = idx + 1
        return results
