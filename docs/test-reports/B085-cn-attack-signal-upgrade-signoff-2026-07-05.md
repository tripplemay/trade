# B085 — cn_attack 信号升级（残差动量先行）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS → done。** F001（残差 vs 裸动量 rank-IC 前置筛 first-look，rescoped）+ F002（本独立验收）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B084 先例），与实现完全隔离，数字经**异路径从零重实现**逐位复算。
> **HEAD = `ad8e99d`；生产 release = `ad8e99d067cd5fa2fe205574dbb1d3e128f6b38e`**（current symlink 逐字符相等，2026-07-05 10:55 部署）。
> 被验收提交：`8e37948 / 03425ef / 2ef3b0d / 5b58f3b / 65871da / bd09e0f / ad8e99d`。

## 1. 验收结论表

| 验收项 | 裁定 | 证据 |
|---|---|---|
| **残差/IC 数字从零重实现抽验（不 import 我方脚本）** | **PASS** | 完全独立 pandas/numpy 重实现，51 月度点：残差 IC `0.0108`、裸 IC `-0.0009`、delta `0.0118`、delta_t `1.98`、resid_t `0.45`、raw_t `-0.04` —— **与报告/JSON 逐位吻合（4 位小数）** |
| **β/残差口径核实（PIT 无前视）** | **PASS** | 手工核对 `000001.SZ / 2020-11-23`：numpy β（仅 ≤t 的 252 行，末日=t）= pandas rolling β = `0.812397`；残差 `0.03343779` 两法一致；**扰动未来收益 β_t 不变 → 无前视证实** |
| **参数无扫参（禁扫参落实）** | **PASS** | 广谱 grep（optuna/argmax/best/grid/param_grid/itertools.product/window-loop/sweep/candidate）**零匹配**；仅 3 个先验硬编码常量 `LOOKBACK_BETA=252 / LOOKBACK_MOM=126 / SKIP=21` |
| **前视核查（signal≤t, forward>t）** | **PASS** | signal 用 `[t-21-126, t-21]` 累计（skip 后全 ≤t）；forward = `px.shift(-21)/px-1`（t→t+21 未来）；单测 `test_forward_return_is_strictly_future` + `test_raw_momentum_is_past_only` 锁；两窗无重叠 |
| **IC 相对比较口径 + borderline t=1.98 诚实性** | **PASS** | raw/residual **同窗同 skip**（唯一差 = β·市场扣除）→ 相对比较对幸存者偏差稳健；报告/trial metrics 明标「t=1.98 恰低于 2.0 = borderline 非铁证，别过度宣称」+ 绝对 IC 0.0108 < \|IC\|>0.03 GO 门槛 —— **无过度归因** |
| **trial 幂等 / N 正确 + 生产落地** | **PASS** | 生产 DB `alembic_version=0040_b085_residual_momentum_screen_trial`；B085 行 `bf-72732307519dec56 / cn_attack_residual_momentum_screen / INCONCLUSIVE` 已落；本地确定性 content-hash id **逐字符 = 生产 id**（幂等）；migration `if id not in existing` guard；`_N_TRIALS + len(B085_TRIALS)` lockstep（bootstrap 5 测过） |
| **零回归（cn_attack 产品码字节不变）** | **PASS** | `git diff 8e37948~1..ad8e99d -- cn_attack 引擎/策略/precompute` = **0 行**；全 range 改动 = 2 研究脚本 + 2 单测 + trial 登记基建（0040 / backfill_b085 / bootstrap +9 / _N_TRIALS +1）+ docs + 状态机 JSON |
| **CI 绿 + HEAD≡prod** | **PASS** | Python CI 绿（`65871da`，覆盖 scripts + 单测）；Backend CI + Frontend CI + Deploy 绿（`ad8e99d`）；current release symlink → `ad8e99d…`（=HEAD） |
| **rescope 偏离审计** | **PASS（合规缩窄）** | 见 §5 |
| **弱结论（INCONCLUSIVE 弱方向支持）合法性** | **PASS** | first-look 一测证据、裁定与数字一致且偏保守（B083/B084 先例） |

## 2. rank-IC 独立异路径复算（不 import 我方脚本）

从零 pandas/numpy 重实现（等权市场 = 横截面均值 → rolling(252) β=cov/var → 残差 → rolling(126).sum().shift(21) 残差动量；raw 同窗；forward=shift(-21)；月末 rank-IC）：

| 量 | 报告/生产 JSON | 独立复算 | 吻合 |
|---|---|---|---|
| n_months | 51 | 51 | ✅ |
| 残差 IC 均值 | 0.0108 | 0.0108 | ✅ |
| 裸 IC 均值 | −0.0009 | −0.0009 | ✅ |
| delta（残差−裸，配对） | +0.0118 | +0.0118 | ✅ |
| delta 配对 t | 1.98 | 1.98 | ✅ |
| 残差 IC t | 0.45 | 0.45 | ✅ |
| 裸 IC t | −0.04 | −0.04 | ✅ |

数据源 = B070 `b081_prices_cache.pkl`（1310 只票，2018-01..2026-06；窗 ≥2019-04-01）。**全部逐位吻合。**

## 3. 无前视 / PIT 证明（β 估计窗）

- **β 窗 PIT**：`rets[col].rolling(252)` 仅用 [t−251, t] 的收益，β_t 是**当期滚动回归**（用 ≤t 数据），非前视。手工核对 `000001.SZ / 2020-11-23`：窗内 252 行末日 == t，numpy(ddof=1) β = pandas β = `0.812397`，残差 `0.03343779` 两法一致。
- **反事实证明**：把 t 之后第 5 日的收益 ×2（扰动未来）→ β_t **完全不变** → β 不泄露未来。
- **signal ≤ t / forward > t 分离**：残差动量窗结束于 t−21（skip），forward = t→t+21 —— 两窗**无重叠**，无自相关污染（月度采样进一步去重叠 IC 膨胀）。

## 4. 禁扫参

`b085_residual_momentum.py` / `b085_residual_vs_raw_ic.py` / `trial_backfill_b085.py`：广谱 grep（optuna / argmax / argmin / best_ / grid_search / param_grid / itertools.product / for-window / for-lookback / sweep / candidate）**零匹配**。回看窗（β 252 / 动量 126 / skip 21）**先验文献口径定死**（Lin 2020 EFM / IRFA 2021 中国证据），trial_registry 仅登记这一 config（DSR N=+1），未夹带未登记候选窗。**禁扫参 = 落实。**

## 5. rescope 偏离审计（引擎 A/B → 前置筛 first-look）

**原 spec F001** = 残差动量 vs 纯保真基线的**完整引擎 A/B**（双本金/turnover/分子窗损耗）。**实际交付** = 残差 vs 裸动量 rank-IC **前置筛 first-look**，完整引擎 A/B 降级 backlog 条件 follow-up。

**审计结论：合规缩窄（PASS），非 scope-dodge。理由：**
1. **符合 first-look 纪律**：spec §0 自身即定「first-look 低承诺 + 弱信号 → INCONCLUSIVE」。廉价 IC 前置筛先于昂贵引擎回测 = 「弱信号不跑昂贵回测」的正确执行（B083/B084 同型先例）。前置筛已产真实证据（残差 > 裸 borderline），非空交付。
2. **尊重硬冻结边界**：完整引擎 A/B 需向**冻结的 cn_attack flagship**（signal.py）加 factor_variant（generator 于 `5b58f3b` 识别此设计张力），与 spec「零回归 cn_attack 产品码字节不变」直接冲突。缩窄避免为**边际弱信号**触永久硬边界 —— 保守方向，风险更低。
3. **披露如实**：rescope 写入 spec（新增 §2026-07-05 rescope 段）、F001 报告、commit message、handoff、trial metrics 五处透明记录；AskUserQuestion 已问用户 → away → 按推荐 option 1（不为弱信号触冻结）推进，路径有据。
4. **裁定保守**：INCONCLUSIVE（弱但真实方向支持），残差绝对 IC 0.0108 远低于 GO 门槛，未把 borderline 夸成 GO。

**软观察（非阻断）**：批次原「信号升级 A/B」headline 仅由前置筛部分兑现，完整引擎 A/B 留 backlog（`B0XX-residual-momentum-engine-ab`，待用户对触冻结 flagship 决策）—— 已正式改 spec + 立 backlog 条目，作为 first-look 批次可接受。

## 6. 其它软观察（非阻断，供后续批参考）

- **S1 — t-stat 用 ddof=0（总体 std）**：`_t_stat` 用 `np.std`（ddof=0）。以样本 std（ddof=1）复算 delta t = **1.96**（对方 1.98 略偏乐观 0.02）。但两者**均 <2.0 且同属 borderline**，报告结论「非铁证/别过度宣称」在两种口径下都成立 → 不影响裁定。建议后续严验批统一用 ddof=1。
- **S2 — 月度采样用日历月末**：`resample("ME").last().index` 取**日历月末**，非交易日的月末被 `if t not in prices.index` 跳过 → 87 个月仅采 51 点（丢 ~40%）。对 resid/raw **同 t 对称施加**，故相对比较（delta）公平，仅损统计功效。建议后续用「每月最后交易日」以增点。
- **S3 — 绝对 IC 带 b070 大盘宇宙幸存者偏差**：报告/trial 已 4 处诚实标注「相对比较稳健、绝对值谨慎」。first-look 合理，严验批须去偏。

## 7. 结论

**B085 cn_attack 信号升级（残差动量先行）2 features 全 PASS → done。**
残差动量 IC 经**独立异路径**从零重实现，51 月度点全部 4 位小数吻合；β 口径 PIT 无前视（手工核对 + 未来扰动反事实双证）；参数三先验常量无扫参；trial 生产落地实测（alembic=0040 + B085 INCONCLUSIVE 行 + 确定性 id 逐字幂等）+ 门禁全绿 + HEAD≡prod（`ad8e99d`）+ 零回归（cn_attack 产品码 0 行）。rescope（引擎 A/B → 前置筛 first-look）经审 = **合规缩窄**（first-look 纪律 + 尊重冻结硬边界 + 五处如实披露 + 保守裁定）。**INCONCLUSIVE（弱但真实方向支持）为与数字一致且偏保守的合法裁定。** 三项软观察（ddof / 月末采样 / 宇宙偏差）方向均与保守裁定同向 → 软观察非阻断，并入严验后续批。

> 评审路线图 P0–P2 收官：本批为评审 P2（cn_attack 信号升级）first-look。完整引擎 A/B 降级 backlog 条件 follow-up（待用户对触冻结 flagship 决策）。
