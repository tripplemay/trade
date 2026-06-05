# B037 — Home 页架构改造（Phase 3 / Stream 4.A）

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态流转：** planning → building → verifying → (fixing ⟷ reverifying) → done
> **依赖：** B027 价格快照（mark-to-market）+ 既有 dashboard/strategies service；是 Phase 3 其他 Home 整合批次（B038/B039）的前置
> **决策对齐：** 2026-06-05 用户已批（见 §2）
> **权威设计参考：** `docs/product/user-personas-and-journeys-2026-05.md` §2 Daily Journey mockup（design-draft 无 Home 稿；该 doc line 161 规定 UI 批次必引用）

---

## 1. 目标

把 Home 页从「quant dashboard」重构为 **daily-engagement 中心**，按 user-personas §2 Daily Journey mockup 落三段版式：**① NAV + Day P&L 段 / ② AI Advisor 段（B039 填）/ ③ market context + 4 sleeve breakdown 段（market 部分 B038 填）**。本批次搭**完整三段骨架** + 自己负责的 NAV/Day P&L/sleeve breakdown 内容，AI/market 段留**占位**。是 Phase 3 → 里程碑 C（Layer 0.5）的起点。

**不做**（见 §6）：AI Advisor 实际内容（B039）/ market context 实际渲染（B038）/ Reports·Recommendations·Risk 重构（B040-B042）/ 真实 broker 账户（永久 no-broker）。

## 2. 决策矩阵（2026-06-05 用户已批，★=拍板）

| # | 决策 | 取值 | 依据 |
|---|---|---|---|
| 1 ★ | Day P&L | **mark-to-market 持仓**（用 B027 价格快照 mark sleeve 持仓算当日 P&L）| 用户拍板 |
| 2 ★ | 段落范围 | **全三段骨架 + B038/B039 占位** | 用户拍板 |
| 3 ★ | 旧 Home | **直接替换**（新 Home 上 `/`，不保留 /admin/legacy-home）| 用户拍板（**偏离** path doc「保留 legacy 直到稳定」，见 §9 风险）|
| 4 | 设计稿 | design-draft 空 → user-personas §2 mockup 为权威；acceptance 含 mockup 一致性项 | planner 规则 + personas line 161 |
| 5 | NAV 源 | 复用 `dashboard._aggregate_nav`（Account cash+equity，单研究账户，手动录入，no-broker）| 既有 |
| 6 | i18n / e2e | 双语（zh-CN + en）+ Playwright Daily Journey 流 | path B037 + user-personas |

## 3. 永久硬边界（继承）

- **系统层（继承）：** no-broker（NAV=手动录入研究账户，非真实券商）/ no-auto-execution / same-origin `/api/*` / auth-gated / Repository / 多用户禁 / Cloud SQL 禁。
- **UI 层（继承）：** **no-execution buttons + 中文等价禁词同级**（Home 不得出现下单/执行按钮）/ B026 banner decommissioned（不复活）。
- **退役（v0.9.31 §16，本批触发）：** 直接替换旧 Home = decommission；走**四处清理铁律**（旧 layout/route 移除 + 旧 i18n keys 清 + 组件保留或删 + 守门测试 + E2E presence→absence）。
- **数据/CI（继承）：** fixture-first 离线 CI / §12.10 请求路径自包含。
- AI 边界：本批不触 AI logic（AI Advisor 段仅占位，B039 填）。

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/
├── services/dashboard.py        # F001 扩：Day P&L (mark-to-market) + sleeve breakdown
├── services/home.py 或扩 dashboard # F001 build_home() 聚合三段数据
├── schemas/home.py              # F001 HomeResponse (nav / day_pnl / sleeves[])
└── routes/home.py 或扩 dashboard route  # F001 GET /home

workbench/frontend/src/app/(protected)/
├── page.tsx                     # F002 替换为新三段 Home
└── （F003）旧 quant dashboard 组件退役清理

workbench/frontend/messages/     # F002 三段 i18n keys（zh + en）；F003 清旧 Home keys
tests/                           # F001 pytest / F002 vitest / F003 Playwright + i18n safety
```

### 4.2 Home 数据（F001）

- `HomeResponse { nav: float, day_pnl: {value, pct} | null, sleeves: [{sleeve, nav_share, day_pnl, positions_summary}] }`。
- **NAV**：复用 `_aggregate_nav`（Account cash+equity）。
- **Day P&L（mark-to-market）**：取最新 AccountSnapshot 持仓 → 用 B027 最新价格快照 mark 各持仓 → 当日 mark 值 vs 前一交易日 mark 值；价格缺失/无持仓 → `day_pnl=null`（UI 显示 —）。**只读**，不触发任何执行。
- **4 sleeve breakdown**：strategies service 的 sleeve 分组 + 各 sleeve 持仓占比 + per-sleeve day P&L。
- 守门：`test_home_request_self_contained`（§12.10）。

### 4.3 前端三段 Home（F002）

- 替换 `(protected)/page.tsx` 为三段版式（对齐 personas §2 mockup）：
  - **① NAV + Day P&L 段**：总 NAV 大数字 + 今日涨跌（颜色编码 + %）+ 状态绿灯。
  - **② AI Advisor 段**：**占位**（"AI 建议即将上线"/B039 填；预留段位置）。
  - **③ market context + 4 sleeve breakdown 段**：market 部分**占位**（B038 填）+ 4 sleeve breakdown 渲染。
- 双语（zh-CN + en）；**无下单/执行按钮**（no-execution UI 边界）；mockup 一致性。

### 4.4 旧 Home 退役（F003，v0.9.31 §16）

- 旧 quant dashboard 直接替换（不保留 legacy）：移除旧 layout/route 引用 + 清旧 i18n keys + 旧组件删除或保留 decommission notice + 守门测试 + 既有 Home E2E presence→absence 翻转（若有）。

### 4.5 安全 / regression test 矩阵

| 测试 | 守门 |
|---|---|
| i18n safety regression（扩集）| 三段 keys 双语齐 + 无禁词（中文等价禁词同级）|
| no-execution buttons 守门 | Home 无下单/执行按钮 + 中文禁词 |
| `test_home_request_self_contained`（§12.10）| /home 请求路径自包含 |
| 旧 Home E2E presence→absence（§16）| 旧 dashboard 元素 absent |

## 5. Feature 拆分

### F001 — 后端 Home 数据（NAV + Day P&L mark-to-market + sleeve breakdown）（generator，2 天）
build_home() + Day P&L mark-to-market（B027 价格）+ sleeve breakdown + GET /home + schema + §12.10 守门 + pytest。详见 features.json。

### F002 — 前端三段 Home 架构（替换旧 dashboard）+ 双语 + 占位（generator，2-3 天）
三段版式 + NAV/Day P&L/sleeve breakdown 渲染 + AI/market 占位 + 双语 + mockup 一致性 + no-execution UI 守门 + vitest。详见 features.json。

### F003 — Playwright Daily Journey e2e + i18n safety + 旧 Home 退役清理（generator，2 天）
e2e + i18n safety regression 扩集 + v0.9.31 §16 四处清理 + E2E presence→absence。详见 features.json。

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1 天）
L1 全门禁 + §16 decommission checklist + no-execution 守门 + L2（新 Home 真 VM 渲染 / Day P&L mark / 旧 dashboard absent / HEAD≡main）+ signoff。详见 features.json。

## 6. 不做的事（YAGNI）

- AI Advisor 段实际内容（B039）/ market context 段实际渲染（B038）。
- Reports / Recommendations / Risk 重构（B040-B042）。
- 真实 broker 账户 / 实时行情推送（NAV/持仓手动录入 + 价格快照 mark）。
- 保留 /admin/legacy-home（用户选直接替换）。

## 7. 验收门槛汇总

| 门禁 | 阈值 |
|---|---|
| backend pytest | F001 ≥ baseline+≥8（B036 收尾 baseline 735）|
| frontend | vitest ≥185（+Home 段）/ Playwright ≥41（+Daily Journey）/ lint 0 / typecheck pass |
| ruff / mypy | exit 0 |
| 安全守门 | i18n 双语齐 + 无禁词 / no-execution buttons / §12.10 自包含 / §16 旧 Home 退役四处清理 + E2E presence→absence |
| 设计稿 | 对齐 user-personas §2 mockup（acceptance 一致性项）|

## 8. 参考文档

- `docs/product/user-personas-and-journeys-2026-05.md` §2 Daily Journey mockup + §7 UI 优先级（**权威**）
- `docs/product/implementation-path-2026-05.md` §4 Phase 3 / Stream 4.A（B037 行）
- `docs/specs/B027-real-data-snapshot-foundation-spec.md`（价格快照 mark-to-market）
- framework v0.9.31 §16（decommission 四处清理）+ evaluator.md §22（E2E presence→absence）+ v0.9.32 §12.10
- 既有 `services/dashboard.py` / `db/models/account.py` + `account_snapshot.py` / strategies service

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 直接替换旧 Home 丢回退路径（偏离 path doc）| 用户已决；旧组件 git 历史可恢复；新 Home 经 L2 真 VM 验收 + Playwright Daily Journey 才签收 |
| Day P&L mark-to-market 价格缺失 | 价格/持仓缺 → day_pnl=null，UI 显示 —，不报错 |
| 三段版式与 B038/B039 占位接口不一致 | 占位段预留明确 slot + props 约定，B038/B039 只填内容不改结构 |
| 旧 Home 退役遗漏 i18n keys / E2E（§16 坑）| 走 v0.9.31 §16 四处清理 + E2E presence→absence 守门 |
| no-execution 边界 | Home 无下单按钮 + 中文禁词守门 |

## 10. 与既有批次的边界

- **复用** B027 价格快照 / dashboard `_aggregate_nav` / strategies sleeve / account + account_snapshot。
- **替换** 旧 quant dashboard Home（`/`）。
- **不动** B031-B036 后端（advisor/market/news/gateway）/ recommendations/risk/reports 页（B040-B042 重构）/ B026 banner。
- **为 B038/B039 预留** Home 占位段。

## 11. 后续批次（不在 B037 范围）

- **B038**（S4.B）：Home 整合 market context（填第三段 market 卡片）。
- **B039**（S4.C）：Home 整合 AI Advisor（填第二段 AI 一句话 + 引用 + disclaimer + INSUFFICIENT_GROUNDING 降级）。
- **B040-B043**：Reports / Recommendations / Risk Robinhood-style 重构 + AI 解释层。→ 里程碑 C（Layer 0.5）。
