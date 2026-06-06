---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B045-real-data-refresh-pipeline：`building`**（2026-06-07 启动；**真实数据刷新 pipeline**，B044 Batch 2 拆分后数据线；数据工程批次）。建 live-refresh pipeline 让 B044 precompute 在 VM 全 sleeve 跑真实数据（`data_source=real`），消除 B044 S2/S3 fixture stub（risk_parity 需 120+ 日频/us_quality 需 fundamentals，wheel fixture 不够→VM stub，仅 momentum real）。**决策（★用户批）：真数据路径=C live-refresh pipeline**（非静态快照）。planner 决（C 后拆分）：B045=pipeline / **B046=regime reconcile+account current_weight**（小，拆出）；数据 store=VM 文件 `/var/lib/workbench/data/snapshots/unified/`；数据源=prices Tiingo(B027)+fundamentals SEC EDGAR(B029 fetch_quarterly_fundamentals，两真实源已存在)；每日 timer(边界 r)。4 features：(F001 g)刷新 CLI(Tiingo+EDGAR→VM unified CSV)+workbench-data-refresh.timer(B037-OPS1 自动接线)+scope 守门；(F002 g)trade loaders data-root env 覆盖(读 VM store/repo-root 兼容)+precompute 设 env；(F003 g)precompute data_source 粒度标记(real/mixed/fixture)+全 sleeve real(S3 消除)；(F004 c)L2 真机刷新+precompute data_source=real 全 sleeve+/current 真实权重 vs B044 fixture+signoff。复用 TIINGO+SEC_EDGAR secret。**风险**：SEC EDGAR fundamentals 覆盖(部分 symbol 无财报→mixed 诚实标记) + disk(B044 S1 82%，unified CSV 增占用)。spec `docs/specs/B045-real-data-refresh-pipeline-spec.md`。
- **B044-real-scoring-precompute：✅ `done`**（2026-06-07，1 fix-round=环境 blocker，0 代码改动）。`/api/recommendations/current` equal-weight→Master 真实评分（SGOV .6/EEM .2/SPY .2，**data_source=fixture 诚实**，仅 momentum real）。trade/ 入 VM venv，precompute→DB→read 闭环，§12.10 AST 守门。signoff `docs/test-reports/B044-real-scoring-precompute-signoff-2026-06-07.md`。沉淀 v0.9.35。**Soft-watch S1：VM disk 82%（曾致主机挂死，持续监控）**；S2/S3（fixture/sleeve stub）→ B045 真数据切换解决。
- **B041-recommendations-robinhood：✅ `done`** / **B040-reports-robinhood：✅ `done`** / **B039-home-advisor-disclaimer：✅ `done`** / **B038-home-market-news：✅ `done`**（2026-06-06 全签收）。
- **🎯 Phase 2 完整收官（B031-B036 全签收）= 里程碑 B；B037-B044 全签收 = 里程碑 C 巩固。** Phase 3 主线：B043-B045(Rec 精炼+AI 解释层 + regime reconcile)。
- **B037-OPS1 ✅ / B037-home ✅ / B036 ✅ / B035 ✅ / B034 ✅**

## 已完成签收
- B001-B044 全部签收。MVP substantively 完成 (PRD §10/§11/§12)。

## 生产状态
- **2026-06-07 B044 done：** prod `/api/health.version=8b39d68` db ok；alembic=0010；trade 入 venv import OK；`workbench-recommendations.timer` enabled+active（B037-OPS1）；precompute `saved=3 data_source=fixture`（risk_parity/us_quality stub 依预期）；authenticated `/api/recommendations/current` 200 真实权重 SGOV .6/EEM .2/SPY .2(data_source=fixture 诚实)；`/api/debug/recent-errors={count:0}`。VM disk 82%(watch-item)。**教训**：长停机使 auto-deploy SCP 静默失败、prod 卡上一版本——恢复后须核对 prod version==main HEAD 并按需 re-deploy。
- **VM 运维笔记：** B037-OPS1 后 timer auto-wiring 能力就位：sudoers drop-in + root wrapper；`deploy.sh` 可自动 install+enable `workbench-*.timer`。

## 永久硬边界（B033 起；v0.9.31+）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene / paths-trigger 含 trade/+scripts/+pyproject.toml
- B033 (p) News raw text 仅落 snapshot path；B035 (r) 调度器允许只读 market-context/prices/news，禁 broker/ticket/execution；B044 (r) 调度器允许 recommendations precompute（含 trade/ import）。
- AI 边界（v0.9.28）：非生成式 embedding（B034）；生成式 prompt+输出校验 references ⊆ input set + B032 red-team gate（B036）。

## Framework 状态
- 最新版本 **v0.9.35**（2026-06-07 B044 沉淀）：generator.md §12.10.2 enforcement 模型「物理缺席→AST 守门」（禁包打进 artifact 供 job 用时同 commit 落 AST 守门，规约 6）+ README §经验教训「生产部署/停机恢复」（长停机 SCP 静默失败→恢复后核对 prod==HEAD）。
- **v0.9.34**（§12.10 自包含扩到所有生产执行路径）/ **v0.9.33**（evaluator.md §24 timer L2 接线检查）/ **v0.9.32**（generator.md §12.10 + evaluator.md §23）。
- 仍 hold：B031 第三方 API live-validate（单例）+ B026 React event edge（单例）。

## 已知 gap
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret 全配齐，Phase 2 无遗留 secret 缺口。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
