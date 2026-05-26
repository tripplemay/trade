---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B028-real-data-backfill：`building`**；F001+F002+F003 pending（generator）+ F004 pending（codex）。Spec：`docs/specs/B028-real-data-backfill-spec.md`。
- 目标：用 B027 TiingoSnapshotLoader 把 Master 4 sleeve ETF + B025 us_quality 30-50 ticker + US-listed ADR proxy（50-80 ticker）的 10+ 年历史日线 OHLCV backfill 到本地 `data/snapshots/{prices,fundamentals}/{vendor,unified}/` 双层 + yfinance 抽样 cross-check + PIT loader enforcement。**不做** strategy 代码切真数据（留 B030）/ 财务 snapshot（留 B029）/ 每日 EOD cron。
- 决策矩阵（2026-05-26 用户已批）：backfill 范围=Master 4 sleeve ETF + B025 + ADR 50-80 ticker / yfinance cross-check=抽样 3-5 ticker × 5 日期 误差 <0.5% / Storage=双层 vendor + unified / PIT=loader 层 enforcement + pytest spot check。
- 新增 dep：yfinance>=0.2.40 走 v0.9.29 §12.8 规约（加入 `[project].dependencies` + safety regression test 守门）。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 第三个 batch（Stream 1.B）**。B026 banner 仍 enable 不破，B030 done 时关闭。
- 后续路径：B029（1.C 财务 SEC EDGAR）→ B030（1.D 全 sleeve 切真）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B027 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B027 Real Data Snapshot Foundation signoff 2026-05-26（1 fix-round；Tiingo 接入 + cost guard + budget log）；B026 Synthetic Data Banner signoff 2026-05-26；B025 US Quality Momentum signoff 2026-05-25。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；B027 Tiingo foundation 已部署到 production；本批次 B028 纯离线 backfill + loader infra 不动 production 服务。

## 永久硬边界（B028 起继续；v0.9.29）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（Tiingo API key 走 secret）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live Tiingo / yfinance）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy / **pyproject runtime vs dev dep hygiene + safety regression test 守门（v0.9.29 §12.8）**
- B027 起新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
- AI 边界（v0.9.28，本批次不引入 AI）：5 子条 spec 列入但本批次不触

## Framework 状态
- 最新版本 **v0.9.29**（2026-05-26 沉淀完成）：B027 deploy-time install layer 教训 — `pyproject` runtime vs dev 判断规则 + `test_runtime_dependencies_pinned.py` ast walker 守门 pattern + 「local vs prod」系列对比表。Codex 标"无 learnings"但 Planner 评估为 framework-grade（高复用窗口）。proposed-learnings.md 空。B026 React event edge 仍单一案例 hold（机制不同不与 B027 deploy edge 合并）。

## 产品规划状态（B025 done 阶段，approved 2026-05-25）
- 8 份 product docs 全 approved：positioning / user-personas-and-journeys / roadmap / llm-provider-evaluation / data-source-evaluation / ai-safety-evals / success-metrics / implementation-path

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已剥离）→ Phase 4 长尾按需
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium`。
- GitHub Secret `TIINGO_API_KEY` 已配置（B027 时完成）；B028 复用，无需新配置。
- B028 F002 本机一次性 backfill 耗时 1-2 小时（Tiingo 60 req/hour 限速）；Tiingo budget 使用率约 5%。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
