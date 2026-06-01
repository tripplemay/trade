# B033-news-ingest Signoff 2026-06-01

> 状态：**PASS**
> 触发：F004 fix-round 1 复验完成，production snapshot 目录 blocker 已解除。

---

## 变更背景

B033 为后续 B034 News↔ticker 与 B036 AI advisor MVP 提供 news ingest 基础设施。范围限定为 SEC EDGAR + Yahoo RSS 两 source 接入、metadata-only news schema、snapshot 文件落盘、manual CLI 入口，以及 production 默认 disabled 的硬边界。

---

## 变更功能清单

### F001：News schema + Repository + alembic migration + NewsSnapshotWriter + NewsAdapter Protocol

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/db/models/news.py`
- `workbench/backend/workbench_api/db/repositories/news.py`
- `workbench/backend/workbench_api/db/migrations/versions/0005_b033_news.py`
- `workbench/backend/workbench_api/news/snapshot.py`
- `workbench/backend/workbench_api/news/adapters/base.py`
- `workbench/backend/tests/unit/test_news_repository.py`
- `workbench/backend/tests/unit/test_news_snapshot.py`
- `workbench/backend/tests/safety/test_news_schema_metadata_only.py`

**改动：**
新增 `news` 表、Repository、snapshot writer、adapter protocol，并以 safety test 锁定 raw text 不入库的永久边界。

**验收标准：**
- `news` schema、repository、snapshot writer、adapter protocol 全部落地
- alembic `0005_b033_news` 可升级可回退
- `test_news_schema_metadata_only.py` 守住 metadata-only 边界

### F002：SEC EDGAR adapter (10-K / 10-Q / 8-K + Form 4)

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/news/adapters/sec_edgar.py`
- `workbench/backend/tests/unit/test_news_adapter_sec_edgar.py`
- `data/fixtures/news/edgar-sample-*.json`

**改动：**
新增 SEC EDGAR adapter，复用既有 contact email / 节流模式，覆盖指定 form types，fixture-first 验证。

**验收标准：**
- `/submissions/CIK*.json` envelope 解析正确
- `10-K / 10-Q / 8-K / 4` 过滤正确
- synthetic `ZQ*` ticker 跳过且告警

### F003：Yahoo Finance RSS adapter + CLI 入口 + 永久边界 (q) 守门

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/news/adapters/yahoo_rss.py`
- `workbench/backend/workbench_api/news/cli.py`
- `workbench/backend/tests/unit/test_news_adapter_yahoo.py`
- `workbench/backend/tests/unit/test_news_cli.py`
- `workbench/backend/tests/safety/test_news_no_scheduler.py`
- `data/fixtures/news/yahoo-sample-*.xml`
- `data/snapshots/news/README.md`

**改动：**
新增 Yahoo RSS adapter、manual CLI fetch 入口、`feedparser` runtime 依赖，以及 production-disabled 边界守门。

**验收标准：**
- Yahoo RSS 解析、snapshot 落盘、CLI dispatch 正常
- 无 `scheduler.py`、无 APScheduler import、无 cron/systemd news fetch
- runtime dependency 守门通过

### F004：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B033-news-ingest-blocker-2026-06-01.md`
- `docs/test-reports/B033-news-ingest-signoff-2026-06-01.md`
- `docs/screenshots/B033-news-ingest/alembic-current.png`
- `docs/screenshots/B033-news-ingest/snapshot-dir.png`

**改动：**
首轮验收发现 production 缺 `data/snapshots/news/` 目录并形成 blocker。fix-round 1 复验确认 deploy 时已创建持久目录并完成签收。

**验收标准：**
- L1 回归全绿
- L2 health / recent-errors / alembic / snapshot dir / no scheduler 全满足
- signoff、截图、状态机闭环完成

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| News↔ticker 关联 | 留给 B034 |
| FRED / market context | 留给 B035 |
| Recommendations 渲染 / AI advisor | 留给 B036 |
| Scheduled cron / auto ingest | 本批次明确禁止 |
| Raw text 入 DB | 本批次明确禁止 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| News snapshot 目录 | production 缺失，F004 L2 fail | deploy 自动 provision，目录存在且为空 |
| Ingest 运行边界 | 无专用守门 | metadata-only + no scheduler/cron/systemd 守门齐备 |
| 后续 B034 基础 | 不完整 | 已具备 news schema / adapters / CLI / snapshot path |

---

## 类型检查 / CI

```text
backend pytest: 572 passed, 2 skipped
backend ruff: pass
backend mypy: Success: no issues found in 180 source files
deploy.sh syntax: bash -n pass
frontend vitest: 172 passed
frontend Playwright: 38 passed
GitHub Actions: 本次签收未新增产品代码；未要求额外 workflow gate
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | production `/api/health.version` = `94a038b235fa63598ac1f0dda7f73603810a039e`；签收时 `main` HEAD = `41d0dbe0f2bf2dd845a987e462b0903c47a9a589`；经 `git diff --name-only 94a038b..41d0dbe` 仅有 `.auto-memory/project-status.md` 与 `progress.json`，产品代码无漂移，按 v0.9.25 接受等价 |
| 端到端流验证 | authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；authenticated `/api/protected-test` = `{"status":"ok","email":"tripplezhou@gmail.com"}` |
| 关键 invariant | `alembic current` = `0005_b033_news (head)`；`/srv/workbench/current/data/snapshots/news` 解析到 `/var/lib/workbench/data/snapshots/news`，目录存在且为空；无 `workbench_api/news/scheduler.py`、无 news cron、无 workbench news systemd unit |
| 浏览器手动验（如 UI 类） | B026 banner absence HTML grep：`/strategies` `/reports` `/recommendations` `/risk` 均 0 hits；截图见 `docs/screenshots/B033-news-ingest/` |

> 本批次 L2 不包含 production ingest 执行。边界 (q) 要求 production-disabled，因此以目录存在且为空、且无 scheduler/cron/systemd 作为物理验证。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → reverifying → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `94a038b235fa63598ac1f0dda7f73603810a039e` |
| Main HEAD (`git rev-parse HEAD`) | `41d0dbe0f2bf2dd845a987e462b0903c47a9a589` |
| Diff (`git log --oneline <deployed>..HEAD`) | `1 commit`：`41d0dbe chore(B033-F004): confirm deploy 94a038b succeeded; VM snapshot dir provisioned` |

结论：production 与 `main` 不同 SHA，但差异仅为状态机元数据文件，产品代码无漂移，按 v0.9.25 接受等价，无需因该差异阻塞签收。

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
| S1 | `workbench_api/news/cli.py` 的默认 snapshot root 在 production wheel/install 路径下解析不稳；本批次未在 production 执行 CLI ingest，因此不阻塞 B033 | low | B034 首次真实执行 ingest 前，将 CLI 默认 snapshot root 显式接到 `WORKBENCH_NEWS_SNAPSHOT_DIR` |

---

## Framework Learnings

本批次无 framework learnings。
