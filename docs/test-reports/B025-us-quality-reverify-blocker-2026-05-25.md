# B025 US Quality Reverify Blocker 2026-05-25

## Scope

- B025 F006 fix-round-1 后的 L1 复验
- 重点覆盖上轮 2 个 blocker 修复项：独立 `/risk` 路由、B025 新增 Playwright 双 locale 套件
- 同步回归 backend/trade/frontend 基础 gates 与 legacy Playwright protected-route 套件

## Result

- 结论：**L1 FAIL**
- fix-round-1 确实补上了 `/risk` 路由与 `33 tests in 5 files` 的 Playwright 规模，但新增与既有 Playwright 套件在真实运行时大面积失败，说明问题从“缺少测试资产”升级成了**实际 UI/selector/报告可见性/console 404 回归**

## Evidence

### 1. 基础 gates 仍然全绿

- `cd workbench/backend && ../../.venv/bin/python -m pytest tests -q` → `241 passed, 2 skipped`
- `cd workbench/backend && ../../.venv/bin/python -m ruff check .` → `All checks passed!`
- `cd workbench/backend && ../../.venv/bin/python -m mypy workbench_api tests` → PASS
- `./.venv/bin/python -m pytest tests -q` → `727 passed`
- `./.venv/bin/python -m mypy trade` → PASS
- `cd workbench/frontend && npm run lint` / `npm run typecheck` / `npm test` / `npm run build` → PASS
- `cd workbench/frontend && npm audit --omit=dev --audit-level=high` → exit `0`（仅 `4 moderate`）
- `cd workbench/frontend && rg -n "http://127\\.0\\.0\\.1:|http://(127\\.0\\.0\\.1|localhost):872[0-9]" .next/static || true` → 无命中

### 2. 上轮两个 blocker 的“形态”已解除

- `cd workbench/frontend && rg --files src/app tests/e2e | sort | rg 'risk/page|b025-us-quality-bilingual\\.spec\\.ts'`
- 命中：
  - `src/app/(protected)/risk/page.tsx`
  - `tests/e2e/b025-us-quality-bilingual.spec.ts`
- `cd workbench/frontend && npx playwright test --list | tail -n 8`
- 末行输出：`Total: 33 tests in 5 files`

### 3. 但 Playwright 实跑失败：`27 failed, 6 passed`

- 规范启动本地栈后执行：
  - `NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test`
- 结果：`27 failed, 6 passed (58.7s)`

### 4. 匿名 `/login` 断言失败：登录页关键 testid / disclaimer 不可见

- `tests/e2e/home-loads.spec.ts`
  - `getByTestId('login-page')` 不可见
- `tests/safety/disclaimer-present.spec.ts`
  - `getByTestId('workbench-disclaimer')` 不可见

### 5. B025 新增双 locale 套件失败点

- `tests/e2e/b025-us-quality-bilingual.spec.ts`
- 失败项包括：
  - `/recommendations` 上 `getByTestId('risk-sleeve-satellite_us_quality')` 不可见（zh/en 都失败）
  - `/risk` 上 `getByTestId('risk-banner')`、`risk-banner-per-sleeve-list`、`risk-sleeve-satellite_us_quality` 不可见（zh/en 都失败）
  - `/reports` 列表上 `getByTestId('report-link-B025-us-quality-momentum-backtest')` 不可见（zh/en 都失败）
  - `/reports/B025-us-quality-momentum-backtest` 页面上中文 disclaimer 文本 `仅供研究使用` 不可见（zh/en 都失败）
  - locale persistence 用例失败

`error-context.md` 中的 `/reports` 页实际可见内容为：

```text
heading "报告"
text: 0 份报告
paragraph: 暂无报告。
```

这直接说明“把 B025 backtest 报告重命名后进入 top-50 列表”的修复，在当前本地运行态并未生效。

### 6. legacy protected-route 套件也被打红：多页出现 console 404

- `tests/e2e/protected-routes.spec.ts`
- `/`、`/strategies`、`/backtest`、`/reports`、`/recommendations`、`/risk`、`/execution/*`、`/snapshots`、`/backlog` 等多数页面失败
- 共同错误模式：

```text
unexpected console errors:
  - Failed to load resource: the server responded with a status of 404 (Not Found)
  ... repeated 8 times
```

这不是测试前置问题，因为：
- 本地 backend health 正常
- frontend/build/vitest 全绿
- Playwright 已成功进入页面并执行 selector 断言

所以这是实际运行态资源/路由加载问题，不是“服务没启动”。

## Required Action

- Generator 需要修复运行态问题，而不是只补测试数量：
  - 恢复 `/login` 页的 `login-page` / `workbench-disclaimer` 契约，或同步修正既有测试与页面 contract
  - 让 `/recommendations` 与 `/risk` 真正渲染 `risk-banner` 和 `satellite_us_quality` sleeve 行
  - 让 `/reports` 列表实际出现 `B025-us-quality-momentum-backtest`，并确保 detail 页能看到双语 disclaimer
  - 排查 protected-route 套件里普遍出现的 console `404` 资源错误
- 修复后再回到 `reverifying`，重新跑完整 L1；本轮不进入 L2

## Conclusion

当前不得签收，状态应退回 `fixing`。
