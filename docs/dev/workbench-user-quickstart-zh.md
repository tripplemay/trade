# 工作台新用户快速上手（中文）

> **维护：** Planner（2026-06-10，应用户两次询问固化；B051 账户源修复后的现状）。
> **权威依据：** `docs/dev/workbench-manual-execution-runbook.md`（与本文冲突时以 runbook/spec 为准）。
> **读者：** 第一次使用工作台的用户（从零现金账户开始）。

---

## 一、心智模型（30 秒）

工作台是你的**投资研究顾问**，不是自动交易机器人。它做三件事：

1. **告诉你该持有什么**——真实市场数据 + Master Portfolio 4 策略（动量 40% / 风险平价 30% / 美股质量 20% / 港股中国 10%）算出目标组合；
2. **告诉你怎么调**——对比你的实际持仓（mark-to-market），算出每标的买/卖股数，生成订单清单（Markdown ticket）；
3. **帮你记账复盘**——券商成交后回填，算执行滑点。

**它永远不下单**（research-only / no-broker）。所有交易由你在券商 App 手动执行。

---

## 二、第一次使用：设置账户（一次性）

1. 登录 `https://trade.guangai.ai`（授权 Google 账号）。
2. **Execution → Account**（`/execution/account`）：
   - **Cash**：可投资现金（如 `100000`）
   - **Base currency**：`USD`
   - **Positions**：已有持仓逐行填（symbol/shares/avg_cost）；**纯现金就留空**（空行自动跳过）
3. **Save**。立即生效：Home 显示净资产；Recommendations 显示「账户已就绪」+ 目标持仓。

---

## 三、日常节奏（三个频率）

| 频率 | 做什么 |
|---|---|
| **每天/随时（1 分钟）** | Home（净资产/今日盈亏）+ Recommendations 顶部**风险横幅颜色** |
| **想深入时** | Reports / Risk / Backtest / Strategies 自由看 |
| **该调仓时** | 走 §四 的 7 步闭环 |

**何时调仓（三选一）：** ① 季度末（策略按 quarter-end 信号调仓，主节奏）；② 风险横幅变红；③ 持仓与目标偏离明显变大。**勿频繁交易。**

**风险横幅：** 🟢 绿=master 回撤 <8% 正常；🟡 黄=某 sleeve 回撤 ≥8% 留意；🔴 红=master 回撤 ≥15% kill-switch 触发 → Ticket 页出现「正常/防守」单选（防守=100% 轮入 SGOV，默认勾防守需主动选回正常）。

---

## 四、调仓 7 步闭环

```
① Recommendations → ② Position diff → ③ Ticket → ④ 券商下单（你）
                                                        ↓
   ⑦ Journal history ← ⑥ Reconcile ← ⑤ Fills（回填成交）
```

1. **Recommendations**（`/recommendations`）：看目标组合 + per-position AI「为什么」（引用真实评分/信号日）+ 风险横幅。
2. **Position diff**（`/execution/position-diff`）：每标的带符号 Δ 股数——🟢正=买、🔴负=卖。
   - ⚠️ **第一次建仓**：持仓为零时部分标的进 **"Unmatched targets"**（无成本参考价），只给目标权重，股数自算：**股数 ≈ 目标权重 × 现金 ÷ 现价**（例：20% × $100,000 ÷ $50 = 400 股）。回填一次成交后即全自动。
3. **Ticket**（`/execution/ticket`）：**Generate ticket** → 生成 Markdown 清单 → **Download**。红态有正常/防守单选。**Void latest** 可作废（作废后不可 reconcile）。
4. **券商下单**：照清单下**限价单**（LIMIT；参考价="Reference close" 列，非实时）。
5. **Fills**（`/execution/fills`）：上传券商成交 CSV（Schwab / IBKR / 通用三格式，见 runbook §CSV formats）或手工逐行填。无法匹配的行勾选 `allow_unmatched` 重提。
6. **Reconcile**：标记 ticket 已执行 + 算滑点 + 用实际成交生成新账户快照。目前经 API 触发（专页在待办）：
   ```bash
   curl -X POST -H "Cookie: authjs.session-token=<session>" \
     https://trade.guangai.ai/api/execution/reconcile/<ticket_id>
   ```
   重复调用幂等（`already_reconciled=true`）。
7. **Journal history**（`/execution/journal-history`）：总滑点 / 月度趋势 / 异常笔 / 窗口切换 3m-6m-1y。

> **第 6 步很重要**：reconcile 后系统才有你的真实成本基础，下次调仓全自动算股数。

---

## 五、页面速查

| 页面 | 用途 |
|---|---|
| Home | 净资产+今日盈亏总览（每日一瞄）|
| Recommendations | 目标组合+AI 解释+风险横幅（决策起点）|
| Execution → Account | 账户（现金+持仓），一切计算的地基 |
| Execution → Position diff | 该买卖多少股 |
| Execution → Ticket | 生成/管理订单清单 |
| Execution → Fills | 回填券商成交 |
| Execution → Journal history | 执行质量复盘 |
| Risk | 风控详情（回撤/kill-switch/AI 解释）|
| Reports | 每日真实业绩报告（canonical）|
| Backtest | 自选策略+时段历史回测（含 AI 解释）|
| Strategies | 4 sleeve 策略说明 |
| Snapshots | 数据新鲜度 |
| backlog / dev / docs | 内部工具页（日常可忽略）|

---

## 六、新手避坑清单

1. **先设账户**再看推荐（账户是地基）。
2. **只下限价单**；参考价研究级非实时。
3. **红色≠恐慌**——系统给防守选项且默认勾上，让你主动确认。
4. **第一次建仓股数自算**（§四-2 公式），回填一次后全自动。
5. **勿跳过 Fills + Reconcile**——不回填则系统不知道你实际持有什么，下次推荐的 current_weight 会失真。
6. **季度节奏**——两次调仓之间每天看 Home 即可，勿频繁交易。

---

## 故障速查（详表见 runbook §Troubleshooting）

| 症状 | 处理 |
|---|---|
| Ticket 生成报 409 "no snapshot" | 先去 Account 页设账户保存 |
| Fills 上传 400 提示 allow_unmatched | 勾「Accept unmatched fills」重提 |
| CSV 报 "Could not identify CSV adapter" | 换 runbook 的 Generic 格式重导出 |
| Recommendations 显示「账户缺失」 | 已于 B051（2026-06-10）修复；若复现请报障 |
