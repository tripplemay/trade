# B044 — 真实评分基础（precompute → recommendation_snapshot → /api/recommendations/current）

> **状态：** planning（2026-06-06 起草）。
> **批次类型：** 新功能 / 基础设施（**真实评分基础**，Layer 0→1 在 recommendations 面的完成）。**拆两批的第 1 批**（核心评分闭环）；第 2 批 B045 = regime reconcile + account current_weight + 精炼。
> **命名/排序：** 非 Phase 3 roadmap UI 序列的**插入式基础批次**（同 B037-OPS1 插入先例）。roadmap B042（Risk UI）/B043（AI 解释）不变，但 **B043「为什么这样建议」依赖本批 + B045 的真实评分**。
> **配套权威设计：** `docs/product/positioning-2026-05.md` §1.1 + §13（Master Portfolio + 5 因子 + risk parity + satellite）。

---

## 1. 目标

把 `/api/recommendations/current` 从 **equal-weight 占位**改为返回 **Master Portfolio 真实评分权重**。真实评分逻辑已全部存在于 `trade/` 包（5 因子 / risk parity / HRP / `trade/backtest/master_portfolio.py` `_build_portfolio_target()` 混合）。本批通过 **precompute → DB → read** 架构接入。

**本批（Batch 1）范围 = 核心评分闭环**：trade/ 入 venv + recommendation_snapshot 表 + precompute CLI/timer 跑 master 真实评分 + `/api/recommendations/current` 读真实权重。
**不在本批（留 Batch 2 / B045）**：regime sleeve 名实 reconcile、account current_weight（读 AccountSnapshot，本批仍可 0.0 或简单值）、评分精炼/调参 UI。

---

## 2. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 架构 | ★ **precompute → DB → read**（照 B036 advisor 读侧范式） | 唯一让请求路径守 §12.10 的架构 |
| 评分在哪跑 | ★ **A：把 `trade/` 装进 VM venv** | VM timer 直接 import trade/ 评分写 DB；运维简单（一个 timer）；trade/ 进 artifact，§12.10 请求路径保护改由 AST 守门兜底 |
| 范围拆分 | ★ **拆两批，本批=核心评分** | Batch 2=regime reconcile + account current_weight + 精炼 |
| 权威评分组成 | **`trade/backtest/master_portfolio.py` 现有组成**（planner 决） | momentum(global_etf_momentum 0.40)/risk_parity(0.30)/us_quality(0.20)/hk_stub(0.10→defensive)；regime 注册项名实不符留 B045 reconcile |

---

## 3. 永久硬边界（继承 + 本批修订）

**继承不破：**
- **§12.10 请求路径自包含**：`/api/recommendations/current` 请求路径**禁 import `trade/`**、禁读 repo-root 数据；只读 `recommendation_snapshot` DB 表。**本批 trade/ 进 venv 后，此边界改由 AST 守门强制**（见 §4.5）。
- no-execution / same-origin / auth-gated / Repository / 定位 §1.1（评分=配置权重，非收益预测）。
- **§12.10.1（v0.9.34）**：precompute CLI 接入 timer 自动执行路径，其 import 闭包（含 trade/ 及 trade 的数据 loader）按自包含审计；**本批关键风险**——trade loader 读 repo-root `data/snapshots/`，VM 上可能无 → 须解决真实数据可用性（§4.4）。

**本批修订：边界 (r) 收编 quant 评分预计算**：
- 调度器允许（a）只读市场数据拉取（market-context/prices/news）+（b）AI advisor 预计算（B036）+ **（c）确定性 quant 评分预计算（B044，read-only，写 recommendation_snapshot）**；仍 NOT 交易执行/下单/broker。
- `test_market_scheduler_scope.py` 扩：允许 recommendations precompute import（含 trade/ 策略），仍禁 broker/order_ticket/execution/tickets/fills/reconcile。

---

## 4. 技术架构

### 4.1 `trade/` 可安装 + 入 venv（F001）

- `trade/` 加 packaging（pyproject 或纳入 backend wheel 构建 / editable install），deploy.sh 把 trade/ 装进 `/opt/workbench/.venv`（与 workbench_api 并存）；处理 trade/ 自身依赖（pandas/numpy 等）。
- CI backend build/test 流程纳入 trade/（确保 wheel/install 含 trade/ + 依赖解析正确）。
- **风险**：trade/ 依赖体量（pandas 等）增大 artifact + 首次 install；需验 deploy 不破、backend 启动不变。

### 4.2 recommendation_snapshot 表（F002）

- `db/models/recommendation_snapshot.py`：as_of_date / symbol / sleeve / target_weight / rationale / computed_at / master_meta（JSON：planning_weights、数据源标记 real/fixture）；UniqueConstraint(as_of_date, symbol)；镜像既有 snapshot 表风格。
- alembic 迁移（down_revision=当前 head 0009）。
- `db/repositories/recommendation_snapshot.py`：save_batch（幂等覆盖 as_of_date）/ latest_snapshot（最新 as_of_date 全行）。

### 4.3 precompute CLI + timer（F002）

- `workbench_api/recommendations/precompute.py` + `cli.py`：**import `trade.backtest.master_portfolio`**，跑 `_build_portfolio_target()`/`_resolve_child_weights()` 真实评分「as of today」→ 最终 {symbol: weight} + per-sleeve breakdown → 写 recommendation_snapshot。**仅此模块允许 import trade/**（非请求路径）。
- `deploy/systemd/workbench-recommendations.{service,timer}`（每日 oneshot，镜像 market-context；**B037-OPS1 循环+通配符零成本自动接线**）。
- scheduler scope 守门扩 recommendations precompute（边界 r-c）。

### 4.4 真实数据可用性（F002，关键）

- precompute 用 trade strategies 既有 loader（B030 unified CSV 真数据 + fixture fallback）。
- **VM 上须有真实输入数据**：本批须解决——把 unified CSV 数据随 release 下发到 VM 可读路径，或 precompute 经 Tiingo（workbench_api 既有 loader）取价 + 真实 fundamentals 源；**若真实数据不可用→fixture fallback，但必须显式标记 master_meta.data_source=fixture 且 L2 记录**（不得把 fixture 当 real 蒙混，参 v0.9.21 fixture-vs-real signal）。
- L2 验真：手动 trigger precompute service → 检查 recommendation_snapshot 是否真实数据评分（记录 real / fixture 哪种）。

### 4.5 /api/recommendations/current 读 snapshot（F003）

- `services/recommendations.py` `_build_target_positions` 替换：读 `recommendation_snapshot` latest_snapshot → 映射 TargetPosition（target_weight 真实；current_weight 本批仍 0.0 或简单，留 B045 接 AccountSnapshot；diff=target-current）。
- 无 snapshot（precompute 未跑）→ graceful 空 / 占位（不抛错；记录「评分待生成」）。
- **§12.10 AST 守门**：`tests/safety/test_recommendations_request_self_contained.py`——断言 `routes/recommendations.py` + `services/recommendations.py`（请求路径）**不 import trade/**；仅 `workbench_api/recommendations/precompute.py`（job）允许。

### 4.6 测试

- pytest：recommendation_snapshot repo（save_batch 幂等 / latest）；precompute（fake/real master scoring → 写表，含 data_source 标记）；/api/recommendations/current 读 snapshot（有/无 snapshot 两态）+ auth-gated；§12.10 AST 守门（请求路径无 trade import）；scheduler scope 含 recommendations。
- 既有 recommendations 契约（schema TargetPosition / gate/wash/export）不破。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | `trade/` 可安装 + deploy.sh 装进 venv + CI build/install 纳入 trade/（backend 启动/部署不破）|
| F002 | generator | recommendation_snapshot 表(alembic)+repo + precompute CLI（import trade master_portfolio 真实评分）+ workbench-recommendations.{service,timer} + 真实数据可用性 + scheduler scope 守门 + pytest |
| F003 | generator | `/api/recommendations/current` 读 recommendation_snapshot（替换 equal-weight）+ §12.10 AST 守门（请求路径禁 trade import）+ graceful 无 snapshot + pytest |
| F004 | codex | L1 + L2 真 VM 验收（trade/ 入 venv + precompute 真机跑出真实评分写表 + /api/recommendations/current 返回真实权重 + 数据源 real/fixture 记录 + timer 自动接线 + 请求路径无 trade import）+ signoff |

---

## 6. 不做的事（YAGNI / 留 B045）

- 不做 regime sleeve 名实 reconcile（master backtest 用 global_etf_momentum；注册表 regime_adaptive 对齐留 B045）。
- 不接 account current_weight（本批 current_weight=0.0 或简单值；读 AccountSnapshot 留 B045）。
- 不做评分调参 UI / 不改 5 因子权重 / 不改 master planning_weights。
- 不做 AI「为什么这样建议」（B043）。
- 不输出预期收益数字（定位 §1.1）。
- 不改前端 Recommendations UI（B041 已重构；本批只换数据源，前端透明）。
- 不让请求路径 import trade/（仅 precompute job）。

---

## 7. 验收门槛汇总

- **F001**：trade/ 可安装 + deploy.sh 装进 venv + CI 纳入；backend 启动/既有路由不破；backend pytest ≥ baseline（trade/ install 不破既有测试）；ruff/mypy 0（含 trade/ 若纳入 lint scope 则单独处理）；deploy.sh dev rehearsal 不崩。
- **F002**：recommendation_snapshot 表+迁移(head 推进)+repo；precompute CLI import trade master_portfolio 跑出 {symbol:weight}+sleeve breakdown 写表（data_source 标记）；workbench-recommendations.{service,timer}；scheduler scope 守门含 recommendations；pytest ≥ baseline+≥10；真实数据可用性方案落地（unified CSV 下发 / Tiingo / fixture fallback 显式标记）。
- **F003**：/api/recommendations/current 读 snapshot 真实权重（有 snapshot）/ graceful（无 snapshot）+ auth-gated；**§12.10 AST 守门**（请求路径 routes/services 无 trade import）；既有 schema/gate/wash/export 契约不破；regen api.ts（若 schema 变）；pytest。
- **F004**：L1 全门禁 + secret grep 0；L2（真 VM）：(1) health 200 + SHA≡main HEAD；(2) recent-errors=0；(3) **trade/ 已入 venv**（import 不报错）；(4) **precompute 真机 trigger → recommendation_snapshot 有真实评分行**（记录 data_source=real/fixture 哪种 + 哪些 symbol/weight）；(5) **GET /api/recommendations/current authenticated 200 返回真实权重**（非 equal-weight；target_weight 反映 master 评分）+ anon 401；(6) **workbench-recommendations.timer 经 B037-OPS1 自动 enabled+active 无 warn**（§24）；(7) **请求路径无 trade import**（守门）；(8) HEAD≡main + B026 absent。Signoff 用模板（§24 timer 接线 + §L2 新行为 + §Production/HEAD + §Post-signoff Deploy + 数据源 real/fixture 声明）；docs/screenshots（可选 Recommendations 真实权重）。Framework 候选：trade/ 入 artifact 改变 §12.10 enforcement 模型（从「物理缺席」转「AST 守门」）= 强候选，记 signoff §Framework Learnings。

---

## 8. 参考文档

- 真实评分源：`trade/backtest/master_portfolio.py`（`_build_portfolio_target`/`_resolve_child_weights`）/ `trade/strategies/{us_quality_momentum,risk_parity,regime_adaptive,global_etf_momentum}/`
- 现状占位：`workbench_api/services/recommendations.py`（`_build_target_positions` equal-weight）/ `schemas/recommendations.py`
- precompute 范式参考（读侧）：B036 advisor `workbench_api/advisor/precompute.py` + `advisor_recommendation` 表 + timer
- §12.10 / §12.10.1 自包含：`framework/harness/generator.md`；§24 timer L2：`evaluator.md`
- B037-OPS1 timer 自动接线：`docs/specs/B037-OPS1-...-spec.md`
- 数据源：B030 unified CSV / B027 Tiingo loader `workbench_api/data/tiingo_loader.py` / B037 price_snapshot

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| trade/ 入 venv 破坏 §12.10 请求路径保护 | AST 守门强制请求路径无 trade import（§4.5）；仅 precompute job 允许；framework 沉淀 enforcement 模型转变 |
| VM 无真实输入数据→评分跑 fixture 蒙混成 real | master_meta.data_source 显式标记 + L2 必记 real/fixture（v0.9.21）；优先下发 unified CSV / Tiingo |
| trade/ 依赖（pandas 等）增大 artifact + install 失败 | F001 单独验 deploy install + backend 启动；CI build 纳入 trade/ 依赖解析 |
| regime sleeve 名实不符导致评分缺一块 | 本批照 master_portfolio 现有组成（momentum/risk_parity/us_quality/hk_stub）；regime reconcile 留 B045，spec 明记 |
| precompute 评分耗时/失败阻断 | oneshot best-effort；失败→snapshot 不更新→/current graceful（旧 snapshot 或空）；不阻断请求路径 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：前端 Recommendations UI（B041）/ gate-check/wash-sale/export-to-ticket(B023) / backtest 引擎 / 5 因子与 master 权重逻辑（仅调用）。
- **B045（Batch 2）**：regime sleeve reconcile + account current_weight（AccountSnapshot）+ 评分精炼。
- **B043 依赖**：本批 + B045 提供真实评分后，B043 AI「为什么这样建议」才有真东西可解释。
