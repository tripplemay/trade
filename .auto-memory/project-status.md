---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B027-real-data-snapshot-foundation：`verifying`**；F001 completed（11206ac）+ F002 completed（3d14413）+ F003 pending（codex L1+L2+signoff）。Spec：`docs/specs/B027-real-data-snapshot-foundation-spec.md`（含 2026-05-26 vendor reselect 修订）。
- F001+F002 本地 gates 全绿：backend pytest 273+2 skipped（243 baseline + 32 新 specs；spec ≥10 ×2 floor ✓）/ ruff + mypy 清 / alembic up/down 验证 / trade pytest 727 + frontend vitest 166 unchanged。
- 目标：为 Stream 1 Real Data 打地基。把 **Tiingo Starter $10/月** 接入 backend Repository 抽象层 + cost guard ($10 月 cap + 80% alert + BudgetExceeded raise) + GitHub Secret TIINGO_API_KEY 注入 .env.production。**不做** backfill / 不切 sleeve / 不动 strategy 代码（B028+ 责任）。
- 决策矩阵（2026-05-26 用户已批，含 vendor reselect）：轻批次范围（Tiingo adapter + Repository + cost guard，不含 backfill）/ API key 方案 A（.env.production + GitHub Secrets）/ yfinance cross-check 留 B028 / vendor 原 Polygon.io rebrand 为 Massive.com 引发稳定性疑虑后改 Tiingo（独立 fintech 老牌 2014 起未 rebrand），月预算节省 $19。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 起点（Stream 1.A）**。B026 banner 仍 enable 显示，B030 done 时 by acceptance 关闭。
- 后续路径：B028（1.B 价格 backfill + 新增 yfinance_loader.py cross-check）→ B029（1.C 财务 SEC EDGAR）→ B030（1.D 全 sleeve 切真）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B026 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B026 Synthetic Data Banner signoff 2026-05-26（2 fix-rounds，production-only React event edge 防御性双路径修复）；B025 US Quality Momentum signoff 2026-05-25。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup + 4 sleeve 完整持仓展示（含 satellite_us_quality 5 因子，仍 synthetic data）+ Layer 0 synthetic data banner。

## 永久硬边界（B027 起继续；v0.9.28 + B027 新增）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（**Tiingo API key 走 secret 不入代码**）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live Tiingo）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy（v0.9.27 §12.7）
- **AI 边界（v0.9.28，本批次不引入 AI）：** (a) no auto-execution / (b) no 收益预测数字 / (c) no 替代 quant / (d) 必须可引用 / (e) 解释/summarize/translate/context aggregation 允许
- **新增（B027 起）：** (f) Tiingo API key 仅 backend 用永不入前端/build/log + (g) 月预算 cap $10 USD enforced（≥80% alert / ≥100% BudgetExceeded raise + halt）

## Framework 状态
- 最新版本 **v0.9.28**（2026-05-25 沉淀完成）。B026 done 阶段 production-only React event edge 现象**暂不沉淀**（用户决策），仅在 `framework/proposed-learnings.md` 加历史注释（v0.9.20 BL-060 模式），等二例再合并为 v0.9.29。

## 产品规划状态（B025 done 阶段，approved 2026-05-25）
- 8 份 product docs 全 approved：positioning / user-personas-and-journeys / roadmap / llm-provider-evaluation / data-source-evaluation / ai-safety-evals / success-metrics / implementation-path（接续地图）
- 产品定位：AI-augmented personal portfolio decision support tool, built on a quant-strategy chassis

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已在 B025 落地剥离）→ Phase 4 长尾按需
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器。
- **GitHub Secret `TIINGO_API_KEY` 已配置**（2026-05-26 用户预先配置完成）；Generator F001/F002 实施无需中断等待 user 协助。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
