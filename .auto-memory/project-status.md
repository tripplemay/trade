---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B110 纯 E/P first-look ✅ done — ★最终裁定 `NO-GO`（用户 2026-07-21 裁定）**。**更正了 F004 原裁定 `INCONCLUSIVE_COVERAGE_LIMITED`**；原 signoff 保留不改写作证据链（已加作废横幅）。更正论证：`docs/test-reports/B110-F004-adjudication-correction-2026-07-21.md`。
- **操作含义**：不值得继续投入 handoff 剩余 9 道 gate；**不改 `DATA_NO_GO`**；★**不等于「A 股价值因子无效」**——规模中性未建 → size-adjusted 残值未测，而建它正是 handoff §4.6 缺失项（循环依赖，下轮 planning 须显式定价）。
- **★★更正三依据**（5 路独立复核，两路零 import 被测代码）：(1) **D1 空转**——signoff 裁定表漏了 `vs B-wide` 列，主口径 `+0.9606%` / `−0.7619%` **两端都 ≤1.0% 线**，B-scored 侧已是歧义带**乐观端**；evaluator 只验触发条件、未验是否改变裁定。(2) **NO-GO 是 OR 结构**——第二析取项 Q4(14.28%)>Q5(12.75%) 在 **4 变体×2 基准 8/8 全成立**，D1/D6 动不了；D6 只挑战第一析取项却被外溢到整个析取式。(3) ★**附录 D8 已锁死**「顶层组不是最优 → 照字面执行、**不因统计不显著放宽**」，signoff 中 `D8` 仅在「D1-D8」写法出现一次、**从未作为规则引用**，反把漏读记成「框架缺优先级」(S1)。另 spec §2 专条「IC 高而多头腿无超额 = NO-GO 而非 INCONCLUSIVE」实质命中（`a_long_ann=−0.3237%`）。
- **★★决策级新发现：主判据正号 100% 来自波动率，不来自选股。** Q5 月度均值 **1.2346% < 基准 1.2616%**，只是 σ 6.84% vs 8.16%、复利拖累少 1.2843pp。**保持均值缩放到基准波动率 → 超额变 −0.3492pp。** 几何 +0.96% 与算术 −0.32% **符号相反**（D2 本已要求算术并排，signoff 裁定表未并排）。降波不需要 E/P 就能买到。
- **★★F004 三处证据强度缺陷（用户裁定：记缺陷+沉淀，不重做）**：(1)「240/240 R2 对拍 MATCH」**同义反复**——抽样池 `ep` 非空 ⟺ R2 已全 MATCH，BREAK 按构造抽不到（被排除池随机 400 条 BREAK=78）；★**正是附录 §4 明令警惕的 B109 自欺形态，原样搬到替代校验上**。(2) 漏斗闭合断言 `(a−b)+(b−c)+(c−d)+d≡a` **代数恒真**，捏造数字也 True，真判据 `funnel_closes()` 从未跑（补验 144/144 无误）。(3) 三档 stub 敏感带**无独立留痕**，而它恰是驱动 D6 的输入。
- **★可信度分层**：**统计层**已被两路零-import 独立复算逐位证实；**数据层**（PIT TTM 正确性、`total_mv` 的 PIT 性、复权/退市终值构造、宇宙幸存者偏差）**仍只有 F004 单方证据且半数检查无鉴别力**——后续引用须保留此标注。
- **B110 实测保留项**：144 月覆盖合并 90.18%/中位 90.54%/最差 71.69%（2015 股灾停牌）、R1=0、`period_not_fetched=0`、`fwd_missing=0`；SE 3.15%、t 0.30、CI95 含 0；等价式为 Decimal 下代数恒等式**不得称交叉验证**，真校验 R1+R2（R2 断裂 7,949 已 fail-closed）；F002 已修 Tushare 空响应/整页边界截断（曾致 2022 年 `COMPONENT_MISSING` 11561 → 修复后 4）。
- **B109 PIT 数据层 ✅ done**：10 道 gate 只 G4 完全通过，G1/G3b/G5/G7/G8/G9 未动；交付的是 research-grade 脚本不是可运维数据层。**B108 巨潮 parser ⏹ 转向**（F003=superseded，硬门从未通过）。**B107–B074 ✅**。

## 接续 / 待决策
- **B110 已收口，不自动推进后续 gate。** 若将来重开，前置是**规模中性**（handoff §4.6），且须先解决上述循环依赖。
- `framework/proposed-learnings.md` 新增 **B110 六条待确认**：条款触发≠裁定改变（含不对称性自检）／OR 结构下敏感性只挑战对应析取项／evaluator 漏读已有规则记成框架缺口／一致率必须报分母筛选逻辑+禁恒真断言／「保守」须限定对数据还是对资本／几何年化混入降波须与算术并排。累计 40+ 条待确认。
- **B109 遗留缺陷**（附录 §7）：`panel_cli.py:99` 用 `fetch_single_checked` 拉 `stock_basic`，对空响应零防护（命中则宇宙退化为只剩 338 只退市名）；`universe.py:69` 静默丢弃畸形行。
- **可复现性缺口**：`docs/audits/B110-F002-monthly-funnel.csv` 被 `.gitignore` 的 `*.csv` 拦截却被列为签收证据；`git status --short` 遗漏检查对 gitignored 文件静默通过。
- Tushare token 建议轮换（用户曾明文提供，未执行）；backlog：residual-engine（B100 INCONCLUSIVE）+ B106-S3。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉教训）——本批次的裁定更正即此纪律的直接产物。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**A 股 PIT 禁**：latest-wins、法定截止日冒充公告日、流通市值代总市值、当前股本回填历史、只拉 `list_status=L`。
- 冻结再验证 pipeline 永不 validated；golden 只进测试 fixture seam；smart-money first-look 全部 research-only（0 产品码）。**`DATA_NO_GO` 保持不变。**
- B108 方法纪律：最终测量须在**全新 seed** 的 holdout 上；Generator 不得抽评测样本；**被规则挡住不等于被验证过**；每轮修复后必须重审跨模块交互。

## Framework / 环境
- Framework 最新：P5-F2（c5694f7）、v0.9.55（f67332e）、v0.9.53（B077 §36/§37）。
- 本机 `python3`=3.9 不可用，一律 `.venv/bin/python`；ruff 须 `python -m ruff check .`；scipy 未装；`tushare` 1.4.29 已装。生产活面 `https://trade.guangai.ai`，真 VM `34.180.93.185`（本批次未做 L2）。
