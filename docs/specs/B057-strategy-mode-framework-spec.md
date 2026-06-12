# B057 — 通用「策略模式」框架 + regime 第一个落地消费者

> **批次类型：** 混合批次（4 generator + 1 codex）
> **状态：** planning → building（2026-06-12 与用户讨论定案；B056 done 后启动，用户调序 B057 先于 B055）
> **来源：** 2026-06-11 用户提出 regime 独立成模式 + 2026-06-12 用户选「通用模式框架 + regime 第一个消费者」。backlog B057。
> **范围裁定（用户确认）：** 通用框架 + regime 落地（目标+回测+模拟盘+surface）；**真实多账户执行链刻意延后**（follow-on，等 paper 验证后再配资）。

---

## 1. 愿景：让「策略模式」成为一等公民

现在系统围绕「一个 Master 目标 + 一个账户」建。用户已确立**多策略模式**方向（Master 综合 / regime 全天候 / 未来进攻 / …，各自独立）。**B057 = 把"策略目标/模式"从 Master-only 推广成参数化一等公民**，让任何策略以**最小成本**插入，并把现成的 **regime 作为第一个真实消费者**校准框架（不建空中楼阁）。

**框架每个模式自带：**
```
策略模式 = 策略目标(precompute) + 回测(B050 分发) + 模拟盘账户(B056) + surface(推荐/模拟盘视图)
                                                        ↑ 真实多账户执行链 = 后续 follow-on（本批不含）
```

**用户决策（2026-06-11/12）：** 资金=独立账户；先验证（回测+模拟盘）再配资；通用框架 + regime 第一消费者；真实执行延后。

---

## 2. 范围

**做（本批）：**
- **框架核心**：策略目标层从 Master-only 推广成**每模式一份**（统一接口，Master+regime+未来同源）。
- **regime 落地**：regime 目标 precompute（`derive_regime_adaptive_weights`）+ 接入 B050 回测分发（`run_regime_adaptive_monthly_backtest`）+ 接入 B056 模拟盘（参数化已就绪）+ 多模式 surface 可选可看。
- **前端**：模式选择器 + 每模式推荐/模拟盘视图。

**不做（延后 follow-on，等 paper 验证后）：** 真实多账户（每模式独立真金账户）+ 参数化执行链（每模式 diff/ticket/fills/reconcile）。本批真金交易仍只走 Master。

**硬边界：** §12.10.2（目标 precompute job 侧 import trade，请求路径只读）/no-AI/regime 仍 research-grade（不预测）。不改 regime 算法 / Master 评分 / 执行流。

---

## 3. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 通用策略目标层（每模式一份目标，参数化 strategy_id；Master+regime 统一接口）+ regime 目标 precompute |
| F002 | generator | regime 接入 B050 回测分发（adapter + report，回测页可跑）|
| F003 | generator | regime 接入 B056 模拟盘（参数化目标源）+ 多模式模拟盘 |
| F004 | generator | 前端多模式 surface（模式选择器 + 每模式推荐/模拟盘视图，中文）|
| F005 | codex | L1+L2 真 VM——Master+regime 双模式可回测+可模拟盘+可选；regime 前向验证；signoff |

## 4. F001 — 通用策略目标层 + regime 目标 precompute（generator）

1. **目标层推广**：把"当前策略目标"从 Master-only（recommendation_snapshot）推广成**每模式一份**——通用 `strategy_target`（或 recommendation_snapshot 加 strategy_id/mode 维度，generator 定迁移路径，保 Master 兼容）。统一接口：`get_target(strategy_id) → {symbol: weight, as_of, meta}`，Master/regime/未来同源。
2. **模式注册**：轻量 mode registry（id/display_name/strategy_id/target_producer/backtest_key/cadence）。Master（quarter-end）+ regime（monthly）。
3. **regime 目标 precompute**：新 job 调 `trade.strategies.regime_adaptive.weighting.derive_regime_adaptive_weights`（+ detect_regime）在最新真实数据上产出 regime 当前目标→写通用目标层；月度 cadence；§12.10.2（job 侧 import trade allowlist）。
4. **测试**：通用目标接口（Master/regime 同源读）+ regime precompute 产真实目标 + 兼容 Master 现有读路径不破。
5. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / alembic head（若加列/表）/ §12.10.2 守门。

## 5. F002 — regime 接入 B050 回测分发（generator，触 trade/）

1. **分发注册**：B050 `_DISPATCH` 加 `regime_adaptive`（`run_regime_adaptive_monthly_backtest`）+ 结果 adapter（regime result → BacktestRunResponse 字段）+ report builder（双语，沿用 B054 中文报告）。
2. **回测页可跑**：用户选 regime → 月度回测 → 真实多资产数据 → 非退化结果（regime 自带 9 资产 universe）。
3. **mypy trade 自检**（B050 教训）。
4. **测试**：regime 回测产非退化且异于 Master/其它；adapter 字段；月度 cadence。
5. Gates：backend+trade pytest ≥ baseline+ / ruff / mypy(workbench+trade) 0。

## 6. F003 — regime 接入 B056 模拟盘（generator）

1. **参数化目标源**：B056 paper 引擎已按 strategy_id 参数化；F001 通用目标层让 paper 引擎对 regime 同样 `get_target(regime_adaptive)`→虚拟调仓（月度 cadence）。regime 模拟盘账户=独立虚拟账户。
2. **多模式模拟盘**：用户可激活 regime 模拟盘（独立虚拟本金）与 Master 模拟盘并存；每日 MTM job 覆盖所有模式账户。
3. **测试**：regime 模拟盘激活+忠实跟 regime 目标+月度调仓+MTM。
4. Gates：同 F001。

## 7. F004 — 前端多模式 surface（generator）

1. **模式选择器**：推荐页 + 模拟盘页加模式切换（Master / regime；未来进攻自动出现）——每模式显**自己的目标推荐** + **自己的模拟盘**。
2. **regime 模式视图**：regime 当前目标（9 资产 + 防御状态）+ regime 模拟盘（复用 B056 6 区块）+ regime 回测入口。明确标 regime=research/前向验证中。
3. **中文** + i18n parity + api.ts 同步。
4. **测试**：vitest（模式切换/regime 推荐/regime 模拟盘）+ i18n parity。
5. Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift 0。

## 8. F005 — Codex L1+L2 + signoff（codex）

L1 全门禁。L2 真 VM：①**通用框架**：Master + regime 双模式各有目标、各可回测、各可模拟盘、surface 可切换；②**regime 落地**：regime 回测页跑出非退化结果、regime 模拟盘激活忠实跟 regime 目标+前向 MTM；③**框架被真实校准**（regime 作为真实消费者跑通=框架不悬空）；④回归 B050-B056 + Master 模拟盘/推荐/实盘不破 + recent-errors=0 + HEAD≡main；⑤演练自清。Signoff（§通用框架双模式证据 + §regime 回测+模拟盘前向 + §Master 不破）。§25 须正面真机证据。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 抽象建歪（无真实消费者）| regime 作第一消费者校准（用户拍板）；F005 验框架被 regime 跑通 |
| 推广目标层破 Master 现有读路径 | F001 保 Master 兼容；回归 Master 推荐/模拟盘/实盘不破 |
| 触 trade/ CI 严 | 本地 mypy trade（B050 教训）|
| 范围过大 | 真实多账户执行链刻意延后；本批限框架+regime 回测/模拟盘/surface |

## 10. 延后（follow-on，本批不含）

- **真实多模式执行**：每模式独立真金账户 + 参数化 diff/ticket/fills/reconcile/journal + 执行页模式选择器。**触发条件**：用户 paper 验证某模式值得配资后再立项。
- B055 进攻选股引擎（用户调序到 B057 之后）→ 届时复用本框架零成本插入。

## 11. Core Acceptance（一句话）

策略模式成为参数化一等公民——Master + regime 各有目标/回测/模拟盘/surface 视图，regime 作为第一个真实消费者跑通校准框架；用户能回测 + 模拟盘前向验证 regime（先验证再配资），真实多账户执行延后。
