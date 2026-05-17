# B021 Cloud Deploy & Auth Signoff 2026-05-17

> 状态：**PASS**（progress.json status=done）
> 触发：B021 F006 fix-round 5 后，Codex 对 L1 本地测试、L2 生产部署、OAuth 登录后首页健康探针做复验。

---

## 变更背景

B021 将 workbench 从本地开发脚手架推进到 `https://trade.guangai.ai` 的单用户云端基础设施层：Google OAuth、后端 JWT 验证、SQLite/Alembic/Repository、systemd/nginx 部署、GitHub Actions 自动部署、SQLite 到 GCS 备份，以及观测与健康检查增强。

本批次不包含业务页面、交易执行 UI、broker SDK、paper/live API、Cloud SQL/Postgres 或多用户能力。

---

## 变更功能清单

### F001：Google OAuth integration

**Executor：** generator

**验收结果：** PASS

**证据：**
- L1 auth 单元测试覆盖 allowlist callback、JWT encode/decode、backend JWT dependency、匿名/非 allowlist 行为。
- L2 既有 Chrome profile 打开 `https://trade.guangai.ai/` 后进入受保护首页，证明 allowlisted OAuth session 可用。
- 上轮 L2 已通过浏览器 OAuth happy path，并验证 `/api/auth/session` 为 `tripplezhou@gmail.com`、`/api/protected-test` 返回 200。

### F002：SQLite + Alembic + Repository data layer

**Executor：** generator

**验收结果：** PASS

**证据：**
- Backend pytest `73 passed`，覆盖 migration/bootstrap/repository/health DB connectivity。
- L2 `GET https://trade.guangai.ai/api/health` 返回 `"db_connectivity":"ok"`。

### F003：systemd + nginx + certbot deploy artifacts

**Executor：** generator

**验收结果：** PASS

**证据：**
- L2 `systemctl show workbench-backend.service workbench-frontend.service`：两服务均 `ActiveState=active` / `SubState=running`。
- 两服务均为 `CPUQuotaPerSecUSec=2s`、`MemoryMax=2147483648`、`OOMScoreAdjust=500`。
- 外网 `GET /api/health` 返回 200。

### F004：GitHub Actions deploy pipeline

**Executor：** generator

**验收结果：** PASS

**证据：**
- `Workbench Frontend CI` at `4eb9c48` completed success: https://github.com/tripplemay/trade/actions/runs/25978401123
- `Workbench Deploy` at `4eb9c48` completed success: https://github.com/tripplemay/trade/actions/runs/25978424745
- Production `/api/health.version` is `4eb9c48d5488c876cbe34d517d9d65a2a5bd47d7`.
- Local HEAD is `ee9b4ce43605f1afec58bc07c08b4bf0925f07c8`; `git diff --name-only 4eb9c48..HEAD` only contains `.auto-memory/project-status.md` and `progress.json`, so the deployed product artifact is equivalent by the harness SHA mismatch rule.

### F005：SQLite snapshot backup to GCS

**Executor：** generator

**验收结果：** PASS

**证据：**
- L2 GCS daily bucket contains backup objects:
  - `workbench-20260515T200927Z.db.gz`
  - `workbench-20260515T204316Z.db.gz`
  - `workbench-20260516T030001Z.db.gz`
- Production `/api/health` reports `last_backup_size_bytes=114` and non-null `last_backup_age_seconds`.

### F006：Observability + Codex L1/L2 verification

**Executor：** codex

**验收结果：** PASS

**L1 证据：**
- Backend: `../../.venv/bin/python -m pytest` → `73 passed`
- Backend: `../../.venv/bin/python -m ruff check .` → `All checks passed`
- Backend: `../../.venv/bin/python -m mypy` → `Success: no issues found in 52 source files`
- Frontend: `npm test` → `21 passed`
- Frontend: `npm run lint` → no ESLint warnings/errors
- Frontend: `npm run typecheck` → pass
- Frontend: `npm run build` → pass
- Frontend Playwright: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3099 npm run test:e2e` → `2 passed`
- Dev rewrite probe: `curl --noproxy '*' http://127.0.0.1:3099/api/health` returned backend JSON with `"status":"ok"` and `"db_connectivity":"ok"`.

**L2 证据：**
- `GET https://trade.guangai.ai/api/health` returned:

```json
{"status":"ok","version":"4eb9c48d5488c876cbe34d517d9d65a2a5bd47d7","db_connectivity":"ok","uptime_seconds":1061.827,"last_backup_age_seconds":83438.832,"last_backup_size_bytes":114,"active_user_count":0}
```

- Browser screenshot on production signed-in home shows `Backend: ok (build 4eb9c48d5488c876cbe34d517d9d65a2a5bd47d7)`, closing the prior `Backend unreachable: Failed to fetch` blocker.
- VM resource limits verified by `systemctl show`.
- Neighbors: `nginx` active; PM2 `aigc-gateway`, `kolmatrix`, and `kolmatrix-staging` processes online.

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| Trading / broker integration | B021 is infrastructure only; broker SDKs and paper/live URLs remain forbidden. |
| Business workbench pages | Strategy, recommendation, execution, and portfolio pages are deferred to B022/B023. |
| Multi-user auth | OAuth allowlist remains single-user. |

---

## 类型检查 / CI

```text
Backend pytest: 73 passed
Backend ruff: All checks passed
Backend mypy: Success, 52 source files
Frontend vitest: 21 passed
Frontend lint/typecheck/build: pass
Frontend Playwright: 2 passed

Workbench Frontend CI 4eb9c48: success
Workbench Deploy 4eb9c48: success
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha equivalent to main HEAD | `/api/health.version=4eb9c48d...`; `HEAD=ee9b4ce...`; diff from deployed SHA to HEAD only contains `.auto-memory/project-status.md` and `progress.json`, so no product-code drift. |
| OAuth happy path | Existing allowlisted Chrome session reaches `https://trade.guangai.ai/` protected home instead of `/login`; previous L2 report verified browser OAuth returned `tripplezhou@gmail.com` session and `/api/protected-test` 200. |
| Home backend probe | Production screenshot shows `Backend: ok (build 4eb9c48d...)`. |
| Health endpoint | Public `/api/health` returns 200 with `status`, `version`, `db_connectivity`, `uptime_seconds`, `last_backup_age_seconds`, `last_backup_size_bytes`, `active_user_count`. |
| VM isolation | Backend and frontend services active with CPUQuota 200%, MemoryMax 2G, OOMScoreAdjust 500. |
| Backup | GCS daily bucket has at least 3 backup objects; health reports latest backup size. |
| Neighbor services | `nginx` active; PM2 `aigc-gateway`, `kolmatrix`, `kolmatrix-staging` online. |

---

## Ops 副作用记录

本批次 Codex 复验未执行数据库 ops，未执行删除、批量修改、支付或外部通知。VM 侧只读检查为 `systemctl show`、`gcloud storage ls`、`systemctl is-active`、`pm2 list`。

---

## Harness 说明

本批改动经 Harness 状态机完整流程交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 真实浏览器非 allowlist Google 账号拒绝路径未实测；当前机器只有 allowlisted 登录态。L1 已覆盖 frontend signIn callback 非 allowlist false、backend 非 allowlist JWT 403。 | low | 下次有可用非 allowlist 测试 Google 账号时补一次手工 L2。 |
| S2 | AGENTS 引用的 `docs/dev/codex-policies.md` 和 `scripts/test/codex-{setup,wait}.sh` 当前仓库不存在；本轮按 harness/evaluator 规则和子项目脚本完成验证。 | low | Planner done 阶段确认文档/脚本引用是否需要补齐或更新。 |

---

## Framework Learnings

本批次无新的 framework learnings 需要追加。
