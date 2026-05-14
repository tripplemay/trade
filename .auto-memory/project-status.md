---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B014-regime-adaptive-stress-validation：`done`**；Codex 已完成 reverifying，写入签收报告并把 `docs.signoff` 指向 `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`。
- Spec: `docs/specs/B014-regime-adaptive-stress-validation-spec.md`（含 Amendment 2026-05-14 数据源 pivot）。
- 已交付：9 资产真实 acquisition manifest 稳定；stress 验收通过（2020 max DD `-0.0476334902`，2022 max DD `-0.0165552431`）；cross-strategy comparison 完成（共享 overlap window 2020-06-01..2022-12-31，B013/B006/B010/60-40 都已跑完）；signoff 已落盘。
- 关键决策（不变）：9 资产宇宙；SGOV 实际首可得日 ~2020-06-01；2020 窗口使用 SGOV cash-placeholder pre-inception rows；2022 窗口完整可用；跨策略对比在 B010 default 可跑的 overlap window 上执行；max DD>15% 才走 proposed-learnings，本批未触发。
- 硬边界：默认 CI 仍 fixture/mock-first；yfinance 仅用于 scripts/ 和评估；no-broker/no-paper/no-AI/no-secret-in-strategy。
- 踩坑沉淀：B006 default 宇宙不能直接吞含 SGOV 的全量比较 bundle，需按策略宇宙拆分记录集；B013 2020 stress 需要 SGOV pre-inception cash-placeholder rows 才能按 spec 得出可用结果。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- BL-B010-S1 + BL-B011-S2 + BL-B010-S3 + BL-B013-D1 + BL-B013-D2 仍在 backlog。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`（环境记录在 environment.md）。
- B014 真实 CSV、manifest、stress report、comparison report、signoff 已全部落地；后续若要继续迭代，只需从 `docs/test-reports/` 和 `progress.json` 续接。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
