# B053 — 加固扫尾批（reconcile 对账完整性 + 孤儿回收 + 并发/语义/时区防御）

> **批次类型：** 混合批次（3 generator + 1 codex）。
> **状态：** planning → building（2026-06-10 B052 done 签收后转正启动；用户授权「B052 done 后即启」）
> **来源：** 四轮系统审计产出汇总——第四轮 `threat-model-audit-2026-06.md`（#1-#4 + 脆弱性）+ 第三轮 `post-b052-hidden-bug-audit-2026-06.md`（BL-AUDIT-S1）+ B050 审计（BL-B050-S1）。用户 2026-06-10 批凑批。
> **性质：** 全部小修；修复原则=**不可能状态 fail-fast/警告，不静默修正**（对齐系统「诚实降级」一贯原则）。

---

## 1. 范围

| 项 | 严重度 | 来源 |
|---|---|---|
| reconcile 静默吞对账异常（负现金/超卖）| 🔴 中-高 | 第四轮 #1 |
| worker 孤儿 running 回收 + 前端轮询超时 | 🟠 中 | 第四轮 #2 |
| snapshot_at 同秒 tie-breaker | 🟡 低-中 | 第四轮 #3 |
| has_mark 标注（持有无价 vs 未持有）| 🟡 低-中 | 第四轮 #4 |
| advisor 幂等 status 区分 + risk_explanation 条件显式化 | 🟡 中 | BL-AUDIT-S1 |
| backlog status 字段（建列 or 移除）| 🟢 低 | BL-B050-S1 |
| date.today()→now(UTC).date() 全局统一 + 权重和断言 | 🟢 加固 | 第四轮 §5 |

**不做：** 不改 reconcile 正常路径算法 / 不支持做空 / 不改回测引擎 / 不做时区配置化（统一 UTC 即可）。§12.10.2 等硬边界不破。

## 2. F001 — reconcile 对账完整性（generator）

1. **超卖拒绝**：`reconcile.py:156-158` 检测 `sell shares > held shares` → 不再静默归零；整个 reconcile 拒绝（409，detail 指明行号/symbol/卖出 vs 持有数），或按行进入需用户确认的 warning 列表（generator 按现有 fills `allow_unmatched` 交互范式二选一并注明）。
2. **负现金拒绝/警告**：`reconcile.py:299` 检测 `prior_cash + cash_delta < 0` → 409（detail 给出差额与可能原因「fill 价格/股数/费用录入错误」）或 ReconcileResponse 显式 warning 字段；**绝不静默 max(0,...)**。
3. **幂等不破**：already_reconciled 路径不变。
4. **测试**：超卖 fill→409+行级信息；负现金→409/warning；正常路径回归；边界（恰好卖空到 0 股 / cash 恰好 0 合法通过）。
5. Gates：backend pytest ≥ baseline+ / ruff 0 / mypy 0。

## 3. F002 — 状态与并发加固（generator）

1. **worker 孤儿回收**：worker `main()` 启动时回收 stale `running` 行（置 `error` + `error_kind=interrupted`，前端 i18n 友好提示「回测被中断，请重新运行」；或重置 queued 重跑——generator 二选一注明，倾向 error+interrupted 诚实告知）。加 `claim` 时间戳若 schema 需要（或用现有时间列判 stale）。
2. **前端轮询超时**：backtest-poll 加最大轮询时长（如 10 分钟）→ 超时显示友好提示而非永久转圈（i18n 双语）。
3. **snapshot_at tie-breaker**：`repositories/account_snapshot.py` latest()/排序补 `created_at`（或 id）次级排序；nav_history 重建排序同步核查。
4. **advisor 幂等**：`advisor/precompute.py:66` skip 条件加 `and latest.status == STATUS_OK`（拒答行不算已生成，重跑重试）+ 回归测试（种 INSUFFICIENT_GROUNDING 行→同日重跑应重新生成）。`risk_explanation.py:84` 幂等条件显式化（`is not None` + 区分降级）。
5. **测试**：孤儿 running 启动回收 + 轮询超时（vitest）+ 同秒两行 latest() 确定性 + advisor 降级重试。
6. Gates：backend pytest ≥ baseline+ / frontend vitest/tsc/lint / ruff/mypy 0 / §12.10.2 不破。

## 4. F003 — 语义与防御加固（generator）

1. **has_mark 标注**：`TargetPosition` 加 `has_mark: bool`（或等价），recommendations 前端对「持有但无标价」显示区分文案（非 0% 误导）；i18n 双语；api.ts 同步。
2. **backlog status**：二选一（建 status 列+migration+真实存读 vs schema 移除字段）——按产品意图 generator 裁定注明（内部工具页，倾向移除以最小化）。
3. **date.today() 统一**：全局替换为 `datetime.now(UTC).date()`（grep 全部出现点：execution/tickets/canonical/risk_explanation 等），去「服务器 TZ=UTC」隐含假设；加一条守门测试（grep AST 禁新增 date.today()）。
4. **权重和断言**：recommendation_snapshot `save_batch` 或读取侧加 `abs(sum(weights)-1.0)<1e-6` 断言（防未来引擎漂移）。
5. **测试**：has_mark 渲染 + backlog status 行为 + date 统一守门 + 权重断言。
6. Gates：同 F002 + i18n parity + api.ts drift 0 + alembic head（若 backlog 建列）。

## 5. F004 — Codex L1+L2 验收 + signoff（codex）

L1 全门禁。L2 真 VM：①超卖/负现金 fill 提交→**明确拒绝/警告非静默**（evaluator §25 正面证据：实际提交一笔错误 fill 看到 409/warning）；②重启 worker 后无永久 running 孤儿（可模拟：跑回测中 systemctl restart worker→run 转 interrupted 非永久 running）；③双击保存账户→latest 稳定；④无标价持仓显示区分文案；⑤advisor 降级日重跑自愈；⑥回归 B050/B051/B052/B043 全链 + recent-errors=0 + **演练自清（B052 规约）**。Signoff 模板全段。

## 6. Core Acceptance（一句话）

错误录入被明确拒绝而非静默修正、崩溃/部署不再留下永久卡死的回测、并发保存与降级重试行为确定——把四轮审计挖出的全部边角防御缺口一批扫清。
