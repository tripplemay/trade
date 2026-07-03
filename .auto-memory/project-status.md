---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B079 ✅ done（2026-07-03）**(标的名称显示,名称为主代码次之 `贵州茅台 600519.SH`)= F001-F003 generator+F004 独立 Evaluator(代 Codex,用户 /goal 授权)**真机验收 PASS**。F001 轻量 symbol_name store+纯DB get_names+curated seed(US27+ETF15+CN/HK26,进程内不依赖 seed job)+A股 zero-fetch 捕获(cn_marketcap sina names_out,含ST);F002 10 response model 加 name+各 service 一次 batch resolve_symbol_names enrich;F003 SymbolLink name-prop+10 site+详情页头部。**真机实证**:master/regime recommendations·position-diff·paper·symbols 详情 US/ETF/大盘名正确(CAT→Caterpillar Inc./600519.SH→Kweichow Moutai);cn_attack 50 条 A股 name=null 优雅纯 code 兜底。**A股 中文名待下次日刷(01:30 UTC 07-04)落库**——F001 捕获码 16:20-18:35 部署晚于今日 01:30 日刷,系 spec 诚实边界①「待日刷」非 FAIL;wiring 已核实(生产 ExecStart 传 --cn-universe-sina-fallback,sina VM-可达)。零回归全守(safety172/research disclaimer/read-only 落库)。signoff docs/test-reports/B079-symbol-name-display-signoff-2026-07-03.md。commits d188096/585d30a/157cb21/ef30cc9。
- **B079 soft-watch**：下次日刷后抽查 `symbol names — captured=N written=M` 日志行 + `SELECT source,COUNT(*) FROM symbol_name` 确认 akshare_spot 落库、cn_attack 面出现中文简称（首次捕获未观测,非阻断）。
- **接续**：planner 已备 B080(P0 监控)+B081(P0.5 引擎修真) spec 草稿，B079 done 后可启动。
- **B078 ✅ done（2026-06-26）** = A股 data-refresh 卡死修复(B075 宽宇宙回归)。F001 超时+watchdog/F002 round-trip cost+freshness gate/F004 CN 基本面覆写 bug。A股 数据恢复(06-26)+paper cash +187.52 转正。signoff docs/test-reports/B078-ashare-data-refresh-hang-fix-signoff-2026-06-26.md。
- **B077 ✅ done（2026-06-25，CLI代Codex）** = A股 聪明钱数据可行性摸底。整体 NOT-GO（北向ELIMINATED/资金流浅/龙虎榜INCONCLUSIVE_COVERAGE_LIMITED 80.8%小盘未覆盖）。signoff docs/test-reports/B077-cn-attack-smart-money-signoff-2026-06-25.md。
- **B076 ✅ done（2026-06-24）**。B075 ✅ done（2026-06-22）。

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
