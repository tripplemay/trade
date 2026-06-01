---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B034-news-ticker-embedding：`verifying`**（2026-06-01；Phase 2 / Stream 2.B 第九个 batch）。在 B033 news 基础设施上加语义关联层，为 B036 AI advisor 提供 news↔sleeve 关联 + 可引用 news URL/SHA。spec `docs/specs/B034-news-ticker-embedding-spec.md`。**F001 ✅ done**（`news_embedding` 表 + alembic 0006 + NewsEmbedder bge-m3 + 离线 fixture 向量 + S1 env 闭合 + 非生成式守门；bge-m3 live-validate dim=1024）。**F002 ✅ done**（ticker_match + 确定性 topic taxonomy + sleeve_tickers + NewsAssociationService hard ∩ + 纯 Python cosine 软排序）。**F003 ✅ done**（`GET /recommendations/news` auth-gated 纯结构化 + 前端 NewsPanel topic chip/score/筛选/外链；backend pytest 638 / vitest 176 / Playwright 39 全绿；api.ts 重生）。**当前 sprint=F004（Codex evaluator）**：L1 全门禁 + AI 边界 + 永久边界守门 + alembic head=0006 / L2 真 VM（alembic current=0006 / HEAD≡main / B026 banner absence / NewsPanel 纯结构化截图 / Post-signoff Deploy）+ signoff。
- **B034 决策矩阵（2026-06-01 用户已批，★=用户拍板）：** Embedding=**bge-m3**（复用 B031 `LLMGateway.embed`；gateway 实际只暴露 bge-m3 非计划写的 Cohere）/ 存储=独立 `news_embedding` 表 vector 落 JSON + 应用内 cosine（SQLite + 禁 pgvector/Cloud SQL）/ ★生产 ingest=**保持 fixture-first 不跑**（B033 边界 (q) 不动）/ ★Ticker=**字典硬匹配 + cosine 软排序** / ★UI=**丰富面板** / Topic tagging=确定性非 LLM / AI 边界=**非生成式守门**（5 子条生成式约束落 B036）/ ¥≈0。
- **B034 首次触发 AI 边界，但仅非生成式检索基建**（embedding 只产向量、不产 user-facing AI 文本）；守门 `tests/safety/test_b034_no_generative_ai.py`。生成式建议 / `INSUFFICIENT_GROUNDING` / red-team 15 样本 → **B036**。
- **不做**：生成式 AI 建议（B036）/ 生产 ingest（保持 (q)）/ FRED（B035）/ pgvector / 换 embedding provider。
- 后续路径：B034（2.B 本批）→ B035（2.C market context）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。

## 已完成签收 + MVP 完工
- B001-B033 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：**B033 News Ingest signoff 2026-06-01**（1 fix-round；prod snapshot dir provision blocker→修复；SEC EDGAR + Yahoo RSS adapter + News schema + snapshot writer + CLI；边界 (p)(q)）；B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A）。

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
