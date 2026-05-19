# B023 Workbench Phase 2 Reverify-2 Blocker 2026-05-19

## Scope
- F008 fix-round-2 复验
- L1 本地启动 / backend + frontend 基线
- Playwright protected-route E2E
- `npm audit --omit=dev --audit-level=high`

## Result
- 结论：**FAIL / do not sign off**
- fix-round-2 解决了上一轮的 `.venv` 缺依赖阻塞：`codex-setup.sh` 现在会自动同步 `python-multipart`，backend 能启动，backend pytest / ruff / mypy 与 frontend vitest / lint / typecheck / build 皆可通过。
- 但 L1 仍未满足 F008 acceptance，存在两个阻塞项：
  1. `npm audit --omit=dev --audit-level=high` 仍为红，直接命中 acceptance。
  2. 按 AGENTS.md 规定的唯一本地启动路径 `bash scripts/test/codex-setup.sh` 启动时，默认 dev DB `workbench/backend/workbench-dev.db` 若未先迁移到 `0002_b023_execution_workflow`，`/recommendations`、`/execution/ticket`、`/execution/fills`、`/execution/journal-history` 会因缺表返回 500；手动执行 `bash workbench/backend/scripts/migrate.sh` 后，这 4 页 E2E 全转绿。

## Evidence
- 本地启动恢复：
  - `bash scripts/test/codex-setup.sh`
  - 结果：脚本自动执行 `.venv` re-sync，`python-multipart 0.0.29` 安装成功，backend 启动正常。
- Backend 基线：
  - `.venv/bin/python -m pytest workbench/backend/tests -q` → `202 passed, 2 skipped`
  - `.venv/bin/python -m ruff check workbench/backend/workbench_api workbench/backend/tests` → `All checks passed!`
  - `.venv/bin/python -m mypy workbench/backend/workbench_api workbench/backend/tests` → `Success: no issues found in 117 source files`
- Frontend 基线：
  - `cd workbench/frontend && npm test` → `29 passed, 117 passed`
  - `cd workbench/frontend && npm run lint` → `No ESLint warnings or errors`
  - `cd workbench/frontend && npm run typecheck` → pass
  - `cd workbench/frontend && npm run build` → pass
  - `rg -n "127\\.0\\.0\\.1:8723|http://127\\.0\\.0\\.1|localhost:8723|http://localhost:8723" workbench/frontend/.next` → no matches
- Playwright auth setup：
  - README 明示本地可用任意测试值设置 `NEXTAUTH_SECRET` + `ALLOWED_USER_EMAIL`
  - 使用：
    - `NEXTAUTH_SECRET=codex-local-test-secret`
    - `ALLOWED_USER_EMAIL=codex@example.com`
- 首次 authed E2E 失败根因：
  - 未带测试 env 启动 frontend 时，middleware 日志持续报 `MissingSecret`
  - 带测试 env 重启后，auth 恢复，问题收敛为 execution 页 API 500
- 执行页 500 直接证据：
  - Playwright 全量跑（带本地测试 env）先失败 4 页：
    - `/recommendations` → `GET /api/execution/risk-panel → 500`
    - `/execution/ticket` → `GET /api/execution/risk-panel → 500`, `GET /api/execution/tickets → 500`
    - `/execution/fills` → `GET /api/execution/tickets → 500`
    - `/execution/journal-history` → `GET /api/execution/journal-history → 500`, `GET /api/execution/slippage-analytics?window=3m → 500`
  - backend 实时日志：
    - `OperationalError: no such table: account_snapshot`
  - DB 状态（失败前）：
    - `sqlite3 workbench/backend/workbench-dev.db '.tables'`
    - 仅有 `account alembic_version backlog_entry snapshot_meta`
- 手动迁移后：
  - `bash workbench/backend/scripts/migrate.sh` → upgrade `0001_initial -> 0002_b023_execution_workflow`
  - `sqlite3 workbench/backend/workbench-dev.db '.tables'`
  - 结果：`account account_snapshot alembic_version backlog_entry fill_journal_entry order_ticket snapshot_meta`
  - 迁移后重启 + 复跑：
    - failing 4 页子集 → `5 passed`
    - protected-route + disclaimer 全量 → `19 passed (13.0s)`
- 审计阻塞：
  - `cd workbench/frontend && npm audit --omit=dev --audit-level=high`
  - 结果：exit 1
  - 直接命中：
    - `next` high advisories（含 SSRF / DoS / middleware bypass 等）
    - `postcss` moderate
  - 当前依赖：
    - `next: ^14.2.35`
    - `postcss: 8.4.47`

## Required Action
- Generator:
  - 解决 frontend prod dependency audit 红线，至少清掉 `npm audit --omit=dev --audit-level=high` 的 high finding。
  - 修复本地唯一启动路径对 dev DB schema 的要求：要么 `codex-setup.sh` / canonical local boot 流程自动确保 `workbench-dev.db` 到 `alembic head`，要么 fail-fast 并给出明确 migration gate；当前“服务能起但 execution 页 500”不可接受。

## Conclusion
- 本轮复验未通过。
- `progress.json` 应退回 `fixing`。
