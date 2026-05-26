---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B029-fundamentals-snapshot：`building`**；F001+F002+F003 pending（generator）+ F004 pending（codex）。Spec：`docs/specs/B029-fundamentals-snapshot-spec.md`。
- 目标：为 B025 us_quality_momentum 30-50 ticker backfill 10+ 年 PIT 财报（8 ratio：ROE / gross_margin / FCF Yield / debt_to_assets / PE / PB / EV/EBITDA / earnings_yield）。数据源 **SEC EDGAR 免费自 parse XBRL**（companyfacts API）。**不做** strategy 代码切真财务（B030）/ Master ETF + ADR proxy fundamentals / 每日 EOD cron / forecast。
- 决策矩阵（2026-05-26 用户已批）：SEC EDGAR 首选 / 仅 B025 us_quality 30-50 ticker × 10+ 年 / Schema 与 B025 fixture 11 列严格一致 / 4 features 拆分。
- 新增永久产品边界 (h)(i)(j)：SEC EDGAR User-Agent 必含 contact email + Rate limit 10/sec hard + Ratio 公式锁定 strategy doc §6。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 第四个 batch（Stream 1.C）**。受益 v0.9.27 §12.7.1 paths-trigger 已修：改 trade/+workbench_api/+scripts/ 自然触 CI/Deploy 不需 dispatch 兜底。B026 banner 仍 enable 不破。
- 后续路径：B030（1.D 全 sleeve 切真 + strategy 代码改读路径）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B028 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B028 Real Data Backfill signoff 2026-05-26（1 fix-round；52 vendor + 153K rows unified；25/25 cross-check PASS；SPY PIT spot-check）；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；production HEAD 已追到 B028 deploy SHA `15dfb4b`。

## 永久硬边界（B029 起继续；v0.9.29 + §12.7.1）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（API key 走 secret）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live vendor）/ pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy + **paths-trigger 已含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1 — B028 微沉淀）**
- 新增（B027 起 (f)(g)）：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- **新增（B029 起 (h)(i)(j)）：** SEC EDGAR User-Agent 必含 contact email；Rate limit 10/sec hard；Ratio 公式锁定 strategy doc §6
- AI 边界（v0.9.28，本批次不引入 AI）：5 子条 spec 列入但本批次不触

## Framework 状态
- 最新版本 **v0.9.29**（2026-05-26 沉淀完成）+ §12.7.1 sub-pattern 微沉淀（2026-05-26 B028 done 阶段；不 bump 版本）。proposed-learnings.md 空。B026 React event edge 仍单一案例 hold。下一沉淀候选取决于 B029-B030 实际踩坑。

## 产品规划状态（B025 done 阶段，approved 2026-05-25）
- 8 份 product docs 全 approved：positioning / user-personas-and-journeys / roadmap / llm-provider-evaluation / data-source-evaluation / ai-safety-evals / success-metrics / implementation-path

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite）→ Phase 4 长尾按需
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium`。
- GitHub Secret `TIINGO_API_KEY` 已配置（B027 时）；B028 已复用。
- **B029 F001 实施需配置 GitHub Secret `SEC_EDGAR_CONTACT_EMAIL`**（任意 generic research-only 邮箱即可）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
