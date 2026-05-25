# B025 US Quality Momentum Blocker 2026-05-25

## Scope

- B025 F006 首轮 L1 验收
- 覆盖 backend `pytest/ruff/mypy`、trade `pytest/mypy`、frontend `lint/typecheck/vitest/build/audit`、artifact/safety/offline 扫描、Playwright 本地套件与 B025 route/test 覆盖检查

## Result

- 结论：**L1 FAIL**
- 原因不是基础实现回归，而是 **B025 F005/F006 明确要求的 Playwright 双 locale 验收资产未交付**，导致 L1 acceptance 不成立，L2 也不能按规格继续

## Evidence

### 1. 基础 gates 全绿

- `cd workbench/backend && ../../.venv/bin/python -m pytest tests -q` → `241 passed, 2 skipped`
- `cd workbench/backend && ../../.venv/bin/python -m ruff check .` → `All checks passed!`
- `cd workbench/backend && ../../.venv/bin/python -m mypy workbench_api tests` → `Success: no issues found in 120 source files`
- `./.venv/bin/python -m pytest tests -q` → `727 passed`
- `./.venv/bin/python -m mypy trade` → `Success: no issues found in 62 source files`
- `cd workbench/frontend && npm run lint` → PASS
- `cd workbench/frontend && npm run typecheck` → PASS
- `cd workbench/frontend && npm test` → `34 files, 157 passed`
- `cd workbench/frontend && npm run build` → PASS
- `cd workbench/frontend && npm audit --omit=dev --audit-level=high` → exit `0`（仅 `4 moderate`）
- `cd workbench/frontend && rg -n "http://127\\.0\\.0\\.1:|http://(127\\.0\\.0\\.1|localhost):872[0-9]" .next/static || true` → 无命中
- `./.venv/bin/python -m pytest tests/unit/test_us_quality_fixture.py -q` → `25 passed`
- `./.venv/bin/python -m pytest tests/unit/test_us_quality_factors.py -q` → `24 passed`

### 2. 现有 Playwright 只有 19 项，低于 F006 要求的 `≥29`

- `cd workbench/frontend && npx playwright test --list | tail -n 5`
- 输出末行：`Total: 19 tests in 4 files`

### 3. `tests/e2e` / `tests/safety` 没有 B025 新增双 locale 套件文件

- `cd workbench/frontend && rg --files tests/e2e tests/safety`
- 输出仅有：
  - `tests/e2e/protected-routes.spec.ts`
  - `tests/e2e/home-loads.spec.ts`
  - `tests/e2e/auth-setup.ts`
  - 以及既有 safety specs
- 未看到任何 B025 新增的 zh/en route smoke、`/strategies` us-quality 验收、报告页 locale 验收等新 spec 文件

### 4. 现有 19 项旧套件在正确启动本地栈后可以通过，但这不能替代 B025 新增要求

- 先按规范启动：
  - `NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com bash scripts/test/codex-setup.sh`
  - backend 启动版本：`7174172`
- 再执行：
  - `cd workbench/frontend && NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test`
- 结果：`19 passed (23.3s)`
- 说明：当前 legacy suite 健康，但 **B025 F006 写明的 `19 baseline + ≥10 双 locale` 没有落地**

### 5. spec/L2 文案里的独立 `/risk` 路由在当前前端 app tree 不存在

- `cd workbench/frontend && find src/app -maxdepth 4 -type f | sort | rg '/risk|risk/'`
- 结果：无命中
- 另查：
  - `rg -n '/risk|risk-panel|RiskBanner|us_quality_momentum' workbench/frontend/src workbench/frontend/tests`
- 结果显示风险信息是通过 `src/components/risk/RiskBanner.tsx` 嵌入在 `recommendations` / `execution/ticket` 等页面，不是独立 `/risk` 页面

## Required Action

- Generator 需要补齐 B025 Playwright 验收资产，使 F005/F006 acceptance 可成立：
  - 新增至少 `10` 个 B025 双 locale Playwright 断言，覆盖 `zh-CN` / `en`
  - 覆盖 `satellite_us_quality` 的策略高亮、5 因子标签、recommendations 展示、report list/detail 双语内容、locale 切换与持久
- Planner/Generator 需要统一 spec 与实现口径：
  - 若本批次确实没有独立 `/risk` 路由，应把 F005/F006 的 `/risk` 验收改写为 `RiskBanner` 嵌入页验证
  - 若必须有 `/risk` 路由，则这是产品缺口，需由 Generator 实现

## Conclusion

当前不得签收，状态应退回 `fixing`。
