---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B003-mvp-product-prd：`done`**；MVP PRD 已独立签收。
- 当前无 active batch；`backlog.json` 有 BL-001，等待下一批次纳入或裁决。

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`

## 生产状态
- Documentation-only so far; no product code, migrations, deployment, broker API, secrets, or live-money operation.

## 下一步建议
- Next Planner should open **B004-core-engineering-foundation**.
- B004 should produce engineering docs/spec first: Python package boundary, config, fixture policy, pytest/ruff/CI, no-live guards, frontend architecture plan only.
- BL-001: incorporate `docs/research/strategy-audit-report-2026-05-12.md` into portfolio allocation / account-level risk planning before B005 scope locks.

## 已知 gap（非阻塞）
- B004/B005 need fixture/mock-only CI and L1 guards for no live broker, PIT, paper/live boundaries, and AI no-buy/no-autoparameter behavior.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
