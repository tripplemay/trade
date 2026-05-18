---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B022-workbench-phase1：`reverifying`**（fix-round 3）。Round-2 deploy 之后 Codex L2 reverify 显示 3/4 路由恢复（/api/dashboard 200、/api/recommendations/current 200、/api/backlog GET 200、/api/recommendations/export-ticket 200），剩 /api/snapshots GET 500 + /api/backlog POST 500，且 operator 仍无 SSH 提供 journalctl。本轮 4 修复 + 1 新诊断面：(a) **services/snapshots.list_snapshots 加 degrade**（round-2 miss 了，只改了 SSE POST 没动 LIST），同 pattern try/SQLAlchemyError → 返空 list；(b) **routes/backlog._default_config prod fallback** — 真正的 backlog POST 根因：生产 wheel 装在 /srv/workbench/.../site-packages，Path(__file__).parents[4] 不是 repo root，dev 时的 `git add backlog.json && git commit` 链根本没 git tree。新逻辑 detect /srv/workbench/current 存在 → 写 /var/lib/workbench/backlog/backlog.json + _noop_git_runner；durability 靠 SQLite + daily backup（已记录限制：prod backlog 改动不进 git history，B023 接 proper auditable persistence）；(c) **services/backlog 3 个 mutation 加 per-phase 结构化日志** _log_phase_failure(operation, entry_id, phase, exc)，能在 journalctl/error buffer 里 tag db_upsert_commit / json_dump / git_commit；(d) **新 observability/error_buffer.py** in-memory deque(maxlen=50) + Lock 守护；(e) **新 auth-gated GET /api/debug/recent-errors** — 返 last 50 unhandled exceptions {ts,method,path,exception_type,exception_message}，替代 journalctl 给 Codex 诊断面。app.py global exception_handler 同时 record_error 和 _unhandled_logger.exception。Regression: test_db_degrade.py +1 snapshots，new test_backlog_prod_config.py 3 tests，new test_error_buffer.py 3 tests（踩到 typing.TypedDict 在 pydantic v2+py3.11 PydanticUserError 的坑，已切 typing_extensions.TypedDict）。本地：backend pytest 135+2 skipped(128→135)/ruff/mypy 93 / frontend lint+tsc+vitest 79 全绿；api.ts regen for /api/debug/recent-errors。等部署后 Codex curl /api/debug/recent-errors 即可看 500 实际 exception_type，不再需要 SSH。
- Spec：`docs/specs/B022-workbench-phase1-spec.md`（2026-05-17 已加 §Status + §Cloud+auth+Repository adaptation 段，标 ready to execute）
- 范围：7 read-mostly 业务页（Home / Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog）+ 最小必要 write（snapshot refresh / backlog CRUD / 触发 backtest / 导出 target positions Markdown）+ 5 chart 组件 + AG Grid table 组件 + workbench 文档+截图 + Codex L1+L2 真 VM 10 项验收。
- B020+B021 已交付的 8 surface F001 必须复用不重写：workbench skeleton / CI workflows / OpenAPI pipeline / NextAuth + 后端 JWT + allowlist / SQLite + Alembic + Repository + workbench-bootstrap CLI / systemd+nginx+cert / GHA deploy/rollback / SQLite→GCS backup / 观测层。
- 后续路径：**B023 Workbench Phase 2**（manual execution UI：position diff / order ticket / fill journal）。
- 关键决策：所有 frontend fetch 用 same-origin /api/* 路径（framework v0.9.24 #3 强制）；所有 API endpoint 在 require_authenticated_user gate 后；读 SQLite via Repository 非直读文件；ResizablePanel 仅 F008 Backtest 页用单页 split（不引 react-grid-layout）。
- 硬边界：no-broker / no-paper / no-live / no-secret-in-strategy；workbench cloud 仅 trade.guangai.ai 暴露 + OAuth 单 email allowlist；任何 placeholder 字符串 PLACEHOLDER-REPLACE-ME 不许进 workbench/ 源码；framework v0.9.24 #1-4 + v0.9.21 #1 + v0.9.22 + v0.9.23 全部继续约束。

## 已完成签收
- B001-B021 全部已签收；最近：B021 cloud deploy/auth `docs/test-reports/B021-cloud-deploy-auth-signoff-2026-05-17.md`

## 生产状态
- `https://trade.guangai.ai` live；OAuth gating 工作；/api/health 含 6 obs 字段；daily 03:00 UTC backup auto；nginx + pm2 aigcgateway + apify-kol 共住未受影响；workbench-deploy.yml CI/CD 全绿。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / **BL-B011-S2 high (B022 后接 satellite)** / BL-B013-D1 low / BL-B013-D2 low。
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B021 soft-watch S1：非 allowlist 浏览器实测未做（无可用第二 Google 账号）；L1 已覆盖。
- framework/proposed-learnings.md 为空（v0.9.21 + v0.9.22 + v0.9.23 + v0.9.24 已沉淀 9 条 5/15-5/17 候选）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
