# B057 — 通用「策略模式」平台（多模式：目标+回测+模拟盘+真实执行）+ regime 第一个落地消费者

> **批次类型：** 混合批次（5 generator + 1 codex）。**规划过最大的批次。**
> **状态：** planning → building（2026-06-12 与用户讨论定案；B056 done 后启动，用户调序 B057 先于 B055）
> **来源：** 2026-06-11 用户提出 regime 独立成模式 + 2026-06-12 用户选「通用模式框架 + regime 第一消费者」+「本批含真实多账户执行」。
> **范围裁定（用户 2026-06-12 确认）：** 通用框架 + regime 落地（目标+回测+模拟盘+surface）+ **真实多账户执行链**（每模式独立真金账户 + 参数化 diff/ticket/fills/reconcile/journal）。

---

## 1. 愿景：策略模式成为一等公民（含真实独立交易）

用户已确立**多策略模式平台**方向。B057 = 把"策略目标/模式"从 Master-only 推广成参数化一等公民，**让任何策略以最小成本插入并可独立真实交易**；regime 作第一个真实消费者校准框架（不建空中楼阁）。

**框架每个模式自带（全维度）：**
```
策略模式 = 策略目标(precompute) + 回测(B050) + 模拟盘账户(B056) + 真实账户+执行链 + surface
```

**用户决策（2026-06-11/12）：** 资金=独立账户（每模式自己的真金账户）；通用框架 + regime 第一消费者 + **本批含真实执行**。

### ⚠️ 两条诚实约束（写进实现+验收）

1. **能力≠配资**：建真实多账户执行=有能力独立交易任何模式；**funding 仍归用户**。**强烈建议 regime 先模拟盘验证再投真钱**（纪律守在配资决策）。前端对未验证模式标注「研究态/前向验证中」。
2. **不动摇 Master 执行链**：用户正要真实交易 Master。执行链多账户化**必须向后兼容**（Master 走默认模式、现有路径行为不变），**F006 硬回归 Master 执行不破**（B051 账户源 + B053 对账完整性 per-mode 保留）。

---

## 2. 范围

**做（本批，全维度）：**
- **框架核心**：策略目标层 + 账户层 + 执行链 全部从 Master-only 推广成**每模式一份**（参数化 strategy_id/mode，Master+regime+未来同源）。
- **regime 落地**：目标 precompute（`derive_regime_adaptive_weights`）+ B050 回测 + B056 模拟盘 + 真实账户+执行链 + surface。
- **真实多账户执行**：每模式独立真金账户（account_snapshot 加 mode 维度，Master 默认向后兼容）+ diff/ticket/fills/reconcile/journal 参数化按 mode。
- **前端**：推荐+执行页模式选择器 + 每模式全套视图。

**硬边界：** §12.10.2 / no-AI / regime 研究态不预测 / **B051 账户源单一性 per-mode + B053 对账 fail-fast per-mode 保留** / 不改 regime 算法 / Master 评分。

---

## 3. Feature 分解（6 features，5g+1c）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 通用策略目标层（每模式一份，参数化 strategy_id）+ regime 目标 precompute |
| F002 | generator | regime 接 B050 回测分发（adapter + report）|
| F003 | generator | regime 接 B056 模拟盘（参数化目标源）+ 多模式模拟盘 |
| F004 | generator | **多账户模型 + 参数化执行链**（每模式真金账户 + diff/ticket/fills/reconcile/journal 按 mode；Master 向后兼容；B053 对账 per-mode）|
| F005 | generator | 前端多模式 surface（推荐+执行页模式选择器 + 每模式全套视图，中文）|
| F006 | codex | L1+L2 真 VM——多模式全平台 + ★Master 执行硬回归不破 + regime 落地 + signoff |

## 4. F001 — 通用策略目标层 + regime 目标 precompute（generator）

1. **目标层推广**：从 Master-only(recommendation_snapshot) 推广成每模式一份——通用接口 `get_target(strategy_id)→{symbol:weight,as_of,meta}`（recommendation_snapshot 加 strategy_id/mode 维度 vs 新表，generator 定迁移保 Master 兼容）。
2. **模式注册**：mode registry（id/display_name/strategy_id/target_producer/backtest_key/cadence；Master quarter-end / regime monthly）。
3. **regime 目标 precompute**：job 调 `derive_regime_adaptive_weights`(+detect_regime) 产 regime 当前目标→写通用目标层；月度；§12.10.2（job 侧 import trade）。
4. **测试**：通用目标接口(Master/regime 同源)+regime precompute+Master 读路径不破。
5. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / alembic head / §12.10.2 守门。

## 5. F002 — regime 接 B050 回测分发（generator，触 trade/）

B050 `_DISPATCH` 加 regime_adaptive(`run_regime_adaptive_monthly_backtest`)+adapter+双语 report；回测页可跑非退化结果；**本地 mypy trade**（B050 教训）；测试 regime 回测异于 Master+月度 cadence。Gates：backend+trade pytest/ruff/mypy 0。依赖 F001。

## 6. F003 — regime 接 B056 模拟盘（generator）

B056 paper 引擎已参数化；F001 通用目标层让 paper 对 regime `get_target`→月度虚拟调仓；regime 模拟盘=独立虚拟账户，与 Master 并存；每日 MTM 覆盖所有模式。测试 regime 模拟盘激活+忠实跟目标+MTM。Gates 同 F001。依赖 F001/F002。

## 7. F004 — 多账户模型 + 参数化执行链（generator，最重，最安全攸关）

1. **多账户模型**：account_snapshot 加 **mode/strategy_id 维度**（Master 默认 = master_portfolio 向后兼容，现有单账户行为不变）；每模式独立真金账户（现金+持仓）；B051 账户源单一性 per-mode 保持（latest() per mode）。
2. **执行链参数化**：position-diff / ticket / fills / reconcile / journal 全部参数化按 **(mode → 该模式真金账户 + 该模式目标)**——读对应账户、对应目标、写对应账户。
3. **B053 对账完整性 per-mode 保留**：超卖/负现金 409 拒绝逻辑在每个模式账户上仍生效（不静默修正）。
4. **Master 向后兼容（关键）**：默认 mode=master_portfolio，无 mode 参数时走 Master（现有 API/前端不破）；新模式显式带 mode。
5. **测试**：多账户隔离（regime 账户≠Master 账户）+ 每模式 diff/ticket/reconcile 正确 + **Master 现有路径行为不变（向后兼容回归）** + B053 对账 per-mode（超卖/负现金 409）。
6. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / alembic head / api.ts drift（schema 加 mode）。

## 8. F005 — 前端多模式 surface（generator）

1. **模式选择器**：推荐页 + **执行页全套**（account/position-diff/ticket/fills/journal）加模式切换（Master/regime；未来自动出现）——每模式显自己的 推荐/目标/账户/diff/ticket/journal + 模拟盘 + 回测入口。
2. **诚实标注**：未配资/未验证模式标「研究态/前向验证中」；模拟盘 vs 真实账户清晰区分。
3. 中文 + i18n parity + api.ts 同步。
4. 测试：vitest（模式切换/regime 全套视图/Master 不破）+ i18n parity。
5. Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift 0。

## 9. F006 — Codex L1+L2 + signoff（codex）

L1 全门禁。L2 真 VM：①**通用平台**：Master+regime 各有 目标/回测/模拟盘/真实账户+执行链/surface，可切换；②**regime 落地**：回测非退化+模拟盘前向+（可选）regime 真实账户走一遍 diff/ticket；③★**Master 执行硬回归**——Master 现有 推荐/diff/ticket/reconcile/journal/账户 行为完全不变（B051 账户源+B053 对账 per-mode 不破，用户正用 Master 真实交易）；④**B053 对账 per-mode**：regime 账户超卖/负现金仍 409；⑤回归 B050-B056+recent-errors=0+HEAD≡main；⑥演练自清。Signoff（§多模式全平台证据+§regime 落地+§★Master 执行不破+§对账 per-mode+§Ops）。§25 须正面真机证据。

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| **动摇 Master 执行链**（用户正真实交易）| F004 向后兼容(Master 默认 mode 路径不变)；F006 ★Master 执行硬回归；最高优先回归项 |
| 真金多账户对账错误 | B053 对账完整性 per-mode 保留（超卖/负现金 409 不静默）；F006 验 per-mode |
| 抽象建歪 | regime 第一真实消费者校准 |
| 范围过大/批次最大 | 6 features 分步；F004 最重单列；可能多 fix-round（用户已知是最大批次）|
| 能力建好诱使过早配资 | 前端标注研究态；planner 建议 regime 先 paper 验证再 funding（纪律守配资决策）|

## 11. Core Acceptance（一句话）

策略模式成为全维度一等公民——Master + regime 各有 目标/回测/模拟盘/真实账户+执行链/surface，可独立真实交易，regime 作第一真实消费者校准；**且 Master 现有执行链完全不破**（用户正真实交易）；funding 决策仍归用户（建议先 paper 验证）。
