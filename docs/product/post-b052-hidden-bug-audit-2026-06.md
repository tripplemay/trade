# 已上线功能全面审计——隐患/隐藏 bug 排查（2026-06-10）

> **作者：** Planner（用户 2026-06-10 指派「对已上线功能全面审计，排查类似隐患，找隐藏 bug」）。
> **背景：** 用户上手期三次报障揭示三个缺陷家族——B050 装饰性控件（输入被执行层忽略）、B051 两表读写分裂（写 A 读 B）、B052 演练数据污染（append-only 历史无过滤聚合）。本审计按家族 + 两个衍生视角（幂等占位复用 / 退化输入鲁棒性）全面扫描。
> **方法：** 3 路并行只读代码审计（两表分裂全表矩阵 / 污染面全扫 / 幂等+退化输入），关键发现经 Planner 亲自读码复核定性。
> **前序审计：** `b050-class-decorative-control-audit-2026-06.md`（装饰性控件）+ `trade-recommendation-fidelity-audit-2026-06.md`（交易保真度）——家族 1 已扫过两轮，本次聚焦新家族。

---

## 1. 结论摘要

**发现 1 个真隐患（中等）+ 2 个低风险注意项；其余大面健康。** 关键确认：B052 清理范围已覆盖全部演练污染点（无清理盲区），退化输入防守全面 graceful（B052 清完后单点数据安全）。

| 发现 | 严重度 | 判定 |
|---|---|---|
| advisor precompute 幂等不区分降级产物 | 🟡 中 | **真隐患**（B043 幂等占位同模式第二例）|
| risk_explanation 幂等条件可读性 | 🟢 低 | 现状 graceful（upsert 覆盖），改 update 会变隐患——注意项 |
| OrderTicket DB+Markdown 文件双源写入非原子 | 🟢 低 | 有 degrade 兜底（缺文件→重渲染，runbook 已记录）——by-design 注意项 |

---

## 2. 🟡 真隐患：advisor precompute 幂等把「拒答产物」当「真实产物」复用

- **位置**：`advisor/precompute.py:66-68` —— `if latest.generated_at.date() == run_date: skip`，**不检查 `latest.status`**。
- **机制**：`advise_sleeve` 在 LLM 不可用/拒答时落库 `STATUS_INSUFFICIENT_GROUNDING` 行；当日任何重跑（timer 重试/手动触发）看到「今天已有行」即 skip → **整日卡在拒答 advice，无法当日自愈**（次日 run_date 变化才重试）。
- **同模式先例**：B043 fix-round 1 ——recommendations precompute 幂等复用占位 rationale（永久卡住，因信号日季度才变）。advisor 此处是同一反模式的第二例，仅卡住时长不同（一天 vs 一季度）。
- **用户可见**：当日 LLM 抖动一次 → advisor 页全天显示拒答/无建议，即使 LLM 早已恢复。
- **修复**（一行 + 测试）：skip 条件加 `and latest.status == STATUS_OK`——降级行不算「已生成」，重跑时重试。
- **framework 含义**：「幂等/缓存复用必须区分真实产物 vs 占位/降级值」候选（B043 单例）**达二例门槛**，建议 done 阶段沉淀。

## 3. 🟢 低风险注意项（不立即修）

1. **risk_explanation.py:84**：幂等条件 `existing.explanation` 真值检查 + upsert（delete+insert）组合当前 graceful；若未来重构为条件 update，会复现 §2 同款隐患。修 §2 时顺手把条件改为显式 `is not None` + status 区分即可。
2. **OrderTicket DB 行 + Markdown 文件双源**（`tickets.py:405-418` 写入无事务原子性）：文件丢失（runs_dir 重置）→ detail 路由**降级重渲染**（`_resolve_markdown_file` docstring 明示，runbook §Troubleshooting 已记录「DB row preserved」）。判定 by-design 降级，非缺陷；若未来 ticket 量大可考虑 markdown 入库，目前不动。

## 4. ✅ 健康面确认（审计留证）

### 4.1 两表读写分裂（B051 家族）——无新分裂
- 20 张表写入者/读取者矩阵全扫：**B051 修复无遗漏**（无第三处 `select(Account)` 运行时读）；
- 语义相邻表对全部 by-design：`price_snapshot`（Home day-pnl，timer 写）vs `price_history`（NAV 序列，backfill 写）分工明确口径一致；`news`↔`news_embedding` FK+CASCADE 强同步；`investment_report`（canonical 权威）vs `backtest_run`（用户 ad-hoc）语义分离；`backtest_data_window` vs `snapshot_meta` 各司其职。

### 4.2 演练数据污染（B052 家族）——B052 范围无盲区
- 全部「无过滤全量聚合」点：master_drawdown / per_sleeve_drawdowns / wash_sale / journal-history / slippage analytics —— 污染源**全部**是 B052 正在清理的三表（account_snapshot/order_ticket/fill_journal_entry），**清完即全部自愈，无清理盲区**；
- latest-only 读取的 precompute 产物表（recommendation/advisor/risk_explanation/market_context/news）= 新行自然覆盖，自愈；
- `backtest_run` 无列表端点，验收期 run 用户不可见；`price_history/price_snapshot` 写入源唯一受控（Tiingo timer/backfill），无测试写入路径；
- `investment_report` 验收期报告是真实引擎产物（canonical 跑真数据），非污染；`llm/tiingo_budget_log` 演练消耗是真实花费的准确记账，且月份隔离，非污染。

### 4.3 退化输入鲁棒性——全面 graceful（B052 清理后安全）
- 单点/空 NAV 序列回撤=0（`nav_history.py:73-81` 显式防守）；空 per-sleeve→registry skeleton；空 fills/journal→结构化空态；`nav<=0`/`reference_price<=0`/0-trades metrics 全有显式守护。**无除零/`max([])`/空索引崩溃点。** B052 清完只剩 1-2 行快照时一切安全。

### 4.4 幂等检查全扫
- recommendations precompute：✅ 已修（B043 F001，显式对比占位文案）；backtest explanation：✅ run 一次性语义无缓存；risk_explanation：✅ 现状 graceful（见 §3.1）；advisor：🟡 见 §2。

---

## 5. 处置建议

1. **advisor 幂等修复**（一行+测试，小）：建议并入进行中的 B052（同为「降级值被当真」主题，先例 B050 F005 审计产出并入）；或入 backlog 下批做。
2. **framework 沉淀候选**（done 阶段提）：「幂等/缓存复用区分真实 vs 降级产物」（B043+advisor 二例达门槛）。
3. risk_explanation 条件显式化随 §1 顺手；OrderTicket 双源不动（degrade 兜底已足）。

**总判断**：三次报障的缺陷家族均无更多隐藏同类——B051 修复完整、B052 范围无盲区、退化输入全面防守。新发现的 advisor 幂等是 B043 同模式残留（当时只修了 recommendations 没扫 advisor），一行可修。系统数据流完整性经三轮审计后整体可信。
