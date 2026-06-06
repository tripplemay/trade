# B038 — Home 今日市场新闻（Phase 3 / Stream 4.B）

> **状态：** planning（2026-06-06 起草）。
> **批次类型：** 新功能（Phase 3 产品 roadmap S4.B）。
> **配套权威设计：** `docs/product/user-personas-and-journeys-2026-05.md` §2 Daily Journey mockup（design-draft/ 空，以 personas mockup 为权威，同 B037）。

---

## 1. 目标与范围再定义

roadmap S4.B 原文「Home 整合 market context（来自 B035）：Home 第三段渲染 market 指标卡片」。**经 building-前 codebase 核查（2026-06-06）：B037 的复用决策已把 `MarketContextCard`（6 个 B035 宏观系列）真实接入 Home 第三段——字面目标已提前完成。**

personas §2 mockup 的「📰 Today's market context」段含**两部分**：① 市场指标（S&P/QQQ/10y…，**已由 B037 渲染**）+ ② **今日市场新闻标题**（`Fed minutes released` / `TSMC reports Q1 earnings beat`，**Home 上尚无**）。

**因此 B038 真实范围（2026-06-06 用户已批）= 把今日市场新闻搬上 Home 第三段**，补齐 mockup 真实 gap。复用 B033 news 数据 + B034 association/embedding 基础。

---

## 2. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| B038 范围 | ★ **重定为「Home 今日市场新闻」** | 字面市场指标卡片 B037 已完成；真实 gap 是 mockup 新闻段 |
| 生产新闻新鲜度 | ★ **放开边界 (q)：加 news ingest timer** | `workbench-news.timer` 每日只读拉取，归边界 (r) 同类；否则 Home 新闻生产为空。B037-OPS1 使其 deploy 自动接线零成本 |
| endpoint 形态 | **独立 `GET /api/news/latest`（self-fetch）** | 与 MarketContextCard(/api/market-context) / AdvisorSection(/api/advisor) 同模式，不折叠进 /api/home |

---

## 3. 永久硬边界（继承 + 本批修订）

**继承不破：**
- no-broker / no-execution / same-origin /api/* / auth-gated / Repository。
- **B033 边界 (p) 不破**：news raw text 仅落 snapshot path 不内联 DB（新 feed 只读 metadata 行，守门 `test_news_schema_metadata_only` 不破）。
- **B034 非生成式边界不破**：Home 新闻段纯 metadata（title/source/url/published_at/topics/matched_tickers），**无 AI 生成摘要**（守门 `test_b034_no_generative_ai` 字段集不破）。
- **UI no-execution**：Home 新闻段无下单/执行按钮 + 中文禁词同级守门（扩 Home 既有 guard）。

**本批修订（★用户已批）：边界 (q) → (r) 收编：**
- 旧 (q)：「News ingest 默认 production-disabled（无 scheduler/cron/APScheduler）」。
- 新：**news ingest 纳入边界 (r) 的「只读市场数据拉取」**——允许 **systemd timer**（外部 systemd，read-only SEC EDGAR + Yahoo RSS 拉取），与 market-context/advisor/prices timer 同机制。
- **仍明确 NOT**：① in-process scheduler（`workbench_api/news/scheduler.py` 仍禁、apscheduler/aiocron/schedule import 仍禁——守门 `test_news_no_scheduler` 保留，systemd timer 不触发其断言）；② 交易执行/下单/broker。
- `test_market_scheduler_scope.py` 扩：允许 news ingest import，仍禁 broker/order_ticket/execution/tickets/fills/reconcile。

---

## 4. 技术架构

### 4.1 后端 — 全局最新新闻 feed

- **Repository**：`NewsRepository` 新增 `list_latest_global(*, limit=20, since=None, source=None, form_type=None) -> list[News]`（跨 ticker，newest-first，无 sleeve scoping）。
- **Service**：`services/news.py` `build_latest_news(session, *, limit, ...)`——按 recency + 可选 topic/source 过滤，**不做 ticker 匹配 / 不需 sleeve 上下文**；输出 metadata-only items。复用 `tag_topics()` 确定性 topic 标签（非 AI）。
- **Schema**：`schemas/news.py` `LatestNewsResponse { items: [LatestNewsItem] }`，`LatestNewsItem` 复用 B034 字段子集（news_id/title/source/url/published_at/topics）—— **去掉 matched_tickers/score**（无 sleeve 语境）或保留 tickers（mention）。守 B034 非生成式字段集。
- **Route**：`routes/news.py` `GET /api/news/latest`（auth-gated, same-origin）→ build_latest_news；app.py 注册；next.config PROXIED_PREFIXES + dev-rewrites guard + regen api.ts。
- **§12.10 自包含**：请求路径不读 repo-root，新 feed 走 DB repo。

### 4.2 后端 — news ingest timer（边界 (q)→(r)）

- `deploy/systemd/workbench-news.{service,timer}`（每日 oneshot，read-only，镜像 `workbench-market-context.*`）；ExecStart 跑现有 `python -m workbench_api.news.cli fetch --source=all`（B033 CLI，复用，request_spacing/budget guard）。
- **零 deploy.sh / sudoers 改动**：B037-OPS1 的 `workbench-*.timer` 循环 + sudoers 通配符自动覆盖 `workbench-news.timer`（本批首次验证 durable 价值）。
- scheduler scope 守门扩 news；`test_news_no_scheduler` 仍绿（systemd 非 in-process）。

### 4.3 前端 — Home 新闻元素

- Home 第三段（`(protected)/page.tsx`）MarketContextCard **下方**加新闻元素：改造 `NewsPanel`→去 sleeve 下拉的 `HomeNewsPanel`（或参数化 NewsPanel 接受可选 sleeve，None=global），self-fetch `GET /api/news/latest`。
- 渲染 compact 列表（mockup §2：标题 + source + 日期，外链 target=_blank rel=noopener），top N（默认 5-8）；loading/empty/error 三态；**双语 zh-CN + en**。
- 对齐 personas §2 mockup「📰 Today's market context」段位置（指标卡 + 新闻列表同段）。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 后端：全局 news feed（repo+service+schema+`GET /api/news/latest`）+ `workbench-news.timer`（边界 (q)→(r)）+ scope 守门扩 news + pytest |
| F002 | generator | 前端：Home 第三段新闻元素（HomeNewsPanel self-fetch）+ 双语 + no-execution 守门扩 + vitest + Playwright Daily Journey 更新 |
| F003 | codex | L1 + L2 真 VM 验收（`/api/news/latest` 200 + `workbench-news.timer` 自动接线 enabled + Home 新闻段浏览器手验 + 双语 + 边界守门）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做 AI 生成新闻摘要（守 B034 非生成式；摘要类是 B039/B043 范畴）。
- 不做 sleeve-scoped 新闻改动（recommendations 页 NewsPanel 不动）。
- 不把 news 折叠进 `/api/home` payload（独立 endpoint）。
- 不改 B035 market-context / B037 三段 Home 结构（仅在第三段加新闻元素）。
- 不触 B039 AI Advisor 段 / Reports·Rec·Risk 重构。
- 不放开 in-process scheduler（仅 systemd timer）。

---

## 7. 验收门槛汇总

- **F001**：repo `list_latest_global` + service + `GET /api/news/latest`(auth 200 / anon 401 / schema pin) + `workbench-news.{service,timer}` 单元 + scope 守门含 news；backend pytest ≥ baseline+≥10；ruff/mypy 0；§12.10 自包含；边界 (p) metadata-only + B034 非生成式字段集守门不破；`test_news_no_scheduler` 仍绿。
- **F002**：Home 第三段新闻元素渲染（top N 标题+source+日期+外链）+ loading/empty/error 三态 + 双语齐 + no-execution 守门扩 Home（无下单按钮+中文禁词）；frontend vitest ≥ baseline+ / lint 0 / typecheck；Playwright Daily Journey 加新闻段可见断言（双 locale）；不破 B037 Home 结构。
- **F003**：L1 全门禁 + secret grep 0；L2（真 VM）：`GET /api/news/latest` authenticated 200 + 结构化 payload（v0.9.32 §23）；anon 401；**`workbench-news.timer` 经 B037-OPS1 deploy 循环自动 enabled+active（无手装、无 warn——验证 §24 + B037-OPS1 durable）**；手动 trigger `workbench-news.service` 验真（有新闻行 / 或 SEC-rate-limit 合规空，记录哪种）；Home 新闻段浏览器手验对齐 mockup + 双语 + 无下单按钮；health 200 / recent-errors=0 / HEAD≡main；signoff 用模板（§24 timer 接线勾选 + §L2 新路由 200 + §Production/HEAD + §Post-signoff Deploy）+ ≥1 截图（Home 新闻段）。

---

## 8. 参考文档

- 权威 mockup：`docs/product/user-personas-and-journeys-2026-05.md` §2（line 50-53 新闻段）
- B033 news ingest（边界 p/q）：`docs/specs/` B033 + `workbench_api/news/cli.py` / `db/models/news.py` / `db/repositories/news.py`
- B034 association/embedding：`workbench_api/news/association.py` / `schemas/recommendations.py`（SleeveNewsItem 字段参考）/ `components/recommendations/NewsPanel.tsx`
- B035 market-context timer 镜像：`deploy/systemd/workbench-market-context.*`
- B037-OPS1 durable timer 接线：`docs/specs/B037-OPS1-...-spec.md` + `deploy.sh` 循环 + sudoers 通配符
- evaluator.md §24（新 timer L2 接线检查）/ §23（新路由 L2 200）

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 生产新闻表空（feature 看似坏） | ★放开 (q) 加 news timer 每日拉取；F003 L2 验 timer 自动接线 + 手动 trigger 验真 |
| 边界 (q)→(r) 收编误读为放开 in-process scheduler | spec §3 明确仅 systemd timer；`test_news_no_scheduler` 保留 + scope 守门；project-status §永久硬边界同步修订 |
| SEC EDGAR rate-limit / Yahoo RSS 空窗 | 复用 B033 CLI 既有 request_spacing + budget guard；空结果→Home empty 态合规（记录） |
| B034 非生成式边界被新 feed 破坏 | LatestNewsItem 复用 metadata-only 字段集；守门 `test_b034_no_generative_ai` 同级覆盖新 schema |

---

## 10. 与既有批次的边界

- **B033/B034 不改契约**：news model/repo 仅新增 global 查询方法（不改既有 ticker/sleeve 查询）；NewsPanel/recommendations 页不动。
- **B035/B037 不改**：MarketContextCard + 三段 Home 结构不动，仅第三段追加新闻元素。
- **B037-OPS1 复用**：news timer 走其 durable 接线，零 deploy/sudoers 改动。

---

## 11. 后续批次（不在 B038 范围）

- B039：Home 整合 AI Advisor（第二段；注意 B037 已复用 AdvisorSection，需先核查真实 gap，同 B038 模式）。
- B040-B043：Reports/Rec/Risk 重构 + AI 解释层。
