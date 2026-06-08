# B047 — Backtest（on-demand async 真实引擎）+ Reports（真实投资报告）

> **状态：** planning（2026-06-08 起草）。
> **批次类型：** 新功能 / 架构（里程碑 C order 7「所有页面接真实引擎」）。**大批次**（5 features，含新建 async worker daemon）。
> **来源：** 2026-06-07 回测页 + Reports 页讨论——Backtest 是 `_compute_synthetic_backtest` 合成 stub；Reports 读 `docs/test-reports/` 开发 signoff 语料（错误类别）。
> **配套：** positioning §1.1 / `docs/strategy/04-...` / `trade/reporting/master_portfolio.py`（真实引擎报告生成）。

---

## 1. 目标

让 Backtest 页 + Reports 页都接**真实 master_portfolio 回测引擎**（`trade/backtest/master_portfolio.py` + `trade/reporting/`），去合成 stub / 去开发签收语料。两者同源（回测引擎同时产出结果 + 投资报告）。

---

## 2. 决策（2026-06-07/08 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| Backtest 架构 | ★ **Option A on-demand async** | 保留交互式 Run + 任意参数；建 async worker（请求路径只读 DB，worker import trade，守 §12.10.2）|
| Reports 开发签收 | ★ **过滤出用户 Reports** | 用户 Reports 只显真实投资报告（kind=investment）；100+ 开发 signoff 过滤/挪 dev 视图 |
| worker 形态 | **长驻 systemd service 轮询队列**（planner 决） | 无 async infra；长驻 worker poll backtest_run 队列，低延迟取任务；B037-OPS1 自动接线 `workbench-*.service` |
| Reports 报告源 | **canonical 定时回测 Master+各 sleeve → 报告 kind=investment**（planner 决） | 权威报告（默认参数）；on-demand 任意参数运行属 Backtest 页非 Reports |

---

## 3. 永久硬边界（继承）

- **§12.10.2**：请求路径（routes/services/backtests + reports）**禁 import trade**；仅 worker（`workbench_api/backtests/worker.py`）+ canonical precompute allowlist。AST 守门。
- 定位 §1.1：回测=历史结果非预测，不出「预期年化」；报告标 research-only。
- no-execution / B023 不破 / i18n（Reports/Backtest 文案双语）。
- 边界 (r)：worker/canonical 是确定性回测计算（read-only 数据），非交易执行。

---

## 4. 技术架构（Option A async）

### 4.1 backtest_run 队列+结果表（F001）

- `db/models/backtest_run.py`：run_id / strategy_id / params(JSON) / status(queued/running/done/error) / metrics(JSON) / equity(JSON) / allocations(JSON) / trades(JSON) / report_markdown / created_at / finished_at / error。alembic 迁移。
- `db/repositories/backtest_run.py`：enqueue / claim_next_queued（worker 取任务，原子置 running）/ save_result / get_by_run_id。
- §12.10.2 worker allowlist 守门（`test_backtests_request_self_contained.py`：routes/services/backtests 无 import trade；仅 worker/canonical 允许）。

### 4.2 async worker（F002）

- `workbench_api/backtests/worker.py`：**import trade.backtest.master_portfolio + trade.reporting**，长驻循环——claim_next_queued → 跑 `run_master_portfolio_quarterly_backtest(params)` → map MasterPortfolioBacktestResult → metrics/equity/allocations/trades + `generate_master_portfolio_reports` 报告 → save_result(done)；异常→error。空队列 sleep（~2-5s 低延迟）。
- `deploy/systemd/workbench-backtest-worker.service`（长驻 Restart=always；B037-OPS1 sudoers/wrapper 覆盖 workbench-*.service 自动接线）。
- scheduler scope 守门扩 worker（边界 r 确定性回测，禁 broker/execution）。

### 4.3 Backtest API async + 前端轮询（F003）

- `routes/backtests.py` `POST /run`：enqueue（写 queued 行）→ 返回 **202 + run_id**（请求路径不 import trade）；`GET /{run_id}`：读 DB（status + result，替换 in-memory/synthetic）。
- `services/backtests.py`：去 `_compute_synthetic_backtest`；读 backtest_run DB。
- 前端 Backtest 页：Run → POST → 轮询 GET /{run_id}（queued/running 显进度 → done 渲染真实 metrics/equity/trades，复用 B040 MetricsDisplay）；无 worker/超时 graceful。

### 4.4 Reports 真实投资报告（F004）

- canonical 回测：`workbench_api/backtests/canonical.py`（CLI + timer 或 worker enqueue canonical Master+各 sleeve 默认参数）→ 生成报告写 `investment_report` 表（run_id/strategy_id/as_of_date/markdown/metrics_json/kind=investment）。
- `services/reports.py`：用户 Reports 列表/详情**只显 kind=investment**（真实投资报告）；**开发 signoff（docs/test-reports/）过滤出用户视图**（挪 dev/admin kind 或单独 dev 路由）。
- 前端 Reports：渲染真实投资报告（B040 metrics 卡 + Markdown）；dev signoff 不在用户 Reports。

### 4.5 测试（各 F）

- pytest：backtest_run repo（enqueue/claim/save/get）；worker（fake trade result→save done；异常→error）；canonical 报告生成；reports kind=investment 过滤（dev signoff 不在用户列表）；§12.10.2 守门（请求路径无 trade，worker 允许）；scope 守门含 worker。
- 前端 vitest/Playwright：Backtest Run→轮询→真实结果；Reports 显投资报告非开发签收；双语。

---

## 5. Feature 拆分（大批次）

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | backtest_run 队列+结果表（alembic）+ repo（enqueue/claim/save/get）+ §12.10.2 worker allowlist 守门 |
| F002 | generator | async worker（import trade 跑真实回测+生成报告→DB）+ workbench-backtest-worker.service + scope 守门 |
| F003 | generator | Backtest API async（POST /run enqueue 202 / GET /{run_id} DB 读，去 synthetic）+ 前端轮询渲染真实结果 |
| F004 | generator | Reports 真实投资报告（canonical Master/sleeve 报告→investment_report kind=investment + 开发 signoff 过滤出用户 Reports）+ 前端 |
| F005 | codex | L1 + L2 真 VM（worker service 接线 + on-demand Run→真实回测结果 + Reports 投资报告非开发签收 + dev signoff 过滤 + §12.10.2 守门 + B023 不破）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做参数扫描批跑/优化器（单次 on-demand 即可）。
- 不删开发 signoff（仅从用户 Reports 过滤/挪 dev 视图）。
- 不让请求路径 import trade（worker/canonical 才可）。
- 不改 master 评分逻辑 / B044-B048 / 不真实下单。
- 不输出收益预测（回测=历史结果）。

---

## 7. 验收门槛汇总

- **F001**：backtest_run 表+迁移+repo（enqueue/claim 原子/save/get）+ §12.10.2 守门（请求路径无 trade，worker/canonical allowlist）；backend pytest ≥ baseline+≥8 / ruff 0 / mypy 0。
- **F002**：worker import trade 跑 `run_master_portfolio_quarterly_backtest`→map 结果+`generate_master_portfolio_reports`→DB；workbench-backtest-worker.service（Restart=always，B037-OPS1 接线）；scope 守门含 worker；pytest（fake result→done/异常→error/claim 原子）。
- **F003**：POST /run enqueue 202+run_id（请求路径无 trade）+ GET /{run_id} DB 读（去 synthetic）+ 前端 Run→轮询→真实 metrics/equity/trades 渲染（复用 B040）+ graceful（无 worker/超时）；frontend vitest+Playwright；§12.10.2 守门绿。
- **F004**：canonical Master+各 sleeve 报告→investment_report kind=investment + 用户 Reports 只显 investment（开发 signoff 过滤/挪 dev）+ 前端渲染真实报告；pytest（kind 过滤 dev signoff 不在用户列表）+ vitest。
- **F005**：L1 全门禁 + secret grep 0 + B023/§12.10.2 守门绿；L2（真 VM）：(1) health 200 + HEAD≡main + recent-errors=0 + alembic head；(2) **workbench-backtest-worker.service 接线 active**（B037-OPS1）；(3) **on-demand Run→真实回测结果**（POST /run→轮询→done，metrics/equity 来自真实引擎非 synthetic，记录 vs 旧 seed 差异）；(4) **Reports 显真实投资报告**（Master/sleeve 回测，非开发 signoff；dev signoff 已过滤出用户 Reports）；(5) §12.10.2 请求路径无 trade 守门；(6) B026 absent。Signoff（§24 worker service 接线 + §Production/HEAD + §Post-signoff Deploy + **synthetic→real 对比 + Reports 内容类别修正证据**）。**Framework 候选（强）**：async worker（请求→队列→worker→DB→轮询）若成通用范式 / Reports 内容类别错配 记 §Framework Learnings。

---

## 8. 参考文档

- 真实引擎：`trade/backtest/master_portfolio.py`（run_master_portfolio_quarterly_backtest）+ `trade/reporting/master_portfolio.py`（generate_master_portfolio_reports）
- 合成 stub（替换）：`services/backtests.py`（_compute_synthetic_backtest）/ `routes/backtests.py`
- 复用范式：`recommendations/precompute.py`（job import trade）+ recommendation_snapshot 表/repo + §12.10.2 守门 `test_recommendations_request_self_contained.py`
- Reports 现状：`services/reports.py` + `reports_scanner.py`（读 docs/test-reports/）
- B037-OPS1 timer/service 接线 + §12.10.2 / 边界 r

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| async worker 是新 infra（fix-round 高）| F001 表/F002 worker 先行，F003 接 API，F004 Reports；claim 原子防并发；F005 L2 端到端 |
| worker 长驻 service 崩/卡 | Restart=always；超时/异常→error 状态；前端 graceful；空队列 sleep |
| §12.10.2 请求路径误 import trade | AST 守门（请求路径禁，worker/canonical allowlist）；F005 验 |
| canonical 回测数据不足（B048 S1 价格历史）| 复用 B045 unified 真数据；不足→报告标 degraded 诚实(v0.9.21) |
| 大批次 5 features | 清晰依赖序；若过大可拆 Backtest(F001-3) / Reports(F4) 两批（generator 反馈时定）|

---

## 10. 与既有批次的边界 + 后续

- **不改**：master 评分 / B044-B048 / 前端 Home/Rec/Risk。
- **解锁**：Backtest + Reports 接真实引擎（里程碑 C「所有页面接真实引擎」再进一步）。
- **后续 order**：B049 全页面真实化审计 gate(8)；B043 AI 解释并行（解释真实回测数字）。
