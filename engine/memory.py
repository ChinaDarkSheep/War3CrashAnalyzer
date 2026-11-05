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

# --- JASS VM / 引擎对象监控 ---
# 1.27a (1.27.0.52240) 实测锚点，全部为 Game.dll 模块内 RVA：
#   [Game.dll + 0xBE4238] -> CGameWar3
#   CGameWar3 + 0x1C      -> CGameState
#   CGameState + 0x194    -> 句柄表容量
#   CGameState + 0x198    -> 当前句柄数
#   CGameState + 0x19C    -> 句柄表数组，每项 12 字节，+4 为对象指针
GAME_WAR3_RVA = 0xBE4238
GAME_STATE_OFFSET = 0x1C
HANDLE_CAPACITY_OFFSET = 0x194
HANDLE_LENGTH_OFFSET = 0x198
HANDLE_TABLE_OFFSET = 0x19C
HANDLE_ENTRY_SIZE = 12


class AgentMonitor:
    """按 CGameState 句柄表统计当前活动对象。

    1.27a 没有可靠的静态 TCDataAllocator 锚点（旧硬编码 0xBE64F0 / 0xBE6530
    在本版本读到的是 TSGrowableArray 等其他全局结构），因此改为遍历句柄表：
    对象首 dword 是虚表，再借 MSVC RTTI 还原类名。统计的是活动句柄数，
    不是对象池容量。
    """

    _DISPLAY_NAMES = {
        "CUnit": "单位 (Unit)",
        "CDestructable": "可破坏物 (Destructable)",
        "CItem": "物品 (Item)",
        "CGroup": "单位组 (Group)",
        "CMapLocation": "点 (Location)",
        "CTimerWar3": "计时器 (Timer)",
        "CTriggerWar3": "触发器 (Trigger)",
        "CTriggerAction": "触发器动作 (TriggerAction)",
        "CPlayerWar3": "玩家 (Player)",
        "CForce": "玩家组 (Force)",
        "CSoundWar3": "声音 (Sound)",
        "CRectWar3": "区域 (Rect)",
        "CFilterFunc": "过滤函数 (FilterFunc)",
        "CUnitEventReg": "单位事件 (UnitEvent)",
        "CPlayerEventReg": "玩家事件 (PlayerEvent)",
        "CGameEventReg": "游戏事件 (GameEvent)",
        "CTimerExpireEventReg": "计时器事件 (TimerEvent)",
    }

    def __init__(self, h_process, game_base, game_size=0x1000000, vm_monitor=None):
        self.h_process = h_process
        self.kernel32 = ctypes.windll.kernel32
        self.game_base = game_base
        self.game_size = game_size
        self.vm_monitor = vm_monitor or JassVMMonitor(h_process, game_base, game_size)
        self._class_cache = {}

    def read_memory(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if self.kernel32.ReadProcessMemory(
                self.h_process, ctypes.c_void_p(address), buffer, size,
                ctypes.byref(bytes_read)):
            return buffer.raw[:bytes_read.value]
        return None

    def read_u32(self, address):
        data = self.read_memory(address, 4)
        return int.from_bytes(data, "little") if data and len(data) == 4 else 0

    def _class_name(self, vtable):
        if vtable in self._class_cache:
            return self._class_cache[vtable]
        name = None
        if self.game_base <= vtable < self.game_base + self.game_size:
            col = self.read_u32(vtable - 4)
            if self.game_base <= col < self.game_base + self.game_size:
                td = self.read_u32(col + 12)
                if 0x00010000 < td < 0x80000000:
                    raw = self.read_memory(td + 8, 128)
                    if raw:
                        text = raw.split(b"\x00")[0].decode("latin1", "ignore")
                        if text.startswith(".?A"):
                            name = text[4:].split("@")[0]
        self._class_cache[vtable] = name
        return name

    def _display_name(self, class_name):
        if not class_name:
            return "其他/未识别"
        return self._DISPLAY_NAMES.get(class_name, class_name)

    def get_object_counts(self):
        """返回 {显示名: {'count': 数量, 'class': 原始类名}}，按数量降序。"""
        info = self.vm_monitor.get_jass_handles_info()
        if not info:
            return {}
        table = info["table"]
        capacity = info["total"]
        data = self.read_memory(table, capacity * HANDLE_ENTRY_SIZE)
        if not data or len(data) < capacity * HANDLE_ENTRY_SIZE:
            return {}

        counts = {}
        for index in range(capacity):
            offset = index * HANDLE_ENTRY_SIZE + 4
            obj = int.from_bytes(data[offset:offset + 4], "little")
            if not (0x00010000 < obj < 0x80000000):
                continue
            class_name = self._class_name(self.read_u32(obj))
            label = self._display_name(class_name)
            entry = counts.get(label)
            if entry is None:
                counts[label] = {"count": 1, "class": class_name or ""}
            else:
                entry["count"] += 1
        return dict(sorted(counts.items(), key=lambda item: -item[1]["count"]))

class JassVMMonitor:
    """只读取经过实测验证的 CGameWar3 / CGameState 锚点。

    找不到锚点或数值越界时返回 None，不再做全堆扫描：
    旧实现的全堆启发式单次耗时 36~61 秒且返回过误报值。
    """

    GAME_WAR3_RVA = GAME_WAR3_RVA
    GAME_STATE_OFFSET = GAME_STATE_OFFSET
    HANDLE_CAPACITY_OFFSET = HANDLE_CAPACITY_OFFSET
    HANDLE_LENGTH_OFFSET = HANDLE_LENGTH_OFFSET
    HANDLE_TABLE_OFFSET = HANDLE_TABLE_OFFSET

    def __init__(self, h_process, game_base, game_size=0x1000000):
        self.h_process = h_process
        self.kernel32 = ctypes.windll.kernel32
        self.game_base = game_base
        self.game_size = game_size
        self.GAME_WAR3 = None
        self.GAME_STATE = None
        self.refresh_anchors()

    def read_memory(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if self.kernel32.ReadProcessMemory(
                self.h_process, ctypes.c_void_p(address), buffer, size,
                ctypes.byref(bytes_read)):
            return buffer.raw[:bytes_read.value]
        return None

    def read_u32(self, address):
        data = self.read_memory(address, 4)
        return int.from_bytes(data, "little") if data and len(data) == 4 else 0

    def _in_module(self, value):
        return self.game_base <= value < self.game_base + self.game_size

    def _is_object(self, address):
        return (0x00010000 < address < 0x80000000
                and self._in_module(self.read_u32(address)))

    def refresh_anchors(self):
        self.GAME_WAR3 = None
        self.GAME_STATE = None
        holder = self.read_u32(self.game_base + self.GAME_WAR3_RVA)
        if not self._is_object(holder):
            return False
        state = self.read_u32(holder + self.GAME_STATE_OFFSET)
        if not self._is_object(state):
            return False
        self.GAME_WAR3 = holder
        self.GAME_STATE = state
        return True

    def get_jass_handles_info(self):
        if self.GAME_STATE is None and not self.refresh_anchors():
            return None
        capacity = self.read_u32(self.GAME_STATE + self.HANDLE_CAPACITY_OFFSET)
        active = self.read_u32(self.GAME_STATE + self.HANDLE_LENGTH_OFFSET)
        table = self.read_u32(self.GAME_STATE + self.HANDLE_TABLE_OFFSET)
        if not (0 < capacity <= 0x20000 and 0 <= active <= capacity):
            return None
        if not (0x00010000 < table < 0x80000000):
            return None
        return {
            "total": capacity,
            "active": active,
            "free": capacity - active,
            "table": table,
            "game_war3": self.GAME_WAR3,
            "game_state": self.GAME_STATE,
        }
