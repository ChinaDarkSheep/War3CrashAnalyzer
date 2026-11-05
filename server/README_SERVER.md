# 魔兽崩溃分析后端服务 (War3 Crash Analysis Backend)

这是一个为 `War3CrashAnalyzer` 开发的配套后端服务，用于收集、存储和可视化来自不同地图的崩溃数据。

## 核心功能
1. **数据采集**：接收来自客户端的崩溃日志、OS 信息及地图名称。
2. **自动化分析**：服务器端二次校验崩溃地址，匹配已知知识库。
3. **大数据展示**：通过 Web 界面展示崩溃高发地图、常见崩溃原因统计及实时流水。

## 快速启动
1. 确保已安装 Python 环境。
2. 安装依赖：
   ```bash
   pip install flask
   ```
3. 启动服务器：
   ```bash
   python War3CrashAnalyzer/server/app.py
   ```
4. 访问 Web 仪表盘：
   打开浏览器访问 `http://43.163.75.93:2234`

## 目录结构
- `app.py`: Flask 主程序及 API 接口（默认监听 2234 端口）。
- `crash_data.db`: SQLite 数据库（自动生成）。
- `static/index.html`: 前端数据展示界面。

## 客户端集成
客户端 `War3SuperAnalyzer.py` 已集成上报逻辑，上报地址已配置为 `http://43.163.75.93:2234/api/report`。
