---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- B112 → done（2026-08-06，fix_rounds=2，2/2）。
- 签收：docs/test-reports/B112-signoff-2026-08-06.md；独立证据：
  docs/test-reports/B112-F002-independent-evidence-2026-08-06.json。
- 最终机制裁定（100 万档）：pure NO-GO；quality NO-GO。
- 容量观察（10 万档）：pure NO-GO；quality GO，不覆盖其机制档失败。
- H6：30×1500 PIT 宇宙；三段价格合计 5,731,069 行；CSI300 窗口交易日
  1780/1780；V0 已对 pre-B112 2e81836 固定 golden。
- 本地 18/18 定向、1777/1777 全量、ruff/mypy/compile 全绿；
  Python CI 31141903592、Backend CI 31141903609、Deploy 31142505697 全绿。
- 防御闸未接入 strategy_modes / precompute / timer / readiness；DATA_NO_GO 不变。

## 遗留 / 跟踪
- Soft-watch：跨进程浮点末位噪声 ≤3e-13；hash 差异须展开字段 diff，
  ≤1e-10 且仅数值末位可接受，否则 blocker。
- backlog：BL-B112-OPS1、BL-B112-PRB1 保留。
- proposed-learnings 待 Planner done 阶段处理。
- 生产服务器：ssh deploysvr（旧 GCP IP 已退役）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins。
- Generator 不裁自己代码；被规则挡住不等于被验证；Generator 不得抽评测样本。
