# P5.0 泄露语料与回归基线

本目录用于给「泄露定位&修复」建立可量化的行为基线。当前实现仍是正则启发式，因此语料同时记录三类事实：

1. **真实泄露**：目标语义下应该被报告的问题；
2. **误报**：注释、字符串、共享全局对象、长期对象被误判；
3. **危险修复**：销毁返回值、销毁逃逸对象、重复销毁、破坏 GUI 枚举等绝对不能发生的编辑。

## 目录

```text
tests/
  test_leak_engine.py          # unittest 回归与基线快照
  run_leak_corpus.py           # 命令行运行器
  leak_corpus/
    corpus.json                # 用例清单与预期标注
    baseline.json              # 当前实现的行为快照（会随重构更新）
    cases/*.j                  # 合成 JASS 用例
    .real_baseline/            # 真实地图基线，仅本地，已 gitignore
```

## 用例字段

| 字段 | 含义 |
| --- | --- |
| `expected_findings` | 目标语义下应报告的发现；`variable: null` 表示同函数同类型即可 |
| `must_fix_patterns` | 修复结果中必须出现的正则（仅 A 级用例使用） |
| `forbidden_fix_patterns` | 修复结果中绝不能出现的正则，命中即安全违规 |
| `destroy_checks` | 指定销毁调用的允许次数范围，用于发现漏销毁和重复销毁 |
| `expected_guarded_returns` | 每个 `return` 前都应完成清理的出口数量 |
| `level` | A 自动修复 / B 只给建议 / C 仅报告 |

所有用例都会额外检查：

- 修复器是否幂等（连续执行两次结果一致）；
- 是否出现分析异常；
- 基线快照是否与 `baseline.json` 一致。

自动修复白名单（P5.0.1 止血后）：

- 只修改点（location）、单位组（group）、新建玩家组（force）。
- 矩形、计时器、触发器、哈希表、布尔表达式只报告，不修改。
- `GetPlayersAll()` 等共享句柄、`return` 返回值、赋给全局/数组/哈希表的句柄、多出口函数一律不自动修改。
- 创建函数按完整标识符匹配，注释与字符串先掩码。

## 运行

```bash
# 人类可读报告
python tests/run_leak_corpus.py

# JSON + 严格模式（有违规时退出码 1）
python tests/run_leak_corpus.py --json --strict

# 生成/更新当前行为基线
python tests/run_leak_corpus.py --write-baseline

# 回归测试
python -m unittest tests.test_leak_engine -v
```

## 真实地图基线（可选）

真实地图脚本可能包含作者版权内容，因此运行器只输出哈希与指标，不保存脚本正文：

```bash
python tests/run_leak_corpus.py --maps "<地图目录>" --limit 10
```

结果写入 `tests/leak_corpus/.real_baseline/real_baseline.json`，该目录已加入 `.gitignore`。建议至少准备 10 张地图，覆盖纯 JASS、GUI 生成脚本、加密图和 Lua 图；Lua 图当前只应得到“拒绝写入”的结果，不参与 JASS 修复统计。

也可以用环境变量让 unittest 执行真实地图基线：

```bash
WAR3_LEAK_MAP_DIR="<地图目录>" WAR3_LEAK_MAP_LIMIT=10 python -m unittest tests.test_leak_engine -v
```

未设置 `WAR3_LEAK_MAP_DIR` 时该测试自动跳过。默认使用仓库根目录的 `MPQEditor.exe`，可用 `WAR3_MPQ_EDITOR` 指定其他路径。

## 基线维护

`baseline.json` 是当前实现的“行为快照”，不是正确性证明。P5.1+ 每次有意改变定位或修复行为时：

1. 先看 `python tests/run_leak_corpus.py` 的差异；
2. 确认变化符合目标（例如漏报减少、危险修复消失）；
3. 再执行 `--write-baseline` 更新快照；
4. 同步删除已经通过的 `expectedFailure` 装饰器。

`CurrentDefectTests` 里的断言记录的是当前仍存在的缺陷，修复后应删除或改写成目标断言，而不是长期保留。P5.0.1 止血完成后，原有多数“危险编辑”断言已改为 `ExistingCapabilityTests` 的防回退断言；仍待 P5.2 处理的是分支内销毁漏报和长期计时器误报。
