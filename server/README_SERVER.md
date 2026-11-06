# 魔兽崩溃分析后端服务 (War3 Crash Analysis Backend)

这是一个为 `War3CrashAnalyzer` 开发的配套后端服务，用于收集、存储和可视化来自不同地图的崩溃数据。

## 核心功能
1. **数据采集**：接收来自客户端的崩溃日志、OS 信息、地图名与哈希、游戏版本、模块内偏移、调用栈、栈指纹、归属结论等派生字段（自动上报不上传地图或 dmp 原始文件；网页兜底上传可包含 dmp 与平台日志）。
2. **自动化分析**：服务器端二次校验崩溃地址，匹配已知知识库；客户端提供分析结果时优先采用。
3. **大数据展示**：通过 Web 界面展示崩溃高发地图、常见崩溃原因统计及实时流水，流水含版本、归属与栈指纹。
4. **聚合统计**：按「地图身份 + 栈指纹」聚合相同崩溃，记录发生次数与作者标注位。
5. **原始日志上传**：网页收集崩溃记录与 KK 平台会话日志，返回 6 位上传码；原始文件私有保存 7~15 天后自动删除。
6. **服务端入库与管理端**：网页上传的日志在服务端重新诊断并写入报告与聚合；维护者可用令牌保护的 `/admin/uploads` 查看、预览、下载与删除原始文件，操作全程审计。

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

## 原始日志上传（P2.6）
面向玩家的兜底采集入口：网页上传崩溃记录文件夹，必要时附加 KK 对战平台会话日志，返回 6 位上传码便于群里报码和后续查询。

### 页面与接口
- `GET /upload`：上传页，两个区域（崩溃记录 / KK 平台日志），支持拖拽文件夹、选择文件夹与 zip。
- `POST /api/upload`：`multipart/form-data`，字段 `crash`、`kk`（可重复），以及可选的 `crash_paths`、`kk_paths`（与文件顺序一致的 JSON 字符串数组，用于保留子目录结构）。
- `GET /api/upload/<code>`：按 6 位上传码查询派生信息，不返回原始日志、绝对路径或文件清单。
- `GET /u/<code>`：上传记录页。

### 限制与安全
- 单次请求上限 **50 MB**（`MAX_CONTENT_LENGTH` 额外预留 2 MB 协议开销），超限返回 413。
- 每类最多 **40 个文件**，单次落盘最多 120 个文件；仅接受 `.txt / .log / .dmp / .mdmp / .bin / .zip`。
- 崩溃区优先识别 `Crash.txt`、`Error.txt`、`War3Crash.txt`、`Bug.txt`（允许时间前缀，如 `2026-10-14 19.11.29 Crash.txt`）以及 `.dmp/.mdmp`；每个子目录视为一次崩溃。
- KK 区必须包含 `platform.log`、`downloader.log` 或 `war3/<pid>/war3dll.log` 之一；从日志中提取游戏版本、地图名、地图 MD5 与平台会话时间。
- KK 安装路径因用户而异，页面仅以默认目录 `C:\Program Files (x86)\kkduizhan` 举例，并提示用户从快捷方式打开实际安装位置后进入 `log`。
- zip 仅作兜底：拒绝加密包、符号链接、路径穿越、非白名单扩展名、超过 200 个条目或解压后超过 50 MB。
- 上传内容按 SHA-256 去重；相同文件重复上传返回原上传码，不重复计数。
- 每 IP 每小时默认 10 次上传、240 次上传码查询（内存限流，服务重启后清零）。

### 保留与隐私
- 原始文件默认保留 **14 天**，可通过环境变量限制在 **7~15 天**；到期后删除整个上传目录，`raw_uploads` 只保留版本、地图、偏移、诊断摘要与时间。
- 原始文件存放在 `server/uploads/<6 位码>/`，不在 Flask 静态目录内，无法通过 URL 直接访问。
- 公开接口不返回原始日志、OS 信息、Windows 用户名、计算机名或本地绝对路径。
- 上传码为 6 位数字，只用于报码与查询；不要把它当作访问凭证公开传播完整日志内容。

### 环境变量
| 变量 | 默认值 | 说明 |
|---|---|---|
| `WAR3_UPLOAD_DIR` | `server/uploads` | 原始文件根目录，需可写且不要放在 `static/` 下 |
| `WAR3_RAW_RETENTION_DAYS` | `14` | 原始文件保留天数，自动收敛到 7~15 |
| `WAR3_UPLOAD_RATE` | `10` | 每 IP 每小时上传次数上限 |
| `WAR3_UPLOAD_SALT` | 启动时随机 | IP 哈希盐；多实例部署时需固定为同一值 |
| `WAR3_ADMIN_TOKEN` | 未设置 | 管理端与管理接口令牌；未设置时管理端禁用（503） |
| `WAR3_DB_PATH` | `server/crash_data.db` | SQLite 路径，便于测试或迁移 |

### 部署注意
- 反向代理（Nginx）需把 `client_max_body_size` 调到 **55m** 以上，否则 50 MB 上传会被前置代理拦截。
- 反向代理后 `request.remote_addr` 会变成代理地址；如需按真实 IP 限流，请在代理层完成限流，或改为可信的 `X-Forwarded-For` 解析。
- KK 平台只保留最近会话日志，崩溃后应尽快上传；网页已提示用户先不要重启平台。

## 上传入库（P2.7）
上传成功的崩溃日志会在服务端复用客户端的纯 Python 模块（`core.logtext`、`core.stack_parser`、`core.environment`、`core.diagnosis`、`core.fingerprint`、`core.knowledge`）重新诊断，不再依赖浏览器传来的结论。

- 诊断流程与客户端一致：提取崩溃地址 → 解析完整调用栈 → 定位崩溃帧或首个有效帧 → 换算 `.text` RVA（逻辑地址 + 0x1000）→ 明文原因、环境分析、版本锁定与知识库查表 → 栈指纹 → 四行结论。
- 每份崩溃日志写入 `crash_reports`，新增 `upload_code` 关联上传码；`content_hash` 唯一约束保证同一日志只入库一次，重复上传只补齐空缺字段。
- 入库后按「地图身份 + 栈指纹」累加 `crash_aggregates`；重复内容触发 `rebuild_aggregates()` 重建，作者标注不受影响。
- 代表记录（优先有 RVA、其次含 dmp、再次文件更多）的诊断结果回写 `raw_uploads`，上传码查询页与自动上报展示同一口径的版本、地图、偏移、指纹与归属。
- 入库使用 SQLite `SAVEPOINT` 隔离：即使诊断或入库失败，用户仍能拿到上传码，原始文件也照常保留。
- 平台日志单独上传（无崩溃日志）不入库，只作为地图与版本线索。

## 维护者管理端（P2.7）
访问 `/admin/uploads`。管理端只面向维护者，默认关闭：未设置 `WAR3_ADMIN_TOKEN` 时所有管理接口返回 503。

```bash
# Linux / macOS
export WAR3_ADMIN_TOKEN='请换成足够长的随机字符串'

# Windows PowerShell
$env:WAR3_ADMIN_TOKEN='请换成足够长的随机字符串'
```

页面首次打开时填写令牌，保存在浏览器 `sessionStorage`，后续请求通过 `X-Admin-Token` 头发送；令牌错误返回 403。建议部署在 HTTPS 之后。

### 接口
| 方法与路径 | 说明 |
|---|---|
| `GET /api/admin/uploads` | 列表。支持 `q`（码/地图/模块/偏移/指纹/分析文本）、`version`、`attribution`、`has_kk`（0/1）、`raw`（1 可用 / 0 已删除）、`limit`（1~200，默认 50）、`offset` |
| `GET /api/admin/uploads/<code>` | 详情：上传元数据、原始文件清单、关联崩溃报告、审计记录（最近 40 条） |
| `GET /api/admin/uploads/<code>/preview?path=<相对路径>` | 文本预览，单次最多 **512 KB**，返回截断标记；dmp/bin 返回 415 |
| `GET /api/admin/uploads/<code>/file?path=<相对路径>` | 单文件下载（`Content-Disposition: attachment`） |
| `GET /api/admin/uploads/<code>/archive` | 整包 zip 下载，在内存中打包，不产生临时文件 |
| `POST /api/admin/uploads/<code>/delete` | 删除原始文件：删除上传目录并写入 `raw_deleted_at`；诊断与聚合元数据保留 |
| `POST /api/admin/uploads/<code>/reingest` | 补跑入库，用于 P2.7 之前的上传或入库失败记录；只补齐空缺字段 |

### 安全与审计
- 文件路径参数只能是上传目录内的相对路径，绝对路径、`..` 穿越与目录外软链均被拒绝。
- 原始文件已删除时，预览 / 下载 / 整包 / 补跑返回 410。
- `admin_audit` 表记录 `preview` / `download_file` / `download_archive` / `delete_raw` / `reingest`，含时间、上传码、明细与 IP 哈希（使用 `WAR3_UPLOAD_SALT`，不存明文 IP）。
- 删除只影响原始文件；`crash_reports` 与聚合统计是脱敏派生数据，会继续保留，避免历史统计被单次删除篡改。
- 管理端接口不复用公开的上传码查询逻辑，必须通过令牌校验。

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
- `crash_data.db`: SQLite 数据库（自动生成，含聚合、案例缓存与上传账单）。
- `uploads/`: 原始日志私有目录（自动生成，默认保留 14 天，已被 `.gitignore` 忽略）。
- `static/index.html`: 总览仪表盘。
- `static/author.html`: 作者查询与标注页。
- `static/upload.html`: 崩溃日志与 KK 会话日志上传页。
- `static/upload_status.html`: 上传码查询页。
- `static/admin_uploads.html`: 维护者管理端（令牌保护）。
- `static/md5.js`: 浏览器本地地图 MD5 计算。

## 客户端集成
客户端上报逻辑位于 `core/reporter.py`，上报地址为 `http://43.163.75.93:2234/api/report`（另含域名地址回退）。
