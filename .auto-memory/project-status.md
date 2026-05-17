---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B021-cloud-deploy-auth：`reverifying`**；fix-round 5（commit 4eb9c48）：HEALTH_URL 改为 same-origin `/api/health` + dev-only Next.js rewrites 代理 backend + safety guard 防硬编码 localhost。CI 全绿、deploy 自动跑、生产 `/api/health` version=4eb9c48。等 Codex 重跑浏览器登录后看首页 Backend OK。
- Spec：`docs/specs/B021-cloud-deploy-auth-spec.md`
- 范围：cloud infra 层——Google OAuth（F001）+ SQLite/Alembic/Repository（F002）+ systemd/nginx/certbot（F003）+ GitHub Actions deploy/rollback（F004）+ SQLite→GCS backup/restore（F005）+ Codex L1+L2 + observability + signoff（F006）。
- 后续路径：**B022 Workbench Phase 1** → **B023 Workbench Phase 2**。
- B021 prep 5/5 ✅；`trade/` 零第三方依赖，workbench/ 独立依赖图。
- 硬边界：no-broker / no-paper / no-live / no-secret-in-strategy；CPUQuota=200% + MemoryMax=2G + OOMScoreAdjust=500 隔离邻居。

## 已完成签收
- B001-B020 全部已签收；B020 dev infrastructure: `docs/test-reports/B020-dev-infrastructure-signoff-2026-05-15.md`

## 生产状态
- 本地 dev only；trade.guangai.ai 待 B021 部署。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / BL-B011-S2 high / BL-B013-D1 low / BL-B013-D2 low；BL-B018-S1 已 resolved。
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- L1 fix-round 5 全绿：backend pytest 73/73 + ruff/mypy 52 files；frontend vitest 21（含新 no-hardcoded-backend-host safety）+ lint/typecheck/build/Playwright 2/2 + 本地 dev rewrite smoke probe（curl /api/health via Next.js → backend JSON）。生产 OAuth happy path + 首页 health probe 都应通。
