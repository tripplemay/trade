---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B035-market-context：`done`**（2026-06-05；Phase 2 / Stream 2.C 第十个 batch）。F001/F002/F003 generator ✅ done；F004 Codex ✅ signoff。L1 PASS：backend pytest 704 passed +2 skipped / B035+B033 safety guards 19 passed / ruff 0 / mypy 0 / alembic 0007↔0006 / frontend lint+typecheck / vitest 180 / Playwright 40。L2 PASS：production `/api/health.version=9338a9f`；authenticated `/api/protected-test`=200；authenticated `/api/debug/recent-errors`=`{"count":0,"records":[]}`；authenticated `/api/market-context`=200 且返回 6 条纯结构化 series；anon `/api/market-context`=401；VM env 含 `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`；`alembic_version=0007_b035_market_context`；`workbench-market-context.timer` enabled+active；`market_context_observation` 31 行 / 6 series；snapshot dir 落 6 个 JSON；news 无 scheduler，边界 `(q)` 保持。签收：`docs/test-reports/B035-market-context-signoff-2026-06-05.md`。
- **B035 决策矩阵（2026-06-04 用户已批，★=拍板）：** 数据源=★**FRED + Alpha Vantage** / 新 secret=★**FRED_API_KEY + ALPHAVANTAGE_API_KEY**（用户申请 key + §12.9 四处接线）/ 更新=★**引入 scheduler/cron 每日自动**（systemd timer 非 APScheduler）/ 存储=★**复用 B027/B029 snapshot foundation** / live-validate=两源第三方 API（**B031 候选复用窗口**）/ CI=fixture-first ¥≈0。
- **不做**：AI advisor（B036）/ market context 喂 quant 策略 / 盘中实时 / 付费源 / in-process APScheduler。
- 后续路径：B035（2.C 本批）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。
- **B034 ✅ signoff 2026-06-04**（1 fix-round；news_embedding bge-m3 + ticker 硬匹配+cosine + Recommendations NewsPanel；alembic 0006；prod /recommendations/news 200）。

## 已完成签收 + MVP 完工
- B001-B033 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：**B033 News Ingest signoff 2026-06-01**（1 fix-round；prod snapshot dir provision blocker→修复；SEC EDGAR + Yahoo RSS adapter + News schema + snapshot writer + CLI；边界 (p)(q)）；B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `9338a9fef37fa5d27b1fc629a7511518617cbe59`（签收前 `main` HEAD = `3f75bb7e408fd45cea2ca05a77f6dc20df72fd47`，diff 仅 `progress.json` + `.auto-memory/project-status.md`，产品代码等价）；`alembic_version=0007_b035_market_context`；authenticated `/api/market-context`=200（6 series）；anon `/api/market-context`=401；VM `/etc/workbench/workbench.env` 13 key（含 `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`）；`workbench-market-context.timer` enabled+active（每日 00:00 UTC）；`market_context_observation` 31 行 / 6 series；`/var/lib/workbench/data/snapshots/market-context/` 已建并落 6 个 JSON。B034 旧状态保留（news 无 scheduler，边界 q 不变）。
- **VM 运维笔记（2026-06-05）：** timer 由 admin（tripplezhou）一次性手动 install/enable；deploy 用户无 `/etc/systemd` + `enable` sudoers，deploy.sh best-effort 仅 warn（单元文件现随 release 下发，fresh VM 重建可复装）；env 文件更新走 bootstrap-env workflow + admin `sudo install` 到 `/etc/workbench/`。

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
