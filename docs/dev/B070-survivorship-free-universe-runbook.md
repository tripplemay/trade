# B070 F002 — survivorship-free PIT 宇宙构建 runbook（真建证据）

**批次：** B070（A股 进攻策略 去幸存者偏差重验）F002。
**结论：** 去偏宇宙**真建成功**——基于 F001 GO 的 baostock dated 成分，建出 **29 个季度调仓 × 800 名真实 PIT 成分**（HS300∪ZZ500∪SZ50），**含已退市名**，并经 `trade.data.cn_attack_universe.load_cn_universe` **零改动读取**（与 cn_attack 策略 loader 集成通过）。同时建**current 成分对照宇宙**，使 F003 能隔离幸存者偏差为**单一变量**（用户 2026-06-19 裁定口径）。

> **gated / 研究态：** 写研究 data root（`data/research/b070/`，gitignored），**不动**生产 `/var/lib/workbench/data`；B067 live advisory 读 seed-43 宇宙**字节级不变**。生产 `cn_universe.py` 仅更新被证伪的 docstring（注释，无行为变更）。

---

## 1. 产物与命令

| 产物 | 路径（研究 root，gitignored）| 内容 |
|---|---|---|
| 去偏宇宙（survivorship-FREE）| `snapshots/universe/cn_pit_universe.csv` | 每调仓日真实 PIT 成分（含当时在册的已退市名）|
| 对照宇宙（survivorship-BIASED）| `snapshots/universe/cn_pit_universe_current_control.csv` | 今日成分套回所有历史调仓日（仅幸存者）|
| 价格（含退市名）| `snapshots/prices/unified/prices_daily.csv` | F003 回测读价（含 `tradestatus` 列供 §28 停牌剔除）|

```bash
# 建宇宙(成分,~3min,本机 .venv 即可,baostock 自有 host 可达)
.venv/bin/python scripts/research/b070_build_survivorship_free_universe.py \
    --out-dir data/research/b070 --from-date 2019-01-01 \
    --out-json data/research/b070/f002_universe_build.json

# 拉价格(含退市名;全量 ~1900 名 3-4h = F003/VM 跑;本机 sample 验脚本)
.venv/bin/python scripts/research/b070_fetch_survivorship_free_prices.py \
    --out-dir data/research/b070 --limit 0   # limit>0 = 抽样
```

代码：纯逻辑 + §5 守门 `scripts/research/b070_survivorship_free.py`（单测 `tests/unit/test_b070_survivorship_free.py` 19 例）；驱动脚本 build / fetch 各一。仅 baostock，无 broker。

---

## 2. 真建证据（本机实跑 2026-06-19，from 2019-01-01）

- **29 个季度调仓**（2019-03-31 → 2026-03-31），**每期 800 名** PIT 成分（HS300∪ZZ500∪SZ50 去重；SZ50⊂HS300）。
- **union ever = 1310** distinct 名，current = 800 → **non-current = 536**（轮出+退市）。
- **★幸存者偏差信号（non-current 占比，越往前越大）：**

| 调仓日 | 成员 | non-current 占比（轮出+退市）|
|---|---|---|
| 2019-03-31 | 800 | **46.5%** |
| 2022-09-30 | 800 | 31.3% |
| 2026-03-31 | 800 | 5.6% |

- **退市子集（诚实拆分，F001 §5 verify-lens 纪律）：** non-current 抽样 80 名经 `query_stock_basic` 核 status/outDate → **10 名确证退市（12.5%）**，与 F001 verify-lens 独立估计 ~12% 吻合。例：小天鹅A(000418.SZ, 2019-06 被美的吸并)、*ST泛海(2024)、ST阳光城(2023)、*ST中天、ST美置… = **B068 current-only 宇宙系统性缺席的输家**。
  > non-current 大头是「仍上市、轮出指数」；**真退市 ≈ non-current × 12.5%**（2019 期 ≈ 0.465×0.125 ≈ **6% 的宇宙是退市名**）。F003 量化幸存者偏差只能归因到这个退市子集，**不得**归因整个 non-current。

- **★集成证据（网络无关，trade loader 真读）：** `load_cn_universe(2019-06-15)` → 800 PIT 成员（点位正确，取 ≤ 该日最近块 2019-03-31）；`load_cn_universe_history` → 29 块全读出；**小天鹅A `000418.SZ`（2019-06 退市）∈ 2019-03-31 宇宙 = True** → cn_attack 策略现在**真能看见并持有**这些退市输家。
- **价格脚本验证（sample 60 名，2018-01→今）：** 60/60 priced、**119,671 行**，schema `date,ticker,open,high,low,close,adj_close,volume,tradestatus` 正确（adj_close=qfq close）。该 60 名为排序靠前的活跃大盘 → 停牌仅 1.24%；**退市名停牌远更高**（F001 实测 乐视 29.6%/康得 26.5%）→ F003 据 `tradestatus`/volume 剔停牌。全量 ~1310 名 3-4h = F003/VM 跑。

> 注：sample 取排序前 60（`000xxx` 活跃名），未含退市名轨迹——退市名价格可达性 F001 Gate B 已定证（乐视 17.89→1.69 右删失到 outDate，4/4）；F002 此处验的是**脚本格式 + 单 session 批量**，不重复 F001。

---

## 3. §5 硬约束落实（F001 verify-lens 高优）

| # | 约束 | 落实 |
|---|---|---|
| ③ | MCAP-RANK GAP（退市名无免费 mcap，别 mcap top-N）| **用指数成分直接当宇宙，不按 mcap 重排**；CSV 的 rank/market_cap/score 仅占位（策略用自有动量+质量重排，`load_cn_universe` 只取 ticker）|
| ④ | 瞬时空返回 err0 → 重试 | `DatedConstituentLoader` 拉取后 `within_expected_band` 断言（==300/500/50 ±10%），空/短**退避重试**，耗尽抛 `TransientConstituentError`，**绝不**写空/短块（单测焊死）|
| ⑤ | 持一 session + 缓存 | build/fetch 全程**单次 login**；成分按 (index, date) 记忆化 |
| ② | CEILING（仅指数band去偏）| 仅 HS300/ZZ500/SZ50（baostock 无 zz1000/zz800）→ **大/中盘band内**去偏，退市微小盘仍缺席=残余偏差（比 B068 小，非零）；report 显式标 |
| ① | STOP-BIAS（停牌）| 价格 CSV 带 `tradestatus` 列 + volume → F003 据此剔停牌（信号+成交），退市价记出场 |
| ⑥ | 证伪 docstring | `cn_universe.py:31-44` docstring 据实更新（baostock 免费使能，去偏宇宙=gated 研究产物）|

**对照口径（用户裁定）：** F003 回测 **PIT 去偏宇宙 vs current 对照宇宙**——两者都是指数成分口径、成员数同（800/期），唯一差 = 是否含历史退市/轮出名 → 差值=**纯幸存者偏差**（composition 恒定，非混入口径差）。

---

## 4. 零回归 / 不变量

- **生产零回归：** 去偏宇宙写研究 root，生产 daily refresh / B067 advisory / seed-43 宇宙**未触**；`cn_universe.py` 仅 docstring 改（无行为/字节变更）。US/B066/B068/Master 不破。
- **research-only / no-broker：** 仅 baostock；无下单、无 live 配资。
- **诚实边界续挂：** 仅消除幸存者偏差（且仅指数band）；2024Q4 顺风高估不在本批；去偏后正收益≠可配资，仍研究态。
