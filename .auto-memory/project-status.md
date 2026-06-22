---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B073 verifying** = 测试自动化 Phase 2.1（VCR 录放 + AI Safety Eval 网关韧性）。F001+F002 ✅ done(generator),交 Codex F003 安全相邻验收(★mutation 核安全不削弱)。触发=B072 外部网关宕拖红 gate(活证)。spec docs/specs/B073-...-spec.md。
- **F001 ✅ done**:VCR=vcrpy 8.2.1+pytest-recording(dev-dep),tests/cassettes/<module>/ 集中 committed,record_mode=none 离线重放,match_on 排 body(httpx 紧凑 JSON→body 逐字不可手维护)→同URL多POST靠录制顺序消歧,filter_headers scrub Authorization。3 httpx loader(tiingo fetch_daily_bars/sec fetch_raw_companyfacts+health_check/gateway advise)真 client 经 cassette 重放;akshare+yfinance committed CSV frame fixture 经 module=/ticker_factory= seam 重放;现有 in-process fake 全留。**坑**:SEC parse_companyfacts 拒真 SEC shape(要 synthesized parsed_ratios)→VCR 测 fetch_raw_companyfacts;本机无 live key→cassette 手 authored(tests/cassettes/README.md re-record runbook);tests/fixtures/frames/*.csv 被 .gitignore *.csv 忽略已加反忽略。
- **F002 ✅ done**:①新增 always-on 确定性 VCR'd red-team 硬门(test_ai_advisor_red_team_vcr.py,无 key/--block-network);②live eval 韧性经 workbench_api/llm/eval_resilience.py(纯函数):is_infra_unreachable(仅 429/5xx/TransportError;404/auth 须红)+advisor_paths_changed+evaluate_red_team_sample(注真 LLMGateway+client= stub)。verdict→pytest:UNSAFE 硬红(§0)/INFRA_SKIP(503+advisor未变)/INFRA_BLOCK(503+advisor变,unreachable≠safe pass)/非infra raise。ai-safety-eval.yml:fetch-depth:0+AI_ADVISOR_PATHS_CHANGED detect(fail-closed)+确定性 eval 步+保留 live。test_safety_eval_workflow 加 3 不变量(原 8 全留)。门禁全绿:backend 1537 passed/17 skipped(--block-network)+ruff 目录上下文+mypy CI-exact 0。
- **⚠️ 网关 402 Payment Required(2026-06-22 CI 实测,账户余额耗尽)**:生产 AI 功能(解释/新闻翻译/advisor)当前不可用,需充值 aigc-gateway。B073 F002 已让此 402 在 live red-team eval 中 INFRA_SKIP(非红,advisor 逻辑未变)而非拖红 deploy——网关运营问题不再阻断不相关部署;充值后 live eval 自动恢复真跑。
- **B072 ✅ done（2026-06-21）** = Phase 2 核心(golden 全栈 CI seed_golden_e2e.py 推 4 表 + e2e 交易闭环 b072-closed-loop.spec.ts=BL-B023-S1 自动化 + 可注入时钟 8 timer --as-of 共享 cli_clock.py)。无 prod-affecting。signoff docs/test-reports/B072-...-signoff-2026-06-21.md。

## 遗留 / soft-watch
- **F002 合规**：避 no-execution 禁词（EN execute/place order/send to broker；ZH 执行/下单/实盘等）；新 spec 须加入 playwright.config.ts authed testMatch；fills CSV generic 格式小额买单+allow_unmatched，reconcile 1M cash 不超卖。
- **F003 clock-seams**：paper/mtm+advisor+prices+canonical 干净 seam（加 flag 即可）；precompute 簇（recommendations/regime/cn_attack）需 plumb as_of 入价格 cutoff（precompute.py:248/262 硬 now）。
- **B070 follow-on（非本批）**：2 因子去偏 baostock；港股 P3（backlog B055）。A股 进攻 P3 / hk_china 重测在池。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。
- **v0.9.48**（B066）：§28 停牌 ffill+NaN 安全读价 / §29 多变体退化空仓必须红旗。
- **v0.9.47**（B065）：§19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：§27 前端「本机绿≠CI 绿」二坑。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。golden 必须落 `data/fixtures/**` 才 commit。
