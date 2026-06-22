---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B072 ✅ done（2026-06-21，Codex F004 PASS）** = 测试自动化 Phase 2 核心（golden 全栈 CI + e2e 交易闭环 + 可注入时钟）。3g+1c。**F004:e2e 闭环 6 步全绿+mutation K/L/M 有牙齿+acceptance 18/18+时钟快进真验**。F001 golden→DB 全栈 seed(4 表确定性) / F002 e2e 闭环(recommend→diff→ticket→fills→reconcile→journal=BL-B023-S1 自动化) / F003 可注入时钟(8 timer CLI --as-of,默认 now 零回归)。★范围裁定守住(不引 docker/Postgres)。**B072 无 prod-affecting 改动**(纯测试/CI+时钟默认 now)。signoff docs/test-reports/B072-...-signoff-2026-06-21.md。
- **⚠️ 外部故障(非 B072,ops soft-watch)**:AI Safety Eval CI 红=LLM 网关 `aigc.guangai.ai` 503/429 宕机/限流(test_ai_advisor_red_team 全挂)。**影响**:①阻断自动部署 gate(但 B072 无 prod 改动不急);②生产 AI 功能(B043 解释/B054 新闻翻译/B036 advisor)运行时调此网关→宕则降级(应优雅降级,需确认)。**429 警示**:勿连发重跑,等网关恢复单次重跑→绿→gate 解。
- **F001 ✅ done**：golden→DB 全栈 seed `workbench/backend/scripts/seed_golden_e2e.py` 推 4 表（price_snapshot 38×2 marks / recommendation_snapshot 真 Master golden 评分 7 行 sum=1.0 as_of=2023-09-29 / account_snapshot 1M+SPY10+AAPL5 闭环账户 / investment_report 复用 seed_e2e_reports b040 slug），确定性。全栈 CI 编排扩 `workbench-frontend.yml`：装 root trade（../..）+ golden seed + backtest worker daemon。acceptance `tests/acceptance/test_b072_golden_fullstack_seed.py` 3 测有牙齿。**坑**：DbPriceProvider 需 price_snapshot 2 close 否则 diff 全 unmatched（spec 只列 3 表但闭环要 marks，故加 price_snapshot）；frontend CI 原不装 trade。
- **F002 ✅ done**：e2e 交易闭环 `workbench/frontend/tests/e2e/b072-closed-loop.spec.ts`（authed testMatch）。6 步 recommend→diff→ticket→fills→reconcile→journal。reconcile 无 UI 控件→经鉴权 `page.request.post /api/execution/reconcile/{id}` 调（=BL-B023-S1 手动冒烟）；fills CSV 内联 buffer（`*.csv` gitignore 仅反忽略 data/fixtures/**）；账户由 F001 golden seed 提供。本机 Playwright 全栈实跑 2 passed + tsc/eslint/vitest 343 绿。
- **F003 ✅ done**：可注入时钟 timer CLI `--as-of`（默认 now 零回归）。共享 `cli_clock.py`；8 timer 接旗标（recommendations+regime 深 plumb as_of→价格 cutoff 真快进；advisor/prices/data_refresh/canonical/paper-mtm/news 现有 run-date seam 直穿）；cn_attack（as-of 数据派生）+worker（daemon）出范围（cli_clock 文档说明）。acceptance `test_b072_clock_injection.py`（≥3 timer 快进有牙齿）+unit `test_b072_clock_cli.py`（全 8 CLI 贯穿+默认 now）。
- **F004（Codex 验收，verifying 中）**：golden 全栈起得来+e2e 闭环 6 步绿+时钟快进真验+mutation 核+零回归+signoff。
- **门禁**：F001 CI 双绿；F002 Frontend CI 绿；**F003 Backend CI 绿 + Frontend CI 重跑后绿**（首跑 1 个旧 flaky `risk-banner` defensive 342/343，重跑过=与 F003 无关，F003 零前端改动）。
- **⚠️ AI Safety Eval 红（外部故障，非 F003）**：`test_ai_advisor_red_team` 15 样本全 `httpx aigc-gateway 503/429`——LLM 网关 `aigc.guangai.ai` 宕机/限流（F003=定时器时钟，与 AI advisor 无关）。**阻断自动部署直到网关恢复**；429 说明连续重跑触发限流，须等网关恢复后再单次重跑（勿连发）。

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
