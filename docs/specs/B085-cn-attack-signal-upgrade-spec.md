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

## ★2026-07-05 rescope（Planner, 前置筛结果 + 冻结边界驱动）

**前置筛（scripts/research/b085_residual_vs_raw_ic.py）实测：残差动量 edge 弱**——仅 borderline 改进裸动量
（delta t=1.98），残差绝对 IC 0.0108 < |IC|>0.03 GO 门槛。**完整引擎 A/B 需触及冻结的 cn_attack flagship
（signal.py 加变体），是永久硬边界**（AskUserQuestion 已问用户；用户 away → 按推荐 option 1 推进）。

**决定：F001 收窄为前置筛 first-look（残差 vs 裸动量 IC，裁定 INCONCLUSIVE 弱方向支持）；完整引擎 A/B
降级为 backlog 条件 follow-up**（`B0XX-residual-momentum-engine-ab`，待用户对触冻结 flagship 决策）。
理由：弱信号不值得为边际收益触冻结旗舰（研究纪律 + 硬边界尊重）。F002 相应验证前置筛（非引擎 A/B）。

## 2. Feature 拆解（rescoped：1 generator screen + 1 codex verify）

### F001 (g) — ✅ 残差 vs 裸动量 rank-IC 前置筛 first-look（**done**）
- 残差动量计算（scripts/research/b085_residual_momentum.py, 单因子 β 残差, 先验禁扫参, 单测锁隔离特质动量）。
- 前置筛（b085_residual_vs_raw_ic.py）：残差 vs 裸动量 forward-return 月度 rank-IC, 同窗公平, 无前视单测锁。
- 结果：残差 IC 0.0108(t=0.45) vs 裸 -0.0009; delta +0.0118 t=1.98(borderline)。**裁定 INCONCLUSIVE（弱但真实方向支持）**。
  报告 `docs/test-reports/B085-residual-vs-raw-ic-screen.md` + trial_registry 登记（migration 0040, DSR N）。零回归（纯研究脚本）。

### F002 (codex) — 独立验收 + signoff（验证**前置筛**）
- Codex 独立：残差动量 + IC 数字从零重实现抽验（不 import 我方脚本）；β/残差口径核实；参数无扫参（grep）；
  **前视核查**（signal≤t, forward>t）；IC 相对比较（残差 vs 裸）口径 + borderline t=1.98 诚实性；trial 幂等/N 正确；零回归。
  signoff `docs/test-reports/B085-...-signoff.md`；INCONCLUSIVE（弱支持）确认。
- **引擎 A/B 不在本批验收范围**（降级 backlog follow-up 待冻结决策）。

## 3. 验收（通用段）
- Gates：mypy trade + backend / 根 ruff / root pytest 全量（触 trade/ 读取）/ 单测（残差动量计算 + 分窗口 + turnover）/ CI 全绿。
- 诚实：first-look 证据一测；残差动量若不提升 = INCONCLUSIVE 合法；OOS 提升须排窗口落位；分子窗损耗 + turnover 显式（B084 教训）。零回归 cn_attack 产品码字节不变。
