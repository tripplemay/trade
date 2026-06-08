# B042 — Risk Panel UI 微调（Robinhood-style）+ BL-B023-S2 kill-switch red 演练

> **状态：** planning（2026-06-08 起草）。
> **批次类型：** 新功能（Phase 3 S5.C UI 微调，**前端-only**）+ BL-B023-S2（Codex red 态演练）。里程碑 C order 6。
> **配套：** `docs/product/user-personas-and-journeys-2026-05.md` §7（Risk 低-中等改造）/ positioning §1.1。
> **前置：** B048 已让 risk 数据**真实**（mark-to-market master/per-sleeve DD + valuation_basis + degraded_symbols + 真实 kill_switch state）→ 本批在**真风控数据**上 Robinhood 化 UI。

---

## 1. 目标

把 Risk Panel UI 微调成 Robinhood-style 一致呈现（drawdown/kill-switch 颜色 + 字体一致化 + 术语 tooltip），并验证 kill-switch red 态 UI（BL-B023-S2）。**前端-only**（B048 数据已真，零后端改动）。

---

## 2. 决策（planner 按 roadmap「微调」定 + 用户 backlog 确认）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 范围 | **前端-only UI 微调**（B048 数据已真） | roadmap「Risk Panel 微调」=polish 非重构 |
| per-sleeve 展示 | **Option A 最小：保 grid + 严重度配色 + tooltip**（planner 决） | 「微调」不重构成卡片（避免 scope creep）|
| 颜色一致化 | **扩 metric-color：colorForRiskState（green/yellow/red 统一 emerald/amber/red 调色板）**（planner 决） | RiskBanner 现 ad-hoc 颜色 → 统一 B040 调色板 |
| valuation_basis | **surface cost_degraded 诚实指示**（planner 决） | B048 价格历史不覆盖时 cost_degraded，UI 标注（接 B048 S1，v0.9.21 诚实）|
| BL-B023-S2 | **bundle 进本批 Codex L2 红态演练**（用户 backlog order 6） | red 样本触发 → red banner + defensive ticket + radio 全链路 |

---

## 3. 永久硬边界（继承）

- risk panel 信息性不 gate ticket（B023）；no-execution（无下单按钮）。
- 定位 §1.1 不出收益预测；drawdown/DD 是历史风险事实。
- i18n 双语齐 + 无禁词 + tooltip parity（v0.9.26）。
- 不改 B048 risk 后端数据/schema（前端透明渲染）。

---

## 4. 技术架构（前端-only）

### 4.1 颜色一致化（F001）

- `lib/metric-color.ts` 扩 `colorForRiskState(state)→{border,bg,text}`（green=emerald/yellow=amber/red=destructive，统一 B040 调色板）；RiskBanner STATE_STYLES 改用之（去 ad-hoc green-700/950）。
- per-sleeve 行严重度配色：复用 colorForDelta 逻辑映射 drawdown（<5% 绿 / 5-8% 琥珀 / ≥per_sleeve_threshold 红）。

### 4.2 风控术语 tooltip（F001）

- 复用 B040/B041 radix tooltip 模式：RiskBanner 的 master DD / kill-switch / per-sleeve drawdown 术语 label 包 tooltip。
- i18n 加 `risk.tooltips.{masterDrawdown,killSwitch,perSleeveDrawdown,defensiveTicket}` 双语（手写解释，术语英文 + 中文）；parity 守门。

### 4.3 valuation_basis 诚实指示（F001）

- RiskBanner/page 渲染 `valuation_basis`：`mark_to_market` 正常；`cost_degraded` 显式标注（如「部分日期价格历史不足，回撤按成本价估算」+ degraded_symbols）—— 接 B048 S1，不蒙混（v0.9.21）。

### 4.4 字体/间距一致化（F001）

- RiskBanner text 层级规范（headline text-sm font-semibold / 数值 font-mono / label muted-foreground），对齐 B040 MetricsDisplay 风格。

### 4.5 BL-B023-S2 red 态演练（F002 Codex）

- Codex L2：PUT 风险样本账户（master DD > 15% 触发 kill_switch）→ red banner + 并排 normal/defensive ticket + radio 选择 → generate-ticket honors 选择全链路；留红态截图。

### 4.6 测试

- vitest：colorForRiskState（三态）+ per-sleeve 严重度配色边界 + 风控 tooltip i18n 双语 + valuation_basis 两态渲染（复用既有 risk-banner red/yellow/green fixtures）+ no-execution 守门。
- Playwright：/risk 三态渲染 + tooltip + 双 locale（red 态真机演练交 F002）。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | RiskBanner Robinhood 微调：colorForRiskState 一致调色板 + per-sleeve 严重度配色 + 风控术语双语 tooltip + valuation_basis 诚实指示 + 字体一致化 + vitest/Playwright |
| F002 | codex | L1 + L2 真 VM 验收（Risk Panel 三态浏览器手验 + 双语 tooltip + 颜色一致 + **BL-B023-S2 red 样本演练**：触发 kill_switch→red banner+defensive ticket+radio+截图）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不改 B048 risk 后端/schema（前端透明）。
- 不把 per-sleeve 重构成卡片（Option A 最小微调）。
- 不新增执行/下单 / 不 gate ticket（信息性）。
- 不输出收益预测。

---

## 7. 验收门槛汇总

- **F001**：colorForRiskState 统一调色板（RiskBanner 去 ad-hoc）+ per-sleeve 严重度配色 + 风控术语双语 tooltip（i18n parity）+ valuation_basis cost_degraded 诚实标注 + 字体一致化；frontend vitest ≥ baseline+ / lint 0 / typecheck / Playwright（三态+双 locale）；no-execution 守门；**backend 不动**。
- **F002**：L1 全门禁（vitest/lint/typecheck/Playwright/双语齐/无禁词/no-execution/tooltip parity）+ secret grep 0；L2（真 VM）：health 200 + HEAD≡main + recent-errors=0；**Risk Panel 三态浏览器手验**（颜色一致 emerald/amber/red + 风控 tooltip hover 双语 + valuation_basis 标注）；**BL-B023-S2 red 演练**（PUT 风险样本 master DD>15%→red banner + 并排 normal/defensive ticket + radio→generate-ticket honors 选择；红态截图 ≥1）；双语切换；B026 absent。Signoff（§Production/HEAD + §Post-signoff Deploy + **red 态演练证据 + valuation_basis 渲染**）；docs/screenshots/B042-risk-panel/ red 态 ≥1 PNG。Framework 候选：薄 UI 批次预计无。

---

## 8. 参考文档

- Risk 现状：`(protected)/risk/page.tsx` / `components/risk/RiskBanner.tsx`（STATE_STYLES ad-hoc）/ `schemas/risk_panel.py`（B048 字段）
- 复用：`lib/metric-color.ts`（B040 colorForMetric/colorForDelta）/ `components/metrics/MetricsDisplay.tsx`（tooltip 模式）/ `components/recommendations/PositionCards.tsx`（B041 卡片）
- BL-B023-S2：backlog + `tests/unit/risk-banner.spec.tsx`（red/yellow/green fixtures）
- 数据真实化前置：B048 signoff（risk_panel mark-to-market）

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 颜色统一破坏既有 red 态 ticket 联动 | colorForRiskState 仅换 class 不改逻辑；既有 risk-banner.spec 红态 ticket 联动测试不破 |
| BL-B023-S2 red 样本 PUT 误操作生产 | 演练后 account 恢复；操作用户授权（同 BL-B023-S1）|
| valuation_basis cost_degraded 常态（B048 S1）| 诚实标注即可；data-refresh 拉近期价后自动改善 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：B048 risk 后端 / 评分 / 其他页。
- **解锁**：Risk Panel 在真风控数据上 Robinhood 化 + red 态演练确证。
- **后续 order**：B047 Backtest+Reports 真实引擎(7)→B049 全页面审计 gate(8)；B043 AI 解释并行。
