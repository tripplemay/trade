---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B078 ✅ done（2026-06-26，CLI代Codex）** = A股 data-refresh 卡死修复(B075 宽宇宙回归)。全批次 PASS：F001(per-call 超时+watchdog)/F002(round-trip cost buffer+freshness gate)/F003(L2 pure_momentum全链路)/F004-fix(CN基本面覆写bug)。★F004-fix 真验收：data-refresh(--no-cn-fundamentals)跑完后 fundamentals.csv 仍 29,893行(CN 行保留, cn_fundamental_rows=29316 preserved)；quality_momentum cash +187.52(从 -102.49转正)。signoff docs/test-reports/B078-ashare-data-refresh-hang-fix-signoff-2026-06-26.md。
- **B077 ✅ done（2026-06-25，CLI代Codex）** = A股 聪明钱数据可行性摸底。整体 NOT-GO（北向ELIMINATED/资金流浅/龙虎榜INCONCLUSIVE_COVERAGE_LIMITED 80.8%小盘未覆盖）。signoff docs/test-reports/B077-cn-attack-smart-money-signoff-2026-06-25.md。
- **B076 ✅ done（2026-06-24）**。B075 ✅ done（2026-06-22）。
- **⚠️ ops: 网关 402 out-of-credit（2026-06-22）**：AI功能不可用，需充值 aigc-gateway。
- **⚠️ cn-universe 今日手动触发（07:27 UTC）仍在运行**：reverify需要REPOPULATE，watchdog 8h(~15:27 UTC截止)；周日06:00 UTC正常自动跑不受影响。

## 遗留 / soft-watch
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存docs/research/，下次深入。
- **B077+B078 done 收尾已闭合**：7 条 learnings 沉淀 v0.9.53+v0.9.54，F003/F004 一致性修。**B075 宽宇宙(1490)引入的两回归(B078 data-refresh 卡死 / B074 满仓负现金)均已闭合。**
- **B070 follow-on**：2因子去偏baostock；港股P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资（B078 不改策略）。

## Framework 状态（最新 4 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本预留 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：generator.md §36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定档 / evaluator.md §31 date-bomb 诊断。
- **v0.9.52**（B076）：generator.md §35 baostock turn 补退市名市值 + survivor/去偏双 cut / planner.md §策略-改动 verdict 设计(全样本+OOS 双门禁)。
- **v0.9.51**（B075）：environment.md VM /tmp PYTHONPATH / generator.md §33 可行性探针复用真 loader / §34 宽集 partial-failure exit-code 容忍。
- **v0.9.50**（B074）：generator.md §32 paper 搁浅现金诊断 / planner.md §根因诊断。
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。
