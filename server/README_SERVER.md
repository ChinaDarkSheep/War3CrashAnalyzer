# 魔兽崩溃分析后端服务 (War3 Crash Analysis Backend)

这是一个为 `War3CrashAnalyzer` 开发的配套后端服务，用于收集、存储和可视化来自不同地图的崩溃数据。

## 核心功能
1. **数据采集**：接收来自客户端的崩溃日志、OS 信息、地图名与哈希、游戏版本、模块内偏移、调用栈、栈指纹、归属结论等派生字段（自动上报不上传地图或 dmp 原始文件；网页兜底上传可包含 dmp 与平台日志）。
2. **自动化分析**：服务器端二次校验崩溃地址，匹配已知知识库；客户端提供分析结果时优先采用。
3. **大数据展示**：通过 Web 界面展示崩溃高发地图、常见崩溃原因统计及实时流水，流水含版本、归属与栈指纹。
4. **聚合统计**：按「地图身份 + 栈指纹」聚合相同崩溃，记录发生次数与作者标注位。
5. **原始日志上传**：网页收集崩溃记录与 KK 平台会话日志，返回 6 位上传码；原始文件私有保存 7~15 天后自动删除。
6. **服务端入库与管理端**：网页上传的日志在服务端重新诊断并写入报告与聚合；维护者可用令牌保护的 `/admin/uploads` 查看、预览、下载与删除原始文件，操作全程审计。
7. **案例复核与知识库合并**：`/admin/cases` 汇总作者标注形成的案例缓存，支持筛选、导出片段、试运行与批量合并进共享 `knowledge.json`；写入前自动备份，运行时立即生效。
8. **上传反馈状态**：维护者在上传详情中标记复核进度并附备注，状态随上传码公开给提交者；客户端可直接凭 6 位码查询服务端诊断与反馈。
9. **客户端下载入口**：`/download` 展示版本、网盘链接、提取码与更新说明；维护者在 `/admin/download` 随时更新，保存即生效，链接留空即下线。

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
| `map_key` / `map_hash` / `map_name` / `map_author` | 地图身份与作者 |
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
- 案例缓存只作为候选，不自动写入全局 `knowledge.json`；由维护者在 `/admin/cases` 复核后手动合并（见 P2.9），避免单张地图的个案污染全局偏移结论。
- 全量重建聚合表时会保留标注内容、来源、置信度、标注人与时间。

## 原始日志上传（P2.6）
面向玩家的兜底采集入口：网页上传崩溃记录文件夹，必要时附加 KK 对战平台会话日志，返回 6 位上传码便于群里报码和后续查询。

### 页面与接口
- `GET /upload`：上传页，两个区域（崩溃记录 / KK 平台日志），支持拖拽文件夹、选择文件夹与 zip。
- `POST /api/upload`：`multipart/form-data`，字段 `crash`、`kk`（可重复），以及可选的 `crash_paths`、`kk_paths`（与文件顺序一致的 JSON 字符串数组，用于保留子目录结构）。
- `GET /api/upload/<code>`：按 6 位上传码查询派生信息与维护者反馈（`feedback.status / label / note / updated_at`），不返回原始日志、绝对路径或文件清单。
- `GET /u/<code>`：上传记录页。

### 限制与安全
- 单次请求上限 **50 MB**（`MAX_CONTENT_LENGTH` 额外预留 2 MB 协议开销），超限返回 413。
- 每类最多 **40 个文件**，单次落盘最多 120 个文件；仅接受 `.txt / .log / .dmp / .mdmp / .bin / .zip`。
- 崩溃区优先识别 `Crash.txt`、`Error.txt`、`War3Crash.txt`、`Bug.txt`（允许时间前缀，如 `2026-10-14 19.11.29 Crash.txt`）以及 `.dmp/.mdmp`；每个子目录视为一次崩溃。
- KK 区必须包含 `platform.log`、`downloader.log` 或 `war3/<pid>/war3dll.log` 之一；从日志中提取游戏版本、地图名、地图 MD5 与平台会话时间。缺少 `md5(...)` 行时，用 `wa(661)` 地图路径里的 32 位文件名兜底推导哈希。
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
| `WAR3_ADMIN_TOKEN` | 未设置 | 管理端与管理接口令牌；未设置时管理端禁用（503），同时保护案例合并 |
| `WAR3_DB_PATH` | `server/crash_data.db` | SQLite 路径，便于测试或迁移 |
| `WAR3_KB_PATH` | 仓库根目录 `knowledge.json` | 共享知识库路径；客户端与服务端需指向同一份文件 |
| `WAR3_KB_BACKUP_DIR` | `server/knowledge_backups` | 合并前备份目录，自动保留最近 50 份 |

### 部署注意
- 反向代理（Nginx）需把 `client_max_body_size` 调到 **55m** 以上，否则 50 MB 上传会被前置代理拦截。
- 反向代理后 `request.remote_addr` 会变成代理地址；如需按真实 IP 限流，请在代理层完成限流，或改为可信的 `X-Forwarded-For` 解析。
- HTTPS 证书的 SAN 必须包含**实际访问的域名**（例如 `ca.darksheep.vip`）；只签主域名会出现证书不匹配。建议把 80 端口 301 跳转到 443，并只通过 HTTPS 使用管理令牌。
- 使用宝塔部署时，**不能把主站证书直接套到子域名站点**：证书按域名签发，`darksheep.vip` 的证书不包含 `ca.darksheep.vip`。请在子域名站点的「SSL → Let's Encrypt」重新申请并勾选该子域名（或使用含 `*.darksheep.vip` 的通配符证书），部署后再开启「强制 HTTPS」。
- KK 平台只保留最近会话日志，崩溃后应尽快上传；网页已提示用户先不要重启平台。

## 上传入库（P2.7）
上传成功的崩溃日志会在服务端复用客户端的纯 Python 模块（`core.logtext`、`core.stack_parser`、`core.environment`、`core.diagnosis`、`core.fingerprint`、`core.knowledge`）重新诊断，不再依赖浏览器传来的结论。

- 诊断流程与客户端一致：提取崩溃地址 → 解析完整调用栈 → 定位崩溃帧或首个有效帧 → 换算 `.text` RVA（逻辑地址 + 0x1000）→ 明文原因、环境分析、版本锁定与知识库查表 → 栈指纹 → 四行结论。
- 每份崩溃日志写入 `crash_reports`，新增 `upload_code` 关联上传码；`content_hash` 唯一约束保证同一日志只入库一次，重复上传只补齐空缺字段。
- 入库后按「地图身份 + 栈指纹」累加 `crash_aggregates`；重复内容触发 `rebuild_aggregates()` 重建，作者标注不受影响。
- 代表记录（优先有 RVA、其次含 dmp、再次文件更多）的诊断结果回写 `raw_uploads`，上传码查询页与自动上报展示同一口径的版本、地图、偏移、指纹与归属。
- 入库使用 SQLite `SAVEPOINT` 隔离：即使诊断或入库失败，用户仍能拿到上传码，原始文件也照常保留。
- 平台日志单独上传（无崩溃日志）不入库，只作为地图与版本线索。

### 地图名与作者（P4.1）
- **来源**：客户端根据 KK 会话的 `wa(661)` 地图路径在本地 `war3` 目录找到 `.w3x/.w3m/.w3n`，只读取 w3i 元数据里的地图名与作者，随上传以 `map_name` / `map_author` 字段提交；**地图文件本身不上传**。
- **名字优先级**：能对上的客户端地图名 > 崩溃日志 `Played Maps` 里的名字 > KK `wa(660)` 地图名。`WorldEditTestMap`、空白、`.w3x` 这类占位名视为弱值，可用平台会话的地图名覆盖。
- **版本后缀**：文件名常带 `_2.5b`、`v1.2` 这类后缀，与日志地图名比对时忽略末尾版本段，避免同一地图被拆成两条聚合。
- **哈希确认**：崩溃日志把地图写成 `038E7600D124B6CD3057B683257B738C.w3x` 时，该 32 位文件名就是地图 MD5。只有它与 KK 会话哈希一致，才采用客户端读到的地图名与作者；哈希不一致时保留崩溃日志里的 MD5 名，不强行套用会话地图。
- **哈希落库**：地图名本身是 32 位 MD5 时，即使没有 KK 会话也会写入 `map_hash`，便于后续与其他记录聚合。
- **重复上传补全**：相同日志再次上传并附带地图元数据时，会补写 `raw_uploads`、`crash_reports` 与 `crash_aggregates` 的 `map_name` / `map_author`，已有作者不覆盖。管理端“补跑入库”会复用 `summary.map_meta`。
- **隐私**：作者字段一旦包含 `/` 或 `\` 直接判为无效，避免把本地路径截成“作者名”；公开接口的 `module` 只保留 DLL 文件名，`analysis` 中的 Windows 绝对路径替换为文件名。

## 维护者管理端（P2.7）
访问 `/admin/uploads`。管理端只面向维护者，默认关闭：未设置 `WAR3_ADMIN_TOKEN` 时所有管理接口返回 503。

```bash
# Linux / macOS
export WAR3_ADMIN_TOKEN='请换成足够长的随机字符串'

# Windows PowerShell
$env:WAR3_ADMIN_TOKEN='请换成足够长的随机字符串'
```

页面首次打开时填写令牌，保存在浏览器 `sessionStorage`，后续请求通过 `X-Admin-Token` 头发送；令牌错误返回 403。建议部署在 HTTPS 之后。

令牌按启动方式（systemd / Docker / 手动运行）设置的完整步骤、验证与轮换见文末「[部署与令牌配置](#部署与令牌配置war3_admin_token)」。

### 接口
| 方法与路径 | 说明 |
|---|---|
| `GET /api/admin/uploads` | 列表。支持 `q`（码/地图/模块/偏移/指纹/分析文本）、`version`、`attribution`、`has_kk`（0/1）、`raw`（1 可用 / 0 已删除）、`feedback`（`pending / reviewing / resolved / need_info`）、`limit`（1~200，默认 50）、`offset` |
| `GET /api/admin/uploads/<code>` | 详情：上传元数据、原始文件清单、关联崩溃报告、审计记录（最近 40 条） |
| `GET /api/admin/uploads/<code>/preview?path=<相对路径>` | 文本预览，单次最多 **512 KB**，返回截断标记；dmp/bin 返回 415 |
| `GET /api/admin/uploads/<code>/file?path=<相对路径>` | 单文件下载（`Content-Disposition: attachment`） |
| `GET /api/admin/uploads/<code>/archive` | 整包 zip 下载，在内存中打包，不产生临时文件 |
| `POST /api/admin/uploads/<code>/delete` | 删除原始文件：删除上传目录并写入 `raw_deleted_at`；诊断与聚合元数据保留 |
| `POST /api/admin/uploads/<code>/reingest` | 补跑入库，用于 P2.7 之前的上传或入库失败记录；只补齐空缺字段 |
| `POST /api/admin/uploads/<code>/feedback` | 写入维护者反馈。JSON 体 `{"status": "pending\|reviewing\|resolved\|need_info", "note": "可选，≤500 字"}`；状态会公开给提交者 |

### 安全与审计
- 文件路径参数只能是上传目录内的相对路径，绝对路径、`..` 穿越与目录外软链均被拒绝。
- 原始文件已删除时，预览 / 下载 / 整包 / 补跑返回 410。
- `admin_audit` 表记录 `preview` / `download_file` / `download_archive` / `delete_raw` / `reingest` / `feedback`，含时间、上传码、明细与 IP 哈希（使用 `WAR3_UPLOAD_SALT`，不存明文 IP）。
- 删除只影响原始文件；`crash_reports` 与聚合统计是脱敏派生数据，会继续保留，避免历史统计被单次删除篡改。
- 管理端接口不复用公开的上传码查询逻辑，必须通过令牌校验。

## 案例复核与知识库合并（P2.9）
作者标注写入的 `knowledge_cases` 只是候选，本功能让维护者在网页上完成「筛选 → 核对 → 合并」的闭环，把确认过的案例落到共享 `knowledge.json`，客户端与服务端同时受益。

### 页面与接口
访问 `/admin/cases`（入口在 `/admin/uploads` 顶部导航），与上传管理端共用 `WAR3_ADMIN_TOKEN`，请求头 `X-Admin-Token`；未配置令牌返回 503，令牌错误 403。

| 方法与路径 | 说明 |
|---|---|
| `GET /api/admin/cases` | 列表。支持 `map_hash`、`map`、`fingerprint`、`module`、`version`、`source`、`merged`（0/1）、`q`（根因/地图/指纹/标注人）、`limit`（1~200）、`offset`；每条附 `merge` 预览（目标地址、是否冲突、已有条目、不可合并原因） |
| `GET /api/admin/cases/<signature>/export` | 导出单条案例为可直接并入 `knowledge.json` 的片段，`Content-Disposition: attachment` |
| `POST /api/admin/cases/merge` | 批量合并。JSON 体 `{"signatures": ["..."], "overwrite": false, "dry_run": false}`；返回逐条状态（`merged` / `preview` / `conflict` / `invalid` / `not_found` / `error`）与计数 |

### 合并口径
- **目标地址**：`modules[模块][归一化版本][0x + 8 位大写偏移]`；版本会归一化（如 `1.27.0.52240 → 1.27a`），偏移会补零与转大写。缺模块、缺版本、偏移无效或根因为空时不会写入，列表直接给出原因。
- **冲突**：知识库已存在同地址条目时默认跳过（状态 `conflict`）；勾选「允许覆盖」后写入，更新 `desc / source / confidence / verified`，保留原条目的 `attribution / suggestion / apis` 等附加线索。
- **来源与验证**：条目 `source` 记为 `case/<12 位签名>`；来源为「作者确认」或「维护者确认」时 `verified=true`，已有 `verified=true` 的条目覆盖后也不会降级。
- **导出**：导出的片段与合并使用同一套归一化与条目构造逻辑，便于离线审阅或手工并入。
- **案例标记**：合并成功的案例写入 `merged_at / merged_key`，列表中显示「已合并」；重复合并同一地址时仍按冲突规则处理。

### 安全与生效
- 每次实际写入前把当前 `knowledge.json` 复制到 `server/knowledge_backups/`（保留最近 50 份），再通过临时文件 + `os.replace` 原子替换，避免写坏原文件。
- 进程内用锁串行化并发合并；`dry_run` 只计算不落盘。
- 写入成功后立即热更新 `settings.KB`、`settings.BUILD_PREFIXES` 与 `core.knowledge` 缓存，服务端诊断无需重启即可命中新条目；客户端需更新随包分发的 `knowledge.json` 后生效。
- 导出与合并均写入 `admin_audit`（`export_case` / `merge_case`，含签名、目标地址与 IP 哈希），便于回溯是谁合并了什么。

## 上传反馈状态（P2.11）
上传码原本只能看到服务端诊断，提交者不知道维护者是否收到、是否需要补充材料。P2.11 在 `raw_uploads` 上增加反馈字段，并同时开放给网页状态页与客户端查询。

### 数据与接口
- `raw_uploads` 自动补 `feedback_status TEXT DEFAULT 'pending'`、`feedback_note TEXT`、`feedback_at DATETIME`；旧记录缺省视为 `pending`。
- 状态固定为四种：`pending` 待处理、`reviewing` 复核中、`resolved` 已处理、`need_info` 需补充材料。
- `POST /api/admin/uploads/<code>/feedback`：令牌保护；状态必须命中枚举，备注最长 500 字（超出返回 400）；成功后写入时间并记 `feedback` 审计。
- `GET /api/admin/uploads` 支持 `feedback` 筛选；公开的 `GET /api/upload/<code>` 返回 `feedback: {status, label, note, updated_at}`。
- 公开反馈只含维护者主动填写的状态与备注，不包含原始日志、文件清单、OS 信息、用户名或本地路径。

### 界面
- `/admin/uploads` 增加反馈筛选、列表反馈徽章；详情顶部提供状态下拉、备注输入与保存按钮，保存后刷新详情与列表。
- `/u/<code>` 在元数据上方展示反馈状态、更新时间和备注；未反馈时显示「维护者尚未更新」。
- 客户端新增「发送给维护者 → 查询上传码状态」对话框：自动填入上次上传码，显示版本/地图/崩溃位置/归属/置信度/服务端诊断与反馈；查询走 `core/uploader.query_upload`，沿用上传地址的域名与 IP 回退。

**验证**：临时 DB + 本地 HTTP 服务跑 19 项断言，覆盖未配置令牌 503、错误令牌 403、非法状态与超长备注 400、旧记录 NULL 视为待处理、反馈写入与公开回显、列表筛选、详情返回与客户端 `query_upload`（含 URL 推导与非法上传码拒绝）；两处内联 JavaScript 通过 `new Function` 语法校验；浏览器实测管理端反馈筛选、详情保存与公开状态页回显；Tk 冒烟渲染「需补充材料」反馈并截图核对布局。

## 客户端下载入口（P2.12）
公开页 `/download` 为玩家提供客户端下载入口；维护者在 `/admin/download` 更新网盘链接，保存即生效，无需重启服务。

### 数据与接口
- 新增单行表 `client_download(id=1, version, url, extract_code, note, updated_at)`，启动时自动创建并插入 `id=1` 空行。
- `GET /api/download`：公开，仅返回 `configured / version / url / extract_code / note / updated_at`；未配置时 `configured=false`。
- `GET /api/admin/download`：令牌保护，返回当前配置。
- `POST /api/admin/download`：令牌保护。JSON 体 `{"version": "...", "url": "https://...", "extract_code": "...", "note": "..."}`；链接只接受 http/https，版本 ≤40、链接 ≤2000、提取码 ≤32、说明 ≤2000 字符，超限或非法链接返回 400。链接留空表示下线入口并清空其余字段；每次保存写入 `download_update` 审计。

### 页面
- `/download`：展示版本、更新时间、网盘按钮（`target="_blank" rel="noopener noreferrer"`）、提取码复制、更新说明、使用步骤与隐私说明；未配置或接口失败时给出明确空状态。
- `/admin/download`：令牌门禁（与其他管理页共用 `WAR3_ADMIN_TOKEN`），表单编辑版本/链接/提取码/说明，同时展示当前生效配置，支持恢复当前值与下线入口；保存成功后提示「公开页刷新后立即生效」。
- 导航：总览、上传、上传码状态、作者页增加「下载客户端」；上传管理、案例复核增加「下载入口」。

**验证**：临时 DB 跑公开/管理接口断言，覆盖初始未配置、保存生效、公开回显、非法链接 400、下线清空、未带令牌 403、审计写入；浏览器实测后台填写保存、公开页版本/提取码/说明展示、复制按钮与下线流程；两个页面内联 JavaScript 通过 `new Function` 语法校验。

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

## 部署与令牌配置（WAR3_ADMIN_TOKEN）

管理端令牌**不是**写在 `config.json` 或 `.env` 里，服务端也没有读取配置文件的逻辑：`server/settings.py` 在启动时从**进程环境变量**读取 `WAR3_ADMIN_TOKEN`，管理蓝图在加载时就固定了这个值。**不需要修改任何 Python 代码**，也不是在网页里设置。

可以把它理解为：启动服务时额外告诉进程一个密码。因此：

- 令牌必须设置在**真正启动 `server/app.py` 的那个进程**的环境里；
- 设置或修改后必须**重启服务**才生效；
- 未设置时 `/admin/*` 与管理接口返回 `503 admin_disabled`；设置后未带令牌或令牌错误返回 `403`。

### 1. 生成令牌

Linux 与 Windows 通用：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

输出约 43 个字符，直接整段使用；不要用弱口令、不要复用其他站点密码。

### 2. 按启动方式设置

**A. systemd（推荐）**

在 service 文件中加 `Environment=`，或改用权限为 `600` 的环境文件：

```ini
[Service]
WorkingDirectory=/opt/War3CrashAnalyzer
# 方式一：直接写进 unit（unit 文件本身应限制为 root 可读）
Environment=WAR3_ADMIN_TOKEN=把生成的令牌粘贴到这里
# 方式二：单独的环境文件，内容为 WAR3_ADMIN_TOKEN=...，并 chmod 600
# EnvironmentFile=/etc/war3-ca.env
ExecStart=/usr/bin/python3 /opt/War3CrashAnalyzer/server/app.py
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart war3-ca
# 可选：确认进程环境里已有该变量
sudo systemctl show war3-ca -p Environment
```

**B. Docker / docker-compose**

```bash
docker run -e WAR3_ADMIN_TOKEN='令牌' ...
# 或
docker run --env-file /etc/war3-ca.env ...
```

compose 使用 `environment:` 或 `env_file:`，修改后 `docker compose up -d` 重建容器。

**C. 手动 nohup / screen / tmux（临时验证）**

最省事的是把变量直接写在启动命令前面，不需要先 `export`：

```bash
cd /www/wwwroot/你的站点目录          # 项目根目录，能看到 server/app.py
WAR3_ADMIN_TOKEN='令牌' nohup python3 server/app.py > server.log 2>&1 &
```

等价写法：

```bash
export WAR3_ADMIN_TOKEN='令牌'
nohup python server/app.py > server.log 2>&1 &
```

变量只在当前命令 / 当前 shell 及其子进程有效；重启进程后需重新带上。如果服务已在运行，先停掉旧进程再带变量启动：

```bash
ps -ef | grep server/app.py
kill <PID>
```

宝塔终端里如果 `python3` 找不到，用 `which python3` 或换成宝塔 Python 项目管理器对应的解释器路径。

**D. Windows PowerShell**

```powershell
$env:WAR3_ADMIN_TOKEN='令牌'
python server\app.py
```

仅对当前窗口生效。需要永久生效用 `setx WAR3_ADMIN_TOKEN "令牌"`，之后**新开**终端启动服务（`setx` 不影响已打开的窗口）。

**E. 宝塔 Python 项目管理器**

新版面板的项目设置里直接有环境变量，优先用面板，不需要动任何 Python 代码：

1. 进入项目设置，找到「环境变量」，从「无」切换为「**指定变量**」。
2. 添加一行：变量名 `WAR3_ADMIN_TOKEN`，值为生成的令牌。
3. 保存设置，然后点项目**重启**。
4. 按上面的方法用 `curl` 验证返回 `403`。

> 也可以选「从文件加载」，但需要在服务器上额外维护环境变量文件；只有一两个变量时「指定变量」最简单。

如果面板没有环境变量选项，则改面板生成的启动脚本：宝塔 → 文件 → `/etc/init.d/<项目名>_pymanager`，在注释后加 `export WAR3_ADMIN_TOKEN='令牌'`，保存后在面板重启项目（或在终端执行 `/etc/init.d/<项目名>_pymanager restart`）。

如果项目是 uWSGI 启动，也可以在项目根目录 `uwsgi.ini` 的 `[uwsgi]` 段加：

```ini
env = WAR3_ADMIN_TOKEN=令牌
```

Gunicorn 启动则在 `gunicorn.conf.py` 加 `raw_env = ["WAR3_ADMIN_TOKEN=令牌"]`。

注意：面板升级或重新保存项目配置时可能重新生成启动脚本或配置文件，升级后如管理端又变回 503，回到项目设置的「环境变量」检查这一项是否还在。

### 3. 验证是否生效

```bash
# 不带令牌：已生效应返回 403；仍返回 503 说明变量没被进程读到
curl -s -o /dev/null -w "%{http_code}\n" https://ca.darksheep.vip/api/admin/download

# 带正确令牌：应返回 200
curl -s -H "X-Admin-Token: 你的令牌" https://ca.darksheep.vip/api/admin/download
```

浏览器打开 `/admin/download` 或 `/admin/uploads`，在令牌框输入后点「进入管理」。令牌只存在当前标签页的 `sessionStorage`，关闭标签即失效，不会写入服务端数据库。

### 4. 安全与轮换

- **只在 HTTPS 下启用**：令牌通过请求头传输，纯 HTTP 会被中间人直接截获。
- 不要把令牌提交进仓库、写进前端代码、发到群里或截图；环境文件权限设为 `600`。
- 令牌比对使用 `hmac.compare_digest`，服务端不保存明文之外的任何副本。
- 轮换：修改环境变量 → 重启服务 → 在管理页点「清除令牌」后重新输入即可；旧令牌立即失效。
- 忘记令牌无法找回，只能重新生成并重启（这是有意的设计，避免任何后门式恢复）。

## 目录结构
- `app.py`: 服务入口，创建应用、注册蓝图并执行建库/聚合重建/到期清理（默认监听 2234 端口）。
- `settings.py`: 路径、环境变量、上传限制与共享知识库加载。
- `common.py`: 版本/偏移归一化、上报字段校验与聚合签名。
- `db.py`: SQLite 建表/迁移、聚合累加与全量重建。
- `legacy_report.py`: 旧版 `/api/report` 的日志解析与知识库查表。
- `upload_store.py`: 上传落盘、zip 安全校验、崩溃区/KK 区解析、限流与到期清理。
- `diagnosis.py`: 服务端诊断（复用 `core/`）与上传日志入库。
- `knowledge_merge.py`: 案例 → 知识库的预览、冲突判定、导出、备份、原子写入与缓存热更新。
- `download_store.py`: 客户端下载配置的单行表读写、链接与长度校验。
- `blueprints/`: 路由蓝图（`pages` / `uploads` / `admin` / `reports` / `aggregates` / `cases` / `downloads`）。
- `crash_data.db`: SQLite 数据库（自动生成，含聚合、案例缓存与上传账单）。
- `knowledge_backups/`: 合并知识库前的自动备份（自动生成，保留 50 份，已被 `.gitignore` 忽略）。
- `uploads/`: 原始日志私有目录（自动生成，默认保留 14 天，已被 `.gitignore` 忽略）。
- `static/index.html`: 总览仪表盘。
- `static/author.html`: 作者查询与标注页。
- `static/upload.html`: 崩溃日志与 KK 会话日志上传页。
- `static/upload_status.html`: 上传码查询页。
- `static/download.html`: 客户端下载页（版本、网盘链接、提取码与说明）。
- `static/admin_uploads.html`: 维护者上传管理端（令牌保护）。
- `static/admin_cases.html`: 案例复核与知识库合并页（令牌保护）。
- `static/admin_download.html`: 下载入口管理页（令牌保护）。
- `static/md5.js`: 浏览器本地地图 MD5 计算。

## 客户端集成
客户端上报逻辑位于 `core/reporter.py`，上报地址为 `http://43.163.75.93:2234/api/report`（另含域名地址回退）。

客户端一键上传逻辑位于 `core/uploader.py`，界面入口为「静态审计 → 发送给维护者 → 上传日志并获取上传码」和托盘菜单「上传最近崩溃日志」。它自动选取最新一份崩溃日志与同名 dmp，可选附加 KK 最近一次会话日志，复用本服务的 `POST /api/upload`，上传前展示清单与隐私说明，成功后回显并复制 6 位上传码；不会上传地图文件。

「发送给维护者 → 查询上传码状态」打开 `gui/upload_status_dialog.py`，自动填入上次上传成功的上传码；`core/uploader.query_upload()` 从上传地址推导 `GET /api/upload/<code>`，同样支持域名与 IP 地址回退，展示服务端诊断与维护者反馈，不下载原始日志。
