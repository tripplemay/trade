# B052 — 生产演练数据清理 + 防再发（修复假 59.60% 回撤 / kill-switch 误触发）

> **批次类型：** 混合批次（1 generator + 1 codex），生产数据卫生 hotfix。
> **状态：** planning → building
> **触发：** 用户 2026-06-10 报：纯现金新账户，推荐页却显示「主组合回撤 59.60% + kill-switch 已触发」。
> **Planner 根因裁定（铁律 9）：** 历届批次 L2 真机验收在生产 `account_snapshot` 留下演练快照（含 BL-B023-S2 人为制造 DD 0.70 的红态演练高峰 ~$126k 量级）；`nav_history.reconstruct_nav_history`（nav_history.py:93）对**全部历史**重建 NAV 序列、回撤=peak-to-latest → 用户真实 $50k 接在演练假峰后被算成 −59.6%。**不会自愈**（假峰是历史最大值）且**误导交易**（kill-switch 触发 → Ticket 默认勾防守 → 新用户建仓会被引导 100% 买 SGOV）。
> **来源：** 用户报障 + Planner 实地核查 2026-06-10（机制 nav_history.py + 数字反推吻合 + source 字段无法区分演练/真实——演练用同一 UI/API 写入路径）。

---

## 1. 根因与影响

| 项 | 内容 |
|---|---|
| 机制 | `reconstruct_nav_history` 无过滤读全部 `account_snapshot`；`master_drawdown` = peak-to-latest |
| 污染源 | 历届 L2 真机验收演练（B046 浮盈演练 / BL-B023-S1 冒烟 NAV $35,246 + fills + journal / **BL-B023-S2 红态演练人为 DD 0.70（假峰 ~$126k）** / B050 防守测试 / B051 验收快照）；signoff 说「account 恢复」但表 append-only，旧行永存 |
| 用户可见失真 | ①Risk/Recommendations 假回撤 59.60% + kill-switch 误触发；②**Ticket 默认勾防守（误导建仓）**；③journal-history 显示演练 ticket/滑点；④wash_sale 读演练 fills；⑤risk_explanation 旧解释引用假 59.60% |
| 不会自愈 | 假峰=历史 max，除非用户 NAV 真超 ~$126k |

## 2. 范围

**做：** (a) 带安全预览的演练数据清理 CLI（执行域三表：`account_snapshot` / `order_ticket` / `fill_journal_entry`，统一 cutoff，dry-run 默认）；(b) 生产实施清理（用户确认边界后）；(c) 防再发=演练收尾清理纳入流程（evaluator 规约，done 阶段沉淀）。

**不做：** 不改 nav_history/risk 算法（机制本身正确，错在数据）；不碰 recommendation/backtest/news/price 等与账户演练无关的表；不做「基线重置」UI 功能（若未来仍需再立项）；不引入演练-source 标记（演练须走真实路径，标记会让验收失真且靠纪律不可靠）。

---

## 3. F001 — 清理 CLI + 生产实施（generator）

1. **清理 CLI**（如 `python -m workbench_api.cli.drill_cleanup`）：
   - 参数 `--keep-from <snapshot_id 或 ISO 日期>`：删除 cutoff **之前**的 `account_snapshot` / `order_ticket` / `fill_journal_entry` 行（执行域三表统一边界）。
   - **默认 dry-run**：完整列出将删行（id / 时间 / source / cash / positions·ticket·fill 摘要）+ 将保留行；`--apply` 才真删。
   - **§12.11.1 入口级 env 守门**：本 CLI 写生产 DB，入口必须套 `require_production_db`（缺 env 响亮失败不写 scratch）。
   - 删后顺带删 `risk_explanation_snapshot` 旧行（引用假回撤的陈旧解释），并提示触发 `systemctl start workbench-risk-explanation.service` 立即重生成（否则等 03:30 timer 自愈）。
2. **测试**：dry-run 不删 + apply 按 cutoff 精确删三表 + cutoff 之后行完整保留 + env 守门 + 空表 graceful。
3. **生产实施**：CLI 上 VM 后，dry-run 输出**交用户确认边界**（哪个快照起是真实数据——用户 2026-06-10 自填现金的那条），确认后 `--apply`。实施记录入 signoff §Ops 副作用。
4. **Gates**：backend pytest ≥ baseline+ / ruff 0 / mypy 0 / §12.10.2（CLI 不 import trade，纯 DB 操作）。

## 4. F002 — Codex L2 验收 + signoff（codex）

1. ★**核心反例（用户报障闭合）**：清理后生产 `/api/execution/risk-panel` master_drawdown ≈ 0（纯现金单点序列 peak=latest）；Recommendations gate `kill_switch PASS`（不再误触发）；Ticket 页**不再默认勾防守**；Risk 解释重生成后不再引用 59.60%。
2. **保留核验**：用户真实快照完整保留（Recommendations 仍「账户已就绪」+ home nav 真实）；journal-history 演练 ticket 清空。
3. **回归**：B051 账户流不破 / B043 解释 / B050 回测 / recent-errors=0 / HEAD≡main。
4. **Signoff**：`docs/test-reports/B052-drill-data-cleanup-signoff-2026-MM-DD.md`（§Ops 副作用=清理实施记录：删行数/各表/cutoff + §核心反例证据）。evaluator.md §25 正面证据。**演练自清**：本批验收若需写入演练数据，收尾必须用本 CLI 自清（首个执行新规约的批次）。

## 5. 防再发（done 阶段 framework 沉淀候选）

evaluator.md 新规约候选：**L2 真机演练写入执行域数据后，收尾必须清理自身写入行**（用 drill_cleanup CLI），「PUT 回原状态 ≠ 无痕」——append-only 历史表会永久记住演练。done 阶段提交用户确认。

## 6. Core Acceptance（一句话）

清掉用户真实使用之前的全部演练行（三表统一 cutoff、dry-run 预览、用户确认边界）后，生产回撤恢复真实（≈0）、kill-switch 不再误触发、Ticket 不再默认防守、用户真实快照完整保留。
