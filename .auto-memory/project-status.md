---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B033-news-ingest：`done`**（2026-06-01；F004 已 signoff）。fix-round 1 修复的 production snapshot dir blocker 已复验通过：deploy.sh 在部署时 provision 持久路径 `/var/lib/workbench/data/snapshots/news` 并把 release 相对路径 symlink 到该目录；目录存在且为空，且不跑 ingest（边界 (q)）。L1 全 PASS：backend pytest 572 passed+2 skipped / ruff 0 / mypy 0 / frontend vitest 172 / Playwright 38。L2 全 PASS：production `/api/health.version`=`94a038b`，与 `main` HEAD `41d0dbe` 仅元数据差异、产品代码等价；authenticated recent-errors 0；alembic current=`0005_b033_news (head)`；无 scheduler.py / cron / systemd news fetch；B026 banner absence 保持。signoff：`docs/test-reports/B033-news-ingest-signoff-2026-06-01.md`；blocker 留档：`docs/test-reports/B033-news-ingest-blocker-2026-06-01.md`。遗留(非阻塞)：CLI DEFAULT_SNAPSHOT_ROOT 生产解析不准，B034 首跑 ingest 前须接 `WORKBENCH_NEWS_SNAPSHOT_DIR`。
- Phase 2 / Stream 2.A：为 B034 News↔ticker + B036 AI advisor MVP 提供 news ingest 基础设施。**不做** FRED（B035）/ News↔ticker（B034）/ Recommendations 渲染 / scheduled cron / 内联 raw text 入 DB / AI advisor。
- 决策矩阵（2026-05-28 用户已批）：Source=SEC EDGAR + Yahoo RSS 二源（FRED 留 B035）/ EDGAR form types=10-K+10-Q+8-K+Form 4 / Universe=US Quality 27 real (synthetic ZQ* skip) + 4 master ETFs / Ticker assoc 不做（留 B034）/ Production ingest=adapter+CLI（无 cron）/ Schema=metadata+snapshot path（raw 落 `data/snapshots/news/`）/ F 拆分=4 features (3g+1c) / 不引入新 secret（复用 B029 `SEC_EDGAR_CONTACT_EMAIL`） / Cost=¥0。
- 新增永久产品边界 (p) + (q)：(p) News raw text 仅落 snapshot path 不内联 DB（守门 `tests/safety/test_news_schema_metadata_only.py`）+ (q) News ingest 默认 production-disabled（无 `workbench_api/news/scheduler.py` + 无 cron + 无 systemd unit，守门 `tests/safety/test_news_no_scheduler.py`）。
- 本批次属 implementation-path-2026-05.md §4 **Phase 2 第八个 batch（Stream 2.A）**。
- 后续路径：B034（2.B embedding）→ B035（2.C market context）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。

## 已完成签收 + MVP 完工
- B001-B032 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（1 fix-round；OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A Layer 0→1 达成）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `94a038b235fa63598ac1f0dda7f73603810a039e`（签收时 `main` HEAD = `41d0dbe0f2bf2dd845a987e462b0903c47a9a589`，仅元数据差异，产品代码等价）；authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；AIGC_GATEWAY_API_KEY + TIINGO_API_KEY + SEC_EDGAR_CONTACT_EMAIL 已 VM env；`news` + `llm_budget_log` + `tiingo_budget_log` 表已存在；`/var/lib/workbench/data/snapshots/news` 已创建且为空；B026 banner decommissioned + `/strategies` `/reports` `/recommendations` `/risk` 均 `BANNER_ABSENT`。

## 永久硬边界（B033 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g) / B029 起 (h)(i)(j) / B030 起 (k) + v0.9.30 §12.9 / B031 起 (l)(m) / B032 起 (n)(o)：继续
- **B033 起 (p)(q)：** (p) News raw text 仅落 snapshot path 不内联 DB / (q) News ingest 默认 production-disabled（无 scheduler / 无 cron / 无 APScheduler import）
- AI 边界（v0.9.28 5 子条）：本批次不触 AI logic（仅 news raw ingest infra）；B034 起 news→embedding 才首次触发

## Framework 状态
- 最新版本 **v0.9.31**（2026-05-27 沉淀完成）：B030 Feature decommission 四处清理铁律。B033 signoff §Framework Learnings 标「本批次无」。**B031 第三方 API live-validate 候选仍 hold 等二例合并**——B033 F002（SEC EDGAR）按建议主动 live-validate，未再撞 spec-invented-endpoint，二例未达成，v0.9.32 不沉淀。B026 React event edge 仍单一案例 hold。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY` + `SEC_EDGAR_CONTACT_EMAIL` + `AIGC_GATEWAY_API_KEY` 已配；B033 不引入新 secret。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
