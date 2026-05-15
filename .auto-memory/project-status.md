---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B021-cloud-deploy-auth：`building`**；F001 OAuth 已完成（commit 2a53c89，CI 全绿），共 6 features 完成 1。Generator 接 F002（SQLite + Alembic + Repository + workbench-bootstrap CLI + /api/health 扩 db_connectivity）。预估剩余 1.5-2.5 周。
- Spec：`docs/specs/B021-cloud-deploy-auth-spec.md`
- 范围：cloud infra 层——Google OAuth（F001）+ SQLite + Alembic + Repository 数据层（F002）+ systemd workbench-{backend,frontend}.service + nginx vhost trade.guangai.ai + certbot（F003）+ GitHub Actions push→SSH→deploy→healthcheck→rollback（F004）+ SQLite→GCS daily backup + 30 daily/12 monthly retention + restore（F005，需用户先 VM SA scope 扩展）+ Codex L1+L2 真 VM 验收 + 可观测性 + signoff（F006）。
- 后续路径：**B022 Workbench Phase 1**（14 features，原 spec B022-workbench-phase1，cloud 适配后修订）→ **B023 Workbench Phase 2**（manual execution UI）。
- B021 prep 5/5 ✅（OAuth + rotated secret + DNS A trade.guangai.ai + VM deploy 用户/dirs/key/sudoers + GCS bucket + 7 GitHub Secrets）。仍剩 1 manual prereq（F005 时做）：VM SA scope 扩展 `devstorage.read_only → cloud-platform`，~30-60s 跨服务下线（kolquest / aigcgateway / apify-kol 共住），用户低峰窗口做。
- 关键决策（详见 `docs/adr/2026-05-15-workbench-direction.md` + cloud addendum）：技术栈 Next.js + shadcn/ui + AG Grid + lightweight-charts；模板 shadcn-dashboard-landing-template；P&L 色 #00c853/#ff3b30；部署 GCP VM 复用现有 nginx；OAuth allowlist 单 email；SQLite + 持久盘 `/var/lib/workbench/db/`。
- 硬边界：`trade/` 零第三方依赖；workbench/ 独立依赖图；no-broker/no-paper/no-live/no-secret-in-strategy；CPUQuota=200% + MemoryMax=2G + OOMScoreAdjust=500 隔离邻居；framework v0.9.21 #1 real-data reverify + v0.9.22 T+1 headroom + v0.9.23 GHA Node 24 forward-compat。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- B014 regime-adaptive stress validation: `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`
- B015 regime-adaptive activation policy: `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`
- B016 risk parity HRP upgrade: `docs/test-reports/B016-risk-parity-hrp-upgrade-signoff-2026-05-15.md`
- B017 B015+B016 real-data validation: `docs/test-reports/B017-real-data-validation-signoff-2026-05-15.md`
- B018 gap root-cause attribution: `docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`
- B019 B010/B013 cadence + vol-target retune: `docs/test-reports/B019-retune-signoff-2026-05-15.md`
- B020 workbench dev infrastructure: `docs/test-reports/B020-dev-infrastructure-signoff-2026-05-15.md`

## 生产状态
- 本地 dev only；trade.guangai.ai 待 B021 部署。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / **BL-B011-S2 high (workbench Phase 1 后衔接 satellite)** / BL-B013-D1 low / BL-B013-D2 low；BL-B018-S1 已 resolved。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- framework/proposed-learnings.md 当前为空（v0.9.21 + v0.9.22 + v0.9.23 已沉淀 6 条 5/15 候选）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
