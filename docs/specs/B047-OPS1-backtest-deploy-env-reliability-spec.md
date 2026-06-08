# B047-OPS1 — Backtest/Reports 部署+env 可靠性（canonical/worker env 硬失败 + worker auto-enable 断言 + Reports 端到端补验）

> **状态：** planning（2026-06-08 起草）。
> **批次类型：** 部署可靠性（OPS，正交 B047 功能码；同 B048-OPS1 / B045-OPS1 先例）。
> **来源：** B047 F005 re-verify 暴露三个部署/env gap + Reports 真机端到端被阻塞（误诊为「读路径待修」，实为 env 写错 DB）。用户 2026-06-08 拍板拆批。
> **配套：** `docs/test-reports/B047-backtest-reports-real-engine-signoff-2026-06-08.md` §⟳⟳ Planner 裁定。

---

## 1. 目标

修 B047 backtest/Reports 基础设施的部署+env 可靠性，使 Reports 真机端到端**自动可证**（无手动兜底），并把 B048-OPS1 的 env-硬失败教训套到 B047 新增的 CLI 入口。done = deploy 链跑过后 Reports 页自然显真实投资报告 + worker 自动 active + canonical/worker CLI 缺 env 响亮失败（不静默写 scratch DB）。

---

## 2. 根因（B047 re-verify 确证）

| Gap | 根因 | 现象 |
|---|---|---|
| **A. canonical/worker CLI 缺 env 静默写 scratch DB** | `canonical.py`/`worker.py` 经 `get_engine()`→`settings.WORKBENCH_DB_URL`，env 未设→回落 `DEFAULT_DEV_DB_URL`（dev/scratch）。deploy.sh 对 alembic 已有 env 硬失败守门（B022 F014），但**手动跑的 CLI 绕过 deploy.sh** | re-verify 裸跑 canonical 写 scratch DB，API 读 prod DB→`/api/reports` 0 items（误诊为读路径 bug）|
| **B. worker 初始 disabled（S1）** | 新增 worker sudoers 授权需在 VM 一次性手动应用到 `/etc/sudoers.d/`（部署不能自授 sudo 权，同 B037-OPS1）| 首次部署命中 `::warning::`，需手动 `enable --now` |
| **C. alembic 0012-0013 未自动升 / 部署链是否真跑过 B047** | 部署用户手动触发（CLAUDE.md）；B047 deploy 可能未真正执行；B048-OPS1 的 `alembic current==heads` 断言若部署没跑就不触发 | prod 缺 backtest_run/investment_report 表或 schema 落后 |

---

## 3. 永久硬边界（继承）

- §12.10.2 请求路径禁 trade（canonical/worker allowlist 不变）；边界 (r) 确定性回测非执行；定位 §1.1；no-execution；不改 B047 功能码逻辑（仅 env/部署硬化 + 断言）。

---

## 4. 技术方案

### 4.1 canonical/worker CLI env 硬失败（Finding A，F001）

- 新增共享守门 `workbench_api/db/require_production_db.py`（或在 canonical.main/worker.main 入口）：启动时若 `settings.WORKBENCH_DB_URL` 解析为 `DEFAULT_DEV_DB_URL`（即 env 未设）**且**非显式 dev 模式 → 响亮非零退出（`::error::` 文案同 deploy.sh：「WORKBENCH_DB_URL unset，将写 scratch DB 非 prod；请 source EnvironmentFile 或经 systemd 运行」），**不静默写 scratch**（B048-OPS1 env-url 空硬失败家族 / v0.9.21 诚实失败）。
- 适用 `canonical.py main` + `worker.py main`（两个 import-trade 的 CLI 入口）。
- 允许测试/本地经显式 `WORKBENCH_DB_URL` 或显式 dev opt-in 跑（不破坏 dev 体验）。

### 4.2 deploy 后断言 worker active + canonical timer enabled（Finding B，F001）

- deploy.sh worker enable loop 后 **post-step assert**（§12.11）：`systemctl is-active workbench-backtest-worker.service` 非 active → 响亮（warning/hard 视 sudoers 应用态）；`systemctl is-enabled workbench-canonical-backtest.timer` 非 enabled → 响亮。
- 确认 deploy 后 schema check 的 required-tables 列表含 `backtest_run` + `investment_report`（Finding C 兜底——B048-OPS1 断言 alembic heads，本批补表名断言）。

### 4.3 守门/测试（F001）

- guard test：env 未设跑 canonical/worker main → 非零退出 + 不触 DB 写（monkeypatch settings 默认 URL）。
- deploy-wiring test：deploy.sh 含 worker is-active assert + canonical timer is-enabled assert + required-tables 含两新表（grep/AST，仿 test_deploy_timer_wiring.py）。
- backend pytest ≥ baseline+ / ruff 0 / mypy 0 / bash -n deploy.sh。

### 4.4 真机 L2 + Reports 端到端补验（F002，Codex，依赖用户触发 deploy）

- **前置**：F001 落 main 后**用户手动触发 Deploy workflow**（部署用户触发，CLAUDE.md）。
- L2：(1) alembic current==heads（含 0012 backtest_run / 0013 investment_report）+ 两表存在；(2) `workbench-backtest-worker.service` **自动 active**（is-enabled/is-active，**非手动 enable**）；(3) `workbench-canonical-backtest.timer` enabled；(4) **canonical service 经 systemd 跑（env 注入→prod DB）** `sudo systemctl start workbench-canonical-backtest.service` → `investment_report` 写 **prod DB** ≥1 行 → `GET /api/reports` 返 ≥1 真实投资报告 → 浏览器 `/reports` 渲染真实报告（非空、非开发签收）【**B047 被推迟的 Reports 端到端，本批闭合**】；(5) **canonical/worker CLI 缺 env→响亮失败**正向验（裸跑不写 scratch）；(6) on-demand backtest 仍真实 + B023 不破 + recent-errors=0 + HEAD≡main。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | canonical/worker CLI 缺 env 硬失败（不静默写 scratch DB）+ deploy.sh worker is-active / canonical timer is-enabled post-step 断言 + required-tables 含两新表 + 守门/测试 |
| F002 | codex | L2 真机（依赖用户触发 deploy）：deploy 链 alembic heads+两表 / worker auto-active / canonical timer enabled / **canonical→prod DB→/api/reports≥1→/reports 渲染真实报告（B047 Reports 端到端闭合）** / CLI 缺 env 响亮失败正向验 / on-demand 真实 / B023 不破 + signoff |

---

## 6. 不做的事（YAGNI）

- 不改 B047 功能码逻辑（worker/canonical 回测计算、reports 读路径——已确认非 bug）。
- 不自动触发部署（用户手动触发不变）。
- 不引入新 async infra / 不改 §12.10.2 / 不动 master 评分。
- 不做 B049 全页面审计（独立后续批次）。

---

## 7. 验收门槛汇总

- **F001**：canonical/worker main 缺 env→非零退出+不写 scratch（守门测试）；deploy.sh worker is-active + canonical timer is-enabled post-step 断言 + required-tables 含 backtest_run+investment_report（wiring 测试）；backend pytest ≥ baseline+≥4 / ruff 0 / mypy 0 / bash -n。
- **F002**（依赖用户 deploy）：L2 六项全正面——alembic heads+两表 / worker auto-active（非手动）/ canonical timer enabled / **canonical→prod DB→/api/reports≥1→/reports 真实报告渲染** / CLI 缺 env 响亮失败 / on-demand 真实+B023 不破+errors=0+HEAD≡main。Signoff（§24 worker+canonical 接线 + §Production/HEAD + §Post-signoff Deploy + **Reports 端到端闭合证据 = B047 遗留缺口关闭**）。Framework 候选（强）：**新 CLI/job 入口必须套 env-硬失败守门（B048-OPS1 教训未自动传播到新入口）** 记 §Framework Learnings。

---

## 8. 参考文档

- B047 signoff §⟳⟳ Planner 裁定（根因 + 三 gap）
- `workbench_api/db/engine.py`（get_engine→settings.WORKBENCH_DB_URL→DEFAULT_DEV_DB_URL 回落）
- `workbench_api/backtests/canonical.py` + `worker.py`（CLI 入口）
- deploy.sh B022 F014 alembic env 硬失败守门（116-137 行）+ worker enable loop（413-427）+ B048-OPS1 alembic heads 断言
- §12.11 deploy post-step assert intended end-state（generator.md）；B037-OPS1 timer/service 接线

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| F002 依赖用户手动触发部署 | spec 明示前置；F001 落 main 后提示用户触发 |
| worker sudoers 仍未应用→仍需手动 enable | post-step assert 响亮暴露；runbook 记一次性应用步 |
| canonical 真数据深度不足→报告薄（B048 S1）| 报告诚实标 degraded（v0.9.21）；非本批范围（数据批次另议）|
| env 硬失败误伤 dev/test | 显式 WORKBENCH_DB_URL / dev opt-in 放行 |

---

## 10. 与既有批次边界 + 后续

- **不改**：B047 功能码 / master 评分 / B044-B048。
- **闭合**：B047 Reports 真机端到端遗留缺口。
- **后续 order**：B049 全页面真实化审计 gate；B043 AI 解释。
