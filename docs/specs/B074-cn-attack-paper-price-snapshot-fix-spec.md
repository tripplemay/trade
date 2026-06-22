# B074 — cn_attack A股 模拟盘建仓修复（A股价同步进 price_snapshot）Spec

**批次定位：** 生产缺陷修复（hotfix，研究态 paper 前向模拟）。两个 A股 进攻模拟盘（cn_attack_quality_momentum / cn_attack_pure_momentum）**激活后从未建仓、全现金、build_complete=0**——根因=**它们的 A股 目标持仓在 paper 价格源 `price_snapshot` 里无 mark**（§17.1 两价格存储分裂）。修=方案 A：把 cn_attack A股 universe 的收盘从统一 CSV 同步进 price_snapshot,让 paper 能估价建仓。

**来源：** 2026-06-22 用户报「两个 A股 模拟盘没建仓」→ planner VM 生产 DB 诊断（铁律 9）→ 根因确认 → 用户确认方案 A 立批。

---

## 0. 根因（planner VM 实测,焊死）

- 两 cn_attack paper 账户:**已激活(2026-06-18)、有有效目标(各 25 A股 名)、有 target_key,但 cash=初始 100000(全现金)、last_rebalanced=空、build_complete=0**（建仓 build 从没跑成）。
- `price_snapshot`(paper 建仓/MTM 经 `DbPriceProvider` 读的价格源)**0 个 A股**——只有美股+hk_china proxy ETF。**交叉核对:25 目标 0 可估价。**
- A股 价格**确在统一 CSV `prices_daily.csv`**（data_refresh 写了 40 个 .SH/.SZ,cn_attack 目标全在内）——**只是从没进 price_snapshot**。
- 机制:`prices/cli.py`(workbench-prices.timer)用 **Tiingo(美股-only)** 填 price_snapshot,符号集=持仓 ∪ `price_universe()=ETF_UNIVERSE∪equity_universe()`（全美股/proxy,不含 A股）→ A股 既不在 universe、Tiingo 也取不了 → 0 A股 进 price_snapshot → paper 估不了 A股 → 建不了仓。
- **Master/regime paper 没事**:目标是美股/proxy ETF,price_snapshot 有。**这是 §17.1 + B058 F002(regime ETF 同款:price_snapshot 缺目标→paper 搁浅现金)的又一实例。**

---

## 1. 复用清单（已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| price_snapshot 填充 CLI | `prices/cli.py`（Tiingo `_build_loader` + 持仓∪`price_universe()` + `uncovered_targets` 检查 L27,B058 F002 同款机制）| 加 A股 CSV→snapshot 同步路径 |
| price_universe | `data_refresh/refresh.py:187 price_universe()=ETF∪equity_universe`（美股/proxy）| 扩含 cn_attack A股 universe |
| 统一 CSV（有 A股 价）| `data/snapshots/prices/unified/prices_daily.csv`（data_refresh 写,40 A股）+ `data_root.unified_prices_path` | A股 价源（非 Tiingo）|
| cn_attack A股 universe | `data_refresh/cn_universe.py CN_UNIVERSE_SEED`（seed-43）+ cn_pit_universe | 要覆盖的 A股 集 |
| paper mark | `paper/mtm.py`（`DbPriceProvider` L62 + `marks_for` L78 读 price_snapshot；rebalance-if-due+build）| 修后能 mark A股→build |
| PriceSnapshotRepository | `db/repositories/price_snapshot.py`（idempotent (symbol,obs_date)）| A股 行写入 |
| acceptance 层（B071-B073）| `tests/acceptance/` + golden | 加「paper 目标可估价」永久守门 |

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — A股 价从统一 CSV 同步进 price_snapshot（cn_attack universe 可估价）（executor: generator）

1. **A股 价源=统一 CSV（非 Tiingo）**：A股 收盘从 `prices_daily.csv`（data_refresh 已写,akshare 来）读 → 写 price_snapshot（`PriceSnapshotRepository`,idempotent）。**不给 prices/cli 加 akshare**（保持其 read-only Tiingo + 新增 CSV→snapshot 同步步骤,或在 data_refresh/prices-cli 适当层做）。
2. **覆盖 cn_attack A股 universe**：price_snapshot 须覆盖 cn_attack 可 target 的 A股 universe（seed-43 / cn_pit_universe 成员），使两变体的 25 目标全可估价。扩 `price_universe()` 或同步路径含之。
3. **§17.1 对齐**：paper mark 源（price_snapshot）与 A股 数据源（统一 CSV）同源核验;`uncovered_targets` 对 cn_attack 目标应为空。
4. 边界：research-safe；A股 价来自既有 CSV（无新 fetch）；US/Master/regime price_snapshot 行零回归。

**Acceptance：** price_snapshot 含 cn_attack 25 A股 目标的 mark（从 CSV 同步,可估价）;US/Master/regime price_snapshot 不破;§12.10.2 守门。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — paper 建仓路径确认 + acceptance 守门（复用测试基建，永不复发）（executor: generator）

1. **acceptance 守门（B071-B073 层）**：永久回归断言 **「每个 active paper 账户的目标持仓在其价格源 price_snapshot 里都可估价（uncovered=空）」**——此 bug 类（目标无 mark→搁浅现金）以后 CI 抓。用 golden/测试 fixture。
2. **建仓触发**：确认价就位后,paper MTM 的 rebalance-if-due/build 路径会让 build_complete=0 的 cn_attack 账户**初始建仓**（B058 finish-only 重试机制）;若需显式触发路径,补之。
3. 单测:cn_attack paper 账户有价时 build 完成（持仓非空、cash 减少、build_complete=1）。

**Acceptance：** acceptance 守门「paper 目标可估价」永久回归（故意制造无 mark 目标→红=有牙齿）;cn_attack paper 有价时 build 完成单测过。Gates 同 F001 + acceptance CI step。

### F003 — Codex L2 真机验收 + signoff（executor: codex）

**真机/真数据批次——signoff 含实测证据（§29）：**
- L1 全门禁（verifying 可跳 L1 复跑,B071 §30）。
- **L2 真机（VM 生产 DB,贴真返回）：** ① prices-cli/同步真跑 → price_snapshot 含 cn_attack 25 A股 目标 mark;② paper MTM 真跑 → **两 cn_attack 模拟盘 build_complete=1 + 持仓非空 + cash≈0**（贴建仓后持仓 + nav）= **建仓成功**;③ acceptance 守门绿;④ Master/regime/US paper **零回归**（仍建仓/MTM 正常）。
- 边界:research-only/no-broker/no 真金;HEAD≡prod;recent-errors=0。signoff 实测证据逐条（贴两账户建仓前后对比）。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**:① US/Master/regime paper + price_snapshot 美股/proxy 行零回归;② research-safe / no-broker / no 真金（paper 前向模拟）;③ A股 价来自既有统一 CSV（无新 fetch、无 Tiingo 改动）;④ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑤ §17.1 paper mark 源与 A股 数据源同源（uncovered 空）。
- **诚实边界**:修的是「模拟盘能建仓」,不改 cn_attack 策略本身（仍研究态、OOS 红卡续挂、edge 微弱不可配资）;建仓只让用户看到 A股 进攻的前向模拟。
- **运维**:修复部署后需 prices-cli + paper-mtm timer 各跑一轮（或 F003 真机触发）让两账户建仓。
