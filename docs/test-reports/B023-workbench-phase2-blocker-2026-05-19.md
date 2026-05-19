# B023 Workbench Phase 2 Blocker 2026-05-19

## Scope
- F008 L1 首轮验收
- 本地 `3099` 测试流程对应的 workbench backend/frontend 启动
- Backend `pytest` / `ruff` / `mypy`
- Frontend `vitest` / `lint` / `typecheck` / `build`
- B023 安全回归与构建产物静态检查

## Result
- 结论：**BLOCKED / do not sign off**
- 根因：backend 在导入 `POST /api/execution/fills/csv` 路由时因缺少运行时依赖 `python-multipart` 直接崩溃，导致本地服务无法启动，L1 smoke 在第一步失败，L2 未执行。
- 影响范围：所有导入 `workbench_api.app` 的 backend 单测在 collection 阶段统一失败，无法进入 F008 的完整本地验收流。

## Evidence
- 环境启动：
  - `bash scripts/test/codex-setup.sh`
  - 结果：backend 启动失败，报错 `RuntimeError: Form data requires "python-multipart" to be installed.`
- 后端测试：
  - `.venv/bin/python -m pytest workbench/backend/tests -q`
  - 结果：16 个 test modules 在 collection 阶段全部因同一 `python-multipart` 缺失报错，中断执行。
- 依赖状态：
  - `.venv/bin/pip3 show python-multipart`
  - 结果：`WARNING: Package(s) not found: python-multipart`
- 代码证据：
  - Multipart 路由定义位于 `workbench/backend/workbench_api/routes/execution.py` 的 `/fills/csv`
  - 依赖已声明于 `workbench/backend/pyproject.toml`：`python-multipart>=0.0.9,<1`
- 已通过的非阻塞子集：
  - `.venv/bin/python -m pytest workbench/backend/tests/safety -q` → `10 passed`
  - `.venv/bin/python -m ruff check workbench/backend/workbench_api workbench/backend/tests` → `All checks passed!`
  - `.venv/bin/python -m mypy workbench/backend/workbench_api workbench/backend/tests` → `Success: no issues found in 117 source files`
  - `cd workbench/frontend && npm test` → `29 passed, 117 passed`
  - `cd workbench/frontend && npm run lint` → `No ESLint warnings or errors`
  - `cd workbench/frontend && npm run typecheck` → pass
  - `cd workbench/frontend && npm run build` → pass
  - `rg -n "127\\.0\\.0\\.1:8723|http://127\\.0\\.0\\.1|localhost:8723|http://localhost:8723" workbench/frontend/.next` → no matches

## Required Action
- Generator:
  - 修复 backend 运行时依赖可用性问题，确保 `python-multipart` 在本地 `.venv` / CI / deploy 环境均被实际安装，而不是只在 `pyproject.toml` 中声明。
  - 补一个 fail-fast 校验，避免 `scripts/test/codex-setup.sh` 仅检查 `.venv` 存在却放过“依赖未同步”的脏环境。
  - 修复后重新进入 `reverifying`，由 Codex 重跑 F008 L1，再决定是否进入 L2 真 VM 18 项。

## Conclusion
- 本轮不能签收。
- `progress.json` 应转入 `fixing`，等待 Generator 修复后复验。
