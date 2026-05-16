---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B021-cloud-deploy-auth：`reverifying`**；fix-round 4 完成（commits c727fd1 + 600fc55 + 1fc6983）。Codex L2 用 GET 测 signin/google 是 false positive — Auth.js v5 GET sign-in 是 UnknownAction，error=Configuration 是设计。POST signin/google with csrfToken → 302 `https://accounts.google.com/o/oauth2/v2/auth?client_id=346196763254-rosgk66u8l...&redirect_uri=https%3A%2F%2Ftrade.guangai.ai%2Fapi%2Fauth%2Fcallback%2Fgoogle&code_challenge_method=S256&scope=openid+profile+email` ✅。详见 docs/test-reports/B021-auth-flow-verification-2026-05-16.md。
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
- L1 fix-round 4 全绿：backend pytest 73/73 + ruff/mypy 52 files；frontend vitest 20 + lint/typecheck/build/Playwright 2/2 + 本地 dev 验证 OAuth providers JSON。生产 OAuth POST flow 已 302 Google + correct client_id/redirect_uri/PKCE。等 Codex 用浏览器跑 happy path + non-allowlist reject。
