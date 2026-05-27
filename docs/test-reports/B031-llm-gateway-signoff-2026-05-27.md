# B031 LLM Gateway Signoff 2026-05-27

> 状态：**PASS**
> 触发：Generator fix-round 1 修复 production gateway URL / endpoint / envelope wiring 后，Codex 完成 F003 复验

---

## 变更背景

B031 是 Phase 2 / Stream 3.A 的起点批次，为 workbench backend 接入 `aigc-gateway` HTTP REST，建立统一 chat / embedding 抽象、routing table 和月度 cost guard。F003 的职责是做 Codex L1 + L2 真 VM 验收并签收。

---

## 验收结论

- `L1 PASS`
- `L2 PASS`
- `signoff = PASS`

本轮修复后，production `LLMGateway().health_check()` 已恢复为 `True`，并保持 `llm_budget_log` `BEFORE=0 / AFTER=0`，说明 gateway reachability 与 no-billing 两条硬边界同时成立。

---

## L1 结果

- backend `pytest`: `469 passed, 2 skipped`
- backend `ruff`: pass
- backend `mypy`: pass
- alembic round-trip: pass
- trade `pytest`: `778 passed`
- trade `mypy`: pass
- frontend `vitest`: `172 passed`
- frontend `build`: pass
- frontend `npm audit --omit=dev --audit-level=high`: only `4 moderate`, no `high`
- Playwright: `38 passed`

安全/边界检查：

- `AIGC_GATEWAY_API_KEY` 四处接线仍存在：
  - `workbench/backend/.env.example`
  - `workbench/backend/workbench_api/settings.py`
  - `workbench/deploy/scripts/deploy.sh`
  - `.github/workflows/bootstrap-env.yml`
- model-name boundary 仍只命中 `routing.py` / fixtures / tests
- `.next` 构建产物未发现 gateway secret / host / model ID 泄漏

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha == main HEAD | production `/api/health.version` = `f31c3027b5a42f4585783d69eb2f84ba290352c5`；local `git rev-parse HEAD` = `f31c3027b5a42f4585783d69eb2f84ba290352c5` |
| VM env 注入 | `/etc/workbench/workbench.env` 中 `AIGC_GATEWAY_API_KEY` 存在（脱敏校验） |
| budget log table | `sqlite3 /var/lib/workbench/db/workbench.db "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_budget_log';"` 返回 `llm_budget_log` |
| gateway smoke | VM 上 `LLMGateway().health_check()` 返回 `True` |
| no-billing invariant | `llm_budget_log` 聚合 `BEFORE=0 / AFTER=0` |
| production recent errors | authenticated `/api/debug/recent-errors` 返回 `{"count":0,"records":[]}` |
| B026 banner invariant | authenticated `/strategies` `/reports` `/recommendations` `/risk` HTML 检查均为 `BANNER_ABSENT` |

---

## Ops 副作用记录

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（building → verifying → fixing → reverifying → done）交付。`progress.json` 已更新为 `status: "done"`，`docs.signoff` 已指向本文档。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `f31c3027b5a42f4585783d69eb2f84ba290352c5` |
| Main HEAD (`git rev-parse HEAD`) | `f31c3027b5a42f4585783d69eb2f84ba290352c5` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0 commits` |

结论：`PASS`

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | `N/A` |
| Workflow run 链接（若是） | `N/A` |
| Production 最终 SHA = signoff commit SHA | `N/A` |
| 接受不同步声明（若否） | `本签收 commit 仅包含 progress.json / features.json / .auto-memory / docs/test-reports / docs/screenshots 等状态机与证据文件，不含产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

---

## Decommission Checklist

本批次不含 decommission。

---

## Soft-watch

无。

---

## Framework Learnings

### 新规律

- 第三方 gateway 接入批次不能只依赖 spec 假设，必须在 F001 阶段就用 live catalog / live envelope 校正 URL、endpoint 和 response shape。
  - 来源：B031 F003 round-1 blocker（placeholder host + invented `/balance` / invented JSON envelope）
  - 建议写入：`framework/harness/generator.md`
