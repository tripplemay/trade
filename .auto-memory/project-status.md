---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B094 ✅ done（2026-07-06, first-look, round1 一轮闭环）** smart-money 游资席位 follow-signal first-look(backlog 免费第二支, 龙虎榜公开, 1g+1c, Workflow-build)。★裁定 **NO-GO(跟游资反而亏, significant NEGATIVE)**: youzi_flag rank-IC N5 -0.0434(t=-4.10)/N10 -0.0426(t=-3.16) 显著负; follow 游资 输裸 LHB baseline N5 -1.00%(t=-2.92)。独立验收(代 Codex, 隔离, 用我自己的独立代码从零重算): ★无前视(手工核对 3 真实事件 上榜日 T 盘后披露→entry 严格 T+1); ★覆盖 23.89% 为 seed-94 uniform-random 子样(非 B077 结构性偏)→显著负号方向可外推/幅度 first-look, NO-GO 保守成立; ★IC/收益我自己代码 bit 级吻合+去重对抗证 immaterial(events 有 7,979 重复行, dedup 后 N5 IC -0.042/t=-3.95 仍显著); ★无扫参+席位识别先验第三方(EastMoney 解读标签, 非事后挑赢家)+§2(c) 141/141 交叉验证坐实; ★NO-GO 与数字一致(judge 负数据无法制造 GO)。research-only(无 workbench/无 trade 包无¥200)+门禁全绿+CI 三绿(013f681)+HEAD≡prod。signoff docs/test-reports/B094-youzi-first-look-signoff-2026-07-06.md。
- **★smart-money backlog 免费两支信号均已测尽 = 机构席位 first-look(B077)INCONCLUSIVE_COVERAGE_LIMITED + 游资席位 follow(B094)NO-GO。用户首要 institutional-following 目标仍需付费 Tushare ¥200 全覆盖机构席位, 本批故意未买, 保留给用户。**
- **B093 ✅ done** hk_china 真个股 vs proxy 决策级重跑 → **NO-GO(保 ETF-proxy)**, real-stock 悬案(B063 以来)闭合。**B092 ✅** US 攻击选股 first-look INCONCLUSIVE。**B091 ✅** MA 多日历 bug。**B090/B089/B088/B087 ✅**。**B086–B074 done**(B077 NOT-GO)。
- **接续**：★战略决策待用户(P0-P2 无强 edge; 所有免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构席位 ¥200 Tushare 待用户] + test-automation P3-P5(基建) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。

## 遗留 / soft-watch
- **B094 O1/O2/O3/O4**（非阻断）：events.csv 重复(date,ticker)键未去重+fetch docstring 'one row per stock' 措辞不准(immaterial, dedup 后仍显著 NO-GO) / §1 caveat 'small-cap sit outside' 措辞欠精确(实为随机子样 sign 无偏, 加固 NO-GO) / priced tickers 实际 1,279 非满 1,500 / 仅 N5 follow-edge 显著(报告透明贴 t-stat)。
- **B093 O1/O2/O3**（非阻断）：报告未溯源 2024-03 shared-date 机制 / proxy 本身弱基准 / 25 季 SGOV-floored 单 regime+幸存者=结构性天花板窗口不可扩。
- **B089/B088**：carry/turnover 措辞略强+窗口 caveat。**B087/B086/B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实, real-stock live 不激活）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
