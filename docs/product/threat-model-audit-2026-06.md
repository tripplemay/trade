# 第四轮审计：正向威胁建模——已知家族之外的隐患路径（2026-06-10）

> **作者：** Planner（用户 2026-06-10 指派「设想已发现 bug 家族之外的其他隐患路径并审计」）。
> **方法：** 与前三轮「从已爆发 bug 反推家族」不同，本轮**正向设想** 10 个未审过的失败维度，筛出 4 个高怀疑路径（时间/时区、外部降级×交易数值、并发/孤儿状态、数据备份），3 路并行 agent 深审 + Planner 逐项复核定性。
> **前序：** `b050-class-decorative-control-audit` / `trade-recommendation-fidelity-audit` / `post-b052-hidden-bug-audit`。

---

## 1. 结论摘要

**发现 2 个真隐患（中-高/中）+ 2 个低-中问题 + 一批脆弱性加固项；备份等关键基础设施确认健康。**

| # | 发现 | 严重度 | 状态 |
|---|---|---|---|
| 1 | reconcile 静默吞掉对账异常（负现金夹零 + 超卖归零，均无警告）| 🔴 中-高 | 真隐患 |
| 2 | backtest worker 孤儿 running 无回收（每次 deploy 都是触发窗口）| 🟠 中 | 真隐患 |
| 3 | 同秒 snapshot_at 无 tie-breaker（latest() 排序不稳定）| 🟡 低-中 | 真问题 |
| 4 | 「持有但无价」vs「未持有」在 recommendations 展示层同为 0.0 | 🟡 低-中 | 展示混淆（diff 层有防护）|
| — | 时区/精度/竞态等 5 项脆弱性 | 🟢 低 | 加固项记录 |

---

## 2. 🔴 真隐患 #1：reconcile 静默吞掉对账异常

**这是财务记账完整性问题。** 两处同族（`services/reconcile.py`）：

1. **超卖静默归零**（`reconcile.py:156-158`）：fill 记录卖出 150 股但只持有 100 股 → `new_shares<0 → 0.0`，注释说「short positions out of scope」——但这把「不支持做空」和「输入错误」混为一谈：用户手抄 fill 输错股数时，系统**接受并静默消除头寸**，无任何警告。
2. **负现金静默夹零**（`reconcile.py:299`）：`new_cash = max(0.0, prior_cash + cash_delta)`——fill 价格/股数输错导致现金算出负数时，静默夹到 0，**差额凭空消失**，无日志无异常无前端提示。

**用户后果**：手工录入 fill 是该系统的常规操作（runbook §5），输错是常态风险；输错时系统不报错反而「修正」账目 → 用户后续对账发现钱数/持仓对不上，**且没有任何线索指向那笔错误录入**。违反系统一贯的「诚实降级/fail-fast」原则（对比：fills 上传对 unmatched 行是 400+提示的）。

**修复方向**：两处检测到不可能状态（负现金/超卖）→ 拒绝 reconcile（409+具体行号提示）或至少在 ReconcileResponse 上警告标注；不静默修正。

## 3. 🟠 真隐患 #2：worker 孤儿 running 永久卡死

- **机制**（复核确认）：`worker.py` process_next 先 claim（status→running）commit 再跑引擎；`claim_next_queued` **只领 queued**；启动时**无 stale-running 回收逻辑**。
- **触发窗口比想象常见**：worker 由 systemd 管理，**每次 deploy 都 restart worker**——部署恰逢有回测在跑 → 该 run 永久卡 `running` → 前端轮询永久转圈（前端无轮询超时上限）。OOM/崩溃同理。
- **用户后果**：回测页该次 run 永远 pending，用户无法分辨是慢还是死；只能放弃重跑（旧行永久残留）。
- **修复方向**：worker 启动时回收孤儿（`running` 且超时 → 置 error_kind=interrupted 或重置 queued）+ 前端轮询加超时提示。

## 4. 🟡 低-中问题

3. **同秒 snapshot_at 无 tie-breaker**（`repositories/account_snapshot.py:24` 仅 `ORDER BY snapshot_at DESC`）：快速连续两次保存账户（双击）→ 同秒两行 → `latest()` 返回不确定 → 页面可能显示旧版本现金。修复一行：排序补 `created_at/id` tie-breaker。
4. **current_weight=0.0 双义**（`mark_to_market.py:58-64`）：「持有 100 股但无标价」与「未持有」都显示 0%——execution position-diff 有 Unmatched 卡片防护（已复核 `execution.py:223-224`），但 recommendations 展示层无区分，用户可能误读持仓状态。修复方向：TargetPosition 加 `has_mark` 标注或文案区分。

## 5. 🟢 脆弱性加固项（非现行 bug，记录在案）

| 项 | 说明 |
|---|---|
| `date.today()` vs `datetime.now(UTC).date()` 混用 | 现行一致仅因「服务器 TZ=UTC」隐含假设；该假设未显式固定，环境变化会咬人。另：用户（UTC+8）晚 20:00 后操作的 ticket/as_of 日期标签=UTC 日=用户的「昨天」（市场日语义其实合理，但未向用户说明）|
| naive/aware datetime 混用 | `snapshot_at` naive 列 + 各写入者 `now(UTC).replace(tzinfo=None)` 口径现行一致；未来任何 aware 比较会 TypeError——结构性脆弱 |
| timer 链无完成性检查 | data-refresh 02:30 失败/超时 → recommendations 03:00 基于旧数据照跑，无新鲜度告警（数据是旧的真数据，非假数据，故低危）|
| 权重和无断言 | Σtarget_weights 数学上自洽=1（sleeve-relative 约定），但写/读两侧均无 assert，防御性缺失 |
| CSV torn read / cost_guard 读改写竞态 | 窗口极窄/超额≤单次调用成本，可忽略，记录即可 |

## 6. ✅ 健康面确认（本轮排除的设想路径）

- **DB 备份完备**（设想路径 D 排除）：`workbench-backup.service` → GCS + `workbench-restore.sh` + 后端 `observability/backup_status.py` 监控——财务数据有异地备份与恢复路径。
- **precompute 事务结构安全**（设想的 advisor-locked 复刻排除）：LLM 调用在 `save_batch/commit` 之前，调 LLM 期间不持 SQLite 写锁。
- **mark 缺失在交易执行层有防护**：position-diff 的 Unmatched 分支明确区分「持有但无价」（仅展示层混淆，见 §4.4）。
- **浮点精度**：DB 层 Numeric(20,4) + 手工流程量级，累计误差可忽略。
- advisor 幂等（上轮已发现，BL-AUDIT-S1 在池）。

---

## 7. 处置建议

#1/#2/#3 与已在需求池的 BL-AUDIT-S1（advisor 幂等）、BL-B050-S1（backlog status）天然凑成一个**加固扫尾批**（候选 B053：全部小修——reconcile 异常拒绝 + worker 孤儿回收 + tie-breaker + advisor 幂等 + has_mark 标注，约 1 个 generator feature 量级 ×2-3）。#5 脆弱性项随该批顺手统一（date.today→now(UTC).date 全局替换）或留档。

**四轮审计总评**：系统经四轮、累计 11 路 agent 对抗审查——核心交易链路（策略→推荐→diff→ticket）、数据流完整性、风控真实性、备份均健康；遗留的都是**边角防御性缺口**（输错数据时的静默行为、进程崩溃后的状态回收、并发排序稳定性），无架构性风险。
