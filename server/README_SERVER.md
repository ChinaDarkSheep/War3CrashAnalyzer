# 魔兽崩溃分析后端服务 (War3 Crash Analysis Backend)

这是一个为 `War3CrashAnalyzer` 开发的配套后端服务，用于收集、存储和可视化来自不同地图的崩溃数据。

## 核心功能
1. **数据采集**：接收来自客户端的崩溃日志、OS 信息、地图名与哈希、游戏版本、模块内偏移、调用栈、栈指纹、归属结论等派生字段（不上传地图或 dmp 原始文件）。
2. **自动化分析**：服务器端二次校验崩溃地址，匹配已知知识库；客户端提供分析结果时优先采用。
3. **大数据展示**：通过 Web 界面展示崩溃高发地图、常见崩溃原因统计及实时流水，流水含版本、归属与栈指纹。
4. **聚合统计**：按「地图身份 + 栈指纹」聚合相同崩溃，记录发生次数与作者标注位。

## 上报字段（P2.1）
`/api/report` 在原有 `map / os / log_content / crash_address / analysis_result` 基础上新增：

| 字段 | 说明 |
|---|---|
| `map_hash` | 所选地图文件的 MD5（32 位小写） |
| `game_version` | 归一化游戏版本，如 `1.27a` |
| `module` / `relative_offset` | 崩溃模块与模块内 RVA |
| `attribution` / `confidence` | 归属分类与置信度 |
| `fingerprint` / `fingerprint_version` / `fingerprint_frames` | 栈指纹、其版本与组成帧 |
| `stack` | 调用栈（模块 + RVA，最多 48 帧） |
| `dmp` | dump 摘要（引擎、异常码、模块、文件版本等，不含路径） |

服务端启动时自动为旧库补列；重复日志只补齐空缺字段，不覆盖已有值。

## 崩溃聚合（P2.2）
同一地图的同一栈指纹只保留一条聚合记录，用于回答「这个地图的这个问题崩了多少次」。

**地图身份**：优先使用 `map_hash`（`md5:<hash>`）；没有哈希的旧数据回退为 `name:<小写地图名>`。
**签名**：`signature = sha1(map_key + "|" + 大写指纹)[:12]`，即聚合表主键。
**计数**：新日志入库时 `occurrence + 1`；同一日志重复上报不会重复计数，只补齐空缺字段。

`crash_aggregates` 表字段：

| 字段 | 说明 |
|---|---|
| `signature` | 聚合主键（地图身份 + 指纹） |
| `map_key` / `map_hash` / `map_name` | 地图身份 |
| `fingerprint` / `game_version` | 栈指纹与版本 |
| `module` / `relative_offset` / `attribution` | 崩溃位置与归属 |
| `occurrence` | 累计发生次数 |
| `annotation` | 作者标注（重建时保留，不被覆盖） |
| `first_seen` / `last_seen` / `last_report_id` | 首次、最近时间与最近一条报告 |

表结构升级或历史数据修正后可调用 `rebuild_aggregates()` 全量重建，作者标注按签名保留。

### 查询接口
- `GET /api/aggregates?map_hash=<md5>&map=<地图名>&fingerprint=<指纹>&limit=50`
  按次数倒序返回聚合记录，含 `total` 总数；`map_hash` 只接受 32 位十六进制，`limit` 范围 1~200。
- `GET /api/stats` 新增 `top_fingerprints`（Top 10），与仪表盘的地图/搜索过滤条件一致。

## 作者查询页（P2.3）
访问 `http://<服务器>/author`，或点击总览页的「作者查询」入口。

- **地图识别**：选择 `.w3x/.w3m/.w3n` 文件时，浏览器本地计算 MD5（`static/md5.js`），文件不上传；也可直接粘贴 32 位 MD5，或输入地图名（支持总览中出现过的地图名补全）。
- **指纹排行**：按「地图身份 + 栈指纹」列出次数、版本、模块内偏移、归属、最近时间与作者标注。
- **指纹详情**：点击任意行查看累计次数、首次/最近时间、最近 30 天每日趋势，以及最多 20 条脱敏样本。
- **隐私边界**：样本只包含时间、版本、归属、崩溃位置、诊断结论、调用栈与 dump 摘要，**不返回原始日志、OS 信息、Windows 用户名、计算机名或本地路径**。

详情接口：`GET /api/aggregate/<signature>`，`signature` 为 12 位十六进制；不存在或格式错误返回 404。

## 作者标注与案例缓存（P2.4）
作者可在指纹详情中填写根因、来源（作者确认 / 维护者确认 / 社区反馈）、置信度与标注人。标注写入聚合表，并同步到 `knowledge_cases` 案例缓存。

**写入需要令牌**：启动服务前设置环境变量，未设置时标注接口返回 503（功能禁用）：

```bash
# Linux / macOS
export WAR3_ANNOTATION_TOKEN='请换成足够长的随机字符串'
python server/app.py

# Windows PowerShell
$env:WAR3_ANNOTATION_TOKEN='请换成足够长的随机字符串'
python server/app.py
```

作者页填写同一令牌后提交，请求通过 `X-Annotation-Token` 头发送；令牌错误返回 403。建议服务部署在 HTTPS 之后，避免令牌明文传输。

- `POST /api/aggregate/<signature>/annotation`：JSON 体 `{"annotation": "根因", "source": "作者确认", "confidence": 0.9, "annotator": "可选"}`，`confidence` 为 0~1。
- `GET /api/knowledge/cases?map_hash=<md5>&map=<地图名>&fingerprint=<指纹>&limit=50`：查看案例缓存。
- 案例缓存只作为候选，不自动写入全局 `knowledge.json`；由维护者复核后合并，避免单张地图的个案污染全局偏移结论。
- 全量重建聚合表时会保留标注内容、来源、置信度、标注人与时间。

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
- `crash_data.db`: SQLite 数据库（自动生成，含聚合与案例缓存）。
- `static/index.html`: 总览仪表盘。
- `static/author.html`: 作者查询与标注页。
- `static/md5.js`: 浏览器本地地图 MD5 计算。

## 客户端集成
客户端上报逻辑位于 `core/reporter.py`，上报地址为 `http://43.163.75.93:2234/api/report`（另含域名地址回退）。
