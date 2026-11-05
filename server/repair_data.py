import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'crash_data.db')

def extract_crash_info(log_content):
    addr = "Unknown"
    relative_offset = None
    match_a = re.search(r'occurred at (0x[0-9A-F]+)', log_content, re.IGNORECASE)
    match_b = re.search(r'at [0-9A-F]{4}:([0-9A-F]{8})', log_content, re.IGNORECASE)
    if match_a: addr = match_a.group(1).upper()
    elif match_b: addr = match_b.group(1).upper()
    if addr != "Unknown":
        stack_match = re.search(rf'{addr}\s+[0-9A-F]{{8}}\s+0001:([0-9A-F]{{8}})\s+.*Game\.dll', log_content, re.IGNORECASE)
        if stack_match: relative_offset = "0x" + stack_match.group(1).upper()
    return addr, relative_offset

def extract_map_name(log_content):
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
    return map_name

def repair():
    if not os.path.exists(DB_PATH):
        print(f"[-] 数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取所有记录
    c.execute("SELECT id, log_content, map_name FROM crash_reports")
    rows = c.fetchall()
    print(f"[*] 正在处理 {len(rows)} 条记录...")

    for row_id, content, current_map in rows:
        # 1. 修复地图名
        new_map = extract_map_name(content)
        if new_map != "Unknown" and new_map != current_map:
            print(f"   [ID {row_id}] 修正地图名: {current_map} -> {new_map}")
            c.execute("UPDATE crash_reports SET map_name = ? WHERE id = ?", (new_map, row_id))
        
        # 2. 修复分析结果 (如果为空)
        addr, rel = extract_crash_info(content)
        db_addr = rel if rel else addr
        c.execute("UPDATE crash_reports SET crash_address = ? WHERE id = ?", (db_addr, row_id))
    
    conn.commit()
    conn.close()
    print("[+] 修复完成！请重启服务器并刷新网页。")

if __name__ == "__main__":
    repair()
