# B048 — F011 真实 per-sleeve NAV + 历史价格表 → 安全/风控/合规层 mark-to-market 真实化

> **状态：** planning（2026-06-07 起草）。
> **批次类型：** 新功能（F011 根因批次；**里程碑 C 交易安全/风控/合规层真实化**，backlog order 2）。**大批次**（5 features，含历史价格表 foundation）。
> **来源：** 2026-06-07 全面占位核查——交易闭环安全层多处占位共享 F011 根因（gate kill_switch 硬编码 / risk_panel per-sleeve 镜像占位 + 成本价 / wash_sale 永空）。
> **配套：** `docs/product/progress-review-2026-06.md` §5（安全层真实化）+ `docs/dev/workbench-manual-execution-runbook.md`（B023 不破）。

---

## 1. 目标

让交易闭环的**安全/风控/合规层从占位变真**，根因=建真实 per-sleeve NAV 跟踪 + **历史价格表**（支撑真实 mark-to-market 回撤随时间）：
1. **kill_switch gate** 接真实 master DD（去硬编码 pass）。
2. **risk_panel** master DD + per-sleeve DD **mark-to-market 随时间**（去成本价、去镜像占位）——需历史价格重建 NAV 历史。
3. **wash_sale** 从 fills 历史检测（去永空）。

**范围（2026-06-07 用户批：一次做全，含历史价格表）。**

---

## 2. 决策（2026-06-07 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 范围 | ★ **一次做全（含历史价格表 foundation）** | 达真实 mark-to-market per-sleeve+master 回撤随时间 |
| 历史价格 | **新 `price_history` 表**（planner 决） | 深每日收盘，由 job 从 B045 unified CSV materialize；不重载 price_snapshot（其语义=Day P&L 最新+前一日）|
| kill_switch 阈值 | **统一 0.15**（planner 决） | rec 0.20 vs risk_panel 0.15 不一致→对齐 risk_panel 权威 0.15（kill-switch 更早触发，行为变更记 signoff）|
| 估值口径 | **mark-to-market 全程一致**（planner 决） | 复用 B046 `mark_to_market.py`；与 execution diff 口径一致 |
| 历史不足 | **graceful degrade**（planner 决） | 老快照日期早于价格历史→该点退成本价 + 标注；DD 窗口限可 mark 范围，不蒙混（v0.9.21）|

---

## 3. 永久硬边界（继承）

- **risk panel 信息性，不 gate ticket**（B023 设计）；kill_switch gate 在 recommendations 也是信息性。本批不新增执行/下单能力。
- **§12.10 / §12.10.2**：历史价格 backfill job 读 B045 unified CSV（job 上下文，可），写 `price_history` DB；**请求路径（risk_panel/recommendations）只读 DB，禁 import trade**（AST 守门不破）。
- **B023 工作流不破**：ticket→fills→reconcile→journal / wash-sale 渲染（现读 []，本批填真）不回归。
- 定位 §1.1：回撤/权重是配置/风险事实，非收益预测。

---

## 4. 技术架构

### 4.1 历史价格表 foundation（F001）

- 新 `db/models/price_history.py`（symbol/obs_date/close/source/fetched_at；UniqueConstraint(symbol,obs_date)；深每日，与 price_snapshot 分离）+ alembic 迁移（down_revision=当前 head）+ `db/repositories/price_history.py`（save_if_new 幂等 / `close_on_or_before(symbol, date)` / `closes_by_symbol_since(symbol, since)`）。
- **backfill job** `workbench_api/price_history/`（CLI + 可挂 data-refresh timer）：读 B045 unified CSV（`<data_root>/snapshots/prices/unified/prices_daily.csv`，深历史）→ 写 price_history（master 全 universe symbol）；§12.10 job 读 CSV 写 DB，请求路径只读。
- scheduler scope 守门扩 price_history backfill（边界 r 只读）。

### 4.2 sleeve tag 写路径补齐（F002）

- `schemas/execution.py` `PositionEntry` 加可选 `sleeve` 字段；ui_edit（execution.py）/ fill_reconcile（reconcile.py）/ bootstrap **写路径保留/填 sleeve tag**（现丢失 B037 的 tag）→ per-sleeve 分组可靠。
- regen api.ts；schema-tolerant（旧无 tag→'unclassified'，沿用 home.py 语义）。

### 4.3 risk_panel mark-to-market 回撤（master + per-sleeve 随时间）（F003）

- 重建 NAV 历史：对每个历史 AccountSnapshot（date D, positions）→ 用 `price_history.close_on_or_before(symbol, D)` mark-to-market 每持仓 → snapshot NAV(D)；按 sleeve tag 分组 → per-sleeve NAV(D)。
- master DD = peak-to-latest on mark-to-market NAV 历史（复用 `mark_to_market.py` 逻辑）；per-sleeve DD = 各 sleeve NAV 历史 peak-to-latest（去镜像占位）。
- 历史价格不足的快照点 → degrade（退成本价或剔除该点 + 标注），DD 窗口限可 mark 范围。
- `_classify_state` kill-switch / yellow 用真实 mark-to-market master/per-sleeve DD。

### 4.4 kill_switch gate 真实化（F003）

- `recommendations.py` `_build_gate_checks` 接真实 master DD（调 risk_panel 计算或共享 drawdown 函数）→ status 反映真实 DD vs 阈值；**阈值统一 0.15**（去 rec 的 0.20）。

### 4.5 wash_sale 检测（F004）

- `services/wash_sale.py`：读 FillJournalEntry（symbol/side/price/date）+ AccountSnapshot avg_cost → 检测亏损卖出（avg_cost > sell price）+ 30 日内回补同标的 → WashSaleFlag（symbol/last_buy_date/days_since）。
- recommendations.py 用真实 wash_sale_flags（去 []）；B023 ticket 渲染 wash-sale 段自动填真。

### 4.6 测试

- pytest：price_history repo（save/close_on_or_before/since）+ backfill（fake CSV→表）；sleeve tag 三写路径保留；risk DD mark-to-market（已知历史价格+持仓→已知 master/per-sleeve DD；历史不足 degrade）；kill_switch gate 真实 DD + 阈值 0.15；wash_sale（亏损卖+30 日回补→flag；无损/超 30 日→无）；§12.10 守门 + scheduler scope 含 price_history。
- **B023 回归**：ticket→fills→reconcile→journal 不破。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 历史价格表 foundation：`price_history` 表+repo + backfill job（B045 unified CSV → price_history）+ scope 守门 |
| F002 | generator | sleeve tag 写路径补齐（PositionEntry schema + ui_edit/reconcile/bootstrap 保留 tag）+ regen api.ts |
| F003 | generator | risk_panel mark-to-market 回撤（master + per-sleeve 随时间，重建 NAV 历史）+ kill_switch gate 真实化 + 阈值统一 0.15 |
| F004 | generator | wash_sale 检测（FillJournalEntry + avg_cost → 亏损卖+30 日回补）+ recommendations 用真实 flags |
| F005 | codex | L1 + L2 真 VM 验收（price_history backfill + 真实 mark-to-market 回撤 + kill_switch gate 真实 + wash_sale 真实 + B023 不破）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不新增执行/下单/broker 能力（risk/gate 信息性）。
- 不重载 price_snapshot 语义（深历史走新 price_history）。
- 不激活 regime / 不改 master 评分。
- 不输出收益预测数字。
- 不让请求路径 import trade（§12.10.2 守门）。
- 历史价格不足的点不蒙混真实化（degrade + 标注，v0.9.21）。

---

## 7. 验收门槛汇总

- **F001**：price_history 表+迁移+repo + backfill job（B045 unified CSV → 深每日收盘，master universe）+ scope 守门；backend pytest ≥ baseline+≥8 / ruff 0 / mypy 0 / §12.10 job 读 CSV 写 DB 请求只读。
- **F002**：PositionEntry 加 sleeve + 三写路径保留 tag + regen api.ts + schema-tolerant；既有 execution/reconcile 契约不破；pytest sleeve tag 保留。
- **F003**：risk_panel master DD + per-sleeve DD **mark-to-market 随时间**（重建 NAV 历史，复用 mark_to_market.py + price_history）+ 历史不足 degrade；kill_switch gate 真实 master DD + 阈值 0.15；pytest（已知场景 + degrade）；不破 risk schema。
- **F004**：wash_sale 检测真实 flags（亏损卖+30 日回补）+ recommendations 用之；pytest；**B023 ticket wash-sale 渲染不破**。
- **F005**：L1 全门禁 + secret grep 0 + B023 回归绿；L2（真 VM）：(1) health 200 + HEAD≡main + recent-errors=0；(2) **price_history backfill 真机有深历史行**（记录 symbol/日期跨度）；(3) **risk_panel master DD + per-sleeve DD 真实 mark-to-market**（PUT 浮盈/浮亏持仓 + 历史 → 真实回撤非成本价/非镜像；记录 vs 旧）；(4) **kill_switch gate 反映真实 DD**（非硬编码 pass；阈值 0.15）；(5) **wash_sale 真实触发**（构造亏损卖+回补 → flag）；(6) B023 工作流不破。Signoff（§Production/HEAD + §Post-signoff Deploy + §24 若加 timer + **mark-to-market 回撤 vs 旧成本价对比**）。Framework 候选：历史价格重建 NAV / 安全层占位→真实 若出新通用规律记 §Framework Learnings。

---

## 8. 参考文档

- 占位现状：`services/risk_panel.py`（master DD 成本价 + per-sleeve 镜像）/ `recommendations.py`（gate 硬编码 + wash_sale []）
- 复用：`services/mark_to_market.py`（B046）/ `db/models/price_snapshot.py`（累积参考）/ `data_refresh/`（B045 unified CSV）/ `db/models/fill_journal_entry.py`（wash_sale 数据）
- §12.10.2 / 边界 r：`framework/harness/generator.md` + project-status §永久硬边界

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 历史价格深度不足覆盖老快照 | F001 从 B045 unified CSV 深回填；F003 历史不足点 degrade + 标注，DD 窗口限可 mark 范围 |
| 大批次（5 features）fix-round 高 | foundation（F001 价格 / F002 tag）先行；F003/F004 消费；清晰依赖序 |
| 阈值改 0.15 致 kill-switch 行为变 | 信息性非 gate ticket；signoff 记行为变更 |
| sleeve tag 改 execution 写路径破 B023 | schema-tolerant 可选字段；reconcile 保留 tag；B023 回归绿 |
| 重建 NAV 历史性能 | 限 snapshot 数 + price_history 索引；非实时（risk panel 读 DB）|

---

## 10. 与既有批次的边界 + 后续

- **不改**：master 评分/B044-B046 precompute·diff/前端 Rec/Risk UI 结构（B042 后做 UI）/avg_cost 记账。
- **解锁**：交易安全/风控/合规层真实（kill-switch/risk panel/wash-sale）= 交易闭环可信前提。
- **后续 order**：BL-B023-S1 闭环冒烟（order3，用真实 diff+真实安全层）→ HK-China → B042 Risk UI（在真风控数据上）→ B047 → B049 全页面审计。
