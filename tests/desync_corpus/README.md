# P6 异步风险合成语料

用于验证 `core/desync_risk.py` 的规则命中与误报控制。所有用例都是合成脚本，不含真实地图内容。

## 规则

| 规则 | 级别 | 语义 |
| --- | --- | --- |
| D1 | 高 | 本地分支内创建/销毁句柄或修改同步状态 |
| D2 | 高 | 本地分支内执行 `ForGroup` / `ForForce` 枚举 |
| D3 | 高 | 本地分支内取随机数 |
| D4 | 中 | 本地分支写全局变量，且分支外仍读取该变量 |
| D5 | 低 | 相机/鼠标/选中单位等本地输入参与分支条件 |
| L1 | 中 | Lua `pairs` / `next` 遍历 |
| L2 | 高 | Lua `math.random` / `math.randomseed` |
| L3 | 低 | Lua `os.time` / `os.clock` / `os.date` |
| L4 | 低 | Lua `GetLocalPlayer` |

## 标注

`corpus.json` 中每个用例包含：

- `expect`：必须命中的 `(规则, 函数, 行号)`；
- `absent_rules`：同一用例中不应出现的规则。

`jass_visual_safe.j` 与 `lua_safe.lua` 用来固定误报边界：本地纯视觉操作、注释、字符串和长字符串都不应报告。

## 运行

```bash
python -m unittest tests.test_desync_risk -v
```

真实地图精度报告只记录哈希与指标，不保存脚本正文，运行方式见项目路线文档 P6 章节。
