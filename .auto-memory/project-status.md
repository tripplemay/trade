---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B075 ✅ done（2026-06-22，Codex F003 L2 PASS）** = A股 生产股票池扩大到全市场流动 top ~1501。**N=1501 A株价格 / 1490 PIT宇宙 / 1501基本面，zero_errors=0/2992**。price_snapshot 宽集 1501 cn_uncovered=0；precompute从1490选top-25（与种子43重叠=大盘蓝筹预期行为，诚实标注）；paper-mtm rebalanced=0（账户已满持）；Master/regime零回归。cn-universe真建4h21min完成。workbench-cn-universe.timer每周日06:00自动重建。signoff docs/test-reports/B075-ashare-wide-universe-signoff-2026-06-22.md。
- **B074 ✅ done（2026-06-22，Codex F003 VM 真机 PASS,生产 hotfix）** = cn_attack A股 模拟盘建仓修复。两 cn_attack 账户 build_complete=1/各 25 持仓/cash=0/last_rebalanced=2026-06-22。★双根因：#1 price_snapshot 缺 A株 价；#2 CASH sentinel 计入 skipped。framework v0.9.50 沉淀。
- **B073 ✅ done（2026-06-22，Codex F003 PASS）** = VCR 录放+AI Safety Eval 网关韧性。mutation N/O/P/Q 全红（安全门有牙齿）。🎯网关 402→INFRA_SKIP 真机验证。
- **⚠️ ops: 网关 402 out-of-credit（2026-06-22）**：生产 AI 功能（推荐解释/新闻翻译/advisor）不可用，需充值 aigc-gateway。B073 F002 已处理 402 为 INFRA_SKIP 不阻 CI。

## 遗留 / soft-watch
- **cn_attack 宽池 top-25 与种子 43 重叠**：大盘蓝筹偏差，预期行为，已在 B075 signoff 诚实标注。未来若策略参数调整（扩 N、降 market-cap 门槛），可能出现新 tickers。
- **F002 合规**：avoid no-execution 禁词；new spec 须加 playwright.config.ts authed testMatch。
- **B070 follow-on**：2 因子去偏 baostock；港股 P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资（B075 未改策略）。

## Framework 状态（最新 4 版）
- **v0.9.50**（B074）：generator.md §32 paper 搁浅现金诊断 / planner.md §根因诊断。
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。
- **v0.9.48**（B066）：§28 停牌 ffill+NaN 安全读价 / §29 多变体退化空仓必须红旗。
- **v0.9.47**（B065）：§19.1 ruff 本地须目录上下文。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。
