---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B044-real-scoring-precompute：✅ `done`**（2026-06-07，1 fix-round=环境 blocker，0 代码改动）。F001/F002/F003/F004 全签收。`/api/recommendations/current` 从 equal-weight 占位改为 Master Portfolio 真实评分（SGOV .6/EEM .2/SPY .2, data_source=fixture 诚实标记）。trade/ 入 VM venv，VM timer precompute→DB→read 闭环，§12.10 AST 守门（请求路径禁 trade import，仅 precompute 允许）。B037-OPS1 自动接线 timer enabled+active。signoff `docs/test-reports/B044-real-scoring-precompute-signoff-2026-06-07.md`。**强 framework 候选**：trade 入 artifact 改 §12.10 enforcement(物理缺席→AST 守门)。**留 B045**：regime reconcile + account current_weight(AccountSnapshot) + 评分精炼 + 真数据切换。
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
- 最新版本 **v0.9.34**（2026-06-06 B038 沉淀）：§12.10 自包含审计扩到所有生产执行路径。
- **v0.9.33**（evaluator.md §24 timer L2 接线检查）/ **v0.9.32**（generator.md §12.10 + evaluator.md §23 L2 新路由真 VM 200）。
- 仍 hold：B031 第三方 API live-validate（单例）+ B026 React event edge（单例）。

## 已知 gap
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret 全配齐，Phase 2 无遗留 secret 缺口。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
