---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B020-dev-infrastructure：`reverifying`**；fix-round 1：4f0b2a8 修了 Codex L1 唯一阻塞（start_workbench.sh `wait -n` → Bash 3.2 兼容的轮询循环 + regression 静态守卫 + README prerequisites 加 Bash 3.2+ 行）。两 workflow rerun 绿（backend 58s + frontend 3m16s，初次失败是 GHA runner 排队卡死不分配，重跑解决）。Codex 在 macOS /bin/bash 3.2.57 上复跑 boot smoke 后即可签收。其余 7 项 L1 checklist 已 PASS 不重跑。
- Spec：`docs/specs/B020-dev-infrastructure-spec.md`
- 范围：纯 dev tooling 批次——workbench/{backend,frontend} 骨架 + FastAPI hello-world + Next.js 14 placeholder + Vitest/Playwright config + 2 个 CI workflows + 5 个安全 guard regression 测试 + OpenAPI ↔ TS pipeline + dev 文档 + branch protection 指引。预估 1-1.5 周。
- 后续路径（renumber）：**B021 Cloud Deploy & Auth**（Google OAuth + SQLite + Dockerfile + nginx vhost for trade.guangai.ai + CI/CD push→SSH→deploy + 备份 + 可观测性）→ **B022 Workbench Phase 1**（14 features，原 B020 spec 重命名，cloud 适配后修订）→ **B023 Workbench Phase 2**（manual execution UI）。
- 关键决策（详见 `docs/adr/2026-05-15-workbench-direction.md` + cloud addendum）：技术栈 Next.js + shadcn/ui + AG Grid + lightweight-charts；模板 shadcn-dashboard-landing-template；P&L 色 #00c853/#ff3b30；部署到现有 GCP VM；OAuth allowlist 单 email；nginx 复用 aigcgateway 现有反代。
- 硬边界：`trade/` 模块零第三方依赖；workbench/ 独立依赖图；no-broker/no-paper/no-live/no-secret-in-strategy；workbench cloud 暴露限 trade.guangai.ai + Google OAuth allowlist；framework v0.9.21 #1 强制 real-data reverify；framework v0.9.22 强制 T+1 snapshot tail headroom。

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

## 生产状态
- 当前：本地 dev only。云部署 = B021 后 trade.guangai.ai（与 aigcgateway 共住 GCP VM）。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / **BL-B011-S2 high (workbench Phase 1 后衔接 satellite)** / BL-B013-D1 low / BL-B013-D2 low；BL-B018-S1 已由 B019 resolved。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B020 本地验收：backend lint/type/tests、frontend lint/type/tests/build、Playwright E2E、OpenAPI drift、5 个安全 guard trip-test 均完成；唯一 blocking issue 是 boot 脚本 Bash 3.2 兼容性。
- framework/proposed-learnings.md 当前为空（v0.9.21 + v0.9.22 已沉淀 3 条 5/15 候选）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
