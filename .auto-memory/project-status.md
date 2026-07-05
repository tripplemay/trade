---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B082 ✅ done（2026-07-05, round1 闭环）**(红利低波防守腿 3g+1c, cn_dividend_lowvol 研究态)。独立验收(代 Codex)：F002 数字独立重实现逐位复现(策略 7.49%/-40.5% vs 持有 10.64%/-66.2%,规则减回撤不增收益)、阈值无扫参、2024-02 真 HS300 -6.1%、探针重fetch、alembic 0037/trial B082=6/OOS card validated=0·mixed、零回归、no-execution。**r1 阻断 ISSUE-1(生产 live 数据未落地)经 c53375f 修复**(dividend_lowvol 前移到 Tiingo run_refresh 之前,run_refresh 零改动 exit-code 不变,2 隔离单测)。生产实证: 5 CSV 落地+快照 data_source=real tier=full spread 2.7589%(与预测逐位吻合)+512890.SH 5 marks。paper 未激活=诚实边界(激活属用户动作,precompute 不自动激活)。signoff docs/test-reports/B082-...-signoff-2026-07-05.md。**遗留(backlog)**: fx/benchmark/universe 仍在 run_refresh 后同 Tiingo-独立性病未治(commit 0b23e46 具体化)。
- **B081 ✅ done（2026-07-04）**(cn_attack 回测引擎修真) = 全 5 PASS(两轮闭环)。6 高估源各带开关，旧口径 bit 级复现 B070。红卡改**资本条件化**(-16.0%@10万/+27.1%@100万纯保真,validated恒False,source=b081_f005_capital_conditioned)。生产 alembic=0036/trial B081=14。signoff docs/test-reports/B081-...-signoff-2026-07-04.md。
- **B080 ✅ done** 策略生命周期监控(trial 27 回填 migration 0033/周timer/paper 三口径)。**B079 done** 标的名。**B078 done** refresh 卡死。**B077 NOT-GO**。B076/B075/B074 done。
- **B083 🔨 building（2026-07-05 开批）** PEAD/业绩预告事件 first-look(评审 P1 排序 2, 新信号族)。first-look 低承诺=rank-IC 一测(同 B077)非策略;核心不变量=公告日 PIT(进场 T+1,禁财报期末前视)+盈余惊喜先验禁扫参+涨跌停分层 IC。akshare 已确认可得 stock_yjyg/yjkb/yysj/profit_forecast。3 features(2g F001 数据探针/F002 惊喜+IC + 1c F003 验收)。B082 done 后 16min 无并发 planner 开批→本 session 接手。
- **接续**：backlog ~11 项(cn_attack 信号升级/A股数据源/聪明钱/hk_china retest/test-automation/B055/ETF趋势/vol-target/VIX/bootstrap-seed 等)。B081/B082 follow-up(partial=True 变体/refresh 编排脆弱性)待 planner 并入。learnings 队列待用户确认(F005 更正:资本条件化非分数股假象)。

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
