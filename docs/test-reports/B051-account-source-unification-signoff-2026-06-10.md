# B051 Account Source Unification Signoff 2026-06-10

> 状态：**PASS**
> 触发：B051 F002 首轮验收

---

## Scope

B051 修复账户写入与读取分裂：UI Account 页写入 `account_snapshot` 后，Recommendations 与 Home 应立即读取同一账户源，不再受空 `account` 表影响。

---

## L1

```text
backend pytest (B051 targeted): 19 passed
frontend tsc: 0
frontend eslint: 0
```

后端定向覆盖：

- `test_account_source_unification.py`
- `test_bootstrap_cli.py`
- `test_home_route.py`
- `test_recommendations_request_self_contained.py`

---

## L2

### Production / Auth / Data Path

- `GET https://trade.guangai.ai/api/health` → `version=e297548cc977601ca06d71a789ff3d0a278a614a`
- 已登录生产浏览器会话下，关键读路径返回 `200`：
  - `/api/recommendations/current`
  - `/api/home`
  - `/api/execution/risk-panel`

### Core Acceptance: 纯现金账户

起始状态在生产 `/recommendations` 可直接观察到旧症状：

- `更新于 2026-03-31 · 账户 缺失`
- `尚未配置账户`
- `Account equity = 0.00`

随后在生产 `/execution/account` 以 UI 表单保存纯现金快照：

- `cash = 50000`
- `positions = []`
- UI 提示：`已保存快照 (id snap-48a90f5e43ae)`

保存后立即回到 `/recommendations`，正面证据：

- `更新于 2026-03-31 · 账户 已就绪`
- `目标持仓 20 个 sleeve`
- `Account equity = 50000.00`

判定：用户报障已修复。UI 设账户后，Recommendations 不再卡在 “尚未配置账户” 空态。

### Core Acceptance: 含持仓账户

继续在生产 `/execution/account` 以 UI 表单保存带持仓快照：

- `cash = 50000`
- `SGOV 10 shares @ avg_cost 100`
- UI 提示：`已保存快照 (id snap-47ef76c66212)`

保存后回到 `/recommendations`，正面证据：

- 仍为 `账户 已就绪`
- `SGOV 当前 1.97%`
- `SGOV 偏离 +19.98%`
- `Account equity = 51004.50`

判定：Recommendations 不仅认到账户存在，还读到了 snapshot 持仓和 mark-to-market 后的真实权益。

### Home NAV: B046 S1 Closed

在生产首页 `/`：

- 纯现金场景：`净资产 $50,000.00`
- 含持仓场景：`净资产 $51,004.50`
- `今日盈亏 +$0.30 (+0.03%)`
- sleeve 分解出现 `未分类 1 position`

判定：Home `nav` 已从 0.0 修复为真实 `cash + equity`。B046 soft-watch S1 可关闭。

### Regression

- Recommendations gate 仍正常工作：`kill_switch FAIL`、`min_equity PASS`
- Risk / Position Diff / Execution 相关读路径未见回归；保留登录态导航请求均返回 `200`
- 生产健康检查正常：`status=ok`, `db_connectivity=ok`

---

## High-Level Findings

- PASS：`account_snapshot` 已成为 UI 写入后的即时读源，Recommendations 读路径与 Account 页对齐
- PASS：纯现金与含持仓两种账户场景都能在同一生产会话里被立即识别
- PASS：Home NAV 已恢复真实值，B046 S1 关闭
- PASS：Recommendations gate 的 `min_equity` 现在基于真实账户权益，不再固定落在 `0.00`

---

## Ops 副作用记录

本批次无数据库 ops；L2 仅通过产品 UI 写入正常账户快照。

---

## Harness 说明

本批经 Harness 状态机 `planning → building → verifying → done` 交付。
本次签收将把 `progress.json` 更新为 `status: "done"`，并写入 `docs.signoff`。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `e297548cc977601ca06d71a789ff3d0a278a614a` |
| Main HEAD (`git rev-parse HEAD`) | `18bb4d43122c5e95dbc2a919924902e82f532f91` |
| Diff (`git log --oneline <deployed>..HEAD`) | `18bb4d4 chore(B051): framework 队列 — harness-rules 分支规则与 deploy workflow 实际行为失真（自动链式 vs 手动触发），done 阶段裁定` |

判断：HEAD 比 production 多 1 个 framework 元数据 commit；`git diff --name-only e297548..HEAD` 仅含 `framework/proposed-learnings.md`，产品代码无漂移，可接受。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告、`progress.json`、`.auto-memory/project-status.md` 等状态机/证据文件，未推产品代码；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。 |

---

## Decommission Checklist

本批次不含 decommission。

---

## Soft-watch

无。

---

## Framework Learnings

本批次无新增 framework learnings。

---

## Conclusion

Yes。B051 F002 验收通过，可以签收。
