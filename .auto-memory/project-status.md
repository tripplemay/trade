---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B027-real-data-snapshot-foundation：`fixing`**；F001 completed（11206ac）+ F002 completed（3d14413）+ F003 pending。Spec：`docs/specs/B027-real-data-snapshot-foundation-spec.md`。
- Codex 首轮验收结论：**L1 PASS / L2 FAIL**。blocker 报告：`docs/test-reports/B027-real-data-snapshot-foundation-blocker-2026-05-26.md`。
- L1 已通过：backend `pytest 273 passed, 2 skipped` + `ruff` + `mypy` + alembic round-trip；frontend `vitest 166` + `build` + Playwright `38 passed`；artifact grep 未命中 `TIINGO_API_KEY` / Tiingo host 泄漏。
- L2 已确认通过子项：production `/api/health.version` == local `HEAD c46bda37cd165ed5a81153b9b876eee56ae2e5c7`；VM `/etc/workbench/workbench.env` 已有脱敏 `TIINGO_API_KEY`；SQLite 存在 `tiingo_budget_log` 表。
- **当前唯一硬 blocker：production runtime 缺 `httpx`。** Codex 在 VM 上按 systemd 同工作目录 `/srv/workbench/current/backend` 执行 Tiingo smoke：`from workbench_api.data.tiingo_loader import TiingoSnapshotLoader` 直接报 `ModuleNotFoundError: No module named 'httpx'`，因此 F003 L2 第 7 条（`health_check() -> 200 / budget_log +1`）失败。
- 根因特征：本地 `.venv` 带 dev 依赖所以测试全绿；backend `pyproject.toml` 当前仅在 `[project.optional-dependencies].dev` 声明 `httpx`，production venv 未安装该运行时依赖。
- 非阻塞观察：`/opt/workbench/.venv/site-packages/workbench_api` 未包含完整子包树，但 systemd 实际从 release 源码目录启动；这不是本轮 blocker 主因。spec 写 `/etc/workbench/.env.production`，实际是 `/etc/workbench/workbench.env`，属 checklist 文本漂移。
- Generator 下一步：补齐 production runtime `httpx` 安装路径并 redeploy；复验需重新证明 Tiingo smoke 成功、`budget_log +1`、`/api/debug/recent-errors` 正常，以及 B026 banner 不受影响。

## 已完成签收 + MVP 完工
- B001-B026 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B026 Synthetic Data Banner signoff 2026-05-26；B025 US Quality Momentum signoff 2026-05-25。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner。

## 永久硬边界（B027 起继续；v0.9.28 + B027 新增）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（**Tiingo API key 走 secret 不入代码**）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live Tiingo）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy
- 新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
