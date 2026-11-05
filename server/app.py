import os
import sqlite3
import json
import time
import hashlib
import re
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime

app = Flask(__name__, static_folder='static')
DB_PATH = os.path.join(os.path.dirname(__file__), 'crash_data.db')

# --- Crash Knowledge Base (Synced from core/knowledge.py) ---
CRASH_KNOWLEDGE = {
    "0x6F000000": {
        "name": "Game.dll (1.24e)",
        "offsets": {
            "0x00456789": "单位路径搜索逻辑崩溃。通常是由于单位被困在无法移动的地形中。",
            "0x00123456": "渲染引擎溢出。检查是否创建了过多的特效或浮动文字。",
            "0x00789ABC": "同步错误导致的内存违例。检查触发器中是否滥用了 GetLocalPlayer。",
            "0x0044E2C0": "GroupEnumUnitsInRange 崩溃。通常是因为传入了 null 组句柄。",
            "0x00469220": "RemoveLocation 崩溃。通常是因为传入了 null 点句柄。",
            "0x00050EF3": "英雄快捷键 (F9) 字符数组越界。通常是由于英雄数量过多或 UI 字符串处理异常。",
            "0x00055F90": "模型动画与内存冲突。可能是因为在播放动画时该模型或动画已被删除。",
            "0x0008873A": "单位变身 (Metamorphosis/Chaos) 逻辑崩溃。检查非英雄单位变身为英雄或反之的逻辑。",
            "0x00093CE9": "光环层数限制崩溃。同一种光环效果叠加超过 2 层时可能触发。",
            "0x00095B15": "英雄等级变更冲突。在特定触发事件中将英雄等级提升至 2 级以上可能导致崩溃。",
            "0x000ED8A0": "GetExpiredTimer() 冲突。定时器到期函数中引用了非定时器对象或空句柄。",
            "0x0012CF32": "商店购买崩溃。通常是由于非英雄单位（如山丘之王）尝试从特定商店购买物品。",
            "0x00149F62": "镜头应用冲突。在玩家离开或地图切换时强制应用镜头设置导致的空引用。",
            "0x002A0DA6": "烈焰风暴 ('Afrb') 崩溃。当该技能作用于没有任何物品栏位的单位时可能触发。",
            "0x002E0E16": "I2* 系列转换函数崩溃。传入了非法参数（如 -1~-3 或 -9~-12）。",
            "0x002F05C2": "路径寻路逻辑崩溃。两个单位之间完全没有可行路径时的死循环或空引用。",
            "0x002F6337": "计时器恢复崩溃。尝试恢复一个未加载或未初始化的计时器对象。",
            "0x0032755C": "I2* 转换函数严重溢出。参数小于等于 -13 或过大导致的内存越界。",
            "0x00438E02": "治疗守卫 ('Ahwd') 崩溃。召唤单位 ID 为空或未正确定义。",
            "0x0048D130": "魔法效果冲突。多个冲突的 Buff 同时作用于同一个单位。",
            "0x004D3C39": "物品给予逻辑崩溃。尝试向一个不支持物品栏的单位给予物品。",
            "0x005A5AF6": "战斗记录器 ('Battle Recorder') 删除崩溃。在该物品冷却期间尝试将其移除。",
            "0x00685190": "单位坐标越界崩溃。单位移动到了地图边界之外的无效区域。",
            "0x0068B61A": "动态特效删除冲突。在特效移动过程中尝试将其删除导致的同步问题。",
            "0x006AFDE6": "数组索引越界。访问了索引为 -2 或过大的数组元素（-1 通常安全）。",
            "0x006B36CE": "ExecuteFunction 崩溃。尝试执行一个不存在或名为 null 的字符串函数。",
            "0x006B37BB": "GroupEnumUnitsInRange 回调签名错误。Condition 参数必须是 takes nothing returns boolean。"
        }
    },
    "0x6F000002": {
        "name": "Game.dll (1.26a)",
        "offsets": {
            "0x00083B24": "单位/组选择崩溃。通常发生在玩家或代码尝试选择一个正在被删除的单位时。",
            "0x0017F814": "JASS 堆栈溢出。最常见的崩溃，通常由无限递归的触发器或死循环引起。",
            "0x00556040": "字符串内存溢出。大量动态创建字符串且未及时释放。",
            "0x006B6294": "排泄/句柄 (Handle) 问题。通常与计时器或已销毁单位的引用有关。",
            "0x0000836F": "模型/纹理丢失。尝试加载一个不存在的 .mdx 或 .blp 文件。",
            "0x0045B7D9": "音频引擎崩溃。通常与 3D 音效设置或损坏的音效文件有关。",
            "0x004D8F46": "技能施法逻辑崩溃。可能由于触发器中对正在施法的单位执行了非法的即时操作（如立即删除）。",
            "0x004780C1": "UI 刷新冲突。通常发生在自定义 FDF 界面在单位死亡/删除时未能正确同步。",
            "0x00086CA030": "JASS 虚拟机异常。检测到死循环或函数调用递归深度超过 256 层。",
            "0x6F4790C1": "对象访问冲突。尝试访问已销毁的单位或 Handle 对象的成员属性。"
        }
    },
    "0x6F000001": {
        "name": "Game.dll (1.27a)",
        "offsets": {
            "0x0050A568": "移除英雄属性崩溃。检测到脚本尝试对英雄执行 UnitRemoveAbility(..., 'AHer')，这会摧毁英雄数据结构导致 UI 访问冲突。",
            "0x0050B568": "移除英雄属性崩溃。检测到脚本尝试对英雄执行 UnitRemoveAbility(..., 'AHer')，这会摧毁英雄数据结构导致 UI 访问冲突。",
            "0x0017307D": "同步错误与本地玩家冲突。通常在 GetLocalPlayer() 块内执行了改变游戏状态的操作（如创建单位、修改变量），或调用了会导致状态更新的本地 UI/声音函数。",
            "0x0009F8A7": "音频引擎溢出/句柄异常。尝试播放 null 声音句柄或加载了采样率不合规（非 44.1kHz）的音频文件，导致音频缓冲区溢出。",
            "0x00045394": "单位选择与 UI 渲染冲突。当一个被选中的单位或正在多面板显示的单位被 RemoveUnit 彻底移除时，UI 渲染逻辑访问已释放内存导致崩溃。",
            "0x0055AA11": "脚本引擎死循环。检查是否有未加等待的无限循环触发器。",
            "0x0022BB33": "模型资源读取错误。某个模型文件损坏或不完整。",
            "0x00084510": "魔兽内置 UI 刷新崩溃。常见于多面板 (Multiboard) 更新过快。",
            "0x001E35E0": "GroupEnumUnitsInRange 崩溃。空句柄引用。",
            "0x001FE500": "RemoveLocation 崩溃。空句柄引用。",
            "0x03CEFC10": "渲染引擎冲突。通常由于非法模型路径或纹理资源损坏引起。",
            "0x631A97CC": "音频驱动异常。建议检查 mss32.dll 或尝试关闭环境音效。"
        }
    },
    "0x6F000003": {
        "name": "Game.dll (1.28.5)",
        "offsets": {
            "0x001E852A": "同步错误 (Desync)。在联网游戏中，由于本地文件不同步导致的强制退出。",
            "0x003B5A10": "UI 渲染崩溃。自定义 FDF 文件语法错误导致的界面崩溃。"
        }
    },
    "0x6F000004": {
        "name": "Game.dll (1.31.1)",
        "offsets": {
            "0x007823B2": "Lua 脚本语法错误。脚本逻辑严重错误会导致此崩溃。",
            "0x000B3250": "模型解析错误。1.31 对 .mdx 格式要求更严，旧版损坏的模型会导致此地址报错。",
            "0x005D67A4": "哈希表 (Hashtable) 溢出。存入过多的数据未清理。"
        }
    }
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS crash_reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  map_name TEXT,
                  os_info TEXT,
                  crash_address TEXT,
                  log_content TEXT,
                  content_hash TEXT UNIQUE,
                  timestamp DATETIME,
                  analysis_result TEXT)''')
    
    # Auto migration: check for analysis_result and content_hash columns
    c.execute("PRAGMA table_info(crash_reports)")
    columns = [row[1] for row in c.fetchall()]
    if 'analysis_result' not in columns:
        print("[*] 正在为旧数据库添加 analysis_result 列...")
        c.execute("ALTER TABLE crash_reports ADD COLUMN analysis_result TEXT")
    
    if 'content_hash' not in columns:
        print("[*] 正在为旧数据库添加 content_hash 列...")
        c.execute("ALTER TABLE crash_reports ADD COLUMN content_hash TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON crash_reports(content_hash)")
        
    conn.commit()
    conn.close()

init_db()

def get_content_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def extract_crash_info(log_content):
    """
    Extract crash address and Game.dll relative offset from log content
    """
    addr = "Unknown"
    relative_offset = None
    
    # Try multiple formats for address
    match_a = re.search(r'occurred at (0x[0-9A-F]+)', log_content, re.IGNORECASE)
    match_b = re.search(r'at [0-9A-F]{4}:([0-9A-F]{8})', log_content, re.IGNORECASE)
    
    if match_a:
        addr = match_a.group(1).upper()
    elif match_b:
        addr = match_b.group(1).upper()
    
    if addr != "Unknown":
        # Try to find Game.dll offset in stack trace
        stack_match = re.search(rf'{addr}\s+[0-9A-F]{{8}}\s+0001:([0-9A-F]{{8}})\s+.*Game\.dll', log_content, re.IGNORECASE)
        if stack_match:
            relative_offset = "0x" + stack_match.group(1).upper()
        else:
            # Fallback for simple offsets
            clean_addr = addr.replace("0X", "")
            if len(clean_addr) <= 8:
                try:
                    val = int(clean_addr, 16)
                    if val < 0x01000000:
                        relative_offset = "0x" + clean_addr.zfill(8)
                except:
                    pass
    
    return addr, relative_offset

def extract_map_name(log_content):
    """
    Extract map name from log content
    """
    map_name = "Unknown"
    map_match = re.search(r'Played Maps\\(.*?)\.(?:w3x|w3m|w3n)', log_content, re.IGNORECASE)
    if map_match:
        full_name = map_match.group(1)
        suffix_match = re.search(r'\.(w3x|w3m|w3n)', log_content[map_match.start():map_match.end()], re.IGNORECASE)
        suffix = suffix_match.group(1) if suffix_match else "w3x"
        
        if '\\' in full_name:
            map_name = full_name.split('\\')[-1] + "." + suffix
        else:
            map_name = full_name + "." + suffix
            
    if map_name == "Unknown" or map_name == ".w3m" or map_name == ".w3x":
        alt_match = re.search(r'([^\\]+\.(?:w3x|w3m|w3n))', log_content, re.IGNORECASE)
        if alt_match:
            alt_name = alt_match.group(1)
            if "war3" not in alt_name.lower() and "exe" not in alt_name.lower():
                map_name = alt_name
    return map_name

def analyze_crash(log_content):
    addr, relative_offset = extract_crash_info(log_content)
    
    search_target = relative_offset if relative_offset else addr
    
    for ver, data in CRASH_KNOWLEDGE.items():
        if search_target in data['offsets']:
            return f"[{data['name']}] {data['offsets'][search_target]}"
            
    if relative_offset:
        return f"未知 Game.dll 偏移量 ({relative_offset})"
    return "无法定位崩溃原因，建议检查第三方插件"

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/report', methods=['POST'])
def report_crash():
    data = request.json
    map_name = data.get('map', 'Unknown')
    os_info = data.get('os', 'Unknown')
    log_content = data.get('log_content', '')
    
    if not log_content:
        return jsonify({"status": "error", "message": "No log content"}), 400
        
    content_hash = get_content_hash(log_content)
    
    # 优先使用客户端提供的分析结果
    client_addr = data.get('crash_address')
    client_analysis = data.get('analysis_result')
    client_map = data.get('map')
    
    if client_addr and client_analysis:
        addr = client_addr
        analysis = client_analysis
    else:
        # 降级方案：服务器自行分析
        addr, relative_offset = extract_crash_info(log_content)
        addr = relative_offset if relative_offset else addr
        analysis = analyze_crash(log_content)
    
    # 地图名纠正：如果客户端传的是 Unknown，尝试从日志里重新提取
    if not client_map or client_map == "Unknown":
        map_name = extract_map_name(log_content)
    else:
        map_name = client_map

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO crash_reports (map_name, os_info, crash_address, log_content, content_hash, timestamp, analysis_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (map_name, os_info, addr, log_content, content_hash, now_str, analysis))
        conn.commit()
        status = "success"
    except sqlite3.IntegrityError:
        status = "duplicate"
    conn.close()
    
    return jsonify({"status": status, "analysis": analysis})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    map_filter = request.args.get('map')
    search_query = request.args.get('search')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    where_clauses = []
    params = []
    if map_filter:
        where_clauses.append("map_name = ?")
        params.append(map_filter)
    if search_query:
        where_clauses.append("(map_name LIKE ? OR crash_address LIKE ? OR analysis_result LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Top crashing maps
    c.execute("SELECT map_name, COUNT(*) as count FROM crash_reports GROUP BY map_name ORDER BY count DESC LIMIT 5")
    top_maps = [dict(row) for row in c.fetchall()]
    
    # Common crash reasons (based on analysis_result)
    c.execute(f"SELECT analysis_result as reason, COUNT(*) as count FROM crash_reports {where_clause} GROUP BY analysis_result ORDER BY count DESC LIMIT 5", params)
    top_reasons = [dict(row) for row in c.fetchall()]
    
    # Total count
    c.execute(f"SELECT COUNT(*) FROM crash_reports {where_clause}", params)
    total = c.fetchone()[0]
    
    # Daily trends (last 7 days)
    c.execute(f"SELECT date(timestamp) as day, COUNT(*) as count FROM crash_reports {where_clause} GROUP BY day ORDER BY day DESC LIMIT 7", params)
    trends = [dict(row) for row in c.fetchall()]
    
    # Get all maps for filter dropdown
    c.execute("SELECT DISTINCT map_name FROM crash_reports ORDER BY map_name")
    maps = [row['map_name'] for row in c.fetchall()]
    
    conn.close()
    return jsonify({
        "total_reports": total,
        "top_maps": top_maps,
        "top_reasons": top_reasons,
        "trends": trends[::-1], # chronological order
        "maps": maps
    })

@app.route('/api/crashes', methods=['GET'])
def get_crashes():
    map_filter = request.args.get('map')
    search_query = request.args.get('search')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = "SELECT id, map_name, crash_address, analysis_result, timestamp FROM crash_reports"
    where_clauses = []
    params = []
    if map_filter:
        where_clauses.append("map_name = ?")
        params.append(map_filter)
    if search_query:
        where_clauses.append("(map_name LIKE ? OR crash_address LIKE ? OR analysis_result LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " ORDER BY timestamp DESC LIMIT 20"
    
    c.execute(query, params)
    crashes = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(crashes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2234, debug=True)
