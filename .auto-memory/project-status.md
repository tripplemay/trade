---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B022-workbench-phase1：`building`**；F001-F003 完成（shadcn TW3 + 10 UI 组件 / 7 endpoint group schemas + 37 Pydantic models + 16 stub routes / TopBar+SideNav+ThemeProvider+SessionProvider shell + 6 stub pages + Playwright authed project；backend 106 pytest / frontend 21 vitest + 11 Playwright / 全套 lint/tsc/build 全绿）。Generator 接 F004（5 chart wrappers Equity/Drawdown/Heatmap/Pie/Bar + /dev/charts route）。共 14 features 完成 3。预估 5-6 周。
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
