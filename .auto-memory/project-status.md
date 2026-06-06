---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B038-home-market-news：✅ `done`**（2026-06-06 Codex F003 fix-round 1 复验通过签收）。Phase 3 / Stream 4.B 已把今日市场新闻补进 Home 第三段。**最终证据（signoff：`docs/test-reports/B038-home-market-news-signoff-2026-06-06.md`）**：L1 targeted backend `45 passed`（含 `test_news_ingest_self_contained`）+ frontend `28 passed`；production `/api/news/latest` authed `200` 且返回真实 `items[]`、anon `401`、authenticated `/api/debug/recent-errors={"count":0,"records":[]}`；`workbench-news.timer` 通过 **B037-OPS1 durable** 自动 install+enable（deploy run `27052861855` 明示 `workbench-news.timer enabled`，无 wiring warn）；`workbench-news.service` 真机 `status=0/SUCCESS`，journal=`saved=782 skipped_existing=86 errors=0`；production Home zh-CN/en 两轮手验均显示 `home-news-card` + 8 条标题列表 + 0 button + 旧 dashboard 0 + `synthetic-data-banner` 0，截图已落 `docs/screenshots/B038-home-market-news/`。首轮 blocker（`scripts.universe_us_quality` 自包含缺陷）已在 fix-round 1 关闭。
- **B037-OPS1-deploy-timer-sudoers-hardening：✅ `done`**（2026-06-06 Codex F002 签收，0 fix-round）。横切运维修复闭环，根治 B035/B036/B037 三批手装 timer（evaluator.md §24）。deploy run `27050937093` 三 timer 自动 install+enable 无 warn；prod health≡main HEAD `5393343`；三 timer enabled+active；Soft-watch S1 resolved；durable=deploy.sh 循环+sudoers wildcard+root wrapper。signoff `docs/test-reports/B037-OPS1-deploy-timer-sudoers-hardening-signoff-2026-06-06.md`。
- **B037-home-restructure：✅ `done`**（2026-06-06，1 fix-round=prices.timer L2 blocker）。prod `/api/home`=200(`nav=0 day_pnl=null sleeves=3`)；三段 daily-engagement Home 替换旧 quant dashboard（§16 退役+§22）；`alembic=0009`。signoff `docs/test-reports/B037-home-restructure-signoff-2026-06-06.md`。
- **🎯 Phase 2 完整收官（B031-B036 全签收）= 里程碑 B；B037/B038 已 done = 里程碑 C 主线继续。** Phase 3 主线：B039(Home AI)→B040-B043(Reports/Rec/Risk+AI 解释层)→里程碑 C。
- **B036 ✅ signoff 2026-06-05**（AI advisor MVP；prod /api/advisor 200/3 sleeve haiku-4.5；red-team 15/15 gate；alembic 0008；advisor timer）。**B035 ✅**（FRED+AV market context 0007）。**B034 ✅**（news_embedding+NewsPanel 0006）。

## 已完成签收 + MVP 完工
- B001-B033 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：**B033 News Ingest signoff 2026-06-01**（1 fix-round；prod snapshot dir provision blocker→修复；SEC EDGAR + Yahoo RSS adapter + News schema + snapshot writer + CLI；边界 (p)(q)）；B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `9338a9fef37fa5d27b1fc629a7511518617cbe59`（签收前 `main` HEAD = `3f75bb7e408fd45cea2ca05a77f6dc20df72fd47`，diff 仅 `progress.json` + `.auto-memory/project-status.md`，产品代码等价）；`alembic_version=0007_b035_market_context`；authenticated `/api/market-context`=200（6 series）；anon `/api/market-context`=401；VM `/etc/workbench/workbench.env` 13 key（含 `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`）；`workbench-market-context.timer` enabled+active（每日 00:00 UTC）；`market_context_observation` 31 行 / 6 series；`/var/lib/workbench/data/snapshots/market-context/` 已建并落 6 个 JSON。B034 旧状态保留（news 无 scheduler，边界 q 不变）。
- **VM 运维笔记（2026-06-06 更新）：** B037-OPS1 后 deploy 用户已具备受限 timer auto-wiring 能力：sudoers drop-in `/etc/sudoers.d/deploy-workbench` + root-owned wrapper `/usr/local/bin/workbench-install-unit` 已就位，`deploy.sh` 可自动 install+enable `workbench-*.timer`；env 文件更新仍走 bootstrap-env workflow + admin `sudo install` 到 `/etc/workbench/`。
- **B036 L2 前置已就绪（2026-06-05，generator 完成，等 Codex F004 验收）：** prod `/api/health.version=9cce841`（`db_connectivity:ok`）；`alembic 0008_b036_advisor` 已升；`workbench-advisor.timer` admin 已安装 enabled（01:00 UTC oneshot）；**手动 `workbench-advisor.service` 验真 = `Result=success ExecMainStatus=0`、`saved=1 skipped=2 errors=0`**；`advisor_recommendation` 今日 3 sleeve 全 `status=ok` 真 `claude-haiku-4.5` 建议（regime/risk_parity/satellite_us_quality）；`/api/advisor` unauth=401（auth-gated）。**修复 1 round（commit 9cce841）：** advisor precompute 单 session 跨 sleeve 持 SQLite WAL writer 锁 → 下一 sleeve cost_guard（独立连接）写 llm_budget_log `database is locked` → 改 **per-sleeve commit**（WAL+busy_timeout 已先行于 d7533af，仍需释放跨 sleeve 事务）；单测 `test_advisor_precompute`+`test_db_engine` 全绿。

## 永久硬边界（B033 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g) / B029 起 (h)(i)(j) / B030 起 (k) + v0.9.30 §12.9 / B031 起 (l)(m) / B032 起 (n)(o)：继续
- **B033 起 (p)，B038 修订：** (p) News raw text 仅落 snapshot path 不内联 DB；**news ingest 自 B038 起收编到边界 (r)**，允许 systemd oneshot timer 做只读 SEC EDGAR + Yahoo RSS 拉取，但 in-process scheduler 仍禁（`test_news_no_scheduler.py` 保留）。
- **B035 起 (r)，B036/B038 修订：** 调度器允许（a）只读市场数据拉取（market-context / prices / news）+（b）**运行已过 CI safety-gate 的 AI advisor 预计算**（B036）；仍明确 NOT 交易执行/下单/broker；守门 `test_market_scheduler_scope.py`（允许 advisor/news import，禁 broker/ticket/execution）。
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
