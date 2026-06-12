# B058 — 多模式数据修复（模拟盘全现金 + regime 无目标）+ 手动控制基建

> **批次类型：** 混合批次（5 generator + 1 codex）。**Hotfix + 基建**：修正阻挡前向验证的真 bug，并补"手动触发"平台原语。
> **状态：** planning → building（2026-06-12 用户讨论确认 + 同意立项）。
> **来源：** 2026-06-12 用户报障——「新上线的策略，有些没给推荐股票（regime），有些虽给了推荐但模拟盘没按方案配置资产、基本躺现金（Master）」。Planner 代码级根因调查（见 §2）。
> **优先于 B055**：修的是正阻挡用户前向验证的真 bug，非新功能。

---

## 1. 两个症状（用户实测）

| 症状 | 现象 | 层 |
|---|---|---|
| **S1：regime 无推荐** | regime 推荐页没股票 | 推荐层（目标未生成）|
| **S2：Master 模拟盘全现金** | Master 有推荐，但模拟盘基本是现金、没按推荐建仓（用户确认是「(b) 基本现金/缺资产」非漂移）| 模拟盘层（持仓没对齐目标）|

---

## 2. 根因（代码实锤）

### S1 — regime 目标从未生成
`get_target(strategy_id="regime_adaptive")` 读 `recommendation_snapshot WHERE strategy_id`（`targets.py:82-86`），**无行→None→无推荐**。regime 目标的唯一生产者 `run_regime_precompute` **只由月度 timer 触发**（`cli.py` + `regime-precompute.timer`，下次首跑 2026-07-01），**无任何部署期/启动期一次性引导** → 生产上 regime 目标行数 = 0。paper 跟随同一目标，故也空。

### S2 — 模拟盘建仓引擎「跳过无市价目标」+「降级仍提交 target_key 卡死」
1. **跳过无市价目标→落现金**（`engine.py:84-92`）：目标 symbol **必须在 `marks` 价格表里有当前收盘价**才建仓；无市价的目标被跳过、权重落回现金。若所有目标都无市价 → 优雅空操作、全现金（`engine.py:94-108`）。
2. **降级仍提交 target_key → 永不重试（卡死 bug）**：`_apply_rebalance`（`service.py:97`）**无条件**设 `account.target_key = targets.target_key`，**即使本次是「全跳过、没建仓」的空操作**。此后每日 job `rebalance_if_due`（`service.py:177`）只在 `target_key` 变化时重跑 → 既然 key 已设成当前目标，**就算市价之后补上也永不重试** → 卡在现金里直到下个季末目标变化。**这是真 bug**（降级被当成功提交，违反 B053「不可能状态 fail-fast 不静默」家族）。
3. **最可能上游：两个价格源分裂**（B051 同款）——推荐目标由 Master precompute 读 `trade` 统一价格文件（**故推荐能出**）；模拟盘建仓市价走 `DbPriceProvider` 读 workbench `price_history` 表（**可能未覆盖目标 symbol**）→ 推荐有、模拟盘建不上仓。**需 prod 只读确认覆盖实况**（F6）。

---

## 3. 范围

**做：**
- **修 S2 卡死 bug**：降级/跳过的 rebalance **不提交 target_key**（留待市价补上后每日 job 自动重试）；诚实 surface `skipped_symbols`。
- **修 S2 上游**：保证模拟盘 mark 源覆盖各模式目标 universe（对齐两个价格源），无市价时 fail-fast/log 而非静默全现金。
- **修 S1**：通用「手动刷新目标」原语 + regime 一次性引导，让 regime 立即有推荐。
- **手动控制基建**：通用「刷新目标」+「模拟盘对齐当前目标」两原语（按注册表 `target_producer` 派发，所有模式复用）。
- **激活 regime 模拟盘**（用户已选「一并前向验证」）。
- **前端**：两按钮 + 诚实标注（中文）。

**硬边界：** §12.10.2（刷新/precompute 须 import trade，**必须 off-request-path 异步 job**，不在路由内同步跑；复用 B047 异步 worker 范式或 CLI 子进程）/ no-AI / regime 研究态不预测 / **B057 Master 向后兼容不破** / **B053 对账 per-mode 不破** / research-only / no-broker。

**不做：** 改 regime/Master 评分算法；**持续每日强制模拟盘对齐**（毁前向验证——「对齐」仅开局/按需，日常仍按 cadence + 漂移）；改 paper 成本模型。

---

## 4. Feature 分解（6 features，5g+1c）

| id | executor | 标题 |
|---|---|---|
| F1 | generator | 修模拟盘卡死 bug：降级/跳过 rebalance 不提交 target_key（市价补上后每日 job 自动重试）+ 回归 |
| F2 | generator | 修 S2 上游：模拟盘 mark 源覆盖各模式目标 universe（对齐价格源）+ 无市价 fail-fast/log |
| F3 | generator | 通用「手动刷新目标」原语（async job 派发注册表 target_producer）+ regime 目标引导 |
| F4 | generator | 通用「模拟盘对齐当前目标」原语（强制 rebalance once）+ 激活 regime 模拟盘 |
| F5 | generator | 前端两原语按钮 + 诚实标注（推荐/模拟盘页，per-mode，中文）|
| F6 | codex | L1+L2 真机：prod 只读坐实根因 + 验修复 + Master/B057 不破 + signoff |

### F1 — 修卡死 bug（generator，最关键）
- `_apply_rebalance` / `compute_rebalance`：当 rebalance 是**降级空操作**（`traded=False`，或有 `skipped_symbols` 导致目标未真正达成）时，**不提交 `account.target_key`**（或提交一个标记"未达成"的哨兵），使每日 `rebalance_if_due` 在市价补齐后**自动重试**直到真正建上仓。
- 诚实 surface：`skipped_symbols` 记入 rebalance log / 账户状态，用户/前端可见"X 个目标因缺市价未建仓"。
- **测试**：复现"激活时缺市价→全现金→target_key 未提交→次日市价补上→每日 job 自动重试建仓"；Master 正常路径（有市价）一次建满不回退。
- Gates：backend pytest ≥ baseline+ / ruff / mypy 0。

### F2 — 修上游价格覆盖（generator）
- 诊断 + 对齐：模拟盘 `DbPriceProvider`/`price_history` 必须覆盖各模式目标 universe 的当前 mark；若 data-refresh 未覆盖目标 symbol（含 B057 5 个 regime ETF QQQ/VWO/IEF/TLT/DBC），补进 refresh universe 或确保 mark 可得。
- 无市价时**响亮**（log + skipped_symbols），不静默全现金。
- **测试**：目标 universe 的 mark 覆盖断言；缺失时 skipped 正确上报。
- Gates 同 F1（含 alembic head 若触 schema）。

### F3 — 手动刷新目标原语（generator）
- `POST /api/strategy-modes/{strategy_id}/refresh-target` → **入队异步 job**（§12.10.2，不在路由内 import trade）→ 查注册表 `target_producer` → 跑该模式生产者 → 新 `recommendation_snapshot`。轮询状态（复用 B047 async 范式）。
- regime 借此**立即生成目标**（不等 7-01）；Master / 未来 B055 零成本复用。
- **测试**：refresh 端点入队 + job 跑 regime producer 产非空目标 + Master 仍可 refresh；§12.10.2 守门（路由不 import trade）。
- Gates：backend pytest/ruff/mypy 0 / api.ts drift。

### F4 — 模拟盘对齐当前目标原语 + 激活 regime 模拟盘（generator）
- `POST /api/paper/{strategy_id}/rebalance-now`（或等价）→ 强制对当前目标 rebalance 一次（`_apply_rebalance`），开局/按需建满仓。**诚实**：标注"手动调仓一次，日常仍按 cadence + 漂移"。
- 激活 regime 模拟盘账户（依赖 F3 先有 regime 目标）。
- **测试**：align 端点强制建仓到当前目标；regime 模拟盘激活后忠实跟目标；非日常自动（只手动触发）。
- Gates 同 F3。依赖 F1/F3。

### F5 — 前端（generator）
- 推荐页 +「立即刷新目标」按钮（per-mode）；模拟盘页 +「对齐当前目标」按钮（per-mode）+ 诚实 notice（手动调仓 vs 日常 cadence）；skipped_symbols 缺市价提示。中文 + i18n parity + api.ts 同步。
- **测试**：vitest（按钮触发/状态轮询/标注）+ i18n parity。
- Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift 0。

### F6 — Codex L1+L2 + signoff（codex）
L1 全门禁。L2 真 VM：① **prod 只读坐实根因**（Master paper 的 cash/持仓/target_key + recommendation_snapshot Master 目标 + price_history 对目标 symbol 覆盖 + MTM timer 是否跑过）；② **验 S2 修复**：refresh + align 后 Master 模拟盘**真建上仓**（非全现金），缺市价 skipped 诚实上报，卡死不复现（市价补上自动重试）；③ **验 S1 修复**：手动刷新后 regime **有推荐** + regime 模拟盘可激活跟目标；④ ★**Master 执行 + B057 多模式不破**（B051 账户源 / B053 对账 per-mode，§25 正面证据）；⑤ 回归 B050-B057 + recent-errors=0 + HEAD≡main；⑥ 演练自清。Signoff（§S1 修复 + §S2 修复含 prod 实况 + §Master/B057 不破 + §Ops）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| **动摇 Master 执行链/B057 多模式**（用户正真实交易）| F6 ★硬回归；F1/F2 只动 paper 域 + 价格覆盖，不碰 execution |
| refresh job 在请求内 import trade 破 §12.10.2 | F3 强制异步 job（复用 B047 范式）；守门测试 |
| 「对齐」被误用为日常强制 → 毁前向验证 | F4/F5 诚实标注"手动一次/日常按 cadence"；不做自动持续对齐 |
| prod 真实根因与代码推断不符 | F6 先 prod 只读坐实；不符→fixing 调整 |
| 价格源对齐引入回归 | F2 加覆盖断言；F6 回归 paper/mark_to_market |

## 6. Core Acceptance（一句话）

多模式平台**真正产出可用数据**——Master 模拟盘按推荐**建上仓**（不再全现金、缺市价不卡死）、regime **有推荐 + 可激活模拟盘**前向验证；并提供通用「刷新目标 / 对齐模拟盘」手动原语（所有模式复用，诚实标注）；**且 Master 执行链 + B057 多模式完全不破**。
