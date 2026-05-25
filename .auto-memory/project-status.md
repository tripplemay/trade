---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B025-us-quality-momentum-satellite：`fixing`**；F001-F005 ✅；F006 fix-round-3 的功能复验已通过，但仍被 `Production HEAD ≡ main HEAD` 打回。最新 blocker：`docs/test-reports/B025-us-quality-reverify3-blocker-2026-05-25.md`。
- fix-round-3 本身是对 deploy 链路的修复：`.github/workflows/workbench-deploy.yml` 加 `workflow_dispatch` trigger，让 chore-only main SHAs 也能部署；`afa154d` 已成功部署到 production。
- 新问题是 `main` 又前进了一个 chore commit：当前 `origin/main` = `f45ac46`，而 production `/api/health.version` 仍是 `afa154d`，所以 hash 等价性再次失效。
- Codex round-3 结论：L1 全绿。backend `pytest 241+2 skipped` + ruff + mypy，trade `pytest 727` + mypy，frontend lint/typecheck/vitest 157/build/npm audit 全过。首次 Playwright 失败是旧本地栈污染；重启到 `f45ac46` 后，B025 bilingual suite `14/14 passed`。
- L2 功能面继续通过：production 上 zh-CN + en 的 `/strategies`、`/recommendations`、`/risk`、`/reports`、`/reports/[slug]` 均正常；`/api/debug/recent-errors` 为 `200 {"count":0,"records":[]}`；locale switch 聚焦复现 `3/3` 成功并持久到 `/risk`。
- 目标：把 Master Portfolio 的 `satellite_us_quality` sleeve 从 stub 升级为 implemented_strategy，对应 5 因子美股个股策略 + workbench UI 双语展示（继承 B024 i18n）。预估 3-4 周。
- 范围决策（2026-05-25 用户已批）：全栈（strategy + backtest + Master Portfolio + workbench UI）；纯 fixture / mock（synthetic data, not actual filings）；strategy doc §7 完整版因子权重 `0.35 mom + 0.30 quality + 0.15 lowvol + 0.10 value + 0.10 trend`；股票池 = S&P 500 + Nasdaq 100 30-50 ticker 子集跨 ≥7 GICS sector；Top 15 等权；单股 ≤7% / 行业 ≤30%；财报前 5d 不新开仓；月度信号 + Master quarterly cadence；HK-China satellite 留 B026 候选。
- Feature 分配：F001 fixture+universe+filter / F002 5 因子计算 / F003 综合评分+选股+约束 / F004 Master 接入+backtest / F005 workbench UI 双语 (generator) + F006 Codex L1+L2 签收 (codex)。
- ML 边界：禁止 LightGBM/XGBoost/CatBoost/任何 fit-predict 路径；sklearn 仅允许 ranking 工具函数。
- Master Portfolio 改动：精准 1 处（`trade/portfolio/master.py` 中 `satellite_us_quality` sleeve_type SATELLITE_STUB → IMPLEMENTED + strategy_id），其他 3 sleeve（momentum / risk_parity / satellite_hk_china）完全不动。

## 已完成签收 + MVP 完工
- B001-B024 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B024 i18n zh-CN + en `docs/test-reports/B024-i18n-signoff-2026-05-22.md`。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup。
- 当前 live 版本是 `afa154d`，功能面正常，但**仍不满足 Production HEAD = main HEAD**：仓库 `origin/main` 已到 `f45ac46`。

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
