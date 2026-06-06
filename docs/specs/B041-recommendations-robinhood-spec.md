# B041 — Recommendations Robinhood-style 重构（Phase 3 / Stream 5.B）

> **状态：** planning（2026-06-06 起草）。
> **批次类型：** 新功能（Phase 3 S5.B），**前端-only**（无后端改动）。
> **配套权威设计：** `docs/product/positioning-2026-05.md` §line 69（Rec UI 改造表）+ §1.1 / `docs/product/user-personas-and-journeys-2026-05.md` §7 + §3 Quarterly Journey。design-draft/ 空 → 以 positioning + personas 为权威。

---

## 1. 目标与范围

roadmap S5.B：「target positions table → simplified card + '为什么这样建议'（联动 B043 AI 解释层）；**保留专业 view toggle**」。

**核查结论（2026-06-06）**：① UI 重构（简化 card + 专业 view toggle）= 前端-only，可直接做；② **「为什么这样建议」的真实数据/评分不存在**——推荐引擎是 equal-weight 占位（F011 真实评分未建），`TargetPosition.rationale` 是占位文本，无 quant signal 可引用；富 AI「为什么」是 **B043**（依赖真实评分）。

**B041 真实范围（2026-06-06 用户已批「UI 重构 now，富『为什么』留 B043」）：**
- target-positions **简化 card 视图**（大数字 target/current/delta + 颜色编码 + 双语 tooltip，复用 B040 原语）。
- **专业 view toggle**（Radix Tabs：简化 card ⟷ 既有专业 table）。
- surface 现有 `rationale`（占位文本，as-is），**富「为什么这样建议」明确留 B043**。

---

## 2. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 范围 | ★ **UI 重构 now，富「为什么」留 B043** | UI 前端-only 可做；富 rationale 需 AI(B043)+真实评分(未建) |
| 后端改动 | **无**（planner 决） | rationale 字段已存在；占位文本 as-is surface |
| view toggle | **Radix Tabs（简化 card / 专业 table）**（planner 决） | 默认简化 card，toggle 切专业 table |
| 颜色编码 | **复用 B040 colorForMetric**（planner 决） | delta：buy(+)绿 / sell(−)红 / 0 中性 |

---

## 3. 永久硬边界（继承）

- **no-execution UI**：Recommendations 页只有研究工作流（export-to-ticket / gate checks / wash-sale），**无下单/执行按钮 + 中文禁词同级**；本批不新增任何执行按钮（守门扩新 card/toggle）。
- **定位 §1.1**：不输出预期收益数字；card 显示 target/current/delta 权重（配置事实，非收益预测）；tooltip 是术语解释（确定性手写，非 AI）。
- **i18n**：术语英文 + 中文 tooltip；en + zh-CN 双语齐 + 无禁词 + 手动 parity。
- **AI 边界**：本批不触 AI（富「为什么」是 B043）；占位 rationale as-is 不经 AI。

---

## 4. 技术架构（前端-only）

### 4.1 简化 card 视图

- `components/recommendations/PositionCards.tsx`（新）：每个 target position 一张 card——symbol + 大数字（target_weight / current_weight / delta）+ delta 颜色编码（复用 `lib/metric-color.ts`，正=绿 buy / 负=红 sell / 0 中性）+ 现有 `rationale` 文本（占位 as-is）。
- 复用 B040 `MetricsDisplay` 模式 / Home sleeve-card 布局 / radix Tooltip（字段双语 tooltip，如 target_weight=「目标配置权重…」）。

### 4.2 专业 view toggle

- `components/ui/tabs.tsx`（Radix，现成）：target-positions 区上方加 toggle——「简化 / 专业」两态。
- **简化 tab**：PositionCards（默认）。
- **专业 tab**：既有 DataTable（symbol/target_weight/current_weight/diff/rationale 全列，不动）。
- 仅切换 target-positions 呈现；页面其余（饼图/柱图/gate checks/wash-sale/export-to-ticket/NewsPanel）**不动**。
- toggle 状态 useState；i18n `recommendations.view.{simple,professional}`。

### 4.3 i18n

- 加 `recommendations.view.*`（toggle 标签）+ `recommendations.cards.*`（card 字段 label + 双语 tooltip：target/current/delta 解释）。
- en + zh-CN 双语齐 + 无禁词 + parity 守门。

### 4.4 测试

- vitest：PositionCards 渲染（大数字 + delta 颜色 + rationale 文本）+ toggle 切换两态（简化↔专业 table）+ tooltip i18n 双语 + 既有 table 仍渲染。
- Playwright：Recommendations 页默认简化 card 可见 → toggle 切专业 table → 切回；双 locale；无下单按钮。
- no-execution 守门覆盖 PositionCards + toggle。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 前端 Recommendations 简化 card 视图 + 专业 view toggle（Radix Tabs）+ 复用 B040 原语 + surface rationale + i18n + no-execution 守门 + vitest + Playwright |
| F002 | codex | L1 + L2 真 VM 验收（简化 card / 专业 toggle 浏览器手验 + 双语 tooltip + delta 颜色 + no-execution + Markdown export 工作流不破）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做富「为什么这样建议」AI 解释（B043；本批 surface 占位 rationale as-is）。
- 不改后端 recommendations schema / 推荐引擎 / equal-weight 分配逻辑 / F011 真实评分。
- 不输出预期收益数字（定位 §1.1）。
- 不动既有 DataTable 列 / 饼图柱图 / gate checks / wash-sale / export-to-ticket(B023) / NewsPanel(B034)。
- 不触 Home / Reports(B040) / Risk(B042)。

---

## 7. 验收门槛汇总

- **F001**：PositionCards（大数字 target/current/delta + delta 颜色 + rationale 文本）+ 专业 view toggle（Radix Tabs，默认简化，切既有 table）+ 双语 tooltip + i18n parity；frontend vitest ≥ baseline+（card 渲染 + toggle 两态 + 颜色边界 + tooltip 双语 + 既有 table 不破）/ lint 0 / typecheck / Playwright（toggle + 双 locale）；no-execution 守门覆盖新组件；**backend 不动**（无后端 diff）。
- **F002**：L1 全门禁（vitest/lint/typecheck/Playwright/双语齐/无禁词/no-execution/parity 守门）+ secret grep 0；L2（真 VM）：health 200 + SHA≡main HEAD；recent-errors=0；**浏览器手验**：Recommendations 默认简化 card（大数字 + delta 颜色绿/红/中性 + 双语 tooltip）→ toggle 切专业 table → 切回；export-to-ticket 工作流仍可用；无下单按钮（no-execution）；双语切换；定位 §1.1 无「预期收益」；截图（简化 + 专业两态 ≥2 PNG）；HEAD≡main；B026 absent。**本批纯前端无新路由/timer，§23/§24 N/A**。Signoff 用模板（§Production/HEAD + §Post-signoff Deploy）+ docs/screenshots/B041-recommendations-robinhood/ ≥2 PNG。Framework 候选：薄 UI 批次预计无。

---

## 8. 参考文档

- 权威定位：`positioning-2026-05.md` line 69（Rec UI 改造表）+ §23（可解释引用，富版属 B043）
- UI 优先级 + Quarterly Journey：`user-personas-and-journeys-2026-05.md` §7 + §3
- Recommendations 现状：`(protected)/recommendations/page.tsx` / `schemas/recommendations.py`（TargetPosition.rationale 占位）/ `services/recommendations.py`（equal-weight 占位 + F011 deferred）
- 复用原语（B040）：`components/metrics/MetricsDisplay.tsx` / `lib/metric-color.ts` / `components/ui/tooltip.tsx` / `components/ui/tabs.tsx` / Home sleeve 卡片
- B023 export-to-ticket 工作流（不破）：`docs/dev/workbench-manual-execution-runbook.md`

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 占位 rationale 被误读为真实「为什么」 | card 显示现有占位文本 as-is；富「为什么」明确 B043；spec/i18n 不夸大 |
| toggle 破坏既有 table/export 工作流 | 专业 tab 用既有 DataTable 原样；其余面板不动；F002 验 export-to-ticket 仍可用 |
| 占位权重数据被误用为决策 | 沿用既有 disclaimer + no-execution；不新增决策语义；card 仅换呈现 |
| 双语 tooltip 机翻 | 手写 zh/en parity + 守门 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：后端 recommendations / B023 ticket 工作流 / B034 NewsPanel / 既有 charts。
- **B043 联动**：本批 surface 占位 rationale；B043 加 LLM「为什么这样建议」富解释（依赖真实评分，未来）。
- 后续：B042 Risk Panel 简化 / B043 AI 解释层 → 里程碑 C。
