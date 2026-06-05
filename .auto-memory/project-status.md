---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B037-home-restructure：`building`**（2026-06-05 启动）= **Phase 3 / Stream 4.A 首批**（Home+UI 重构，B037-B043 → 里程碑 C / Layer 0.5）。Home 从 quant dashboard 重构为 daily-engagement 中心，按 user-personas §2 Daily Journey mockup 落三段：① NAV+Day P&L / ② AI Advisor 占位(B039) / ③ market context 占位(B038)+4 sleeve breakdown。spec `docs/specs/B037-home-restructure-spec.md`。4 features：(F001) 后端 Home 数据 NAV+Day P&L(mark-to-market B027 价格)+sleeve breakdown + GET /home；(F002) 前端三段 Home 替换旧 dashboard + AI/market 占位 + 双语；(F003) Playwright Daily Journey + i18n safety + 旧 Home 退役四处清理(v0.9.31 §16)；(F004) Codex。
- **B037 决策矩阵（2026-06-05 用户已批，★=拍板）：** Day P&L=★**mark-to-market 持仓**(B027 价格) / 段落=★**全三段骨架+B038/B039 占位** / 旧 Home=★**直接替换**(不留 legacy-home，偏离 path doc 但用户决) / NAV=复用 dashboard._aggregate_nav(手动录入 no-broker) / 设计稿空→personas §2 mockup 权威 + 双语 + Playwright。
- **关键边界**：no-execution buttons（Home 无下单按钮+中文禁词）/ 直接替换旧 Home 触发 **v0.9.31 §16 退役四处清理 + §22 E2E presence→absence** / §12.10 自包含。本批不触 AI logic（AI 段仅占位）。
- **不做**：AI Advisor 内容(B039) / market context 渲染(B038) / Reports·Rec·Risk 重构(B040-B042) / 真 broker 账户 / 保留 legacy-home。
- **🎯 Phase 2 完整收官（B031-B036 全签收）= 里程碑 B 达成。** 后续 Phase 3：B038(Home market)→B039(Home AI)→B040-B043(Reports/Rec/Risk 重构+AI 解释层)→里程碑 C。
- **B036 ✅ signoff 2026-06-05**（AI advisor MVP；prod /api/advisor 200/3 sleeve haiku-4.5；red-team 15/15 gate；alembic 0008；advisor timer）。**B035 ✅**（FRED+AV market context 0007）。**B034 ✅**（news_embedding+NewsPanel 0006）。

## 已完成签收 + MVP 完工
- B001-B033 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：**B033 News Ingest signoff 2026-06-01**（1 fix-round；prod snapshot dir provision blocker→修复；SEC EDGAR + Yahoo RSS adapter + News schema + snapshot writer + CLI；边界 (p)(q)）；B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `9338a9fef37fa5d27b1fc629a7511518617cbe59`（签收前 `main` HEAD = `3f75bb7e408fd45cea2ca05a77f6dc20df72fd47`，diff 仅 `progress.json` + `.auto-memory/project-status.md`，产品代码等价）；`alembic_version=0007_b035_market_context`；authenticated `/api/market-context`=200（6 series）；anon `/api/market-context`=401；VM `/etc/workbench/workbench.env` 13 key（含 `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`）；`workbench-market-context.timer` enabled+active（每日 00:00 UTC）；`market_context_observation` 31 行 / 6 series；`/var/lib/workbench/data/snapshots/market-context/` 已建并落 6 个 JSON。B034 旧状态保留（news 无 scheduler，边界 q 不变）。
- **VM 运维笔记（2026-06-05）：** timer 由 admin（tripplezhou）一次性手动 install/enable；deploy 用户无 `/etc/systemd` + `enable` sudoers，deploy.sh best-effort 仅 warn（单元文件现随 release 下发，fresh VM 重建可复装）；env 文件更新走 bootstrap-env workflow + admin `sudo install` 到 `/etc/workbench/`。
- **B036 L2 前置已就绪（2026-06-05，generator 完成，等 Codex F004 验收）：** prod `/api/health.version=9cce841`（`db_connectivity:ok`）；`alembic 0008_b036_advisor` 已升；`workbench-advisor.timer` admin 已安装 enabled（01:00 UTC oneshot）；**手动 `workbench-advisor.service` 验真 = `Result=success ExecMainStatus=0`、`saved=1 skipped=2 errors=0`**；`advisor_recommendation` 今日 3 sleeve 全 `status=ok` 真 `claude-haiku-4.5` 建议（regime/risk_parity/satellite_us_quality）；`/api/advisor` unauth=401（auth-gated）。**修复 1 round（commit 9cce841）：** advisor precompute 单 session 跨 sleeve 持 SQLite WAL writer 锁 → 下一 sleeve cost_guard（独立连接）写 llm_budget_log `database is locked` → 改 **per-sleeve commit**（WAL+busy_timeout 已先行于 d7533af，仍需释放跨 sleeve 事务）；单测 `test_advisor_precompute`+`test_db_engine` 全绿。

## 永久硬边界（B033 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g) / B029 起 (h)(i)(j) / B030 起 (k) + v0.9.30 §12.9 / B031 起 (l)(m) / B032 起 (n)(o)：继续
- **B033 起 (p)(q)：** (p) News raw text 仅落 snapshot path 不内联 DB / (q) News ingest 默认 production-disabled（无 scheduler / cron / APScheduler；**对 news 不变**）
- **B035 起 (r)，B036 修订：** 调度器允许（a）只读市场数据拉取 +（b）**运行已过 CI safety-gate 的 AI advisor 预计算**（B036）；仍明确 NOT 交易执行/下单/broker；守门 `test_market_scheduler_scope.py`（允许 advisor import，禁 broker/ticket/execution）
- AI 边界（v0.9.28 5 子条）：B034 非生成式（embedding）；**B036 首次全量生成式触发，硬 enforce**（prompt + 输出校验 references ⊆ input set；过 B032 red-team gate）

## Framework 状态
- 最新版本 **v0.9.32**（2026-06-04 沉淀完成，B034 二例合并）：**请求路径 deploy-artifact 自包含铁律**——请求路径禁 import 根级 `scripts/` / 禁读 repo-root `data/fixtures/`（deploy artifact 只含 `workbench_api/` 包），数据须 materialise 入包；本地+CI 掩盖、唯 L2 真 VM 暴露。落地 generator.md §12.10 + evaluator.md §23（L2 必测核心新路由真 VM 200）+ signoff 模板 §L2 勾选行。
- B035 signoff §Framework Learnings 标「本批次无」（systemd-units-in-release 修复属已沉淀 v0.9.32 §12.10 同族，generator 已吸收+守门）。
- 仍 hold（等二例）：**B031 第三方 API live-validate**（B035 FRED/AV live-validate 成功未再撞，二例未达成；复用窗口 B036）+ B026 React event edge（单例）。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret 全配齐（`TIINGO_API_KEY` / `SEC_EDGAR_CONTACT_EMAIL` / `AIGC_GATEWAY_API_KEY` / `FRED_API_KEY` / `ALPHAVANTAGE_API_KEY`，均在 VM env）；Phase 2 无遗留 secret 缺口。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
