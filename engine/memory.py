import ctypes
from ctypes import wintypes
import psutil

# --- Windows API Definitions ---
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

def is_admin():
    try:
        return kernel32.IsUserAnAdmin()
    except:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(wintypes.BYTE)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]

def get_module_info(pid, module_name):
    """获取指定进程中模块的基址和大小，支持 32/64 位混用环境"""
    # 方法 1: Toolhelp32Snapshot
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot != -1:
        try:
            me32 = MODULEENTRY32()
            me32.dwSize = ctypes.sizeof(MODULEENTRY32)
            success = kernel32.Module32First(snapshot, ctypes.byref(me32))
            while success:
                mod_name = me32.szModule.decode('utf-8', 'ignore')
                if module_name.lower() in mod_name.lower():
                    base = ctypes.cast(me32.modBaseAddr, ctypes.c_void_p).value
                    size = me32.modBaseSize
                    return base, size
                success = kernel32.Module32Next(snapshot, ctypes.byref(me32))
        finally:
            kernel32.CloseHandle(snapshot)
    
    # 方法 2: EnumProcessModules (备选方案)
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if h_process:
        try:
            module_handles = (wintypes.HMODULE * 1024)()
            needed = wintypes.DWORD()
            if psapi.EnumProcessModules(h_process, ctypes.byref(module_handles), ctypes.sizeof(module_handles), ctypes.byref(needed)):
                count = min(needed.value // ctypes.sizeof(wintypes.HMODULE), 1024)
                for i in range(count):
                    h_mod = module_handles[i]
                    buf = (ctypes.c_char * 260)()
                    psapi.GetModuleBaseNameA(h_process, h_mod, buf, ctypes.sizeof(buf))
                    name = buf.value.decode('utf-8', 'ignore')
                    if module_name.lower() in name.lower():
                        class MODULEINFO(ctypes.Structure):
                            _fields_ = [
                                ("lpBaseOfDll", ctypes.c_void_p),
                                ("SizeOfImage", wintypes.DWORD),
                                ("EntryPoint", ctypes.c_void_p),
                            ]
                        mi = MODULEINFO()
                        psapi.GetModuleInformation(h_process, h_mod, ctypes.byref(mi), ctypes.sizeof(mi))
                        return mi.lpBaseOfDll, mi.SizeOfImage
        finally:
            kernel32.CloseHandle(h_process)
            
    return None, None

def get_module_base(pid, module_name):
    base, _ = get_module_info(pid, module_name)
    return base

def read_process_memory(h_process, address, size):
    buffer = (ctypes.c_char * size)()
    bytes_read = wintypes.DWORD()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)):
        return buffer.raw
    return None

def find_pattern(h_process, base, size, pattern, mask):
    """简单的内存特征码扫描"""
    try:
        data = read_process_memory(h_process, base, size)
        if not data: return None
        
        pattern_len = len(pattern)
        for i in range(size - pattern_len):
            match = True
            for j in range(pattern_len):
                if mask[j] == 'x' and data[i + j] != pattern[j]:
                    match = False
                    break
            if match:
                return base + i
    except:
        pass
    return None

# --- JASS VM Monitor Classes ---
class AgentMonitor:
    def __init__(self, h_process, game_base, game_size=0x1000000):
        self.h_process = h_process
        self.kernel32 = ctypes.windll.kernel32
        self.game_base = game_base
        self.game_size = game_size
        self.cached_offsets = {}
        self.generator_base = self.find_agent_generators()
        
    def read_memory(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if self.kernel32.ReadProcessMemory(self.h_process, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)):
            return buffer.raw[:bytes_read.value]
        return None

    def find_agent_generators(self):
        """扫描整个 game.dll 区段寻找 AgentGenerator (TCDataAllocator) 数组的起始地址"""
        # 优先尝试 1.27a 的常见位置
        # 1.27a (1.27.0.52240) -> 0xBE64F0
        # 1.27b -> 可能不同
        offsets_127a = [0xBE64F0, 0xA5DA34, 0xBE6530]
        for off in offsets_127a:
            addr = self.game_base + off
            data = self.read_memory(addr, 0x100)
            if data and len(data) >= 0x40:
                # 检查 Location (在 +0x20) 的特征
                # TCDataAllocator 结构: vtable(4), inst_size(4), max_count(4), current_count(4), ...
                loc_size = int.from_bytes(data[0x20 + 4 : 0x20 + 8], 'little')
                if loc_size == 0x14:
                    # 进一步验证虚表是否在 game.dll 范围内
                    vt = int.from_bytes(data[0x20 : 0x20 + 4], 'little')
                    if self.game_base <= vt <= self.game_base + self.game_size:
                        return addr

        # 如果常见位置失败，进行特征码扫描
        # 寻找特定的 inst_size 序列: Group(0x30?), Location(0x14), Unit(0x???), ...
        # TCDataAllocator 数组通常是连续的，每个元素 0x20 字节
        pattern = b'\x14\x00\x00\x00' # Location 的 inst_size
        for offset in range(0, self.game_size - 0x100, 4):
            addr = self.game_base + offset
            data = self.read_memory(addr, 0x4)
            if data == pattern:
                # 命中 0x14，假设这是 Location 分配器的偏移 4
                base = addr - 0x20 - 4
                # 验证前后的分配器
                check_data = self.read_memory(base, 0x60)
                if check_data and len(check_data) >= 0x60:
                    # 检查虚表
                    vt_group = int.from_bytes(check_data[0:4], 'little')
                    vt_loc = int.from_bytes(check_data[0x20:0x24], 'little')
                    if (self.game_base <= vt_group <= self.game_base + self.game_size and 
                        self.game_base <= vt_loc <= self.game_base + self.game_size):
                        return base

        # 最后的手段：全内存堆段扫描
        MEM_COMMIT = 0x1000
        PAGE_READWRITE = 0x04
        current_addr = 0x01000000
        end_addr = 0x7FFFFFFF
        
        import ctypes
        from ctypes import wintypes
        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD), ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]
        
        mbi = MEMORY_BASIC_INFORMATION()
        
        while current_addr < end_addr:
            if self.kernel32.VirtualQueryEx(self.h_process, ctypes.c_void_p(current_addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                if mbi.State == MEM_COMMIT and (mbi.Protect & PAGE_READWRITE):
                    # 减小扫描步长，增加成功率
                    region_size = min(mbi.RegionSize, 1024*1024*5)
                    data = self.read_memory(mbi.BaseAddress, region_size)
                    if data:
                        for i in range(0, len(data) - 0x60, 4):
                            if data[i+0x24:i+0x28] == b'\x14\x00\x00\x00':
                                vt = int.from_bytes(data[i+0x20:i+0x24], 'little')
                                if self.game_base <= vt <= self.game_base + self.game_size:
                                    # 验证 total_count 逻辑
                                    total = int.from_bytes(data[i+0x2C:i+0x30], 'little')
                                    active = int.from_bytes(data[i+0x30:i+0x34], 'little')
                                    if 0 < total < 2000000 and active <= total:
                                        return mbi.BaseAddress + i
                current_addr += mbi.RegionSize
            else:
                break
        return None

    def get_agent_data(self, offset_or_name):
        if self.generator_base is None:
            return None
        else:
            # offset_or_name 是从 local_tab 传来的 relative offset (0x00, 0x20, 0x40 ...)
            gen_ptr = self.generator_base + offset_or_name

        data = self.read_memory(gen_ptr, 32)
        if not data or len(data) < 20: return None
        
        inst_size = int.from_bytes(data[4:8], 'little')
        total_count = int.from_bytes(data[12:16], 'little')
        active_count = int.from_bytes(data[16:20], 'little')
        
        # 校验数据合理性
        if 0 < inst_size <= 0x4000 and total_count < 10000000:
            return {
                "count": total_count,
                "active": active_count,
                "size": inst_size,
                "total_mem": total_count * inst_size
            }
        return None

class JassVMMonitor:
    def __init__(self, h_process, game_base, game_size=0x1000000):
        self.h_process = h_process
        self.kernel32 = ctypes.windll.kernel32
        self.game_base = game_base
        self.game_size = game_size
        
        # 自动探测偏移
        self.GAME_WAR3 = None
        self.G_WC3_PROPS = None
        self.PI_JASS_ENV = None
        self.find_vm_offsets()

    def read_memory(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if self.kernel32.ReadProcessMemory(self.h_process, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)):
            return buffer.raw[:bytes_read.value]
    def find_vm_offsets(self):
        """扫描内存寻找 GAME_WAR3 和 G_WC3_PROPS"""
        # 1. 优先使用特征码扫描 (1.27a 推荐)
        # 8B 0D ? ? ? ? 8B 01 FF 90 (mov ecx, [ppGameWar3]; mov eax, [ecx]; call [eax+0x90])
        pattern = b'\x8B\x0D\x00\x00\x00\x00\x8B\x01\xFF\x90'
        mask = 'xx????xxxx'
        found = find_pattern(self.h_process, self.game_base, self.game_size, pattern, mask)
        if found:
            # 提取指针地址
            ptr_addr_data = read_process_memory(self.h_process, found + 2, 4)
            if ptr_addr_data:
                ptr_addr = int.from_bytes(ptr_addr_data, 'little')
                if self.game_base <= ptr_addr <= self.game_base + self.game_size:
                    self.GAME_WAR3 = ptr_addr

        # 2. 如果特征码没找到，尝试已知偏移
        if not self.GAME_WAR3:
            known_game_war3 = [0xAB65F4, 0xBE6530, 0x57130]
            for off in known_game_war3:
                addr = self.game_base + off
                gw_ptr = self.read_ptr(addr)
                if gw_ptr > 0x10000:
                    for sub_off in [0x3BC, 0x3B0, 0x1C]:
                        ptr = self.read_ptr(gw_ptr + sub_off)
                        if ptr > 0x10000:
                            vt = self.read_ptr(ptr)
                            if self.game_base <= vt <= self.game_base + self.game_size:
                                self.GAME_WAR3 = addr
                                break
                if self.GAME_WAR3: break

        # 3. 探测 G_WC3_PROPS
        known_props = [0xAB7788, 0xBE7D50]
        for off in known_props:
            addr = self.game_base + off
            props_ptr = self.read_ptr(addr)
            if props_ptr > 0x10000:
                for index in [5, 4, 6]:
                    env = self.read_ptr(props_ptr + index * 4)
                    if env > 0x10000:
                        cap = self.read_ptr(env + 4)
                        if 0 < cap < 10000:
                            self.G_WC3_PROPS = addr
                            self.PI_JASS_ENV = index
                            break
            if self.G_WC3_PROPS: break

        if self.GAME_WAR3 and self.G_WC3_PROPS: return

        # 4. 全局启发式扫描 (跳过前 0x10000 字节以防 false positive)
        scan_step = 0x20000
        for offset in range(0x10000, self.game_size - 4, 4):
            if offset % scan_step == 0:
                chunk = read_process_memory(self.h_process, self.game_base + offset, min(scan_step + 0x100, self.game_size - offset))
                if not chunk: continue
            
            i = offset % scan_step
            if i + 4 > len(chunk): continue
            
            val = int.from_bytes(chunk[i:i+4], 'little')
            # 必须是一个指向堆或数据段的指针
            if not (0x01000000 < val < 0x7FFFFFFF or 0x00100000 < val < 0x0FFFFFFF): continue
            
            # 探测 GAME_WAR3
            if not self.GAME_WAR3:
                # 验证其虚函数表是否在 game.dll 范围内
                vtable = self.read_ptr(val)
                if self.game_base <= vtable <= self.game_base + self.game_size:
                    for sub_off in [0x2C, 0x84, 0x1C, 0x398, 0x3BC, 0x3B0]:
                        sub_ptr = self.read_ptr(val + sub_off)
                        if sub_ptr > 0x10000:
                            sub_vt = self.read_ptr(sub_ptr)
                            if self.game_base <= sub_vt <= self.game_base + self.game_size:
                                self.GAME_WAR3 = self.game_base + offset
                                break

            # 探测 G_WC3_PROPS
            if not self.G_WC3_PROPS:
                for index in [5, 4, 6]:
                    env_ptr = self.read_ptr(val + index * 4)
                    if env_ptr > 0x10000:
                        env_data = read_process_memory(self.h_process, env_ptr, 12)
                        if env_data and len(env_data) == 12:
                            vt = int.from_bytes(env_data[0:4], 'little')
                            cap = int.from_bytes(env_data[4:8], 'little')
                            if self.game_base <= vt <= self.game_base + self.game_size and 0 < cap < 10000:
                                self.G_WC3_PROPS = self.game_base + offset
                                self.PI_JASS_ENV = index
                                break
            
            if self.GAME_WAR3 and self.G_WC3_PROPS: break

    def get_jass_handles_info(self):
        if not self.GAME_WAR3:
            self.find_vm_offsets()
            if not self.GAME_WAR3: return None
            
        # 优先尝试从绝对偏移文件读取 (最准确)
        active = self.heuristic_scan_handle_table()
        if active > 0:
            return {'total': 8192, 'free': 8192 - active, 'active': active}
            
        game_war3_ptr = self.read_ptr(self.GAME_WAR3)
        if not game_war3_ptr: return None
        
        # 1.27a 可能的 GameState 偏移
        gs_ptr = 0
        best_total = 0
        for off in [0x1C, 0x84, 0x398, 0x3B0, 0x3BC, 0x580, 0x584, 0x6CC, 0x6D8]:
            temp_gs = self.read_ptr(game_war3_ptr + off)
            if temp_gs > 0x10000:
                for sub_off in range(0x10, 0x500, 4):
                    cap = self.read_ptr(temp_gs + sub_off)
                    if cap in [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]:
                        length = self.read_ptr(temp_gs + sub_off + 4)
                        if 10 < length <= cap:
                            items_ptr = self.read_ptr(temp_gs + sub_off + 8)
                            if items_ptr > 0x10000:
                                active = self.count_active_handles(items_ptr, length)
                                if active > best_total:
                                    best_total = active
                                    gs_ptr = temp_gs
                                    
        if not gs_ptr or best_total < 10:
            return None
            
        return {
            'total': 8192, # 估算值
            'free': 8192 - best_total,
            'active': best_total
        }

    def count_active_handles(self, items_ptr, length):
        active = 0
        try:
            # 每个元素 12 字节，读取整个数组
            size = min(length * 12, 100000 * 12) # 限制读取大小防止卡顿
            data = self.read_memory(items_ptr, size)
            if data:
                for j in range(0, len(data), 12):
                    ptr = int.from_bytes(data[j+4:j+8], 'little')
                    if ptr > 0x10000:
                        active += 1
        except Exception:
            pass
        return active
        
    def heuristic_scan_handle_table(self):
        # 既然重启了魔兽，旧的绝对地址就失效了，我们需要进行实时的快速特征码扫描
        active_count = 0
        try:
            MEM_COMMIT = 0x1000
            PAGE_READWRITE = 0x04
            current_addr = 0x01000000
            end_addr = 0x7FFFFFFF
            
            # 使用更严谨的结构体声明以兼容 64位/32位 Python
            import ctypes
            from ctypes import wintypes
            class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD), ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]
            
            mbi = MEMORY_BASIC_INFORMATION()
            
            best_ht_active = 0
            
            while current_addr < end_addr:
                if self.kernel32.VirtualQueryEx(self.h_process, ctypes.c_void_p(current_addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                    if mbi.State == MEM_COMMIT and (mbi.Protect & PAGE_READWRITE):
                        data = self.read_memory(mbi.BaseAddress, min(mbi.RegionSize, 1024*1024*10)) # limit size for speed
                        if data:
                            for i in range(0, len(data) - 12, 4):
                                cap = int.from_bytes(data[i:i+4], 'little')
                                if cap in [4096, 8192, 16384, 32768, 65536, 131072]:
                                    length = int.from_bytes(data[i+4:i+8], 'little')
                                    if 100 < length <= cap:
                                        items = int.from_bytes(data[i+8:i+12], 'little')
                                        if 0x01000000 < items < 0x7FFFFFFF:
                                            # Found potential HandleTable
                                            active = self.count_active_handles(items, length)
                                            if active > best_ht_active and active > 10:
                                                best_ht_active = active
                    current_addr += mbi.RegionSize
                else:
                    break
                    
            if best_ht_active > 0:
                return best_ht_active
                
        except Exception as e:
            print(f"[-] HandleTable Scan Error: {e}")
        return active_count

    def heuristic_scan_jass_env(self):
        try:
            MEM_COMMIT = 0x1000
            PAGE_READWRITE = 0x04
            current_addr = 0x01000000
            end_addr = 0x7FFFFFFF
            
            import ctypes
            from ctypes import wintypes
            class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD), ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]
            
            mbi = MEMORY_BASIC_INFORMATION()
            
            best_env_addr = 0
            best_env_threads = 0
            
            while current_addr < end_addr:
                if self.kernel32.VirtualQueryEx(self.h_process, ctypes.c_void_p(current_addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                    if mbi.State == MEM_COMMIT and (mbi.Protect & PAGE_READWRITE):
                        data = self.read_memory(mbi.BaseAddress, min(mbi.RegionSize, 1024*1024*10))
                        if data:
                            for i in range(0, len(data) - 20, 4):
                                cap = int.from_bytes(data[i+4:i+8], 'little')
                                if cap in [4, 8, 16, 32, 64, 128]:
                                    length = int.from_bytes(data[i+8:i+12], 'little')
                                    if 0 < length <= cap:
                                        items = int.from_bytes(data[i+12:i+16], 'little')
                                        if 0x01000000 < items < 0x7FFFFFFF:
                                            count = int.from_bytes(data[i+16:i+20], 'little')
                                            if count == length or count == length - 1:
                                                if length > best_env_threads:
                                                    best_env_threads = length
                                                    best_env_addr = mbi.BaseAddress + i
                    current_addr += mbi.RegionSize
                else:
                    break
                    
            if best_env_addr != 0:
                return best_env_addr
                
        except Exception as e:
            print(f"[-] JassEnv Scan Error: {e}")
        return None

    def get_jass_env(self):
        # 1. 优先尝试从 GameWar3 偏移获取 (1.27a 推荐)
        if self.GAME_WAR3:
            gw_ptr = self.read_ptr(self.GAME_WAR3)
            if gw_ptr > 0x10000:
                # 1.27a 的 JassEnv 漂移：可能在 0x2C, 0x3BC, 0x3B0, 0x1C, 0x398
                for off in [0x2C, 0x3BC, 0x3B0, 0x1C, 0x398, 0x84, 0x580]:
                    env = self.read_ptr(gw_ptr + off)
                    if env > 0x10000:
                        # 检查虚表是否属于 game.dll
                        vt = self.read_ptr(env)
                        if self.game_base <= vt <= self.game_base + self.game_size:
                            # 进一步扫描内部结构寻找 RunningInstances
                            for sub_off in range(0x0, 0x200, 4):
                                cap = self.read_ptr(env + sub_off)
                                if cap in [4, 8, 16, 32, 64, 128]:
                                    length = self.read_ptr(env + sub_off + 4)
                                    if 0 <= length <= cap:
                                        items = self.read_ptr(env + sub_off + 8)
                                        if items > 0x10000:
                                            # 验证 items 数组的第一个元素是否可能是线程指针
                                            first_item = self.read_ptr(items)
                                            if first_item == 0 or (first_item > 0x10000 and self.read_ptr(first_item) > self.game_base):
                                                return env
            
        # 2. 实时全局堆特征扫描
        env_addr = self.heuristic_scan_jass_env()
        if env_addr:
            return env_addr
            
        # 3. 从 G_WC3_PROPS 获取 (兜底)
        if self.G_WC3_PROPS:
            props_base_ptr = self.read_ptr(self.G_WC3_PROPS)
            if props_base_ptr:
                indexes = [self.PI_JASS_ENV] if self.PI_JASS_ENV is not None else [5, 4, 6]
                for index in indexes:
                    env = self.read_ptr(props_base_ptr + index * 4)
                    if env and env > 0x10000:
                        vt = self.read_ptr(env)
                        if self.game_base <= vt <= self.game_base + self.game_size:
                            return env
        return None

        # 备选方案：从 G_WC3_PROPS 获取
        if not self.G_WC3_PROPS:
            self.find_vm_offsets()
        
        if self.G_WC3_PROPS:
            props_base_ptr = self.read_ptr(self.G_WC3_PROPS)
            if props_base_ptr:
                indexes = [self.PI_JASS_ENV] if self.PI_JASS_ENV is not None else [5, 4, 6]
                for index in indexes:
                    env = self.read_ptr(props_base_ptr + index * 4)
                    if env and env > 0x10000:
                        cap = self.read_ptr(env + 4)
                        length = self.read_ptr(env + 8)
                        if 0 <= length <= cap < 10000:
                            return env
        return None

    def read_ptr(self, addr):
        data = read_process_memory(self.h_process, addr, 4)
        return int.from_bytes(data, 'little') if data else 0

    def read_string(self, addr, max_len=256):
        if not addr: return "<null>"
        data = read_process_memory(self.h_process, addr, max_len)
        if not data: return "<error>"
        try:
            res = data.split(b'\x00')[0].decode('ascii', errors='ignore')
            return res if res else "<empty>"
        except: return "<error>"

    def get_active_instances(self):
        env = self.get_jass_env()
        if not env: return []
        
        # TJassThreadLocal structure (vtable at 0, RunningInstances at 4 or 8)
        # We need to find the correct offset by looking at the capacity
        instances_array_addr = 0
        for off in [4, 8, 12, 16]:
            cap = self.read_ptr(env + off)
            if cap in [4, 8, 16, 32, 64, 128]:
                length = self.read_ptr(env + off + 4)
                if 0 <= length <= cap:
                    items = self.read_ptr(env + off + 8)
                    if items > 0x10000:
                        count = self.read_ptr(env + off + 12)
                        if count == length or count == length - 1:
                            instances_array_addr = env + off
                            break
                            
        if not instances_array_addr:
            return []
            
        capacity = self.read_ptr(instances_array_addr)
        length = self.read_ptr(instances_array_addr + 4)
        items_ptr = self.read_ptr(instances_array_addr + 8)
        
        instances = []
        if items_ptr and length < 1000: # Sanity check
            for i in range(length):
                inst_ptr = self.read_ptr(items_ptr + i * 4)
                if inst_ptr:
                    instances.append(inst_ptr)
        return instances

    def get_instance_info(self, inst_ptr):
        info = {}
        info['ptr'] = hex(inst_ptr)
        info['is_child'] = self.read_ptr(inst_ptr + 24) != 0
        info['op_ptr'] = self.read_ptr(inst_ptr + 32)
        
        # Read CodeStack (TSGrowableArray at offset 36)
        # FCapacity (36), FLength (40), FItems (44)
        stack_length = self.read_ptr(inst_ptr + 40)
        stack_items_ptr = self.read_ptr(inst_ptr + 44)
        
        call_stack = []
        if stack_items_ptr and 0 < stack_length < 1000:
            for i in range(stack_length):
                ret_addr = self.read_ptr(stack_items_ptr + i * 4)
                call_stack.append(ret_addr)
        
        info['call_stack'] = call_stack
        
        # TInstance -> Script is at offset 0x2854 or 0x2858. 
        # Let's try 10324 (0x2854) based on 256*40 + 76 = 10316 + 8
        script_ptr = self.read_ptr(inst_ptr + 10324)
        if not script_ptr or script_ptr < 0x10000:
            script_ptr = self.read_ptr(inst_ptr + 10328) # Try 10328
            
        if script_ptr and script_ptr > 0x10000:
            code_base = self.read_ptr(script_ptr)
            if info['op_ptr'] and code_base and code_base > 0x10000:
                info['op_offset'] = info['op_ptr'] - code_base
            
            # Map call stack to offsets
            info['call_stack_offsets'] = []
            if code_base and code_base > 0x10000:
                for addr in call_stack:
                    info['call_stack_offsets'].append(addr - code_base)
            
        return info
