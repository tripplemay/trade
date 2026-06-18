# B068 — A股 进攻策略 宽宇宙重验 + 波动率倒数加权对比（research-only 验证）Spec

**批次定位：** A股 进攻策略的**研究验证批**（接 B066 引擎之后，解 P1 留白）。在**生产宽宇宙**上重跑 cn_attack，并把**权重方案**作为新对比维度（等权 vs 波动率倒数加权），用 walk-forward 样本外回答三个 B066 留下的开放问题。**纯 research/回测，不改 B067 实盘 advisory surface。**

**来源：** 2026-06-18 用户讨论——B067 上线后发现等权配置，要求以策略分析师角度评判权重机制 + 定本批验证。

---

## 1. 要回答的三个问题（B066 P1 的留白）

| # | 问题 | B066 为何没答 | 本批怎么答 |
|---|---|---|---|
| Q1 | **质量到底加不加值？**（质量+动量 vs 纯动量）| 本地种子宇宙 43 股全通质量门槛 → 两变体选股完全等值，分不出 | 在**宽宇宙**（top 200-300 PIT）上跑，质量门槛才有筛选空间 → 两变体分化 |
| Q2 | **波动率倒数加权能否驯服 OOS 动量崩盘？**（等权 vs 1/σ 加权）| B066 只有等权一种 | 加权重维度对比；理论上风险管理动量(Barroso-Santa-Clara/Daniel-Moskowitz)压崩盘 |
| Q3 | **更长/更干净的 OOS 表现** | B066 OOS = 2025H2 一段动量逆转 | 宽宇宙 + 更长 walk-forward 段，看是否仍脆弱 |

**P1.1 结论 = 研究判定**：哪个（因子 × 权重）配置在 A股 宽宇宙上样本外最稳；据此再定是否调整 B067 实盘 advisory 的默认配置（本批**不改** surface，只验证）。

---

## 2. 分析师立场（焊进设计，诚实约束）

- **等权是稳健基线，不是缺陷**：DeMiguel(2009) 1/N 在估计误差大/历史短场景难被优化打败；A股 正是此场景。**本批保留等权做对照基线**。
- **唯一值得测的权重优化 = 波动率倒数加权**（风险控制非收益预测，低过拟合；精准打 B066 观察到的动量崩盘弱点）。**动量/打分加权明确排除**（堆高崩盘风险 + 最 overfit）；MVO/最小方差排除（OOS 不稳）；组合层波动目标留后续 overlay（带择时，与纯进攻 P1 冲突）。
- **数据窥探纪律**：本批维度 = **2 因子 × 2 权重 = 4 配置**，**退出固定 momentum_decay 基线**（不再乘 3，避免变体爆炸）。walk-forward 样本外验证，**全配置诚实披露，不 cherry-pick in-sample winner**（B066 §29 红旗体系沿用）。
- **诚实出口**：若宽宇宙建不起来（akshare 全市场列表端点 VM 不可达），本批诚实报告「宽宇宙未达成，Q1 质量 A/B 仍未答」=有效 NO-GO（不强凑）。

---

## 3. 复用清单 + 必须新写（本会话已核 B066/B065 源码）

**复用：**
| 资产 | 位置 | 用法 |
|---|---|---|
| cn_attack 引擎 | `trade/strategies/cn_attack_momentum_quality/`（signal/factors/construction/parameters）| 加权重维度参数 |
| 等权构造 | `construction.py`（`build_cn_portfolio` L95，`equal_weight = 1.0/len(candidates)` L132，单票 cap）| 加 `weighting_scheme` 分支 |
| 波动率计算 | `us_quality_momentum/factors.py`（`low_vol_score` L189，trailing 窗口 vol）| 复用算 per-name σ 供 1/σ 加权 |
| 回测引擎 + 多变体报告 | `trade/backtest/cn_attack_momentum_quality/engine.py`（`run_cn_attack_backtest`）+ B066 6 变体对比报告 + §29 红旗 | 扩权重维度 |
| 宽 PIT universe builder | `workbench_api/data_refresh/cn_universe.py`（`point_in_time_top_n` L226，`build_cn_universe` L361，`discover_ashare_superset` best-effort，`CN_UNIVERSE_SEED` 43）| **实建宽 superset**（B065 因 SSL 降级到 seed 43）|
| B050 回测分发 | `worker.py _DISPATCH` | 复用（参数 sweep，非新 strategy_id）|

**必须新写/改：**
1. **宽 A股 universe 实建**：B065 `discover_ashare_superset`（全市场列表 stock_zh_a_spot_em/stock_info_a_code_name）本地 SSL 失败 → 降级 seed 43。本批 **§23 实跑验 VM 上全市场列表端点可达性**（仿 B062/B064 找到 sina/baidu host 可达的先例）；可达 → 建 top 200-300 PIT 宽宇宙；不可达 → 诚实 NO-GO（Q1 未答）。
2. **波动率倒数加权变体**：`construction.py` 加 `weighting_scheme ∈ {equal, inverse_vol}`；`inverse_vol`=weight_i ∝ 1/σ_i（trailing vol，复用 low_vol 计算），归一化后套同样单票 cap + cash buffer。`CnAttackParameters` 加 `weighting_scheme` 字段（默认 equal=向后兼容 B066/B067）。
3. **权重维度进多变体对比**：回测对比扩为 2 因子 × 2 权重 = 4 配置（退出固定 momentum_decay），walk-forward IS/OOS + vs 沪深300 + §29 红旗。

---

## 4. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — 宽 A股 universe 实建（§23 全市场列表端点 + top 200-300 PIT）（executor: generator）

1. **§23 前置**：VM 实跑验 akshare 全市场 A股 列表端点（候选 `stock_zh_a_spot_em` / `stock_info_a_code_name` / sina/baidu 等价；B065 本地 SSL 挂，VM 可能可达如 B062/B064 先例）。
2. 可达 → `discover_ashare_superset` 产宽 superset（数百只）→ `build_cn_universe` 写 `cn_pit_universe.csv`（top 200-300 PIT，ST 排除，无未来泄漏）。
3. 不可达/不稳 → **诚实降级 + 报告标注**（宽宇宙未达成，沿用 seed，Q1 仍未答）。

**Acceptance（§29 实测）：** §23 端点可达性结论（贴真返回行数）；宽宇宙建成则 `cn_pit_universe.csv` 含数百名 PIT 成员（贴样本日成员数）；US 零回归。Gates：backend+trade pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — 波动率倒数加权变体（construction `weighting_scheme`）（executor: generator）

1. `construction.py` 加 `weighting_scheme` 分支：`equal`（现状 1/N，默认）/ `inverse_vol`（weight_i ∝ 1/σ_i，σ 复用 low_vol trailing 窗口；缺 σ 名退化等权或剔除，诚实处理）。
2. 归一化 → 同样单票 cap → cash buffer（与等权同后处理）。
3. `CnAttackParameters` 加 `weighting_scheme`（默认 `equal`，**B066/B067 向后兼容零回归**）。
4. PIT/as_of 安全（σ 只用 ≤as_of 数据，无泄漏）。

**Acceptance：** inverse_vol 变体产**不同于等权**的权重（高波动票权重更低，可验）；σ 计算 PIT 无泄漏；equal 默认不变（B066/B067 回归）；mypy trade。Gates 同 F001。

### F003 — 4 配置宽宇宙回测 + 对比报告 + walk-forward（executor: generator）

1. 回测对比扩为 **2 因子（质量+动量/纯动量）× 2 权重（等权/波动倒数）= 4 配置**（退出固定 momentum_decay 基线）。
2. 在宽宇宙上跑（F001 建成）；walk-forward IS/OOS 段对比 + vs 沪深300 + 真 A股 成本（沿用 B066 方向化成本）。
3. **对比报告（双语）回答 Q1/Q2/Q3**：质量 vs 纯动量分化了吗（Q1）；波动倒数 vs 等权 OOS 崩盘改善了吗（Q2）；宽宇宙更长 OOS 是否仍脆弱（Q3）。
4. **§29 红旗体系**沿用：no_activity / 同族 toggle 失效 / 过拟合（IS≠OOS winner）/ 夏普离谱；**全 4 配置诚实披露不 cherry-pick**。

**Acceptance：** 4 配置各产非退化且可对比的 IS/OOS 指标（贴真数字）；报告明确回答 Q1/Q2/Q3 + 过拟合红旗标注。Gates：backend pytest + ruff 目录上下文 + mypy（若前端展示则 frontend 门禁）。

### F004 — Codex 回测验证 + 研究判定 + signoff（executor: codex）

**真数据批次——signoff 必含实测证据硬段（§29）：**
- L1 全门禁（backend+trade mypy+ruff 目录上下文）。
- **L2 真机实测（VM，贴真返回）：**
  - F001 宽宇宙真建（成员数 / §23 端点可达结论）**或**诚实 NO-GO。
  - 4 配置回测真数字（IS/OOS CAGR/Sharpe/MaxDD/换手 各异且非退化）。
  - **Q1 真答**：宽宇宙下 质量+动量 vs 纯动量 是否分化、谁 OOS 更优（贴对比）。
  - **Q2 真答**：波动倒数加权 vs 等权 的 OOS 崩盘/回撤/夏普对比（贴数字）。
  - **Q3**：更长 OOS 是否仍逆转。
  - 过拟合红旗核（IS≠OOS winner 须存疑，不 cherry-pick）；研究态/no-broker/no 收益预测；B066/B067 引擎+surface 零回归（默认 equal 不变）；HEAD≡prod；S1 全量 cross-source 可顺带补（VM 已可达）。
- **研究判定**：(a) 质量是否加值 (b) 波动倒数是否值得换 (c) 据此是否建议调 B067 实盘默认配置（本批不改，给建议）。signoff 实测证据硬段逐条贴真观测。

---

## 5. 状态流转 + 风险

- 混合批次：`planning → building(F001→F002→F003) → verifying(F004) → done`。
- **风险与缓解：**
  - **宽宇宙端点 VM 不可达**（最大未知，§23）→ 实跑验，不可达诚实 NO-GO（Q1 仍未答，不强凑）。
  - **数据窥探**（多配置）→ 限 4 配置（退出固定）+ walk-forward OOS + 全披露不 cherry-pick。
  - **波动倒数估计噪声** → σ 比收益稳健，低过拟合；缺 σ 名诚实降级。
  - **误碰 B067 实盘** → 本批纯回测，`weighting_scheme` 默认 equal，surface/advisory 零改动。

## 6. 不变量清单（Codex 回归核）

1. B067 实盘 advisory surface / B066 引擎默认行为零回归（`weighting_scheme` 默认 equal）。
2. Master/regime/其它策略/lookup 零回归。
3. research-only / no-broker / no 收益预测 / 不碰 live（本批不改 surface、不上实盘配置）。
4. §12.10.2 / trade 离线 / §23 端点须实跑 / ruff 目录上下文 / mypy CI-exact。
5. US/A股 既有数据零回归（宽宇宙是新增 superset，不改 US）。
