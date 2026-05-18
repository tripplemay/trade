# B022 Workbench Phase 1 Signoff 2026-05-18

> 状态：**PASS**（progress.json status=done）
> 触发：B022 F014 fix-round 4 后，Codex 对本地 L1 回归、生产数据库迁移修复、以及 workbench 关键 L2 用户流做最终复验。

---

## 变更背景

B022 在 B021 的单用户 cloud deploy + OAuth + SQLite/Alembic 基础设施之上，交付
Research Workbench Phase 1：7 个 read-mostly 业务页、最小必要 write
（Backtest run / Recommendations export / Snapshots refresh / Backlog CRUD），以及
配套的 chart/table UI、文档和 Codex L1/L2 验收链路。

本批次不包含交易执行 UI、broker SDK、paper/live trading、多用户账号体系、
Cloud SQL/Postgres 或任何生产下单能力。

---

## 变更功能清单

### F001-F013：Workbench Phase 1 product delivery

**Executor：** generator

**验收结果：** PASS

**证据：**
- Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog /
  Home 页面均可在生产 authenticated 会话中打开。
- Reports 页可读取 `docs/test-reports/`，`B019-retune-sweep` 明细页检测到
  `markdown-heavy-table` = `4`，证明重表格仍走 AG Grid。
- Recommendations 页面 `Export markdown ticket` 按钮可点击，成功写入
  `/var/lib/workbench/runs/2026-05-18/order-ticket-2026-05-18.md`。
- Snapshots 页面列表恢复，refresh 流程完成后不再出现缺表报错。
- Backlog 页面列表、创建流程恢复，受控创建返回 `201` 并在页面展示新增项。

### F014：Codex L1 + L2 verification and signoff

**Executor：** codex

**验收结果：** PASS

**L1 证据：**
- `.venv/bin/python -m pytest workbench/backend/tests/safety/test_deploy_alembic_env_load.py workbench/backend/tests/unit/test_db_degrade.py workbench/backend/tests/unit/test_backlog_prod_config.py workbench/backend/tests/unit/test_error_buffer.py workbench/backend/tests/unit/test_snapshots.py`
  -> `18 passed`
- `.venv/bin/python -m ruff check workbench/backend/tests/safety/test_deploy_alembic_env_load.py workbench/backend/workbench_api/app.py workbench/backend/workbench_api/routes/backlog.py workbench/backend/workbench_api/services/backlog.py workbench/backend/workbench_api/services/snapshots.py workbench/backend/workbench_api/observability/error_buffer.py`
  -> `All checks passed!`
- `.venv/bin/python -m mypy workbench/backend/workbench_api/app.py workbench/backend/workbench_api/routes/backlog.py workbench/backend/workbench_api/services/backlog.py workbench/backend/workbench_api/services/snapshots.py workbench/backend/workbench_api/observability/error_buffer.py`
  -> `Success: no issues found in 5 source files`

**L2 证据：**
- `GET /api/auth/session` -> `200`，已登录用户 `tripplezhou@gmail.com`
- `GET /api/protected-test` -> `200`
- `GET /api/health` -> `200`
- 生产 `/api/health.version` = `8d9a9482ab15099d170155036609062e16627e4f`
- 本地 `HEAD` = `72a31697f11c7b52691b6869ea2ada9aa8e0ec06`
- `git diff --name-only 8d9a948..72a3169` 仅含 `progress.json`，因此生产产物与当前主线产品代码等价
- `GET /api/debug/recent-errors` 在 Backlog create / Snapshots refresh 后仍返回
  `{"count":0,"records":[]}`，说明 round-3 暴露的缺表错误已解除

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| Trading execution / broker integration | B022 仍然是 research-only workbench，不提供 paper/live order execution。 |
| Multi-user auth | 仍是单 allowlist 用户模型。 |
| Cloud SQL / Postgres | 仍未引入，生产继续使用 SQLite + backup。 |

---

## 类型检查 / CI

```text
Backend targeted pytest: 18 passed
Backend targeted ruff: All checks passed
Backend targeted mypy: Success, 5 source files

Production health version: 8d9a9482ab15099d170155036609062e16627e4f
Main HEAD: 72a31697f11c7b52691b6869ea2ada9aa8e0ec06
Diff from deployed SHA to HEAD: progress.json only
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha equivalent to main HEAD | `/api/health.version=8d9a948...`；`HEAD=72a3169...`；二者 diff 仅 `progress.json`，无产品代码漂移。 |
| OAuth / auth gate | 远程调试 Chrome 已登录，`/api/auth/session` 返回 allowlisted user，`/api/protected-test` 返回 200。 |
| Home dashboard | `GET /api/dashboard` 返回 200，页面渲染 recent reports 与零值空态。 |
| Strategies | 页面显示 `4 sleeves`。 |
| Backtest | 浏览器真实点击 `Run backtest` 后约 `551 ms` 返回 `run c5f6dc2dfe28`。 |
| Reports heavy tables | `/reports/B019-retune-sweep` 打开成功，`markdown-heavy-table` = `4`。 |
| Recommendations export | 页面按钮可点击，点击后提示 `Wrote /var/lib/workbench/runs/2026-05-18/order-ticket-2026-05-18.md`。 |
| Snapshots list + refresh | `/api/snapshots` 返回 `200 {"snapshots":[]}`；刷新后页面出现 `COMPLETE / Refresh complete.`，同时列表显示 `1 snapshots`。 |
| Backlog CRUD baseline | 受控 `POST /api/backlog` 返回 `201`，新建项 `BL-WB-4D3D0968` 出现在页面列表。 |
| Error buffer | `GET /api/debug/recent-errors` 在关键写路径后仍为 `count=0`，说明生产不再出现 `no such table`。 |
| Neighbor services | 本轮未发现对现有 authenticated user flow 的邻居服务干扰；health 维持 `db_connectivity=ok`。 |

---

## Ops 副作用记录

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| Codex | reverifying | 生产 authenticated `POST /api/backlog` 受控新增 1 条测试项 `BL-WB-4D3D0968` 用于验证缺表修复后的写路径 | 与该批次 F012 允许的最小必要 write 验收目标一致；未执行删除、批量修改、支付或外部通知 | 用户在本对话中明确要求继续 round-4 复验 |

---

## Harness 说明

本批改动经 Harness 状态机完整流程交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 生产 `/api/health.version` 仍停在 `8d9a948`，而主线 `HEAD` 为 `72a3169`；当前差异只含 `progress.json`，不影响产品等价性。 | low | 维持现状即可；后续任何产品代码改动都应再次要求 production version 对齐。 |
| S2 | Recommendations 直接 API `POST /api/recommendations/export-ticket` 若不给必填 `as_of_date` 会返回 `422`；页面 UI 流程会自行带上正确 payload。 | low | 保持当前 contract；若后续需要 CLI/API 手工触发，可补一份开发者调用示例。 |

---

## Framework Learnings

### 新规律
- deploy 脚本运行的 SSH shell 环境，不能假设与 systemd `EnvironmentFile=` 一致。
  - 来源：B022 fix-round 4，Alembic 迁移误落到 release scratch DB，直到请求触表才暴露。
  - 建议写入：`framework/harness/generator.md` 或 deploy 相关模板，要求所有 migration/deploy 脚本显式 source 生产 env file。

### 新坑
- 生产缺表问题在 `/api/health` 和基础 auth probe 上不会暴露，只有真实业务写路径才会触发。
  - 来源：B021 health/auth 全绿，但 B022 到 Backlog/Snapshots 才暴露 schema drift。
  - 建议写入：要求有 SQLite/Alembic 的云端批次在 L2 必须至少覆盖 1 个真实读表路径和 1 个真实写表路径。

### 模板修订
- Signoff 模板可补充一条“deployed SHA 与 HEAD 不一致时的等价性判断规则”。
  - 建议修改：`framework/templates/signoff-report.md`
