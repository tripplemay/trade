# B020 Dev Infrastructure Signoff 2026-05-15

> 状态：**Evaluator 独立验收 PASS**
> 触发：B020 F005 复验完成，boot 脚本 Bash 3.2 兼容性已修复并在 macOS 默认 `/bin/bash` 3.2.57 上复测通过

---

## 变更背景

B020 交付 workbench-first 路线的基础设施层，不含业务页面、auth、数据库或 cloud deploy。F005 负责补齐分支保护指引、架构文档，并对整批基础设施做独立 L1 验收。

---

## 变更功能清单

### F005：Dev 文档 + branch protection 指引 + Codex L1 验收 + signoff

**Executor：** codex

**文件：**
- `docs/dev/branch-protection-guidance.md`（新增）
- `docs/dev/workbench-architecture.md`（新增）
- `docs/test-reports/B020-dev-infrastructure-review-2026-05-15.md`（新增）
- `docs/test-reports/B020-dev-infrastructure-signoff-2026-05-15.md`（新增）
- `progress.json`（更新）
- `.auto-memory/project-status.md`（更新）
- `workbench/scripts/start_workbench.sh`（generator 已修复，Codex 复验）
- `workbench/backend/tests/unit/test_start_workbench_portable.py`（generator 已新增）

**改动：**
- 分支保护指南明确 `main` 需要 `python-ci`、`workbench-backend`、`workbench-frontend` 状态检查，要求 linear history，禁止 force push，可选 1 review。
- 架构文档记录 workbench backend/frontend 的边界、生成类型管线、安全 guard、CI workflow 与后续 B021/B022/B023 分工。
- evaluator 先前发现 `wait -n` 不兼容 macOS 默认 Bash 3.2；generator 已把 boot 脚本改成 Bash 3.2 兼容的轮询退出，并加了 portable 守卫测试。
- Codex 复验确认一键 boot、健康检查、前端主页、E2E、安全 guard、OpenAPI drift 全部通过。

**验收标准：**
- `bash workbench/scripts/start_workbench.sh` 在默认 `/bin/bash` 3.2.57 上可启动 backend/frontend。
- `curl http://127.0.0.1:8723/health` 返回 `{"status":"ok","version":"<sha>"}`。
- `http://127.0.0.1:3000/` 看到 placeholder card 与 disclaimer。
- backend / frontend lint、typecheck、unit、Playwright、drift 全清。

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| `trade/` 产品实现 | 保持纯 stdlib，不做业务改动。 |
| B021/B022/B023 | 不引入 Google OAuth、SQLite、cloud deploy、业务页面或 execution UI。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| 一键 boot | macOS 默认 Bash 3.2 下失败 | 可用 |
| B020 状态 | `reverifying` / 待复验 | `done` |
| `docs.signoff` | `null` | 指向本报告 |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest workbench/backend/tests/ -q
7 passed

.venv/bin/python -m ruff check workbench/backend
PASS

.venv/bin/python -m mypy workbench/backend
PASS

cd workbench/frontend && npm run lint
PASS

cd workbench/frontend && npm run typecheck
PASS

cd workbench/frontend && npm test
PASS

cd workbench/frontend && PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright npm run test:e2e -- --reporter=list
2 passed

cd workbench/frontend && PYTHON_BIN=../../.venv/bin/python bash scripts/generate-types.sh && git diff --exit-code src/types/api.ts
PASS
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A — B020 仅 local/dev 验收，无 staging 部署。 |
| 端到端流验证 | 主页加载成功，显示 placeholder card + disclaimer。 |
| 关键 invariant | `/health` 返回 `ok`，版本为 `eed7d33`。 |
| 浏览器手动验（如 UI 类）| Playwright E2E 2/2 通过。 |

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程交付。
`progress.json` 已设为 `status: "done"`，`docs.signoff` 已填入本文件路径。

---

## Soft-watch

无。

---

## Framework Learnings

本批次无 framework learnings。

