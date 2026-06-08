# 里程碑 C 验收复盘（2026-06-09）

> **作者：** Planner（用户 2026-06-09 指派「先做里程碑 C 验收复盘」）。
> **目的：** 里程碑 C 全线达成后的整体回顾——固化达成裁定与证据、盘点生产端到端现状、系统性捞出散落遗留项、给下一步建议。
> **配套：** `progress-review-2026-06.md`（§9.1 覆盖矩阵）+ 各批 signoff + `.auto-memory/project-status.md`。

---

## 1. 里程碑 C 定义与达成裁定

**里程碑 C 硬标准（2026-06-07 用户拍板）：** 所有用户投资页面显示内容均接真实引擎、无合成/占位；用户交易闭环端到端可用。

**达成裁定：🎯🎯 2026-06-09 正式达成**（B049 F004 Codex 签收 PASS）。

| 里程碑 C 硬标准 | 达成证据 | 批次 |
|---|---|---|
| 所有用户投资页面接真实引擎 | 8/8 页面审计全 real（Home/Rec/Reports/Risk/Strategies/Backtest/Snapshots/Execution）| B049 F004 |
| 无合成/占位 | 0 synthetic / 0 placeholder（Dashboard 死路由退役→404）| B049 |
| 交易闭环端到端可用 | BL-B023-S1 真实数据 9/9 smoke（target→diff→ticket→fills→reconcile→journal）| BL-B023-S1 |
| Master 4/4 真实 | data_source=real，20 positions，0 stub | BL-B011-S2 |
| 安全/风控层真实 | kill_switch/per-sleeve DD mark-to-market/wash_sale 全真 | B048 |

---

## 2. 交付批次序列（里程碑 C 路径）

| order | 批次 | 作用 | 状态 | 证据 |
|---|---|---|---|---|
| — | B044 | `/api/recommendations/current` equal-weight→Master 真实评分 | ✅ | signoff |
| — | B045 + B045-OPS1 | data-refresh pipeline（Tiingo+SEC→CSV→loaders）+ wheel 部署可靠性 | ✅ | data_source=mixed→real |
| 1 | B046 | execution diff mark-to-market + current_weight + regime reconcile | ✅ | AAPL 成本 13%→市价 23.47% |
| 2 | B048 + B048-OPS1 | F011 真实 per-sleeve NAV→安全层真实化 + alembic 部署可靠性 | ✅ | kill_switch 0.15 单一来源 |
| 3 | BL-B023-S1 | 交易闭环生产冒烟（真实 diff+安全层）| ✅ | 9/9 PASS |
| 4 | BL-B011-S2 | HK-China satellite 实现→Master 4/4 | ✅ | 20 positions，0 stub |
| 5 | B042 | Risk Panel Robinhood 化（真风控数据上）| ✅ | + BL-B023-S2 红态演练 |
| 6 | B047 + B047-OPS1 | Backtest 真实引擎 + Reports 真实投资报告 + 部署可靠性 | ✅ | `/api/reports` 返 1 真实报告 |
| 6.5 | B047-OPS2 | 回测页开箱即坏 hotfix（动态默认范围+深回填）| ✅ | 默认 Run 6pt/112trades/sharpe3.16 |
| **7（收口 gate）** | **B049** | 全页面真实化穷举审计 + 残余清理 | ✅ | **8/8 页面 real = 里程碑 C 达成** |

里程碑 C 路径**零 P0 缺陷逃逸**；部署可靠性问题统一拆 OPS 批次正交处理（B045-OPS1/B047-OPS1/B048-OPS1），未污染功能批次。

---

## 3. 生产端到端现状

- **prod = `9a3859a`**（B049 已部署，HEAD≡prod 零 diff）；recent-errors={count:0}。
- **真实交易闭环（live）**：`/api/recommendations/current`（20 pos 真实评分）→ mark-to-market diff（B046）→ gate 真实（kill_switch/wash_sale B048）→ ticket → fills → `/reconcile/{ticket_id}` 200 → journal。BL-B023-S1 已在真实数据上跑通 9/9。
- **运维接线全就位（零 admin 动作）**：`workbench-backtest-worker.service` auto-active（daemon sudoers 已应用）+ `workbench-canonical-backtest.timer` enabled+active（每日 04:00 生成投资报告）+ `workbench-data-refresh` timer（每日 02:30 刷数据写覆盖窗口）。
- **数据深度**：price_history 18463 行/37 symbol，覆盖 2021-06~2026-06（~5 年，B047-OPS2 深回填 1825 天）。

> **复盘判断**：生产闭环已由 BL-B023-S1 在真实数据上正面确证（9/9）。如需里程碑 gate 的**最终信心复测**，建议跑一次**全新生产端到端 re-smoke**（target→ticket→fills→reconcile→journal 真机一遍），属「产出报告」类任务 → **executor:codex（Codex-only 批次）**（铁律 7）。这是可选项，非阻塞达成裁定。

---

## 4. 遗留项清单（系统性扫描里程碑 C 各批 signoff）

> 来源：Explore 扫描 B044–B049 全部 signoff 的 Soft-watch/Finding，交叉核对解决状态。**绝大多数 soft-watch 已被后续批次解决**（详见各批 signoff）；以下为**仍开放**项。

| 严重度 | 遗留项 | 来源 | 现状 | 建议 |
|---|---|---|---|---|
| **Medium** | VM disk 使用率爬升（82%→84%）| B044 S1 / B045 S1 | 持续监控，无扩容/清理记录；disk 满时易丢诊断日志 | 定期清理日志/缓存或扩容；可单列轻量 OPS 批次 |
| **Low** | home nav=0.0（空账户未设 equity_snapshot）| B046 S1 | BL-B023-S1 冒烟仍复现；day_pnl 正常，仅空账户 nav 展示 | 补 equity_snapshot 初始化或改进空账户处理 |
| **Low** | valuation_basis=cost_degraded（price_history 不覆盖最新 snapshot 日期）| B048 S1 | 诚实标记已就位（非 bug）；待 data-refresh timer 拉近期价自动改善 | 监控；若长期不收敛再立项 |
| **软关注** | `risk-banner.spec.tsx F006` CI 偶发 flake（266/267）| B047-OPS2 | 本地 5/5 + re-run 绿，与改动无关；疑 happy-dom CI 高并发竞态 | 加 `await waitFor` 稳态断言或 quarantine（proposed-learnings 待二例）|

**关键结论**：里程碑 C 无**功能性**遗留（所有页面真实、闭环可用、安全层真）。仅剩 1 个 Medium 基础设施项（disk）+ 2 个 Low 边角项 + 1 个无关 CI flake。**均不影响里程碑 C 达成裁定。**

---

## 5. 复盘洞察

**做得好的：**
- **OPS 批次正交拆分**：部署/env 可靠性问题（B045-OPS1/B047-OPS1/B048-OPS1）一律拆出独立 OPS 批，功能批保持干净——三次「deploy 静默失效」沉淀为 framework §12.11（post-step assert end-state）。
- **诚实占位 ≠ 合成占位**：B049 审计明确区分「合成假数据」（要修）vs「诚实声明式占位」（stub/research-state weight 0.0——要保留，动了反隐瞒）。审计看「内容类别」非只 grep（Reports 接开发签收语料的错配教训）。
- **evaluator 纪律 §25**：core acceptance 须正面证据才可 done（B047-OPS2 默认 Run 非退化、B049 8 页逐页正面审计），杜绝「schema 对就放行」。

**framework 沉淀（里程碑 C 期间）**：v0.9.35→v0.9.40（§12.10 自包含审计扩 AST 守门 / §12.10.3 wheel force-include / §12.11 deploy post-step assert / §12.11.1 入口级 env 守门 / §25 evaluator 纪律）。当前活动候选（③async worker ④satellite 权重口径 + B037-OPS1 sudoers wrapper + CI flake）均单例待二例。

---

## 6. 下一步建议

1. **B043 AI 解释层（路线图唯一明确剩批）**：给 Recommendations/Backtest 加 LLM「为什么这样建议」富解释，解释现已干净全真实的 4/4 Master 评分+回测数字。受 no-AI 硬边界约束（no 收益预测/no 替代 quant/必须可引用/解释 summarize 允许，见 planner.md §AI 边界精细化 v0.9.28）。无 backlog 条目+无 spec，需先讨论定 scope。LLM gateway 可复用 B031 aigc。
2. **可选：生产端到端 re-smoke**（Codex-only 批次）——里程碑 gate 最终信心复测。
3. **可选：disk OPS 轻量批**——处理 Medium 遗留（disk 爬升），防 VM 满。

> 复盘结论：**里程碑 C 干净达成，无功能遗留**。建议优先讨论 B043 scope；disk/home-nav 等遗留可按需轻量处理或并入后续批次。
