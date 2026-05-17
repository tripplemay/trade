---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B021-cloud-deploy-auth：`done`**；Codex F006 signoff：`docs/test-reports/B021-cloud-deploy-auth-signoff-2026-05-17.md`。L1 全绿；L2 生产 `/api/health` OK、登录后首页 `Backend: ok`、systemd quota/backup/邻居服务核验通过。
- Spec：`docs/specs/B021-cloud-deploy-auth-spec.md`
- 范围：cloud infra 层——Google OAuth（F001）+ SQLite/Alembic/Repository（F002）+ systemd/nginx/certbot（F003）+ GitHub Actions deploy/rollback（F004）+ SQLite→GCS backup/restore（F005）+ Codex L1+L2 + observability + signoff（F006）。
- 后续路径：**B022 Workbench Phase 1** → **B023 Workbench Phase 2**。
- B021 prep 5/5 ✅；`trade/` 零第三方依赖，workbench/ 独立依赖图。
- 硬边界：no-broker / no-paper / no-live / no-secret-in-strategy；CPUQuota=200% + MemoryMax=2G + OOMScoreAdjust=500 隔离邻居。

## 已完成签收
- B001-B021 全部已签收；B021 cloud deploy/auth: `docs/test-reports/B021-cloud-deploy-auth-signoff-2026-05-17.md`

## 生产状态
- `https://trade.guangai.ai` 已部署 B021 基础设施层；当前产品 artifact version `4eb9c48`，HEAD `ee9b4ce` 仅差状态机文件。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / BL-B011-S2 high / BL-B013-D1 low / BL-B013-D2 low；BL-B018-S1 已 resolved。
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B021 soft-watch：真实浏览器非 allowlist Google 账号拒绝路径未实测（无可用交互账号）；L1 已覆盖 signIn callback reject + backend 403。
