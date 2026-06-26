---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B078 reverifying（fix_rounds=1，F004-fix done，待 Codex 复验）** = quality_momentum CN基本面覆写 bug。**F004-fix done（commit c121621）**：refresh.py 当 --no-cn-fundamentals 时 `_read_existing_cn_fundamental_rows` 读现有 .SH/.SZ 行保留, 只刷 US, 不再全覆盖; 回归测试修复前红/后绿; gates 全绿 1629 passed。**★Codex 复验关键 ops**：代码只防 FUTURE 覆写, 生产 fundamentals.csv 06-26 已被抹成 US-only(CN 行丢)→ quality_momentum 恢复须先**手动触发 workbench-cn-universe.service(或等周日)REPOPULATE CN 基本面**, 再验 quality_momentum 非空 target + paper 调仓 cash≥0 + 之后日刷不再抹(真验收)。**F003 L2 已 PASS 部分**：data-refresh 卡死修复✅(02:34 UTC 6m54s)/pure_momentum 全链路✅(as_of 06-26 cash+178)/freshness gate✅/美股 Master regime 零回归✅。signoff docs/test-reports/B078-...-signoff-2026-06-26.md。
- **B077 ✅ done（2026-06-25，CLI代Codex）** = A股 聪明钱数据可行性摸底。整体 NOT-GO。signoff docs/test-reports/B077-cn-attack-smart-money-signoff-2026-06-25.md。
- **⚠️ B077 date-bomb已修（2026-06-23,commit 6f54e35）**：cn/hk/yfinance get_quote clock-injectable fix。
- **B076 ✅ done（2026-06-24）**。B075 ✅ done（2026-06-22）。
- **⚠️ ops: 网关 402 out-of-credit（2026-06-22）**：AI功能不可用，需充值 aigc-gateway。

## 遗留 / soft-watch
- **★CN基本面覆写bug(F004-fix焦点)**：refresh.py --no-cn-fundamentals覆写fundamentals.csv→quality_momentum失败。修复=读取现有CN行保留写入。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存docs/research/，下次深入。
- **B077 done 收尾未竟**：3条framework候选待沉淀+F003 features.json一致性。下次done处理。
- **cn_attack宽池top-25与种子43重叠**：大盘蓝筹偏差，预期行为。
- **B070 follow-on**：2因子去偏baostock；港股P3（backlog B055）。
- **DB时序artifact**：CN price_snapshot DB 2026-06-22，明日prices.service(2026-06-27 00:30 UTC)运行后自愈至2026-06-25。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资（B075 未改策略）。

## Framework 状态（最新 4 版）
- **v0.9.52**（B076）：generator.md §35 baostock turn 补退市名市值 + survivor/去偏双 cut / planner.md §策略-改动 verdict 设计(全样本+OOS 双门禁)。
- **v0.9.51**（B075）：environment.md VM /tmp PYTHONPATH / generator.md §33 可行性探针复用真 loader / §34 宽集 partial-failure exit-code 容忍。
- **v0.9.50**（B074）：generator.md §32 paper 搁浅现金诊断 / planner.md §根因诊断。
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。
