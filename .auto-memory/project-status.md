---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B022-workbench-phase1：`reverifying`**（fix-round 2）。Round-1 部署后 OAuth session 阻塞解（F014-1 通），但生产暴露 4 个 authenticated 路由 500：/api/dashboard、/api/recommendations/current、/api/snapshots/refresh SSE、/api/backlog GET。Codex 无法 SSH 拿 journalctl。本轮 3 个正交修复：(a) **Snapshots SSE 根因明确** — FastAPI 同步 get_session dep 在 StreamingResponse 拿 body 后就关 session；routes/snapshots.py 改用 `_streaming_session_factory()` 传 sessionmaker，services/snapshots.refresh_event_stream 收 factory 自己 own 生命周期(try/finally close)；(b) **app.py 全局 exception_handler** 用 `workbench.unhandled` logger 输 structured JSON(event/method/path/exception_type/exception_message+traceback)，下一次部署后 journalctl 能直接看到 3 个同步 500 的实际 SQLAlchemy 错；(c) **3 service 防御降级** — dashboard._aggregate_nav / recommendations._aggregate_account_state / backlog.list_backlog 全包 try/SQLAlchemyError → log + rollback + 返零/空 state，让页面渲染空 state 不 500（backlog 写操作不降级，silent drop 用户输入更糟）。Regression: tests/unit/test_db_degrade.py 4 tests + test_snapshots.py 加 SSE 不发 error 事件 assert。本地：backend pytest 128+2 skipped(124→128) / ruff / mypy 89 / frontend lint+tsc+vitest 79 全绿。等部署后 operator 给 `journalctl -u workbench-backend -n 200` 才能定 3 个同步路由根因。
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
