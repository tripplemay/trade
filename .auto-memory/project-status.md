---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B013-regime-adaptive-multi-asset-mvp：`building`**；Planner 完成 spec + features.json，等待 Generator 起步 F001。
- Spec: `docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md`；用户研究稿移至 `docs/specs/research/B011-regime-adaptive-multi-asset-spec.md`。
- 11 features：F001-F010 generator + F011 codex。
- 关键决策：独立新策略（不污染 B010）；新 9 资产宇宙（SPY/QQQ/VEA/VWO + IEF/TLT/GLD/DBC + SGOV）；L1 200-SMA gating + L2 复用 B010 inverse-vol 8% target + L3 regime（Fast/Slow vol×1.5 & SPY trend → NORMAL/BEAR/CRISIS）+ 3% tolerance band + regime override；真实历史 snapshot 2018-2025（用户授权公开下载）；2020/2022 stress 验收 max DD<15%；轻量参数 sensitivity sweep；B011 Master Portfolio 新增 regime_adaptive sleeve（planning_weight=0.0 保留 B011 向后兼容）。
- 硬边界：fixture/mock-first 默认 CI、no-live/no-secret/no-broker/no-paper/no-AI、AI/LLM SDK 在 strategy 模块禁止（研究脚本除外）、snapshot 获取脚本 opt-in。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- 真实 paper/live broker adapter 仍未实现（B013 范围外）。
- BL-B010-S1（risk parity 专用 fixture）+ BL-B011-S2（satellite 策略 US Quality / HK-China）仍在 backlog；本会话新增 BL-B013-D1（smoothed vol targeting）+ BL-B013-D2（VIX 尾部对冲）+ BL-B010-S3（B010 升级 HRP/HRP-μ/CRISP）作为后续候选。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`（环境记录在 environment.md）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
