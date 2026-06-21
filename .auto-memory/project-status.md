---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B072 building（generator）** = 测试自动化 Phase 2 核心（golden 全栈 CI + e2e 交易闭环 + 可注入时钟）。混合批次 3g+1c。**★范围裁定（焊死）**：全仓 0 docker + sqlite（Postgres 排除）+ systemd → 不引 docker/Postgres，复用现有 sqlite+进程编排半栈扩全栈。spec `docs/specs/B072-test-automation-fullstack-e2e-clock-spec.md`。
- **F001 ✅ done**：golden→DB 全栈 seed `workbench/backend/scripts/seed_golden_e2e.py` 推 4 表（price_snapshot 38×2 marks / recommendation_snapshot 真 Master golden 评分 7 行 sum=1.0 as_of=2023-09-29 / account_snapshot 1M+SPY10+AAPL5 闭环账户 / investment_report 复用 seed_e2e_reports b040 slug），确定性。全栈 CI 编排扩 `workbench-frontend.yml`：装 root trade（../..）+ golden seed + backtest worker daemon。acceptance `tests/acceptance/test_b072_golden_fullstack_seed.py` 3 测有牙齿。**坑**：DbPriceProvider 需 price_snapshot 2 close 否则 diff 全 unmatched（spec 只列 3 表但闭环要 marks，故加 price_snapshot）；frontend CI 原不装 trade。
- **F002 ✅ done**：e2e 交易闭环 `workbench/frontend/tests/e2e/b072-closed-loop.spec.ts`（authed testMatch）。6 步 recommend→diff→ticket→fills→reconcile→journal。reconcile 无 UI 控件→经鉴权 `page.request.post /api/execution/reconcile/{id}` 调（=BL-B023-S1 手动冒烟）；fills CSV 内联 buffer（`*.csv` gitignore 仅反忽略 data/fixtures/**）；账户由 F001 golden seed 提供。本机 Playwright 全栈实跑 2 passed + tsc/eslint/vitest 343 绿。
- **F003 building（下一步）**：可注入时钟 timer CLI --as-of（默认 now 零回归）。
- **F004**：Codex 验收（待 building 完）。
- **门禁**：F001+F002 本机全绿；F001 CI 双绿（Frontend full-stack + Backend acceptance）；F002 待推 CI 跑 Playwright。

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
