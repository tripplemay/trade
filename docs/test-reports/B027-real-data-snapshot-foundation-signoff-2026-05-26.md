# B027 Real Data Snapshot Foundation Signoff 2026-05-26

> 状态：**PASS**
> 触发：F003 fix-round-1 后，Tiingo runtime dependency + health_check budget-log wiring 已解除 blocker

---

## 变更背景

B027 为 Stream 1 Real Data 接入打基础：引入 Tiingo snapshot loader、budget guard 与 `tiingo_budget_log`，但不切换任何 strategy 数据源。F003 的职责是对 F001/F002 做 L1 + L2 验收，并在 production 上确认真实 Tiingo smoke、budget log、secret 注入与既有 B026 banner 均正常。

---

## 变更功能清单

### F003：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-05-26.md`
- `docs/screenshots/B027-snapshot-foundation/production-health.png`
- `docs/screenshots/B027-snapshot-foundation/recent-errors.png`
- `docs/screenshots/B027-snapshot-foundation/strategies-banner.png`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

**改动：**
- 完成 B027 fix-round-1 后的 L1 本地复验
- 完成 production L2：Tiingo `health_check()` 真调用、`budget_log +1`、authenticated recent-errors、banner 保持显示
- 产出 signoff 报告并推进状态到 `done`

**验收标准：**
- backend `pytest/ruff/mypy`、frontend `vitest/build/Playwright` 通过
- production `/api/health.version` 与签收时 `main` HEAD 等价，或仅存在状态机元数据差异
- production `TiingoSnapshotLoader.health_check()` 返回 `True`
- `tiingo_budget_log` 真正 `+1`
- `/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
- B026 banner 仍显示

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| `trade/**` / `workbench/**` 产品实现代码 | 本轮仅做复验与签收，不修改任何产品实现 |
| strategy 数据源切换 | B027 仅打基础，不切到真实 market data |
| B026 banner 产品逻辑 | 本轮只验证其未受影响 |

---

## 类型检查 / CI

```text
L1 reverify:
- backend: pytest 277 passed, 2 skipped
- backend: ruff check . -> pass
- backend: mypy workbench_api tests -> pass
- backend: alembic round-trip (upgrade head -> downgrade 0002 -> upgrade head) -> pass
- frontend: vitest 166 passed
- frontend: next build -> pass
- frontend: Playwright 38 passed
- frontend: npm audit --omit=dev --audit-level=high -> no high severity (4 moderate only)
- artifact grep: .next/static 未命中 TIINGO_API_KEY / api.tiingo.com / backend host 泄漏
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha vs main HEAD | `curl https://trade.guangai.ai/api/health` 返回 `version=49462d62428b78c7f4ec66f5c66a3ae833a30ea0`；签收时本地 `HEAD=033d2f45163526129240e37f4cd1890223d57817`，两者 diff 仅含 `.auto-memory/project-status.md` 与 `progress.json` 这 1 个 reverifying metadata commit |
| 端到端 Tiingo smoke | VM 上按服务同工作目录 `/srv/workbench/current/backend`，以 deploy user + production env 执行 `TiingoSnapshotLoader().health_check()` 返回 `HEALTH_RESULT True` |
| budget log 真实写入 | 同次 smoke 前后：`BEFORE=2`，`AFTER=3`，`DELTA=1`；表内最新行为 `2026-05-26|2026-05|3|0.00015` |
| schema / migration | production DB `sqlite:////var/lib/workbench/db/workbench.db` 中 `.tables` 含 `tiingo_budget_log`；`alembic_version=0003_b027_tiingo_budget_log` |
| authenticated recent-errors | 使用 production `NEXTAUTH_SECRET` mint 的临时 HS256 cookie 访问 `https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}` |
| 浏览器手动验 | `https://trade.guangai.ai/strategies` authenticated HTML 命中中文 banner 文案 `研究原型 · 仅含合成数据 · 不构成投资决策依据`；截图已落盘到 `docs/screenshots/B027-snapshot-foundation/` |

---

## Ops 副作用记录

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| evaluator | reverifying | 生产 VM 上执行 1 次 `TiingoSnapshotLoader.health_check()` smoke | 预期副作用为 `tiingo_budget_log.call_count +1`，已核对 `2 -> 3` ✓ | 用户本轮明确授权开始 L1/L2 验收 |

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing → reverifying → done）交付。`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `49462d62428b78c7f4ec66f5c66a3ae833a30ea0` |
| Main HEAD (`git rev-parse HEAD`) | `033d2f45163526129240e37f4cd1890223d57817` |
| Diff (`git log --oneline <deployed>..HEAD`) | `1 commit` |

等价性判断：

- `git diff --name-only 49462d62428b78c7f4ec66f5c66a3ae833a30ea0..HEAD` 仅含 `.auto-memory/project-status.md` 与 `progress.json`
- 不含任何 `workbench/**`、`trade/**`、`docs/specs/**` 等产品代码或 spec 漂移
- 因此按 v0.9.25 规则接受不同步，视为**产品代码无漂移**

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | `N/A` |
| Workflow run 链接（若是） | `N/A` |
| Production 最终 SHA = signoff commit SHA | `N/A` |
| 接受不同步声明（若否） | `本次签收 commit 仅包含 signoff 报告、截图与状态机元数据，不含任何产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | F003 acceptance 文案写的是 `/etc/workbench/.env.production`，实际 production 读的是 `/etc/workbench/workbench.env` | low | 后续 Planner/Generator 更新相关 checklist 文案，避免再次出现环境文件名漂移 |

---

## Framework Learnings

本批次无 framework learnings。
