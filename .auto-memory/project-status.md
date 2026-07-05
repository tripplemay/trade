---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B082 🔧 fixing（2026-07-05, verifying r1）**(红利低波防守腿 3g+1c)。独立验收(代 Codex)：代码/回测审计**全面 PASS**(F002 数字独立重实现逐位复现 7.49%/-40.5%·10.64%/-66.2%、阈值无扫参、TR-PR 手算、2024-02 更正证实真 HS300 -6.1%、探针重fetch、27+34+68 单测+CI三绿、alembic 0037/trial B082=6 逐位吻合/OOS card validated=0·mixed、零回归、no-execution)。**ISSUE-1(HIGH)阻断**：生产 live 数据从未落地(VM snapshots/dividend_lowvol/ 不存在、journal 全史无 dividend)——根因 cli.py fetch_main 中 dividend_lowvol(akshare)排在无 try/except 的 run_refresh(Tiingo)之后，今日 01:30 首刷撞 Tiingo 429 hang 未到达→03:50 timer 将 data_not_covered。代码正确性已证(真数据本机 producer 端到端 OK)，纯落地问题+部分环境性。建议隔离 akshare CN 系列与 run_refresh 失败(或观察自愈日复验)。报告 docs/test-reports/B082-...-verifying-r1-2026-07-05.md。
- **B081 ✅ done（2026-07-04）**(cn_attack 回测引擎修真) = 全 5 PASS(两轮闭环)。6 高估源各带开关，旧口径 bit 级复现 B070。红卡改**资本条件化**(-16.0%@10万/+27.1%@100万纯保真,validated恒False,source=b081_f005_capital_conditioned)。生产 alembic=0036/trial B081=14。signoff docs/test-reports/B081-...-signoff-2026-07-04.md。
- **B080 ✅ done** 策略生命周期监控(trial 27 回填 migration 0033/周timer/paper 三口径)。**B079 done** 标的名。**B078 done** refresh 卡死。**B077 NOT-GO**。B076/B075/B074 done。
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
