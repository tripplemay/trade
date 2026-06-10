# 产品整体复盘（2026-06-10）

> **作者：** Planner（用户 2026-06-10 指派「做一次产品整体复盘」）。
> **触发：** 路线图明确批次全部完成——里程碑 C 达成（B049）+ 回测分发缺陷修复（B050）+ AI 解释层（B043）。
> **目的：** 盘点产品当前能力全貌、能力边界、全部遗留项，给下一阶段方向一份决策菜单。
> **配套：** `positioning-2026-05.md` / `roadmap-2026-05.md` / `milestone-c-acceptance-retrospective-2026-06.md` / 两份保真度审查 / `progress-review-2026-06.md §9.1 覆盖矩阵`。

---

## 1. 产品一句话

**一个 research-only、no-broker 的 AI 投资顾问工作台**：用真实数据 + 真实量化策略（Master Portfolio 4 sleeve）为用户算出目标仓位，用 mark-to-market 算出可执行的调仓 diff，给出订单 ticket（止于导出，不自动下单），配真实风控安全层 + LLM「为什么」解释层。**用户按系统指示自己去券商执行。**

---

## 2. 能力全貌（当前态，全部真实引擎）

| 能力 | 状态 | 关键批次 |
|---|---|---|
| **真实数据管道** | ✅ Tiingo 价格 + SEC EDGAR 基本面 → 每日 data-refresh → 5 年深度（18463 行/37 symbol）| B045 / B047-OPS2 |
| **Master Portfolio 4/4 真实评分** | ✅ momentum 40% / risk_parity 30% / us_quality 20% / hk_china 10%，data_source=real，0 stub | B044 / BL-B011-S2 |
| **推荐目标仓位** | ✅ 真实评分权重（非等权占位），20 positions，per-position grounded rationale | B044 / B046 / B043 |
| **交易闭环（研究态）** | ✅ 真实 target − mark-to-market current → diff → ticket（双语）→ fills → reconcile → journal | B046 / BL-B023-S1 |
| **安全/风控层** | ✅ kill_switch（master DD vs 0.15 单一来源）/ per-sleeve DD / wash_sale，全真 mark-to-market | B048 |
| **回测引擎** | ✅ per-strategy 分发（momentum/risk_parity/us_quality/hk_china/master 各跑各的）+ 数据覆盖窗口 | B047 / B050 / B047-OPS2 |
| **投资报告** | ✅ canonical 每日真实业绩报告（Reports 页）| B047 / B047-OPS1 |
| **AI 解释层** | ✅ Recommendations/Backtest/Risk 的 grounded LLM「为什么」，no-AI 边界守住 | B043（复用 B031/B032/B036）|
| **全页面真实化** | ✅ 8/8 用户投资页面零合成/占位（里程碑 C 收口 gate）| B049 |
| **部署/运维** | ✅ VM + systemd（data-refresh/canonical/recommendations/advisor/risk-explanation timers + worker daemon），auto-wired 零 admin | B021/B047-OPS1/B048-OPS1 等 OPS 批 |
| **国际化** | ✅ en + zh-CN 双语 parity | B024 |
| **AI 基建** | ✅ LLM gateway（aigc，task→model 路由 + 月度成本护栏 $200）+ 安全 eval（红队 judge gate）| B031 / B032 |

**里程碑达成：** A（合成架构 B001-B025）→ B（云部署 + workbench B021-B023）→ **C（全真实引擎 + 交易闭环，2026-06-09 达成）**。约 50 个批次，零 P0 缺陷逃逸到长期生产。

---

## 3. 能力边界（产品有意为之，非缺陷）

| 边界 | 说明 |
|---|---|
| **research-only / no-broker** | 系统止于「订单 ticket + 导出」，不接券商、不自动下单。用户自己执行。 |
| **no-AI 硬边界** | LLM 只 explain/summarize/translate 真实输出；no 收益预测 / no 替代 quant / 必须可引用真实值。安全 eval CI gate 拦截。 |
| **单账户** | workbench 是单用户单账户工具，非多租户 SaaS。 |
| **季度调仓节奏** | Master 季度末 rebalance（quarter-end signal dates）。 |
| **regime sleeve 研究态** | B013/B014/B015 regime weight=0.0 未激活（诚实披露 research-state），未来 B013 批次。 |
| **定位锚点** | 详见 `positioning-2026-05.md`——「投资顾问」非「自动交易机器人」。 |

---

## 4. 遗留项全清单（系统盘点，按严重度）

> 来源：milestone-c-acceptance-retrospective + 两份审查 + B043 signoff。**均不阻断核心功能，无功能性遗留。**

| 严重度 | 遗留项 | 现状 | 建议 |
|---|---|---|---|
| **Medium** | VM disk 84%↑ | 持续爬升，无扩容/清理记录；满时易丢诊断日志 | 轻量 OPS 批：清日志/缓存或扩容 |
| ~~Low~~ | ~~home nav=0.0（空账户）~~ | **✅ 2026-06-10 B051 RESOLVED**：根因=nav.aggregate_nav 读空 `account` 表而非 UI 写的 `account_snapshot`（两表读写分裂）；B051 统一账户源后生产实证 nav=$51,004.50 真实 | B051 signoff |
| Low | valuation_basis=cost_degraded | price_history 不覆盖最新 snapshot 日；诚实标注已就位 | 监控，data-refresh 自愈 |
| Low | BL-B050-S1 backlog status | 内部工具页 status 编辑后恢复 open（已入需求池）| 建 status 列或显式移除字段 |
| 软关注 | risk-banner.spec CI flake | 本地 5/5，CI 偶发，与改动无关 | 加 waitFor 稳态或 quarantine |
| 软关注 | B043 S1：LLM outage 降级未演练 | 破坏性验证超授权边界 | staging 或授权窗口演练 fallback |

---

## 5. 复盘洞察（做对了什么）

1. **「真实化」分层推进 + 收口 gate**：Layer 0（合成架构）→ Layer 1（真数据/真引擎逐页切换）→ B049 穷举审计 gate 收口，避免「以为全真实、实则残留占位」（Reports 接开发签收语料的错配教训催生「审计看内容类别非只 grep」）。
2. **OPS 批次正交拆分**：部署/env 可靠性（B045-OPS1/B047-OPS1/B048-OPS1）一律拆独立批，功能批保持干净——沉淀 framework §12.11（deploy post-step assert）。
3. **诚实优于伪装**：cost_degraded 标注、stub/research-state 诚实披露、降级回退确定性占位——「annotate, don't fabricate」贯穿安全层与 AI 层。
4. **审查驱动发现孤立缺陷**：用户报「回测选任何策略都一样」→ 两次系统审查挖出 B050 + 防守 SGOV 100 倍超买 + backlog status——沉淀「装饰性控件反模式」（framework §17/§26）。系统真实化程度高，缺陷是孤立执行层缺口而非系统蔓延。
5. **AI 安全前置**：no-AI 边界 + 5 规则 prompt + sentinel 拒答 + references_valid + 成本护栏 + 红队 eval gate，让 B043 解释层复用而非重造安全。

---

## 6. 下一阶段方向（决策菜单）

路线图明确批次已走完，以下是候选方向（非互斥，可组合）：

### A. 加固现有（低风险，巩固）
- **disk OPS 轻量批**（处理 Medium 遗留）+ 扫尾 Low 遗留（home nav / backlog status / fallback 演练）。
- 价值：生产稳健性；成本低。

### B. Phase 4 长尾 alpha 研究（深化策略）
- BL-B013-D1 smoothed vol-target / BL-B013-D2 VIX tail hedge（均 low，research-only fixture-first）。
- regime sleeve 激活（B013，让 Master 5-sleeve）。
- 价值：策略深度/alpha；偏研究。

### C. 产品化 / 真实用户（扩边界，需产品决策）
- 多账户/多用户？paper-trading API 接入（半自动验证）？broker 接入（**会突破 no-broker 硬边界，需重新定位决策**）？
- 价值：从「工具」走向「产品」；但触及定位边界，须用户拍板。

### D. 体验 / 可观测性成熟化
- 监控/告警体系、用户引导、移动端、回测参数编辑器（B050 审查发现 parameters 字段 plumbed 未接 UI）。
- 价值：可用性/可运营性。

**Planner 建议**：当前产品「能力完整、真实可信」但仍是单用户研究工具。下一步取决于**目标**——若要走向真实使用，优先 A（加固）+ C 的产品决策讨论（定位是否扩到半自动/多用户）；若维持研究工具深化 alpha，走 B。建议先和用户明确**产品下一阶段目标**（自用研究深化 vs 走向真实用户/产品化），再定批次。

---

## 7. 结论

约 50 批次、三里程碑，构建出一个**端到端真实、研究态可信、AI 解释 grounded、安全边界清晰**的投资顾问工作台。路线图既定目标全部达成，无功能性遗留，仅少量低危基础设施/边角项。产品已到一个**自然里程碑节点**——下一步是方向选择题（加固 / 深化 alpha / 产品化扩边界），而非未完成的待办。建议下次先定产品下一阶段目标。
