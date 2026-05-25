---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B025-us-quality-momentum-satellite：`done`**；F001-F006 全部完成并签收。Signoff：`docs/test-reports/B025-us-quality-signoff-2026-05-25.md`。
- Production HEAD = main HEAD = `abaaf6e6a162d0ce73305e71ec1c29b54512da5f`（签收时；v0.9.25 §Production/HEAD 等价性 验证通过）。
- F006 经历 4 轮 fix-round（round-1 缺独立 /risk + Playwright 套件不足 / round-2 stale dev process / round-3+4 chore commit deploy drift），产品代码自 `afa154d` 后未变；framework v0.9.27 已沉淀这 3 个跨批次教训以防 B026+ 再撞。
- 目标已达成：把 Master Portfolio 的 `satellite_us_quality` sleeve 从 stub 升级为 implemented + 5 因子美股个股策略 + workbench UI 5 路由双语展示。
- 决策矩阵（2026-05-25 用户已批）：全栈（strategy + backtest + Master + UI）；纯 fixture / mock（synthetic 明示）；因子权重 `0.35 mom + 0.30 quality + 0.15 lowvol + 0.10 value + 0.10 trend`；股票池 30-50 ticker ≥7 GICS sector；Top 15 等权 + 单股 ≤7% + 行业 ≤30% + 财报前 5d 不新开仓；月度信号 + Master quarterly cadence。
- ML 边界：禁止 LightGBM/XGBoost/CatBoost/任何 fit-predict 路径；sklearn 仅允许 ranking 工具函数。
- Master Portfolio 改动：精准 1 处（`satellite_us_quality` SATELLITE_STUB → IMPLEMENTED + strategy_id），其他 3 sleeve（momentum / risk_parity / satellite_hk_china）完全不动。

## 已完成签收 + MVP 完工
- B001-B025 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B025 US Quality Momentum Satellite signoff 2026-05-25；B024 i18n zh-CN + en signoff 2026-05-22。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup + 4 sleeve 完整持仓展示（含新落地的 satellite_us_quality 5 因子）。

## 永久硬边界（B025 起继续）
no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file / 任何按钮 labelled execute/place order/send to broker 禁 + 中文等价禁词同级（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存 / framework v0.9.21-v0.9.27 全约束 / fixture-first 离线 CI / no ML fit-predict / cloud-deploy 批次 deploy workflow 含 workflow_dispatch + Generator chore commit 后 dispatch deploy（v0.9.27）。

## Framework 状态
- 最新版本 **v0.9.27**（2026-05-25 沉淀完成）：B025 B 组 3 候选已写入 generator.md §12.7 + evaluator.md §20 + §21 + planner.md §Cloud-deploy v0.9.27 扩展 (e) + templates/signoff-report.md §Post-signoff Deploy + CHANGELOG + 归档 `framework/archive/proposed-learnings-archive-v0.9.27.md`。A 组 spec 预想 3 条（多因子 fixture / sleeve stub→implemented / earnings 规避）经用户评估复用价值不足不沉淀。proposed-learnings.md 当前空。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已在 B025 落地剥离）→ 候选 B026
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
