---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前批次
- **B002-data-source-and-broker-adapter-spec：`done`**（定义首期数据源、券商适配、PIT 数据模型和环境隔离规则）
- Generator 4/4 done，Evaluator F005 independent review PASS
- Signoff: `docs/test-reports/B002-independent-signoff-2026-05-12.md`

## 上一批次（B001 done，需补独立复验）
- Prior B001 self-signoff was invalidated; independent re-verification is tracked in backlog.

## 生产状态
- Documentation-only batch; no product code, migration, deployment, or live broker operation.

## 路线图（如有）
- Next likely batch: B003 global ETF backtest MVP planning.

## 已知 gap（非阻塞）
- B002 constraints are documentation-only; implementation batches need L1 guard tests for live-order rejection and PIT filtering.

## Backlog（延后）
- Independent B001 re-verification remains pending in backlog.

<!-- 写入规则（来自 harness-rules.md §记忆分层）：
1. 覆盖写，不追加；保持 ≤30 行
2. 所有角色都可写，谁产生变更谁更新
3. 内容边界：只放 WHAT（会变的事实），不放 HOW（行为规范，那是 role-context 的事）
4. 不重复 progress.json 已有的结构化数据（status/completed_features/fix_rounds 等）
-->
