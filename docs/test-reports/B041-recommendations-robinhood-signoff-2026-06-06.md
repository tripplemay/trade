# B041 Recommendations Robinhood Signoff 2026-06-06

> 状态：**PASS**
> 触发：B041 F002 首轮验收通过

---

## 变更背景

B041 对 `/recommendations` 做纯前端 UI 重构：把 target positions 的默认展示从专业表格切到简化 card 视图，并保留一个 Radix Tabs toggle 在「简化 / 专业」之间切换。该批不改后端 schema、不改推荐引擎、不引入 AI 解释，只重构展示层并要求不破 gate checks / wash-sale / export-to-ticket / NewsPanel。

---

## 变更功能清单

### F001：Generator 实现

**Executor：** generator

**结果：**
- 新增 `PositionCards` 简化卡视图，展示 `target/current/delta` 大数字与既有 `rationale`。
- 新增 Recommendations 视图 toggle：默认 `simple`，可切 `professional` 回到既有表格。
- 新增 `recommendations.cards.*` 与 `recommendations.view.*` 双语文案与 tooltip。
- 复用 `colorForDelta` 对 delta 进行红/绿/中性编码。
- no-execution 守门扩展到 `PositionCards`。

### F002：Codex L1 + L2 验收与签收

**Executor：** codex

**文件：**
- `docs/test-reports/B041-recommendations-robinhood-signoff-2026-06-06.md`
- `docs/screenshots/B041-recommendations-robinhood/simple-zh-CN.png`
- `docs/screenshots/B041-recommendations-robinhood/simple-en.png`
- `docs/screenshots/B041-recommendations-robinhood/professional-zh-CN.png`
- `docs/screenshots/B041-recommendations-robinhood/professional-en.png`
- `docs/screenshots/B041-recommendations-robinhood/browser-check.json`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 后端 recommendations schema / engine | 无改动 |
| `rationale` 内容 | 继续沿用既有占位文本，不扩成 B043 的富解释 |
| gate checks / wash-sale / export-to-ticket / NewsPanel | 仅要求不回归，不改逻辑 |
| 新路由 / timer | 无 |
| 任何执行 / 下单能力 | 无改动，仍是 research-only |

---

## 类型检查 / CI

```text
frontend targeted vitest: 53 passed
  - tests/unit/recommendations/PositionCards.spec.tsx
  - tests/unit/page/recommendations.spec.tsx
  - tests/unit/metric-color.spec.ts
  - tests/unit/messages-key-parity.spec.ts
  - tests/safety/no-execution-buttons.spec.ts

local Playwright: 3 passed
  - tests/e2e/b041-recommendations.spec.ts

generator handoff baseline:
  - frontend lint 0
  - frontend typecheck pass
  - frontend vitest 246
  - Playwright green
backend diff: none
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production `/api/health` | `200`，`version=94df2324e39bf6bbd1e38bdbed068b06ae6becf0` |
| Production HEAD vs main HEAD | 签收前 `main HEAD=f04eaf6...`；`git diff --name-only 94df232..f04eaf6` 仅 `.auto-memory/project-status.md`、`features.json`、`progress.json`，按 §Production/HEAD 接受等价不同步 |
| authenticated `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| authenticated `/api/recommendations/current` | `200`，当前为 **空账户路径**：`target_positions=0`、`gate_checks=2`、`wash_sale_flags=0`、`account_present=false` |
| anonymous `/api/recommendations/current` | `401` |
| 浏览器手验 | `docs/screenshots/B041-recommendations-robinhood/browser-check.json`：zh-CN / en 两轮均满足 toggle 从 `simple -> professional -> simple` 正常切换，`gateCount=2`，`recommendations-export` 可见且未 disabled，`syntheticBannerCount=0`，`oldDashboardCount=0`，`issues=[]` |
| 简化视图空态 | 两轮 `emptyStateVisible=1`、`positionCardsVisible=0`，符合 handoff 的空账户说明 |
| 专业视图空态 | 两轮 `professionalTabState=active` 时 `tablePresent=0`，但 gate / export 区保持正常 |
| §1.1 非预测边界 | 两轮 `textHasExpectedReturn=false`、`textHas收益预测=false` |

> 说明：production 当前无 target positions，因此 L2 验证的是空账户下的结构与切换完整性，而不是非空卡片数据。该情况已在 generator handoff 明确为可接受路径。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，`docs.signoff` 已填入本报告路径。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version | `94df2324e39bf6bbd1e38bdbed068b06ae6becf0` |
| Main HEAD | `f04eaf636fe672b178f4d2d9a0df222f7444e8fa` |
| Diff (`git log --oneline <deployed>..HEAD`) | `f04eaf6 chore(B041): F001 done + Frontend CI green -> status=verifying (handoff to Codex F002)` |

**等价性判断：**

`git diff --name-only 94df232..f04eaf6` 仅含状态机文件：

- `.auto-memory/project-status.md`
- `features.json`
- `progress.json`

无 `workbench/**`、`framework/**`、`docs/specs/**` 等产品或 deploy-impacting 改动，因此 production 与当前 HEAD 产品等价，不阻断签收。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine + screenshots` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本次 signoff commit 仅新增验收报告、截图、browser-check 与状态机文件；不含产品代码或 deploy-impacting 改动，按 §Production/HEAD 接受不同步 |

---

## Decommission Checklist

| 检查项 | 状态 | 证据 |
|---|---|---|
| 旧 dashboard 未复活 | **是** | `browser-check.json` 中 `oldDashboardCount=0` |
| B026 synthetic banner 未复活 | **是** | `browser-check.json` 中 `syntheticBannerCount=0` |
| 简化卡视图无下单/执行按钮 | **是** | `browser-check.json` 中空态按钮数 `0`；L1 no-execution 守门 `30 passed` |

---

## Framework Learnings

无新增 framework 沉淀。本批属于纯前端薄 UI 重构，现有 v0.9.25 / v0.9.31 守门已足够覆盖。

---

## Conclusion

可以签收。B041 已在 production 上验证 Recommendations 的简化/专业双视图切换、双语标签和空账户路径表现均符合预期，且 gate checks / wash-sale / export 区未回归。
