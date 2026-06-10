# B051 — 账户数据源统一（修复 UI 设的账户 Recommendations 不认 + home nav=0.0）

> **批次类型：** 混合批次（1 generator + 1 codex），生产 hotfix。
> **状态：** planning → building
> **触发：** 用户 2026-06-10 报：UI Account 页设了账户并保存，Recommendations 仍显示「尚未配置账户」。
> **Planner 根因裁定（铁律 9，不改产品码）：** 系统有两张互不同步的账户表——UI 写 `account_snapshot`，但 `nav.aggregate_nav` + `recommendations._aggregate_account_state` 读另一张 `account` 表（只由 `accounts/me.json` 经 bootstrap 填）。
> **来源：** 用户报障 + Planner 实地核查 2026-06-10。

---

## 1. 根因（已实地确证）

**两张账户表，读写不一致：**

| 表 | 谁写 | 谁读 |
|---|---|---|
| `account_snapshot` | ✅ UI Account 页 `PUT /api/execution/account`（`routes/execution.py:94`）| position-diff / ticket / current_weight / risk / wash_sale / reconcile / home day-pnl |
| `account`（`equity_value` 列）| ❌ 仅 `accounts/me.json` 经 `cli/bootstrap.py` 镜像 | **`nav.aggregate_nav`（nav.py:34 `select(Account)`）+ `recommendations._aggregate_account_state`（recommendations.py:144 `select(Account)`）** |

**后果（同一根因，两个用户可见症状）：**
1. **Recommendations「尚未配置账户」**：`account_present` 来自 `_aggregate_account_state`→`account` 表（空，因无 me.json）→ 即使 UI 写了 `account_snapshot` 也不认；且 `account_present=false` **门控整页**（不渲染目标持仓）。
2. **home nav=0.0**（长期遗留 **B046 soft-watch S1**）：home NAV 复用 `aggregate_nav`→`account` 表（空）→ nav=0.0，即使 `account_snapshot` 有数据。

→ **统一账户源一个 hotfix 同时修好这两个。**

---

## 2. 目标与范围

**目标：** 让 `nav.aggregate_nav` + `recommendations._aggregate_account_state` 读**与执行流同源**的 `account_snapshot`（UI 写的、mark-to-market），使 UI 设账户后 Recommendations 立刻认、home nav 真实。

**单一数据源原则：** `account_snapshot` 成为账户状态的唯一真相源（UI 写 + 若保留 me.json bootstrap 则 bootstrap 也写 snapshot）。

**不做：** 不改 master 评分 / diff / gate 判定逻辑（只改 gate 的 equity 来源）/ 执行流（已读 snapshot 不动）/ recommendation_snapshot（target_positions 与账户正交，不碰）。§12.10.2 等永久硬边界不破。

---

## 3. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 统一账户源到 account_snapshot（aggregate_nav + account_present + gate equity）+ me.json bootstrap 一致 + 测试 |
| F002 | codex | L1+L2 真 VM——UI 设账户即被 Recommendations 认 + home nav 真实 + B046 S1 闭合 + signoff |

---

## 4. F001 — 统一账户源（generator）

1. **`nav.aggregate_nav`（nav.py:27）**：去 `select(Account)`，改从**最新 `account_snapshot`** 算 NAV = `cash + mark-to-market(positions)`（复用 `compute_mark_to_market` + `marks_for`，与 `recommendations._build_target_positions` / `home` day-pnl 同款）。无 snapshot → 0.0 graceful（同现状）。DB 错误降级不变。
2. **`recommendations._aggregate_account_state`（recommendations.py:132）**：`account_present` = 最新 `account_snapshot` 存在；`total_equity` = 上面同一 aggregate（喂 gate min_equity）。无 snapshot → `(False, 0.0)` 不变。
3. **me.json bootstrap 一致**：`cli/bootstrap.py` 镜像 me.json 时**也写 `account_snapshot`**（使 me.json 种子路径与 UI 同源生效）；或明确裁定 `account` 表/me.json 仅向后兼容、读路径一律 snapshot 优先——generator 二选一并注明（推荐：bootstrap 写 snapshot，单一源）。
4. **`account` 表读路径审计**：确认改后无其它读 `Account` model 的路径仍依赖空表造成不一致（grep `select(Account)` / `Account` model 读）；vestigial 则注明（本批不强删，避免扩面）。
5. **测试**：(a) 写 `account_snapshot`（含持仓）→ `account_present=true` + nav=cash+mtm equity；(b) **纯现金 snapshot**（零持仓）→ account_present=true + nav=cash（**新用户场景**）；(c) 无 snapshot → account_present=false + nav=0.0 graceful；(d) gate total_equity 来自 snapshot；(e) me.json bootstrap 后同样 account_present=true（若保留）。
6. **Gates**：backend pytest ≥ baseline+ / ruff 0 / mypy 0 / §12.10.2 守门（请求路径仍只读，不 import trade）/ api.ts drift（无 schema 变则 0）。
7. **不动**：执行流（已读 snapshot）/ master 评分 / recommendation_snapshot / gate 判定逻辑。

---

## 5. F002 — Codex L1+L2 真 VM + signoff（codex）

**L1**：F001 全门禁 + §12.10.2 守门 + 单测（纯现金/含持仓/空/gate equity/bootstrap 一致）。

**L2（真 VM）**：
1. ★**核心反例（用户报障修复）**：UI Account 页设账户（先**纯现金零持仓**，再**含持仓**两种）并保存 → `GET /api/recommendations/current` `account_present=true` + **目标持仓渲染**（不再「尚未配置账户」门控空态）。
2. **home nav 真实（B046 S1 闭合）**：设账户后 `GET /api/home` nav = 真实 cash+equity（非 0.0）。记为 B046 soft-watch S1 resolved 证据。
3. **gate equity**：Recommendations gate min_equity 反映真实账户权益。
4. **回归**：position-diff / risk / execution / reconcile 不破（本就读 snapshot）；recent-errors=0；HEAD≡main；B050 回测 / B043 解释不破。
5. **Signoff**：`docs/test-reports/B051-account-source-unification-signoff-2026-MM-DD.md` 用模板（§Production/HEAD + §Post-signoff Deploy + **§UI 设账户即被认证据（纯现金+含持仓）+ §home nav 真实即 B046 S1 闭合**）。**evaluator.md §25 适用**：account_present=true + 目标持仓真实渲染须正面证据。更新 progress.json status→done。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 改 aggregate_nav 影响 home/其它 NAV 消费者 | nav=cash+mtm 与执行流口径一致；F002 回归 home/risk |
| me.json 种子路径改后失效 | F001(3) bootstrap 也写 snapshot，种子仍生效 |
| `account` 表变 vestigial 引混乱 | F001(4) 审计标注；本批不强删（避免扩面），可后续 decommission |
| gate min_equity 口径变化 | equity 来源换 snapshot，但 gate 判定逻辑不动；F002 核 gate 正常 |

---

## 7. Core Acceptance（一句话）

UI Account 页设账户（含纯现金新用户场景）保存后，Recommendations 立即识别账户并渲染目标持仓、home nav 显示真实权益（非 0.0）——账户状态单一真相源统一到 `account_snapshot`，同时闭合 B046 soft-watch S1。
