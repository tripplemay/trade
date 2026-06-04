# B034-news-ticker-embedding Signoff 2026-06-04

> 状态：**PASS**
> 触发：F004 fix-round 1 复验完成，production `/api/recommendations/news` 500 blocker 已解除。

---

## 变更背景

B034 在 B033 news ingest 基础设施上增加 news↔ticker/sleeve 关联层与 embedding 基建，为 B036 AI advisor MVP 提供可引用的 news URL / SHA 与结构化关联能力。本批次首次触发 AI 边界，但仍限定在非生成式检索基建，不产出 user-facing AI 文本。

---

## 变更功能清单

### F001：news_embedding 表 + NewsEmbedder (bge-m3) + 非生成式守门

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/db/models/news_embedding.py`
- `workbench/backend/workbench_api/db/repositories/news_embedding.py`
- `workbench/backend/workbench_api/db/migrations/versions/0006_b034_news_embedding.py`
- `workbench/backend/workbench_api/news/embedder.py`
- `workbench/backend/tests/unit/test_news_embedding_repo.py`
- `workbench/backend/tests/unit/test_news_embedder.py`
- `workbench/backend/tests/safety/test_b034_no_generative_ai.py`

**改动：**
新增 `news_embedding` 表、repository、`bge-m3` embedding 路径、离线 fixture 向量与非生成式守门。

**验收标准：**
- `0006_b034_news_embedding` 可升级可回退
- `news_embedding.vector` 保持 metadata-only、非 raw text
- embedding 路径不触发 `LLMGateway.chat`

### F002：ticker 字典匹配 + topic taxonomy + NewsAssociationService

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/news/ticker_match.py`
- `workbench/backend/workbench_api/news/topics.py`
- `workbench/backend/workbench_api/news/sleeve_tickers.py`
- `workbench/backend/workbench_api/news/association.py`
- `workbench/backend/tests/unit/test_news_association.py`
- `workbench/backend/tests/unit/test_news_ticker_match.py`
- `workbench/backend/tests/unit/test_news_topics.py`

**改动：**
实现确定性 ticker 匹配、topic taxonomy、sleeve constituents 与 hard match + cosine soft ranking 的 NewsAssociationService。

**验收标准：**
- 27 real ticker + 4 ETF universe 匹配稳定
- 纯 Python cosine 排序通过
- topic/source/form_type/since/limit 过滤正确

### F003：`GET /recommendations/news` + NewsPanel（纯结构化）

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/routes/recommendations.py`
- `workbench/backend/workbench_api/services/recommendations.py`
- `workbench/backend/workbench_api/schemas/recommendations.py`
- `workbench/frontend/src/components/recommendations/NewsPanel.tsx`
- `workbench/frontend/tests/unit/recommendations/NewsPanel.spec.tsx`
- `workbench/frontend/tests/e2e/b034-sleeve-news.spec.ts`

**改动：**
新增 auth-gated same-origin `GET /recommendations/news` 和前端 NewsPanel，渲染 title/source/date/url/topic/score 等纯结构化字段。

**验收标准：**
- 路由返回 `SleeveNewsResponse { items }`
- UI 无 free-form AI 文本
- Playwright 真栈 `/recommendations/news` 请求稳定

### F004：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B034-news-ticker-embedding-blocker-2026-06-04.md`
- `docs/test-reports/B034-news-ticker-embedding-signoff-2026-06-04.md`
- `docs/screenshots/B034-news-ticker-embedding/recommendations-news-200.png`
- `docs/screenshots/B034-news-ticker-embedding/alembic-0006.png`

**改动：**
首轮验收发现 production `/api/recommendations/news` 因运行时读取未部署 fixture 路径而 500。fix-round 1 改为将 universe materialise 成代码常量，复验通过后完成签收。

**验收标准：**
- L1 全门禁通过
- L2 `/api/recommendations/news` 从 500 恢复为 200
- `alembic_version=0006_b034_news_embedding`
- signoff、截图、状态机闭环完成

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 生成式 AI 建议 / advisor 文本 | 留给 B036 |
| 生产 ingest / scheduler / cron | 本批次明确禁止 |
| FRED / market context | 留给 B035 |
| pgvector / Cloud SQL | 本批次明确禁止 |
| embedding provider 迁移 | 本批次明确不做 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Recommendations news route | production 500 | production authenticated 200 |
| Sleeve universe 解析 | 运行时依赖未部署 fixture CSV | 代码常量，deploy artifact 内自包含 |
| News panel | 路由在 VM 不可用 | 纯结构化面板在 VM 可稳定返回 |

---

## 类型检查 / CI

```text
backend pytest: 646 passed, 2 skipped
backend safety guards: 12 passed
backend ruff: pass
backend mypy: Success: no issues found in 196 source files
alembic roundtrip: 0006 -> 0005 -> 0006 pass
frontend lint: pass
frontend typecheck: pass
frontend vitest: 176 passed
frontend Playwright: 39 passed
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | production `/api/health.version` = `ec0289495eaf10255c20064982ed33d554c5905b`；签收时 `main` HEAD = `d7ce15922548f6feb853f6ef5b14d0ff11c02d87`；`git diff --name-only ec02894..d7ce159` 仅 `.auto-memory/project-status.md`，产品代码无漂移，按 v0.9.25 接受等价 |
| 端到端流验证 | authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；authenticated `/api/protected-test` = `{"status":"ok","email":"tripplezhou@gmail.com"}`；authenticated `/api/recommendations/news?sleeve=satellite_us_quality` = `200 {"items":[]}` |
| 关键 invariant | `WORKBENCH_DB_URL=sqlite:///var/lib/workbench/db/workbench.db`；`alembic_version=0006_b034_news_embedding`；`news` + `news_embedding` 表存在；无 `workbench_api/news/scheduler.py`、无 news cron、无 workbench news systemd unit；`/var/lib/workbench/data/snapshots/news` 存在且为空 |
| 浏览器手动验（如 UI 类） | 本地 Playwright 真栈 `b034-sleeve-news.spec.ts` 通过；L2 证据截图见 `docs/screenshots/B034-news-ticker-embedding/` |

> B034 决策矩阵规定 production ingest 继续保持 fixture-first 不跑，因此 L2 不执行 ingest。验证重点是 Recommendations NewsPanel 路由可用且保持纯结构化。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing → reverifying → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `ec0289495eaf10255c20064982ed33d554c5905b` |
| Main HEAD (`git rev-parse HEAD`) | `d7ce15922548f6feb853f6ef5b14d0ff11c02d87` |
| Diff (`git log --oneline <deployed>..HEAD`) | `1 commit`：`d7ce159 chore(B034): F004 fix-round 1 deployed to production (ec02894); awaiting Codex L2 reverify` |

结论：production 与 `main` 不同 SHA，但差异仅为状态机元数据文件，产品代码无漂移，按 v0.9.25 接受等价。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本签收 commit 仅含 `progress.json`、`features.json`、`.auto-memory/**`、`docs/test-reports/**`、`docs/screenshots/**`，未推产品代码；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。 |

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

本批次不含 decommission。

---

## Soft-watch（不阻塞 done，需后续跟进）

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | `GET /api/recommendations/news` 当前 production 返回空数组，说明 route 与 auth 已恢复，但本批次仍保持 fixture-first / no-ingest 边界，未验证真实 news items 排序 | low | 在 B036 或后续受控 ingest 批次中，用真实 news 数据补一次结构化 relevance 验证 |

---

## Framework Learnings

### 新规律
- 请求路径不能依赖 repo-root `data/fixtures/*` 文件，也不能依赖仅在完整 checkout 中存在的运行环境。
  - 来源：B034 F004 fix-round 1，production deploy artifact 不含 fixture CSV，导致 `/api/recommendations/news` 500
  - 建议写入：`framework/harness/generator.md`

### 新坑
- 本地与 CI 都可能因完整 checkout 而掩盖 deploy-artifact 缺口；只有真 VM 会暴露请求路径的 runtime file dependency。
  - 来源：B034 F004 L2 blocker
  - 建议写入：`framework/README.md`

### 模板修订
- 本批次无额外模板修订。
