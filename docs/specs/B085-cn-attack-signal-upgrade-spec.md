# B085 — cn_attack 信号升级 A/B（残差动量先行, 评审 P2）Spec

> 评审 §3.4 / 学术（Lin 2020 EFM；IRFA 2021 残差动量中国证据）。**B081 发现驱动**：cn_attack edge =
> 资本条件化（100万 +27.1% OOS，保留 B070 ~95%）——升级信号让 edge 更稳。**预研** `docs/research/next-batch-prep-cn-attack-signal-upgrade.md`。
> **first-look 低承诺 + 焊死禁扫参**：先做**证据最强的残差动量**一升级（评审建议先行），A/B vs 现纯保真基线；
> 显著提升（保真口径 OOS，非窗口落位）→ 推荐并入策略；否则 INCONCLUSIVE。剩三升级（SUE/剔涨停/2月规避）留后续。

## 0. 设计要点（焊死）

- **基线 = 现 cn_attack pure_momentum 纯保真口径**（B081 修真后：手数/停牌/退市/涨跌停开关默认开, partial=False）。
- **升级 = 残差动量**（idiosyncratic momentum）：裸动量对市场/风格 β 回归取**残差**的动量。★**回看窗/β 模型先验定死**
  （文献口径：滚动 12M 对市场收益回归取残差, 残差过去 N 月累计）——**禁扫参**（B081 partial 混入基线 + B084 挑窗的教训）。
- **A/B**：基线 vs +残差动量, 去偏 B070 PIT, pure_momentum+equal, **双本金**（10万/100万, B081 F005 容量口径必报）。
  照 B081 `b081_engine_fidelity_ab.py` A/B runner 模板（resumable + pickle 缓存）。
- **★数字变差诚实**：残差动量若在保真口径下**不提升**（同 B083 PEAD / B084 sub-window 教训——独立验收会抓过度归因）→ INCONCLUSIVE。
- **零回归**：cn_attack 产品码（signal/engine/precompute）**字节不变**——升级是**新研究口径的 A/B 脚本**，不改产品默认。

## 1. 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| A/B 对照 runner | B081 `scripts/research/b081_engine_fidelity_ab.py` | F001 基线 vs 残差动量 |
| cn_attack 引擎/信号/宇宙 | `trade/backtest|strategies/cn_attack_momentum_quality/` + B070 PIT | 基线 + 残差 signal |
| 指标 / WF / CPCV | B070/us_quality metrics | F001 |
| trial 登记 | B080/B083/B084 data-migration 模式 | F002 |

## 2. Feature 拆解（2：1 generator + 1 codex）

### F001 (g) — 残差动量 A/B（基线 vs +残差, 双本金, 分窗口）
- 残差动量 signal（先验窗, 禁扫参）；A/B vs 现纯保真基线, 去偏 B070 PIT；full + WF 70/30 CAGR/Sharpe/MaxDD/OOS + 双本金 + **分子窗损耗**（B084 教训：别年度聚合掩盖）+ **turnover**（B084 S2 教训：量化换手）。
- 报告 `docs/test-reports/B085-residual-momentum-ab.md` + trial_registry 登记（DSR N）。裁定 GO（保真 OOS 显著提升非窗口落位）/ INCONCLUSIVE。
- **★零回归守门**：cn_attack 产品码字节不变（A/B 是研究脚本）。Gates: mypy trade + 根 ruff + root pytest（触 trade/ 读取路径）+ backend 若触。

### F002 (codex) — 独立验收 + signoff
- Codex 独立：残差动量数字从零重实现抽验（不 import 我方脚本）；β 回归/残差口径核实；参数无扫参（grep）；**分子窗损耗 + turnover 口径核实**（B084 S1/S2 教训直接适用）；OOS 提升是否窗口落位（B070/B084 教训）；双本金容量；零回归（cn_attack 产品码字节不变）。signoff `docs/test-reports/B085-...-signoff.md`；GO/INCONCLUSIVE 确认。

## 3. 验收（通用段）
- Gates：mypy trade + backend / 根 ruff / root pytest 全量（触 trade/ 读取）/ 单测（残差动量计算 + 分窗口 + turnover）/ CI 全绿。
- 诚实：first-look 证据一测；残差动量若不提升 = INCONCLUSIVE 合法；OOS 提升须排窗口落位；分子窗损耗 + turnover 显式（B084 教训）。零回归 cn_attack 产品码字节不变。
