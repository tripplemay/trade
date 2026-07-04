# B080 — 策略生命周期监控 + 试验登记簿 + 冻结式再验证 — 验收签收报告（F005）

**批次：** B080-strategy-lifecycle-monitoring（混合批次 4 generator + 1 codex）
**验收人：** 独立 Evaluator（代 Codex，用户 /goal 授权；铁律 4 实质独立——无实现上下文，一切以仓库现状 + 真机为准）
**日期：** 2026-07-04
**阶段：** verifying(r1) → fixing → reverifying(r2) → **done**
**结论：✅ PASS**（r1 发现 1 BLOCKING，generator 治本修复，r2 生产实测闭环；其余全 PASS）

---

## 0. 裁定摘要

**PASS。** B080（策略生命周期监控 L0+L1：trial_registry + 监控指标 + 冻结再验证 + paper 三口径 + /monitoring 面板）经两轮独立 L2 真机验收通过：

- **r1（首轮，2026-07-04）** 实跑了前轮 signoff（提交 `8507e32`，因无 VM 密钥把全部 L2 真机检查显式 defer）盲区里的真机检查，发现 **1 项实质阻断**：F001 的 trial_registry 历史回填（27 条）在生产为 0 行——回填只走手动 `workbench-bootstrap` CLI、不在自动部署链，无调度器自愈。
- **r2（复验，2026-07-04）** generator 走**治本路线**（data-migration 0033，与红卡迁移 0028 同款随 alembic 自动落地）。生产实测：**trial_registry = 27 行**，抽 3 条对 signoff 原文**逐字一致**，迁移幂等，HEAD≡prod。BLOCKING 闭环。
- 其余 8 项 r1 已 PASS（HEAD≡prod / 两 timer 装载带显式 TimeoutStartSec / 红卡 DB 化生产零回归 / paper 三口径 / signal_scores 前向积累 / no-validated→True 三重守门 / no-execution / L1），修复面（仅迁移 + bootstrap 去重 + stamp 单一源）不触及，无回归。
- B079 soft-watch 一并关闭。

---

## 1. r1 首轮发现（BLOCKING）与 r2 修复闭环

### 1.1 r1 BLOCKING：trial_registry 生产回填缺失

**现象：** 生产 `trial_registry` = 0 行（spec §2 F001 要求 ≥15；团队 L2 清单第 6 项要求 ≥27）。

**根因（部署链非对称）：** F001 的姊妹种子——OOS 红卡——走迁移 0028 `op.bulk_insert` 随 `alembic upgrade head` 自动落地（生产 2 行 ✓）；但 trial_registry 历史回填**不在迁移**（`0029_b080_trial_registry.py` 只建表，docstring 明写「backfill … seeded by workbench-bootstrap … neither belongs in a migration」），只在手动 `workbench-bootstrap` CLI（`_import_trials`），而 `deploy.sh` 只跑 alembic、部署 workflow 无 seed 步骤 → B080 部署后从未在生产重跑 bootstrap → 回填未落库。且**无任何调度器会填它**（不同于 monitoring_metric 周 timer / reverify 季 timer），不会自愈。同源缺口静默影响 B079（生产 curated `symbol_name` = 0）。代码本身正确（本地实证 `HISTORICAL_TRIALS==27`）。

（完整 r1 逐条证据见 `docs/test-reports/B080-strategy-lifecycle-monitoring-verifying-r1-2026-07-04.md`。）

### 1.2 r2 修复（治本）— generator 提交 `0858b44`

改为 **data-migration `0033_b080_trial_backfill_seed`**（Revises 0032），随 alembic 自动落地，与红卡迁移 0028 同款机制：
- `trial_backfill.py`：`TRIAL_BACKFILL_STAMP` 提升为模块级单一源 → CLI 与迁移产出 **byte-identical**（同 id + 同 created_at）。
- `bootstrap.py`：改 import 共享 stamp（行为不变）。
- 迁移 `upgrade()`：读现存 id、**只插不存在者**（`if t["id"] not in existing`），`op.bulk_insert` 仅当有新行；`downgrade()` 删这 27 id。**幂等**：重复 upgrade 时 27 id 全存在 → 零插入；与 CLI upsert 收敛于同一确定性 content id。

### 1.3 r2 复验（生产实测，VM 严格只读）

| 复验判据 | 结果 | 证据 |
|---|---|---|
| ① 生产 trial_registry ≥ 27 | ✅ **27** | `sudo sqlite3 'file:…?mode=ro' 'SELECT COUNT(*) FROM trial_registry'` → 27；batch 分布 B063×3/B066×6/B068×4/B070×2/B075×2/B076×8/B077×2（与 HISTORICAL_TRIALS 完全一致）|
| ② 抽 3 条对 signoff 原文逐字一致 | ✅ 逐字一致 | 见下 |
| ③ 迁移 0033 在生产 alembic head + 幂等 | ✅ | 生产 `alembic_version = 0033_b080_trial_backfill_seed`；迁移实现 insert-only-missing + downgrade-delete（读源确认）|
| ④ 修复面不触及 r1 PASS 项 | ✅ | `0858b44` 仅动 bootstrap.py(10)/trial_backfill.py(7)/migration 0033(新增)；不碰红卡/timer/paper/monitoring；本地 `test_bootstrap_cli`+`test_trial_registry` 10 passed |
| HEAD≡prod | ✅ | 生产 release = `0858b44`（最后产品提交）；后续 `e0d1cd3`/`4f709de` 仅 docs/progress/.auto-memory（paths-ignore 不部署）|

**3 条抽查（生产值 ↔ signoff 源文件，逐字）：**
1. **B070 pure_momentum PIT**：prod `rebal 639 / CAGR 13.1% / Sharpe 0.56 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / OOS_DD -27.8% / SURVIVES_DEBIASING` ↔ `B070-ashare-survivorship-free-signoff-2026-06-19.md`「| survivorship_free_pit | 639 | 13.1% | 0.56 | -58.3% | 28.4% | 0.93 | -27.8% |」✓
2. **B077 机构买入净额 rank-IC**：prod `N1 0.0201 / N5 0.0232 / N10 0.0176 / N20 0.0181` ↔ `B077-F002-first-look-ic.md`「+0.0201 / +0.0232 / +0.0176 / +0.0181」✓
3. **B066 quality+momentum_decay**：prod `CAGR 10.20% / Sharpe 0.896 / MaxDD -12.4% / turnover 0.80 / IS_CAGR 20.7% / OOS_CAGR -10.8% / IS_Sharpe 1.64 / OOS_Sharpe -1.00` ↔ `B066-…-signoff-2026-06-18.md`「10.20% | 0.896 | -12.4% | 0.80 | 1 | 20.7% | -10.8% | 1.64 | -1.00」✓

---

## 2. r1 其余项复述（全 PASS，r2 修复面未触及，无回归）

| # | 检查项 | 结果 | 关键证据（VM 只读实测 / 本地实跑）|
|---|---|---|---|
| 1 | HEAD≡prod | ✅ | r2 后 release=`0858b44`；后续提交 paths-ignore |
| 2 | timer 装载 + 显式 TimeoutStartSec | ✅ | `workbench-monitoring.timer`（Mon 05:00，service TimeoutStartSec=1800）+ `workbench-reverify.timer`（季频 Jan/Apr/Jul/Oct-01 06:00，service TimeoutStartSec=300，长任务在 backtest-worker daemon）；systemd 硬化 + `test_market_scheduler_scope` grep 守门 |
| 3 | 红卡 DB 化生产零回归 | ✅ | `oos_verification_card` 2 行（validated=0 / `-9% ~ -11%` / seed，迁移 0028）；最新 cn_attack 快照（07-03）`master_meta.research_caveat` 与 B079 时代语义逐字一致 |
| 4 | paper 三口径 | ✅ | `paper_account` cn_attack×2=CNY / master·regime=USD（迁移 0032 精确命中）；benchmark 映射 CSI300；首日 annotation-only；Master 零回归 |
| 5 | F002 signal_scores 前向积累 | ✅ | 07-03 快照 `master_meta.signal_scores` PRESENT(519 chars)、07-02 及更早全 NULL（教科书前向积累）|
| 6 | no-validated→True 不变量 | ✅ | grep 全量仅 3 处 docstring；写路径 `reverify_landings.py:59` 硬编码 `"validated": False`；AST + 运行时守门单测 PASS |
| 7 | 参数冻结 | ✅ | `run_frozen_revalidation` 无可调参数；注入→拒绝守门 PASS |
| 8 | /monitoring no-execution | ✅ | page 存在，无 execute/order/buy/sell/broker/ticket affordance；reverify 钮走 `runReverify`（研究 pipeline）；e2e `b080-monitoring.spec.ts` 守门在 |
| 9 | L1 门禁 | ✅ | safety + B080 子集 **223 passed, 15 skipped**（skip=AI advisor 需 key，非 B080）|

**诚实边界（非阻断）：**
- **monitoring_metric = 0**：周频 job 首跑 Mon 2026-07-06 05:00 UTC（timer 已装载+计划，会自愈）；计算路径由 `test_monitoring_compute`/`_cpcv`/`_job` 覆盖（IC 纯函数迁自已单测的 b077）；无 API 真值可供手工 IC 交叉对照——如实标注，非回归。
- **长任务 reverify 未在生产触发**：评估者判断——避免干扰生产数据目录（~30-40min baostock + 写研究目录）；控制面（timer/API/状态表）+ 内核（参数冻结 + no-validated→True）+ 守门单测已验。

**B079 soft-watch 关闭：** 07-04 01:30 日刷落库 `symbol_name` 5203 行（akshare_spot）；最新 cn_attack pure 快照 25/26 解析中文名（德明利 / 东山精密 / 中际旭创 …）；B080 未破 B079 enrich 路径。

---

## 3. 最终裁定

**✅ PASS。** B080 全 5 特性验收通过。r1 独立 L2 真机验收发现前轮 defer 盲区里的 1 项实质阻断（trial_registry 生产回填缺失）；generator 治本修复（data-migration 0033 自动落地）；r2 生产实测闭环——trial_registry 27 行、3 条对 signoff 逐字一致、迁移幂等、HEAD≡prod。四条安全不变量（无 validated→True / 参数冻结 / Master 零回归 / no-execution）成立，红卡 DB 化 / paper 三口径 / signal_scores / timer 装载均生产实测 PASS。B079 soft-watch 关闭。

**治本遗留（proposed-learning，已由 generator 记录）：** bootstrap-only seed 不入部署链是系统性坑（同源已影响 B079 curated symbol_name）；本批 trial 回填已改 data-migration 根治，建议后续 backlog 把 bootstrap 其余种子（如 curated 名）一并接入部署链或迁移。非本批阻断。

**状态机动作：** verifying(r1) → fixing → reverifying(r2) → **done**；completed_features=5；docs.signoff=本报告。

---

*验收产物：本报告 + r1 报告。未改任何产品代码 / 除状态机外的文件。所有数字为 VM 只读实测 + 本地实跑快照。*
