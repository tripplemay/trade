---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `fixing`**（2026-08-01，fix-round 1 复验 FAIL）。F007 已完成并最终 NO-GO；F006 因新 high finding 保持 pending，signoff=null。
- **★生产服务器已迁移**：`ssh deploysvr`（194.238.26.173/root/`~/.ssh/kolmatrix_new`，hostname vmi3430901）；旧 GCP 34.180.93.185 退役（environment.md 已更正，勿再用旧 IP）。
- **F006-1/2 首轮 findings 已修**：5+5bps 双腿、禁同会话成交；persisted Master momentum=EEM/QQQ 纯 ETF、us_quality 15 只、hk fallback/mixed；regime as_of=2026-06-30。
- **★新 High F006-3**：Master paper cash 2026-07-31 `$60.252823` → 2026-08-01 `-$18.944156`。min-trade 跳过小卖单但执行大买单，evaluator 最小复现 cash=`-$105.105`；测试当前 5 pass/1 fail。
- **F007 完成**：191 项独立对拍全匹配；正式 G1 `+2.2098pp`、正式日均 G2 `+2.8457pp` 均过硬门；但仅 11 个可评年份且 bootstrap P=0.862<0.90，冻结双判据 FAIL，最终 **NO-GO**。

## 接续（Generator 修复要点）
- min-trade 过滤后重新做 cash-feasible sizing，显式保证 `new_cash >= -epsilon`；不得 clamp 掩盖超买。
- 让 evaluator 新增的 `test_min_trade_skipped_sells_cannot_fund_executed_buy` 通过，并跑 paper 相关全回归。
- 修复部署后，按生产授权受控恢复 Master paper cash 非负并留痕；转 reverifying 后 Codex 仅复验 F006-3。
- 报告：`docs/test-reports/B111-F006-F007-reverification-2026-08-01.md`；F007 证据：`docs/test-reports/B111-F007-reverify-evidence-2026-08-01.json`。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
