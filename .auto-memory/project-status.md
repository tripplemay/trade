---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B081 ✅ done（2026-07-04）**(cn_attack 回测引擎修真 P0.5) = 全 5 特性 PASS(两轮闭环)。6 高估源修复各带独立开关(停牌/退市/涨跌停/手数/印花税5bp/band部分调仓+死参清理)，旧口径 bit 级复现 B070。**F005 独立验收关键**: r1 研究员级 A/B 数字审计坐实 2 HIGH → fixing(planner 实施 4e1feed) → r2 复验 PASS。**四疑点裁定**: ①lot_rounding 灾难=**10万本金容量下限**(lot@100k OOS-16%→1M+23.5%→10M+28.2% 单调恢复,探针10万本金~9/25买不起一手)非"分数股假象"; ②停牌/退市=合法no-op(0事件); ③partial_rebalance=收益改善型策略变动(绕no-trade-band,OOS+28.4%→32.7%)→默认改False留独立verdict; ④红卡改**资本条件化**(-16.0%@10万/+27.1%@100万纯保真,删"分数股假象",validated恒False)。生产 alembic=0036/trial_registry B081=14/红卡 source=b081_f005_capital_conditioned。signoff docs/test-reports/B081-...-signoff-2026-07-04.md(+verifying-r1)。
- **B080 ✅ done（2026-07-04）**(策略生命周期监控 L0+L1)=全5 PASS。trial_registry 27 回填 data-migration 0033/监控指标+周timer/冻结再验证 pipeline/paper 三口径。signoff docs/test-reports/B080-...-signoff-2026-07-04.md。
- **B079 ✅ done（2026-07-03）** 标的名称显示(soft-watch 已关)。**B078 done** data-refresh 卡死修复。**B077 NOT-GO** 聪明钱摸底。B076/B075/B074 done。
- **接续**：backlog ~19 项(partial_rebalance 策略变体独立 A/B verdict 批次[B081衍生] / B048 安全风控 / B0XX-ashare 数据源等)。

## 遗留 / soft-watch
- **B081 快照自愈**：cn_attack advisory 快照 daily timer 07-05 03:40 UTC 重算入新纯保真口径(部署不触发 timer)；权威红卡表已更正，建议 07-05 后 spot-check 快照 caveat==卡片表。partial_rebalance=True 策略变体留独立 verdict 批次。
- **B080 F004 坑**：api.ts 加带默认值字段仍 TS-required → 前端 fixture tsc 红；api.ts 与 fixture 须**同 commit**(见 proposed-learnings)。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存docs/research/。
- **B070 follow-on**：2因子去偏baostock；港股P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。
- **v0.9.52**（B076）：§35 baostock 补退市名市值 + 双 cut / planner.md 策略改动双门禁 verdict。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
