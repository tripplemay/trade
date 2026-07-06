---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B095 ✅ done（2026-07-06, 混合批 1g+1c, Workflow-build）** test-automation roadmap **P4-F1 确定性语义 lint**(桶 C 确定性部分, additive)。新增 `advisor/semantic_lint.py`(318 行, 纯 re/词表)+`test_semantic_lint.py`(74 测): detect_english_residual(英文残留, URL/sha256 mask+joiner 逐段 acronym 白名单)+detect_banned_phrases(no-AI 禁语 收益预测/自动下单/替代 quant, NEGATION_WINDOW=5 否定守卫)。★裁定 **全 PASS 2/2**。独立验收(代 Codex, 隔离, 用我自己从零构造对抗样本): ★真阳=我自己 10 条已知违例全 HIT; ★零假阳=我自己 10 条合法 grounded advice(多 ticker 斜杠/EV·EBITDA/下单碰撞/难-否定/ISO/acronym)全 CLEAN+committed 12+真 cassette 零 finding; ★变异有牙(否定窗口/bare 下单不误报)。★additive 零回归: git diff 证红队门/dataset 逐字节未动+grep 证**未接入任何 runtime**(唯一 import 者=其单测=advisory-only 生产零变更)+safety 257 passed+CI AI Safety Eval 绿。门禁全绿(ruff/mypy/pytest)+CI 四 workflow 三绿(560a143)+HEAD≡prod。signoff docs/test-reports/B095-test-automation-semantic-lint-signoff-2026-07-06.md。3 软观察非阻断(O1 宁漏勿误漏报口/O2 allowlist 演进/O3 lint 尚无消费者)。
- **★含义**: 推进 test-automation 1 feature(P4-F1 确定性能力层+证据网, 未接 runtime gate, 符合 roadmap advisory 非硬 block)。item **不清空**——P4-F2(LLM-judge 概率性)+P3(生产 synthetic/canary)+P5(独立评审固化)仍 user-gated/需 LLM。
- **B094 ✅ done** 游资席位 follow first-look **NO-GO(跟游资反而亏)**; ★smart-money 免费两支已测尽(机构 B077 INCONCLUSIVE + 游资 B094 NO-GO), 首要 institutional 仍需付费 Tushare ¥200(故意未买, 留给用户)。**B093 ✅** hk_china real-stock **NO-GO(保 proxy)**。**B092/B091/B090–B074 ✅**(B077 NOT-GO)。
- **接续**：★战略决策待用户(所有免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation P3/P4-F2/P5(基建, user-gated) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。

## 遗留 / soft-watch
- **B095 O1/O2/O3**（非阻断）：确定性 pre-filter 固有'宁漏勿误'漏报口(bare 下单剔除+NEGATION_WINDOW=5, docstring 明述, P4-F2 后手) / 小写 allowlist 演进需守证据门 / lint 尚无 runtime/CI 消费者(advisory-only 能力层)。
- **B094 O1–O4**（非阻断, 归档）：events.csv 重复键未去重(immaterial, dedup 后仍显著 NO-GO) / §1 caveat 措辞欠精确 / priced 1,279 非满 1,500 / 仅 N5 edge 显著。
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
