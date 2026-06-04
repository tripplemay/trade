---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B035-market-context：`verifying`**（2026-06-04；Phase 2 / Stream 2.C 第十个 batch）。Home 页市场宏观 context：FRED（10y/VIX/CPI）+ Alpha Vantage（SPY/QQQ/DXY），每日更新，复用 B027/B029 snapshot foundation。spec `docs/specs/B035-market-context-spec.md`。**全部 generator features F001-F003 ✅ done + CI 全绿**（含 F003 rewrite fix-round：next.config PROXIED_PREFIXES 加 market-context）；待 Codex F004 L1+L2 验收。**F001 ✅ done**（market_context 表 + alembic 0007 + FRED+Alpha Vantage 双 adapter + 2 secret 四处接线 + fixtures；AV envelope demo-key live-validated / FRED 端点路径 no-key 400 验证为真；DXY 取 UUP 等效）。**F002 ✅ done**（market CLI 拉 6 series + systemd timer 非 APScheduler `workbench-market-context.{service,timer}` + deploy.sh install/enable + 边界 (r) AST 守门；News (q) 守门仍过；backend pytest 695 / ruff/mypy 0）。**F003 ✅ done**（`GET /market-context` auth-gated 纯结构化 + Home MarketContextCard 6 series + catalog 入包 §12.10 自包含守门；backend pytest 701 / vitest 179 / e2e b035 真栈跑通）。**当前 sprint=F004（Codex evaluator）**：L1 全门禁 + 边界 (r)/§12.10/(q) 守门 + L2（2 key VM env / systemd timer enabled scope 只读 / alembic head=0007 / GET /api/market-context VM authenticated 200 / Home 卡片纯结构化截图）+ signoff。**VM sudoers 提醒**：首个 timer 需授 deploy 用户 install→/etc/systemd/system + `enable --now workbench-market-context.timer`（deploy best-effort warn 不 brick；L2 验 enabled）。
- **B035 决策矩阵（2026-06-04 用户已批，★=拍板）：** 数据源=★**FRED + Alpha Vantage** / 新 secret=★**FRED_API_KEY + ALPHAVANTAGE_API_KEY**（用户申请 key + §12.9 四处接线）/ 更新=★**引入 scheduler/cron 每日自动**（systemd timer 非 APScheduler）/ 存储=★**复用 B027/B029 snapshot foundation** / live-validate=两源第三方 API（**B031 候选复用窗口**）/ CI=fixture-first ¥≈0。
- **⚠️ 用户动作项（阻塞 L2，不阻塞开发）：** 用户需申请 FRED + Alpha Vantage 免费 API key 并配 GitHub Secret + 经 bootstrap-env.yml 注入 VM env。
- **不做**：AI advisor（B036）/ market context 喂 quant 策略 / 盘中实时 / 付费源 / in-process APScheduler。
- 后续路径：B035（2.C 本批）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。
- **B034 ✅ signoff 2026-06-04**（1 fix-round；news_embedding bge-m3 + ticker 硬匹配+cosine + Recommendations NewsPanel；alembic 0006；prod /recommendations/news 200）。

## 已完成签收 + MVP 完工
- B001-B033 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：**B033 News Ingest signoff 2026-06-01**（1 fix-round；prod snapshot dir provision blocker→修复；SEC EDGAR + Yahoo RSS adapter + News schema + snapshot writer + CLI；边界 (p)(q)）；B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `ec0289495eaf10255c20064982ed33d554c5905b`（签收时 `main` HEAD = `d7ce15922548f6feb853f6ef5b14d0ff11c02d87`，仅 `.auto-memory/project-status.md` 元数据差异，产品代码等价）；authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；authenticated `/api/protected-test` OK；authenticated `/api/recommendations/news?sleeve=satellite_us_quality` = `200 {"items":[]}`；`WORKBENCH_DB_URL=sqlite:///var/lib/workbench/db/workbench.db`；`alembic_version=0006_b034_news_embedding`，`news` + `news_embedding` 表已存在；`/var/lib/workbench/data/snapshots/news` 已创建且为空；无 news scheduler.py / cron / systemd unit。

## 永久硬边界（B033 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g) / B029 起 (h)(i)(j) / B030 起 (k) + v0.9.30 §12.9 / B031 起 (l)(m) / B032 起 (n)(o)：继续
- **B033 起 (p)(q)：** (p) News raw text 仅落 snapshot path 不内联 DB / (q) News ingest 默认 production-disabled（无 scheduler / cron / APScheduler；**对 news 不变**）
- **B035 起 (r)：** 项目首个调度器仅允许**只读市场数据拉取**（systemd timer），明确 NOT 交易执行/下单/recommendation/AI；守门 `test_market_scheduler_scope.py`
- AI 边界（v0.9.28 5 子条）：B034 news→embedding 首次触发但仅非生成式；生成式建议留 B036

## Framework 状态
- 最新版本 **v0.9.32**（2026-06-04 沉淀完成，B034 二例合并）：**请求路径 deploy-artifact 自包含铁律**——请求路径禁 import 根级 `scripts/` / 禁读 repo-root `data/fixtures/`（deploy artifact 只含 `workbench_api/` 包），数据须 materialise 入包；本地+CI 掩盖、唯 L2 真 VM 暴露。落地 generator.md §12.10 + evaluator.md §23（L2 必测核心新路由真 VM 200）+ signoff 模板 §L2 勾选行。
- 仍 hold（等二例）：**B031 第三方 API live-validate**（不同模式，单例；复用窗口 B035 FRED+Alpha Vantage / B036）+ B026 React event edge（单例）。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY` + `SEC_EDGAR_CONTACT_EMAIL` + `AIGC_GATEWAY_API_KEY` 已配；**B035 待用户配 `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`**（阻塞 L2，不阻塞开发）。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
