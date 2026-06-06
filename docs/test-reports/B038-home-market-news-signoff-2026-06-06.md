# B038 Home Market News Signoff 2026-06-06

> 状态：**PASS**
> 触发：B038 F003 fix-round 1 完成后复验通过

---

## 变更背景

B038 的真实目标不是再做一遍 market 指标卡，而是把 personas §2 mockup 里的“今日市场新闻”补到 Home 第三段。B037 已经把 market context 卡复用到 Home，本批补的是其下方的新闻列表，并首次把 news ingest 从 B033 的 production-disabled manual CLI 收编到边界 (r) 的 systemd timer。

---

## 变更功能清单

### F001：后端全局最新新闻 feed + workbench-news.timer

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/routes/news.py`
- `workbench/backend/workbench_api/services/news.py`
- `workbench/backend/workbench_api/db/repositories/news.py`
- `workbench/backend/workbench_api/schemas/news.py`
- `workbench/backend/workbench_api/news/cli.py`
- `workbench/deploy/systemd/workbench-news.service`
- `workbench/deploy/systemd/workbench-news.timer`

**改动：**
新增 auth-gated `GET /api/news/latest` 全局 newest-first metadata feed；把 news ingest 收编到 `workbench-news.{service,timer}`；fix-round 1 进一步修掉 `news.cli` 对 repo-root `scripts.universe_us_quality` 的运行时依赖，改为包内 self-contained universe 来源。

**验收标准：**
- authenticated `/api/news/latest` 返回结构化 `items[]`
- news timer 自动 install + enable，无手装
- `workbench-news.service` 在 production 真机可成功执行
- 保持 B034 非生成式边界与 §12.10 自包含

### F002：Home 第三段新闻元素

**Executor：** generator

**文件：**
- `workbench/frontend/src/components/home/HomeNewsPanel.tsx`
- `workbench/frontend/src/app/(protected)/page.tsx`
- `workbench/frontend/messages/en.json`
- `workbench/frontend/messages/zh-CN.json`

**改动：**
Home 第三段在 MarketContextCard 下方增加 HomeNewsPanel，自取 `/api/news/latest`，展示标题列表、source、日期、topic chips 与双语文案，保持 research-only。

**验收标准：**
- zh-CN / en 均显示新闻段
- 列表外链正确
- 无执行/下单按钮
- 旧 dashboard 与 B026 synthetic banner 均不复活

### F003：Codex L1 + L2 验收与签收

**Executor：** codex

**文件：**
- `docs/test-reports/B038-home-market-news-blocker-2026-06-06.md`
- `docs/test-reports/B038-home-market-news-signoff-2026-06-06.md`
- `docs/screenshots/B038-home-market-news/home-news-zh-CN.png`
- `docs/screenshots/B038-home-market-news/home-news-en.png`
- `docs/screenshots/B038-home-market-news/browser-check.json`

**改动：**
完成首轮 blocker、fix-round 1 复验、production API / systemd / browser 手验，并推进状态机到 `done`。

**验收标准：**
- L1 targeted guards 全 PASS
- `/api/news/latest` authed 200 + anon 401
- `workbench-news.timer` 自动接线 + `workbench-news.service` 真机成功
- Home 新闻段双语可见、外链正常、无下单按钮

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| AI 生成新闻摘要 | 本批不做；继续保持 B034 非生成式 |
| sleeve-scoped news | recommendations 页 NewsPanel 不动 |
| `/api/home` payload 形状 | 继续独立 `GET /api/news/latest` self-fetch，不折叠进 `/api/home` |
| B039 AI Advisor Home 演进 | 仍留给后续批次 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Home 第三段 | 只有 market 指标卡 + sleeves | market 指标卡下方新增今日市场新闻 |
| production news ingest | manual-only，默认不跑 | `workbench-news.timer` 每日只读拉取 |
| news CLI 运行路径 | 依赖 repo-root `scripts`，VM oneshot 会炸 | 完全走包内常量，自包含 |

---

## 类型检查 / CI

```text
backend targeted pytest: 45 passed
  - test_news_latest_feed.py
  - test_market_scheduler_scope.py
  - test_b034_no_generative_ai.py
  - test_news_no_scheduler.py
  - test_news_ingest_self_contained.py
frontend targeted vitest: 28 passed
  - tests/unit/home/HomeNewsPanel.spec.tsx
  - tests/safety/no-execution-buttons.spec.ts
artifact secret grep: 0 hits
generator handoff baseline gates:
  - backend pytest 794 / ruff 0 / mypy 0
  - frontend lint / typecheck / vitest / Playwright green
deploy workflow evidence:
  - Workbench Deploy run 27052861855 success
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | production `/api/health.version=d99c0af8c6a44cec44b3e4dcc1ca0e23cc21d54d`；签收前 `main HEAD=6aecc305701b6320f0db49247a5e19bf1a4d833f`，diff 仅 1 个 metadata commit，按 §Production/HEAD 接受等价不同步。 |
| 端到端流验证 | authenticated `/api/news/latest` 返回真实新闻列表（top 20 中前 8 条供 Home 渲染）；SSH `workbench-news.service` journal 显示 `saved=782 skipped_existing=86 errors=0`；`workbench-news.timer` 保持 `enabled + active(waiting)`。 |
| 关键 invariant | authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；anon `/api/news/latest` = `401`。 |
| 新增 user-facing 路由真 VM authenticated 200（v0.9.32 — B034 沉淀） | `curl -H "Cookie: __Secure-authjs.session-token=<temp>" https://trade.guangai.ai/api/news/latest` 返回 200，payload 含 `items[]`，字段集固定为 `news_id/title/source/url/published_at/topics`。 |
| 浏览器手动验（如 UI 类） | 用 headless Playwright 注入 production session cookie 与 `NEXT_LOCALE` 做 zh-CN/en 两轮只读手验；截图落在 `docs/screenshots/B038-home-market-news/home-news-{zh-CN,en}.png`，结构化结果落在 `browser-check.json`。两轮都确认 `home-news-card` 可见、`newsItemCount=8`、`buttonCount=0`、`syntheticBannerCount=0`、`dashboard-card-nav=0`、console/api errors 均为空。 |

> 说明：authenticated 验证继续采用 production env 派生的临时 Auth.js session cookie，不走真实 Google OAuth 交互；对本批 read-only API 和 Home 渲染验收已足够。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库直写 ops。production side effect 仅为只读 news ingest 正常写入其既有新闻表 / snapshot 路径，属于本批 feature 验真目标，不是越界 mutation。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing → reverifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `d99c0af8c6a44cec44b3e4dcc1ca0e23cc21d54d` |
| Main HEAD (`git rev-parse HEAD`) | `6aecc305701b6320f0db49247a5e19bf1a4d833f` |
| Diff (`git log --oneline <deployed>..HEAD`) | `6aecc30 chore(B038): F003 L2 blocker resolved + prod ingest verified -> reverifying` |

**等价性判断：**

`git diff --name-only d99c0af..6aecc30` 仅含：

- `.auto-memory/project-status.md`
- `docs/test-reports/B038-home-market-news-blocker-2026-06-06.md`
- `progress.json`

无 `workbench/**`、`docs/specs/**`、`framework/**` 等产品或 deploy-impacting 改动，因此 production 与当前 HEAD 产品等价，不阻断签收。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本次 signoff commit 仅含 signoff 报告、screenshots、`progress.json`、`features.json`、`.auto-memory/project-status.md` 等状态机/证据文件；不含产品代码或 deploy-impacting 改动。按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需额外 dispatch。 |

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

本批次不含新的 decommission 目标；仍复核既有 decommission 未回归：

| 检查项 | 状态 | 证据 |
|---|---|---|
| 旧 Home quant dashboard 未复活 | **是** | `browser-check.json` 中 `oldDashboardCount=0` |
| B026 synthetic banner 未复活 | **是** | `browser-check.json` 中 `syntheticBannerCount=0` |

---

## Soft-watch（不阻塞 done，需后续跟进）

无。

---

## Framework Learnings

建议 Planner 在 done 阶段评估是否把下面的规律显式沉淀进 §12.10 的表述：

- 既有 manual-only CLI / module 一旦被接入 production 运行路径（如 systemd timer），它及其 import 闭包都必须按 deploy-artifact 自包含规则重新审计，不能只审请求路径本身。

这是 B034 之后同族问题的又一个运行形态，但是否需要新增规则编号，应由 Planner 在 done 阶段统一裁定。

---

## Conclusion

可以签收。B038 已同时满足产品目标和运维目标：Home 第三段现有真实“今日市场新闻”列表，`/api/news/latest` 在 production 上返回结构化真实数据，`workbench-news.timer` 通过 B037-OPS1 durable 机制自动接线，`workbench-news.service` 真机运行成功且无 recent-errors。
