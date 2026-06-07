# 项目进度复盘 + 里程碑 C 用户交易闭环（2026-06-07）

> **作者：** Planner（与用户复盘讨论后撰写）。
> **目的：** 对照路线图盘点已实现/未实现；把里程碑 C 的完成标准**正式扩展为「用户交易闭环可用」**（2026-06-07 用户拍板）。
> **配套：** `docs/product/implementation-path-2026-05.md`（已同步 §3/§6）+ `positioning-2026-05.md` + `user-personas-and-journeys-2026-05.md` §2/§3。

---

## 1. 分层与里程碑（对照基准）

| 层 | 定义 | 里程碑 | 状态 |
|---|---|---|---|
| Layer 0 | synthetic fixture 跑通架构（B001–B025）| — | ✅ |
| Layer 1 | 真实数据落地，回测/评分可信 | **A**（Phase 1）| ✅ 达成 |
| Layer 1.5 | AI 叠加 quant，带引用、永无收益预测 | **B**（Phase 2）| ✅ 达成 |
| **Layer 0.5 完整交付** | 每日 Home 高频可用 + UI 简化 + **用户交易闭环** | **C**（Phase 3 + 真实评分基础）| 🔨 进行中 |

---

## 2. 已实现 ✅

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 0 | B026 防误用 banner（Layer 1 后按 §16 退役，使命完成）| ✅ |
| Phase 1（里程碑 A）| 真实数据 B027–B030（Tiingo 价格 + SEC EDGAR 财报 + 全 sleeve 真数据切换）| ✅ |
| Phase 2（里程碑 B）| AI+News B031–B036（LLM gateway + 红队 safety gate + news + market context + AI advisor MVP）| ✅ |
| Phase 3 前段 | B037 Home 三段 / B038 market / B039 AI disclaimer / B040 Reports Robinhood / B041 Rec Robinhood | ✅ |
| 真实评分基础（路线图外插入）| B044 评分闭环 + B045 真数据 pipeline（3/4 sleeve 真实评分）| ✅ |
| Ops 硬化 | B037-OPS1 timer 自动接线 / B045-OPS1 trade wheel 部署可靠性 | ✅ / 🔨 |

---

## 3. 未实现 ❌ + 原因

| 缺口 | 状态 | 原因 / 依赖 |
|---|---|---|
| **B046 regime reconcile + account current_weight** | 已规划未做 | **current_weight 是交易闭环的关键拼图**（无它则 target vs current diff 算不准）|
| **B042 Risk Panel 微调** | 未做 | Phase 3 主线最后一块 UI |
| **B043 AI 解释层（"为什么这样建议/这个数字"）** | 未做 | 依赖真实评分齐备（B044+B045+B046）|
| **生产 recommendation→ticket 真实路径冒烟** | backlog BL-B023-S1 | 交易闭环的端到端验证（用真实评分而非占位/defensive）|
| **HK-China sleeve（Master 10%）** | by-design stub | 无策略实现（BL-B011-S2 / Phase 4）；当前 defensive 停泊 |

---

## 4. ⚠️ 核心发现：路线图低估了「真实评分」

**「真实数据」≠「真实评分接进线上推荐」。**

- 里程碑 A 完成条件写「全 sleeve 真数据 → Master target 可作真实参考」。
- 但 B030 真数据**只喂进了回测**；线上 `/api/recommendations/current` **一直是 equal-weight 占位**——真实 Master 评分从没接进推荐接口。
- 这个 gap 直到 Phase 3 做 B041（Rec UI）才被发现（我们在给占位数字做 Robinhood 化）。
- → 临时插入 **B044/B045/B046** 三批补基础；代价是 Phase 3 比原 7 批多 ~4 批、里程碑 C 后推。

**这是规划盲点的暴露，非失误。** 现已补救（B044/B045 已让 3/4 sleeve 线上真实评分）。**经验沉淀：今后「真实评分 wired into 线上推荐 + 交易闭环」必须是显式可交付，不能假设真数据=可交易。**

---

## 5. 里程碑 C 达成后的用户体验

### 5.1 核心定位（硬边界）

**系统永不下单、不连券商、不自动执行。** 角色 = 投资决策大脑助手：给方向 + 数据 + 解释；**决策权和执行权 100% 在用户手上**；**永无收益预测数字**。

### 5.2 日常（每天，高频扫一眼）

- **0–5 秒**：Home 顶部真实 NAV + Day P&L + 状态灯。绿灯 = 无需动作（90% 的日子）。
- **5–30 秒**：AI Advisor 一句话建议（带 📎 quant signal + news 引用 + ⚠️ 研究参考非预测 disclaimer）+ 今日市场新闻 + market context + 4 sleeve 表现。
- **AI 无调仓触发权**：仅出文案；触发调仓的是季度节奏 / kill-switch 规则。

### 5.3 季度调仓日（一年 4 次，深度使用）

Recommendations 页 → target positions（Robinhood 大数字 + 颜色 + 中文 tooltip + "为什么这样建议"）→ target vs current diff → gate checks + wash-sale。

---

## 6. 🔑 用户交易闭环（里程碑 C 新增完成标准，2026-06-07 用户拍板）

**「按系统指示交易」= 系统出可执行作业单，用户手动在自己 IBKR 下单，再录回结果。系统全程不碰钱。**

完整闭环（B023 manual-execution，已建框架）：

```
Recommendations  →  diff       →  order ticket   →  用户手动下单  →  fills   →  reconcile  →  journal
(真实目标权重      (target vs     (Markdown 作业单    (自己的 IBKR)    (录成交)   (计划 vs    (整笔留痕)
 B044/B045)         current        双语+disclaimer)                            实际对账)
                    B046)
```

1. **diff**：系统对比真实目标 vs 当前持仓 → 「卖 X 股 A / 买 Y 股 B」。
2. **order ticket**：导出 Markdown 作业单（双语免责声明）—— **这就是"系统的指示"**。
3. **手动下单**：用户照作业单在自己券商**亲手**提交（系统无 broker SDK / 无下单按钮）。
4. **fills**：把实际成交录回系统（支持 3 种 broker CSV）。
5. **reconcile**：核对计划 vs 实际，标偏差。
6. **journal**：整笔调仓存档，可复盘。

---

## 7. 里程碑 C 重定义（完成标准）

**原标准**：「Phase 3 全 7 batch；每日 Home 高频可用 + UI 简化」。

**新标准（2026-06-07 用户拍板，加「用户交易闭环」）：**

里程碑 C = 以下全部达成：
1. ✅ 每日 Home 高频可用（真实 NAV/Day P&L + AI advisor + news/market + sleeve）
2. ✅ Reports/Rec Robinhood 化（B040/B041）
3. ⏳ **真实评分接进线上推荐**（B044/B045 done；B046 current_weight 收口）
4. ⏳ **B042 Risk UI + B043 AI 解释层**
5. ⏳ **交易安全/风控/合规层真实化**（2026-06-07 核查新增，F011 根因批次 B048）：kill-switch gate（去硬编码 pass）+ Risk Panel per-sleeve DD（去镜像占位）+ risk_panel mark-to-market + wash-sale 实现。**安全机制不能假，是交易闭环可信前提**
6. ⏳ **用户交易闭环端到端可用**：真实目标 + 真实 current + 真实安全层 → 准确 diff → ticket → 手动下单 → fills → reconcile → journal，**生产冒烟**（BL-B023-S1）
7. ⏳ **HK-China 10% 实现**（2026-06-07 用户确认）：BL-B011-S2 → Master 4/4 真实
8. ⏳ **回测页接真实引擎**（2026-06-07 用户确认）：B047 → 去合成 stub（架构撞 §12.10.2 需先定）

---

## 8. 到里程碑 C 的剩余工作序列（建议）

| order | 批次 | 作用 | 备注 |
|---|---|---|---|
| ✅ | B045-OPS1 | trade wheel 部署可靠性（S4 resolved）| 基础设施稳定 |
| **1（进行中）** | **B046** | execution diff 改 mark-to-market + current_weight + regime reconcile | **🔑 让 ticket diff 真实可交易** |
| 2 | **B048（F011 根因）** | 真实 per-sleeve NAV → kill-switch gate/risk panel/wash-sale 真实化 | **🔑 安全/风控层变真（闭环可信前提）** |
| 3 | **BL-B023-S1** 交易闭环冒烟 | 真实 diff + 真实安全层 → ticket → fills → reconcile 生产验证 | **🔑 闭环可用确证** |
| 4 | **BL-B011-S2** HK-China 实现 | satellite 策略落地 → Master 4/4 真实 | Master 真实度 |
| 5 | B042 + **BL-B023-S2** | Risk Panel 微调 + kill-switch UI 演练（在真风控数据上）| 体验完整 |
| 6 | **B047** 回测页接真实引擎 | 合成 stub → trade 真实引擎（撞 §12.10.2，架构需先定）| 回测可信 |
| — | B043 | AI 解释层（依赖真实评分齐）| 「为什么」可信 |

**关键洞察**：交易闭环的机械流程（B023 ticket→fills→reconcile→journal）**已经建好**；缺的是**喂给它真实的目标权重（B044/B045 ✓）+ 真实的当前权重（B046）**，再做一次**真实数据的端到端生产冒烟**确证。所以「用户交易闭环」离达成不远——**B046 是最关键的那块拼图**。

---

## 9. 其他方向调整建议

- **ops/infra 硬化**：「trade/ 入 venv」已连产 3 个部署问题 + VM disk 82%→84% 爬升 + 一次主机挂死。B045-OPS1 修一点，但 disk + 部署可靠性值得一次集中盘点。
- **路线图细节漂移记一笔**：数据 provider 实际 Tiingo（路线图写 Polygon）；不影响层级目标，文档可顺手更新。
- **里程碑 A 措辞修订**：A 的「Master target 可作真实参考」应澄清为「真数据进回测」，真实评分进线上推荐归入里程碑 C（已在 §4 沉淀）。
