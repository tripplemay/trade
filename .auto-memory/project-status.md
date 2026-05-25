---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B025-us-quality-momentum-satellite：`reverifying`**；F001-F005 ✅ generator completed；F006 fix-round-2 已完成（commit 0b61dda, CI 26392633486 success），等 Codex 二次复验。Spec：`docs/specs/B025-us-quality-momentum-satellite-spec.md`。Blocker 报告：`docs/test-reports/B025-us-quality-reverify-blocker-2026-05-25.md`（fix-round-1 之后被打回）。
- Fix-round-2 防御性 3 改动：(1) `tests/e2e/global-setup.ts` 新建，遍历 NAV_ITEMS + /login + /reports/<B025-slug> 触发 Next.js dev-mode 编译预热；(2) `playwright.config.ts` 注册 globalSetup + retries 增到 CI=2 / local=1；(3) `protected-routes.spec.ts` diagnostics 过滤 `_next/static/*` 与 `_next/webpack-hmr` 的 404 假阳性。本地 33/33 passed 25.8s；CI Workbench Frontend 绿。
- 基础 gates 全绿：backend `pytest 241+2 skipped` + ruff + mypy，trade `pytest 727` + mypy 62 文件，frontend lint/typecheck/vitest 157/build/npm audit/artifact 无 dev URL 全清。
- 目标：把 Master Portfolio 的 `satellite_us_quality` sleeve 从 stub 升级为 implemented_strategy，对应 5 因子美股个股策略 + workbench UI 双语展示（继承 B024 i18n）。预估 3-4 周。
- 范围决策（2026-05-25 用户已批）：全栈（strategy + backtest + Master Portfolio + workbench UI）；纯 fixture / mock（synthetic data, not actual filings）；strategy doc §7 完整版因子权重 `0.35 mom + 0.30 quality + 0.15 lowvol + 0.10 value + 0.10 trend`；股票池 = S&P 500 + Nasdaq 100 30-50 ticker 子集跨 ≥7 GICS sector；Top 15 等权；单股 ≤7% / 行业 ≤30%；财报前 5d 不新开仓；月度信号 + Master quarterly cadence；HK-China satellite 留 B026 候选。
- Feature 分配：F001 fixture+universe+filter / F002 5 因子计算 / F003 综合评分+选股+约束 / F004 Master 接入+backtest / F005 workbench UI 双语 (generator) + F006 Codex L1+L2 签收 (codex)。
- ML 边界：禁止 LightGBM/XGBoost/CatBoost/任何 fit-predict 路径；sklearn 仅允许 ranking 工具函数。
- Master Portfolio 改动：精准 1 处（`trade/portfolio/master.py` 中 `satellite_us_quality` sleeve_type SATELLITE_STUB → IMPLEMENTED + strategy_id），其他 3 sleeve（momentum / risk_parity / satellite_hk_china）完全不动。

## 已完成签收 + MVP 完工
- B001-B024 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B024 i18n zh-CN + en `docs/test-reports/B024-i18n-signoff-2026-05-22.md`。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup。Production HEAD = main HEAD（v0.9.25 §Production/HEAD 等价性 强制）。

## 永久硬边界（B025 起继续）
no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file / 任何按钮 labelled execute/place order/send to broker 禁 + 中文等价禁词同级（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存 / framework v0.9.21-v0.9.26 全约束 / fixture-first 离线 CI / no ML fit-predict。

## Framework 状态
- 最新版本 **v0.9.26**（2026-05-25 沉淀完成）：B024 3 候选已写入 planner.md + generator.md §15 + CHANGELOG + 归档。proposed-learnings.md 当前空。B025 F006 候选 3 条（多因子 fixture / sleeve stub→implemented / earnings 规避）将于本批次 done 阶段沉淀为 v0.9.27。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已在 B025 落地剥离）→ 候选 B026
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
