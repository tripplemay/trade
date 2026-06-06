# B039 — Home AI Advisor disclaimer（Phase 3 / Stream 4.C，最小范围）

> **状态：** planning（2026-06-06 起草）。
> **批次类型：** 新功能（Phase 3 S4.C），**前端-only 最小范围**。
> **配套权威设计：** `docs/product/user-personas-and-journeys-2026-05.md` §2 Daily Journey mockup（design-draft/ 空，以 personas mockup 为权威，同 B037/B038）。

---

## 1. 目标与范围再定义

roadmap S4.C 原文「Home 整合 AI Advisor（来自 B036）：Home 第二段渲染 AI 一句话建议 + 引用 + disclaimer；INSUFFICIENT_GROUNDING 时段位置保留但内容降级」。

**经 building-前 codebase 核查（2026-06-06）：B037 复用 `AdvisorSection` 已把以下全部接入 Home 第二段——**
- ✅ AI 建议文本（per-sleeve advice + rationale）
- ✅ 引用 📎（`quant_signal_sha` + news_urls 外链 rel=noopener）
- ✅ INSUFFICIENT_GROUNDING fallback（双语，段位保留+内容降级）
- ✅ per-sleeve 布局

**唯一明确剩余 gap = mockup §2 的 `⚠️ disclaimer「这是研究参考，不是收益预测。最终决策由你判断。」` 未渲染。** 后端 `/api/advisor`（B036）已足够（含 advice/rationale/references/status），**无需后端改动**。

**因此 B039 真实范围（2026-06-06 用户已批）= 给 Home AI Advisor 段补双语 disclaimer + 永存守门 + 端到端验证。**

---

## 2. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| B039 范围 | ★ **最小：补 disclaimer + 验证** | 字面目标 B037 已完成；唯一 gap 是缺 disclaimer（安全/合规 UI）|
| Master 一句话总结 | ★ **不做**（留后续/B036 扩展） | 当前 per-sleeve 渲染可接受；统一 Master-level 一句话需 B036 后端生成，超本批 |
| 后端改动 | **无** | `/api/advisor` 既有 schema 足够 |

---

## 3. 永久硬边界（继承）

- **no-execution UI**：AdvisorSection 无下单/执行按钮 + 中文禁词同级（既有 Home guard 不破）。
- **AI 边界（v0.9.28 5 子条）**：disclaimer 文案属固定模板文本（非 AI 生成）；不改 B036 生成式 advice / references ⊆ input set 校验 / B032 red-team gate。
- **i18n disclaimer 双语永存（v0.9.26）**：本批新增的 advisor disclaimer 必须 zh-CN + en 双语齐 + 永存守门（删一边 = 守门 fail）。

---

## 4. 技术架构

### 4.1 disclaimer 渲染

- `components/advisor/AdvisorSection.tsx`：在引用块（`advisor-references`）下方加 disclaimer 元素（`data-testid="advisor-disclaimer"`），渲染固定模板文案。
- 位置对齐 personas §2 mockup（advice → 📎 引用 → ⚠️ disclaimer 顺序）。
- disclaimer 在 `status=ok` 与 `INSUFFICIENT_GROUNDING` 两态都应显示（安全提示不因降级消失）——或至少 ok 态必显；fallback 态本身已是安全提示，disclaimer 仍建议显示。Generator 实施时确认两态行为，spec 倾向**两态都显示**（disclaimer 是通用研究声明，非 advice 专属）。

### 4.2 i18n

- `messages/zh-CN.json` + `messages/en.json` advisor 命名空间加 `disclaimer` key：
  - zh-CN：「这是研究参考，不是收益预测。最终决策由你判断。」
  - en：「This is a research reference, not an earnings prediction. The final decision is yours.」
- 双语齐 + 无禁词。

### 4.3 守门 / 测试

- **i18n-disclaimer-永存守门**（复用/扩 v0.9.26 既有 disclaimer 永存守门）：断言 advisor disclaimer key 在 zh-CN + en 双存；缺一即 fail。
- `AdvisorSection.spec.tsx` 加断言：disclaimer 渲染（ok 态 + INSUFFICIENT 态）+ 双语 + 文案非空。
- no-execution 守门覆盖 disclaimer 元素（无按钮/禁词）。
- Playwright Daily Journey：Home AI Advisor 段 disclaimer 可见（双 locale）。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | AdvisorSection 加双语 disclaimer + i18n keys + 永存守门 + vitest + Playwright Daily Journey 断言 |
| F002 | codex | L1 + L2（Home AI Advisor 段 disclaimer 浏览器手验双语 + no-execution + §永存守门）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做 Master/Home 级一句话总结（留后续；需 B036 后端生成）。
- 不改 `/api/advisor` 后端 schema / B036 生成逻辑 / red-team gate。
- 不改 AdvisorSection 既有 advice/citations/fallback 渲染（仅追加 disclaimer）。
- 不触 B038 新闻段 / market-context / 三段 Home 结构。
- 不动 recommendations/risk/reports 页。

---

## 7. 验收门槛汇总

- **F001**：AdvisorSection disclaimer 渲染（ok + INSUFFICIENT 两态）+ zh-CN/en 双语 key + i18n-disclaimer-永存守门 + AdvisorSection.spec 断言 + no-execution 守门覆盖；frontend vitest ≥ baseline+ / lint 0 / typecheck / Playwright Daily Journey disclaimer 可见（双 locale）不破；backend 不动（pytest 不跑回归亦可，确认无后端 diff）。
- **F002**：L1 全门禁（vitest / lint / typecheck / Playwright / 双语齐 / 无禁词 / no-execution / disclaimer 永存守门）+ secret grep 0；L2（真 VM）：health 200 + SHA≡main HEAD；recent-errors=0；**Home AI Advisor 段 disclaimer 浏览器手验**（advice/引用下方 ⚠️ 研究声明可见 + 双语切换 + 无下单按钮）+ 截图；Production HEAD ≡ main HEAD；B026 banner 仍 absent。Signoff: docs/test-reports/B039-home-advisor-disclaimer-signoff-2026-MM-DD.md 用模板（§Production/HEAD + §Post-signoff Deploy；本批纯前端无新路由/无 timer，§24/§23 标 N/A）；docs/screenshots/B039-home-advisor-disclaimer/ ≥1 PNG。Framework 候选：薄批次预计无；若有记 signoff §Framework Learnings。

---

## 8. 参考文档

- 权威 mockup：`docs/product/user-personas-and-journeys-2026-05.md` §2（line 48 disclaimer）
- AdvisorSection（B036/B037 复用）：`workbench/frontend/src/components/advisor/AdvisorSection.tsx`
- /api/advisor schema（B036，不改）：`workbench/backend/workbench_api/schemas/advisor.py`
- i18n disclaimer 双语永存（v0.9.26）+ Order ticket 双语 disclaimer 永久边界
- B038 spec（同「B037 复用→真实 gap」模式）：`docs/specs/B038-home-market-news-spec.md`

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| disclaimer 只加一种语言 | i18n-disclaimer-永存守门（v0.9.26）双存断言 |
| disclaimer 在 INSUFFICIENT 态被吞 | spec §4.1 倾向两态都显示；F001 确认 + spec 断言两态 |
| 薄批次过度工程 | 严格最小范围；无后端改动；F002 L2 仅手验 disclaimer + 截图 |

---

## 10. 后续批次（不在 B039 范围）

- Master/Home 级一句话总结（需 B036 后端扩展）—— 候选，未排期。
- B040-B043：Reports/Rec/Risk 重构 + AI 解释层。
