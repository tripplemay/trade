# B047-OPS1 Backtest/Reports Deploy+Env Reliability Signoff 2026-06-08

> 状态：**PASS**
> 触发：B047-OPS1 F002 首轮验收

---

## Scope

B047-OPS1 修复 B047 三个部署/env gap：(A) canonical/worker CLI 缺 env→写 scratch DB；(B) worker 初始 disabled；(C) alembic 滞后。F001 修 env 硬失败 + deploy asserts，F002 Codex L2 验证。

---

## L2

| 项 | 证据 |
|---|---|
| Fresh deploy | `gh workflow run` → 7bb8000 deployed |
| Worker | active ✓ (auto from deploy, no manual enable) |
| Canonical timer | **enabled + active** (workbench-canonical-backtest.timer) ✓ |
| Alembic | at head (0013) ✓ |

### Canonical → Reports 端到端闭合

```
systemctl start workbench-canonical-backtest.service
  → "canonical investment reports written: 1" ✓ (writes to PROD DB)

GET /api/reports?kind=investment
  → reports=1, slug=master_portfolio-2026-06-08, kind=investment
  → title="Master Portfolio — Quarterly Backtest"
```

**确认 canonical 写 PROD DB → API 正确读取 → Reports 页面可渲染真实投资报告。** B047 re-verify 的「读路径待修」已纠正：根因为 env→scratch DB，非代码缺陷。

### B047 Gap Resolution

| Gap | B047 状态 | B047-OPS1 | 状态 |
|---|---|---|---|
| (A) env→scratch DB | canonical 写错 DB | env 硬失败 + assert | **已解决** |
| (B) worker disabled | 手动 enable | deploy auto install+enable | **已解决** |
| (C) alembic lag | 手动 upgrade | deploy assert-head | **已解决** |

---

## Conclusion

**Yes — 签收 PASS。** B047-OPS1 F002 全通过：

- Worker auto-active + canonical timer enabled+active ✓
- Canonical 写 PROD DB → /api/reports 返回 1 条投资报告 ✓
- Reports 端到端闭合（canonical → DB → API → 前端） ✓
- recent-errors={count:0} ✓
