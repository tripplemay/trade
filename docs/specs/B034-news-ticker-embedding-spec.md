# B034 — News ↔ ticker / sleeve 关联 + Embedding（Phase 2 / Stream 2.B）

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态流转：** planning → building → verifying → (fixing ⟷ reverifying) → done
> **依赖：** B033 News Ingest（✅ done）+ B031 LLM Gateway（✅ done，`LLMGateway.embed`）
> **决策对齐：** 2026-06-01 用户已批（见 §2）

---

## 1. 目标

为 B033 落地的 news 基础设施加一层**语义关联**：把 news 与 universe 的 ticker / strategy sleeve 关联起来，并在 Recommendations 页呈现「影响本 sleeve 的近期 news」。本批次是项目**首次触发 AI 边界**（news → embedding），但仅限**非生成式检索基建**——embedding 只产生向量、不产生任何 user-facing AI 文本；生成式 AI 建议（含 `INSUFFICIENT_GROUNDING` fallback / 收益预测禁令等 v0.9.28 5 子条）留到 B036。

为 B036 AI advisor MVP 提供：news↔sleeve 关联结果 + 可引用 news URL/SHA（ai-safety §2 β「无引用 hallucinate」red-team 的 input 依赖）。

**不做**（见 §6）：生成式 AI 建议文本 / 生产 ingest（保持 B033 边界 (q)）/ FRED 宏观（B035）/ pgvector 或 Cloud SQL / 自动调度。

## 2. 决策矩阵（2026-06-01 用户已批）

| # | 决策 | 取值 | 依据 |
|---|---|---|---|
| 1 | Embedding 模型 | **bge-m3**（复用 B031 `LLMGateway.embed` + `/v1/embeddings`）| gateway 实际只暴露 bge-m3（`llm/routing.py:60`），非 implementation-path 写的 Cohere；复用 B031 基建，避免再引 provider。**B031 「计划命名 vs 真实 API」教训的复用窗口** |
| 2 | Embedding 存储 | **独立 `news_embedding` 表，vector 落 JSON + 应用内 cosine** | 生产 DB 是 SQLite + 永久边界禁 Cloud SQL/pgvector；universe 31 ticker + 有限 news，暴力 cosine 足够；独立表保持 News 表 metadata-only（边界 (p)）+ 支持换模型重嵌 |
| 3 | 生产 ingest | **保持 fixture-first，不跑生产 ingest，边界 (q) 不动**（无 cron/scheduler/systemd）| 用户拍板。embedding 跑在 fixture/快照 news 上；CI 离线 |
| 4 | Ticker 抽取 | **字典硬匹配 + embedding cosine 软排序** | 用户拍板。硬关联落 B033 已备 `ticker_mentions` JSONB；软排序补语义召回 |
| 5 | Recommendations UI | **丰富面板**：topic tag + 相关度排序 + source/form_type/topic 筛选 | 用户拍板。same-origin `/api/*`、auth-gated、纯只读、**无 AI 文本** |
| 6 | Topic tagging | **确定性规则/分类**（form_type + 关键词 taxonomy），不走生成式 LLM | 保持生成式 AI 留到 B036 |
| 7 | AI 边界（v0.9.28 首触发）| embedding+tagging 属非生成式检索基建；spec 明示无 user-facing AI 文本 + 守门测试；5 子条生成式约束落 B036 | v0.9.28 / positioning §6.1 / ai-safety §2(β) |
| 8 | CI / Cost | fixture-first 离线：fixture embedding 向量入库，live gateway 仅 manual validate；¥≈0 | 继承 B032/B033 fixture-first |

## 3. 永久硬边界（B033 起继续 enforced + B034 AI 边界首触发）

- **系统层（继承）：** no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / **Cloud SQL 禁（⇒ embedding 不得用 pgvector / Postgres extension）** / same-origin `/api/*` / auth-gated / Repository。
- **数据层（B033 (p)(q) 继续）：** (p) raw text 仅落 snapshot path 不内联 DB（`news_embedding.vector` 是向量非 raw text，不违反）；(q) ingest 默认 production-disabled（本批次不新增 scheduler/cron/systemd）。
- **AI 边界（v0.9.28 5 子条，B034 首触发——但仅非生成式）：**
  - 本批次**只做 embedding 向量化 + 确定性 topic tagging + cosine 检索**，**不产生任何 user-facing AI 生成文本 / 收益预测 / 个股推荐结论**。
  - 守门：`tests/safety/test_b034_no_generative_ai.py` 断言 news 关联路径不调用 `LLMGateway.chat` / 不产出 free-form 建议文本；Recommendations news 面板渲染纯结构化字段（title/source/date/url/topic/score），无 LLM 生成段落。
  - `INSUFFICIENT_GROUNDING` fallback / red-team 15 样本 / quant_signal_sha 引用契约 = **B036 范围**，本批次只产出 B036 将引用的 news URL/SHA 数据。

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/
├── db/
│   ├── models/news_embedding.py          # F001 新增：NewsEmbedding 表
│   ├── repositories/news_embedding.py    # F001 新增：NewsEmbeddingRepository
│   └── migrations/versions/0006_b034_news_embedding.py  # F001 down_revision=0005_b033_news
├── news/
│   ├── embedder.py                       # F001 新增：NewsEmbedder（复用 LLMGateway.embed bge-m3）
│   ├── ticker_match.py                   # F002 新增：确定性 ticker 字典匹配
│   ├── topics.py                         # F002 新增：确定性 topic taxonomy
│   └── association.py                    # F002 新增：NewsAssociationService（hard match + cosine rank）
├── schemas/recommendations.py            # F003 扩：SleeveNewsItem / SleeveNewsResponse
└── routes/recommendations.py            # F003 扩：GET /recommendations/news

workbench/frontend/src/app/(protected)/recommendations/
└── （F003）NewsPanel 组件 + topic tag + 相关度排序 + 筛选

data/fixtures/news/
├── embeddings-bge-m3-sample.json         # F001：预录 fixture 向量（CI 离线）
└── （复用 B033 edgar/yahoo fixtures 作为 news 源）
```

### 4.2 `news_embedding` 表 schema（F001）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID PK | `_UuidString` TypeDecorator（跨 SQLite/PG，复用 B033 News pattern）| |
| news_id | UUID FK → news.id | NOT NULL, ON DELETE CASCADE | |
| model | TEXT | NOT NULL | e.g. `'bge-m3'` |
| dim | INT | NOT NULL | 向量维度（bge-m3=1024）|
| vector | JSON | NOT NULL | `list[float]`；`JSON().with_variant(JSONB,'postgresql')`（PG 时 JSONB，SQLite JSON）|
| created_at | DateTime(tz=True) | NOT NULL | |

- **Unique constraint** `uq_news_embedding_news_model (news_id, model)` — 同一 news + 同一 model 幂等。
- **Index** `ix_news_embedding_news_id`。
- alembic `0006_b034_news_embedding`，`down_revision='0005_b033_news'`；upgrade head → downgrade -1（目标显式 `'0005_b033_news'`，遵 B033 F001 教训不用 `-1`/`head` 字面）。

### 4.3 NewsEmbedder（F001）

- `NewsEmbedder(gateway: LLMGateway, repo: NewsEmbeddingRepository)`；`embed_pending(news: list[News], model='bge-m3') -> int`：对缺 embedding 的 news 取 `title + ' ' + (summary or '')` 调 `gateway.embed(texts)` → `save_if_new`（幂等 by (news_id, model)）。
- **CI 离线：** 测试注入 fake/recorded embedding（fixture `embeddings-bge-m3-sample.json` 预录向量 or stub gateway），**不打真 API**；live gateway 仅 generator 本地 manual validate 一次（验证 bge-m3 维度 + envelope，写守门 test 锁 dim=1024）。
- **S1 soft-watch 闭合（B033 遗留）：** 本批次顺手把 `news/cli.py` 的 `DEFAULT_SNAPSHOT_ROOT` 接到环境变量 `WORKBENCH_NEWS_SNAPSHOT_DIR`（默认回落到 repo-relative），**不在生产执行**；解除 B033 signoff §Soft-watch S1。

### 4.4 Ticker 匹配 + Topic taxonomy（F002）

- **`ticker_match.py`：** 从 universe（US Quality 27 + 4 ETF）构建 `{ticker, 公司名/别名} → ticker` 确定性字典 + SEC 已知 CIK→ticker 映射；对 news `title + summary` 大小写无关全词匹配 → 写 `news.ticker_mentions`（JSONB list）。synthetic ZQ* 不入字典。
- **`topics.py`：** 确定性 taxonomy（**非 LLM**）：
  - form_type 映射：`10-K`/`10-Q` → `财报`；`8-K` → `重大事件`；`4` → `内部人交易`。
  - 关键词规则（Yahoo RSS title）：dividend→`股息` / guidance→`业绩指引` / upgrade·downgrade→`评级变动` / merger·acquisition→`并购` 等（规则表内联，可扩）。
  - 一条 news 可多 topic；无命中 → `其他`。
- **`association.py` — `NewsAssociationService`：**
  - `news_for_sleeve(sleeve: str, *, limit, since, topic?, source?, form_type?) -> list[SleeveNewsRelevance]`。
  - **硬关联：** sleeve 的成分 ticker（来自 strategies service）∩ `news.ticker_mentions` → 命中。
  - **软排序：** `cosine(news_embedding, sleeve_query_embedding)`；sleeve_query 由 sleeve 标签 + 成分 ticker 名构造并经同一 bge-m3 嵌入（fixture 离线）。
  - **score** = 硬命中加权 + cosine；返回带 `matched_tickers / topics / score / news(title,source,url,published_at,content_sha256)`。

### 4.5 API + 前端（F003）

- **`GET /recommendations/news`**（auth-gated, same-origin）：query `sleeve`(必填) / `topic?` / `source?` / `form_type?` / `limit?`；返回 `SleeveNewsResponse { items: SleeveNewsItem[] }`，`SleeveNewsItem = { news_id, title, source, url, published_at, content_sha256, topics[], matched_tickers[], score }`。**纯结构化、无 AI 文本。**
- **前端 NewsPanel**（Recommendations 页）：每 sleeve 下丰富面板 —— topic tag chips + 相关度（score）排序 + source/form_type/topic 筛选器 + 外链 URL（`rel="noopener noreferrer"`）。

### 4.6 Fixture（CI 离线）

- 复用 B033 `data/fixtures/news/edgar-sample-*.json` + `yahoo-sample-*.xml` 作 news 源。
- 新增 `embeddings-bge-m3-sample.json`：预录每条 fixture news 的 bge-m3 向量（+ sleeve_query 向量），CI cosine 可复现。
- 不打真 gateway / 真 SEC / 真 Yahoo。

### 4.7 安全 / regression test 矩阵

| 测试 | 守门 |
|---|---|
| `tests/safety/test_b034_no_generative_ai.py` | news 关联路径不调 `LLMGateway.chat`；面板字段无 free-form AI 文本（v0.9.28 / 边界 §3）|
| `tests/safety/test_news_schema_metadata_only.py`（B033 既有，扩集）| News 表仍无 raw_text/body/content；`news_embedding.vector` 是向量非 raw text |
| `tests/safety/test_news_no_scheduler.py`（B033 既有）| 仍无 scheduler.py / cron / apscheduler import（边界 (q)）|
| `test_critical_runtime_deps_pinned.py` | 若引入新 runtime dep（如 numpy 做 cosine）须 pin（v0.9.29 §12.8）；优先纯 Python 实现避免新 dep |
| secret grep | 不引入新 secret（复用 AIGC_GATEWAY_API_KEY；grep .env.example/config.py/deploy.sh/bootstrap-env.yml 0 新增）|

## 5. Feature 拆分

### F001 — Embedding 基建（generator，2 天）
News embedding 表 + repository + alembic 0006 + NewsEmbedder（bge-m3 复用 B031）+ fixture 向量 + S1 env 闭合 + 非生成式守门。详见 features.json。

### F002 — News↔ticker/sleeve 关联 + topic tagging（generator，2-3 天）
确定性 ticker 字典匹配 + 确定性 topic taxonomy + NewsAssociationService（hard match + cosine 软排序）+ repository/service 测试。详见 features.json。

### F003 — Recommendations 丰富面板（generator，2 天）
`GET /recommendations/news` API + 前端 NewsPanel（topic tag + 相关度排序 + 筛选）+ vitest + Playwright。详见 features.json。

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1 天）
L1 全门禁 + AI 边界守门 + L2 真 VM（alembic head=0006 / 仍无 scheduler / HEAD≡main / B026 banner absence / Recommendations 面板纯结构化无 AI 文本）。详见 features.json。

## 6. 不做的事（YAGNI）

- 生成式 AI 建议文本 / 收益预测 / 个股推荐结论 → **B036**。
- `INSUFFICIENT_GROUNDING` fallback / red-team 15 样本执行 → **B036**。
- 生产 news ingest（cron/scheduler/真实拉取）→ 仍保持 B033 边界 (q)。
- FRED / Alpha Vantage market context → **B035**。
- pgvector / 专用向量库 / ANN 索引 → 暴力 cosine 足够（小 universe）。
- 换 embedding provider（Cohere/OpenAI）→ 复用 gateway bge-m3。

## 7. 验收门槛汇总

| 门禁 | 阈值 |
|---|---|
| backend pytest | F001 ≥ baseline+≥12 / F002 ≥ +≥10 / F003 ≥ +≥6（B033 收尾 baseline 572 passed）|
| frontend | vitest ≥172（+ NewsPanel 新增）/ Playwright ≥38（+ 面板 e2e）/ lint 0 / typecheck pass |
| ruff / mypy | exit 0 |
| alembic | upgrade head（0006_b034_news_embedding）+ downgrade 到 0005_b033_news 可逆 |
| 安全守门 | §4.7 全过；**AI 边界非生成式守门**；无新 secret；无 scheduler |
| AI Safety Eval workflow | 不破（本批次未触生成式 LLM advisory，但若 paths 命中 llm/ 需保证 workflow 绿）|

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 2 / Stream 2.B（B034 行）
- `docs/product/llm-provider-evaluation-2026-05.md` §4 Embedding 选型（bge-m3 vs Cohere 现实）
- `docs/product/ai-safety-evals-2026-05.md` §2 (β) 无引用样本（B034 产出 B036 将引用的 news URL/SHA）
- `docs/product/positioning-2026-05.md` §6.1 AI 永久边界 5 子条
- `docs/specs/B033-news-ingest-spec.md`（News 表 / adapter / snapshot / fixture pattern）+ signoff §Soft-watch S1
- `workbench_api/llm/gateway.py`（`LLMGateway.embed`）+ `llm/routing.py`（bge-m3 路由）
- framework v0.9.28（AI 边界 5 子条 + spec acceptance 模板）/ v0.9.29 §12.8（runtime dep）/ v0.9.30 §12.9（secret 三处接线，本批次无新 secret）

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| bge-m3 真实维度 / envelope 与假设不符 | F001 generator 本地 live-validate 一次锁 dim=1024 + envelope，写守门 test（参 B031 教训）|
| cosine 纯 Python 慢 / 引入 numpy 成新 dep | universe 小，纯 Python list cosine 足够；若用 numpy 须 pin（§4.7）|
| sleeve→ticker 映射来源不清 | F002 wire 到 strategies service 既有 sleeve/ticker；spec 锁 service 契约，测试用 fixture sleeve |
| 误把 embedding 当 AI 生成 → 触发 v0.9.28 生成式约束 | §3 明示非生成式 + 守门测试；spec/commit 明确区分 |
| Recommendations 面板渲染夹带 AI 文本 | 面板纯结构化字段；`test_b034_no_generative_ai` + 前端断言守门 |

## 10. 与既有批次的边界

- **不动** B033 News 表 schema / adapters / snapshot writer（只新增 `news_embedding` 表 + 读 News）。
- **不动** B031 LLMGateway（只复用 `embed`）/ B032 AI Safety Eval workflow。
- **不动** 既有 strategies / risk / execution / tickets / B026 banner decommissioned 状态。
- Recommendations 路由**只新增** `GET /recommendations/news`，不改 `/current` `/export-ticket`。

## 11. 后续批次（不在 B034 范围）

- **B035**（Stream 2.C）：Market context FRED + Alpha Vantage。
- **B036**（Stream 3.C）：AI advisor MVP —— 整合 quant signal + real data + **B034 news 关联结果** → 生成式建议含 quant_signal_sha + news_urls 引用；`INSUFFICIENT_GROUNDING` fallback；通过 ai-safety red-team 15 样本 = **🎯 里程碑 B Phase 2 终点**。
