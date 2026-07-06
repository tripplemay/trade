# B100 — 残差动量完整引擎 A/B（frozen cn_attack construction）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B100 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079-B099 先例）
> 说明：前一验收 agent 因 API 连接故障中途失败未提交裁定，本报告从头独立重做，不依赖任何残留。

---

## 0. 一句话结论

F001 交付的**残差动量完整引擎 A/B** 是一次**方法严谨、裁定诚实的 INCONCLUSIVE**。它在**冻结的 cn_attack
construction（`build_cn_portfolio`）上跑两遍，只差动量输入**（BASELINE=裸动量，VARIANT=B085 残差动量），
同宇宙/调仓日/skip/top_n/cap/等本金/成本。**残差不胜裸，边际 trailing**（Δ CAGR −1.33pp、Δ Sharpe
−0.032、turnover 近同），INCONCLUSIVE 是 B085 前置筛（残差 delta t=1.98 borderline）后**预期且合法**的结果。
**★命门 1（BLOCKING）：research-only 不触冻结 flagship——整批 `trade/` 产品码 0 行改动**，经独立复算逐位一致，
残差 β PIT 无前视经手工核对坐实，CI 全绿，HEAD≡prod。**签收 PASS。**

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B100 = 残差动量完整引擎 A/B（research-only wrapper，B085 IC 前置筛明推的下一步引擎测）|
| F001（executor:generator） | 冻结引擎双臂 A/B → **INCONCLUSIVE**（残差边际 trailing）。commit `2579da5`（impl）/ `0daf6f6`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金 / 无 data_root 写）|
| 交付物 | `scripts/research/b100_residual_engine_ab.py`、`tests/unit/test_b100_residual_engine_ab.py`、`docs/test-reports/B100-residual-engine-ab.md`、`data/research/b070/b100_residual_engine_ab.json`（本机） |

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机数据缓存齐全（`data/research/b070/b081_prices_cache.pkl` = 169 MB 真实无幸存者偏 PIT 价格面板，
2018-01-02→2026-06-18，2051 dates × 1310 tickers），故**不是 fixture-only 验收，而是在真实 7 年面板上
独立重跑两臂 + 逐位重算指标 + 残差 β 手工核对**。独立复算脚本一次性运行后删除（未入交付）。

---

## 3. 逐项裁定

### ★命门 1（BLOCKING）— research-only 不触冻结 flagship：**PASS（清）**

- **整批 `trade/` 产品码 0 行改动（决定性）：** `git diff 4360264^..HEAD -- trade/` = **空**；
  `git diff 4360264^..HEAD -- trade/strategies/cn_attack_momentum_quality/ trade/backtest/cn_attack_momentum_quality/` = **空**。
  F001 impl commit `2579da5` 仅触 `docs/test-reports/ + scripts/research/ + tests/unit/`（696 insertions，3 文件）。
- **结构证（read-only 复用）：** 研究脚本 `from ...construction import build_cn_portfolio` / `from ...parameters import CnAttackParameters`
  纯 import 调用，**未把 residual factor_variant 加进生产 flagship**；生产 `signal.py / construction.py / parameters.py / size.py` 逐字节不变。
- **不 mark validated / 不触 data_root：** 报告结尾明标 *"No cn_attack product code modified … no data_root written; nothing marked validated"*；
  脚本只写 `docs/test-reports/` 与 `data/research/b070/`（研究输出），不写 `WORKBENCH_DATA_ROOT`。
- **无生产消费者：** `scripts/research/b100_*` 是独立研究模块，`.github/workflows` 无接线，无 CI 硬门自动消费。

> 命门 1 是本批最重的 BLOCKING 项。**冻结 flagship（OOS red-card）零改动**，research-only 边界坐实。

### ★命门 2 — 公平对照（等本金双臂 A/B + 残差无前视）：**PASS（1 benign soft-watch）**

- **唯一差 = 动量输入：** 两臂均调用同一 `run_arm(prices, <momentum>, reb_dates, …, _PARAMS)`，仅
  `raw_momentum` vs `residual_momentum` 不同；成本模型、`top_n=25`、cap、eligibility、调仓日**完全一致**。
  单测 `test_arms_differ_only_in_momentum_input` 锁：同动量 → **bit-identical** 权益曲线；换动量 → 曲线变。
- **等本金 / 双本金（B081 教训）：** 两臂各自独立权益簿、均 start=1.0、同一成本模型，无一臂借另一臂本金或杠杆优势。
- **窗口匹配（独立复跑证）：** 两臂均 **87 次调仓、同窗口 2019-04-30 → 2026-06-18、1730 个权益日**。
  面板自 2018-01-02 起，残差需 252+126+21≈399d 预热在 2019-04-30 已完全 warm，两臂**同日起跑**（无残差因预热更晚起跑导致的窗口不公）。
- **残差 β PIT 无前视（手工核对 + 未来变异）：** 抽 name=`000723.SZ` date=`2026-05-08`，用**严格过去 252d** 窗手算
  β=1.1210 → 手算残差 = 引擎残差到 1e-9（`residual_returns` 的 rolling β 确为 PIT）；把 t 之后价格 ×5 猛击，
  t 处残差**不变**（future-mutation invariant）。8 个 L1 单测另锁两条无前视不变量（信号对未来价格突变不敏感、
  仅 t-SKIP 之前数据可达）。裸动量 `.rolling(126).sum().shift(21)` 亦纯过去。**无前视坐实。**
- **成本/turnover 计入且正确：** `_turnover_and_cost` = Σ|Δw|，买付 commission+slippage、卖另付印花（A 股卖方）；
  单测锁首调仓全买无印花 / 轮动收卖方印花 / 无变动零成本，且**双臂用同一成本模型**。年化 turnover 10.61(裸) vs 10.73(残差) 近同。
- **soft-watch S1（scored-pool 计数差，benign）：** 残差臂因需 252d β 窗（裸仅 126d），86/87 调仓日 scored-pool
  计数略异（裸中位数 ~1253、残差 ~1234，中位差 19 ≈ 1.5%）。但**两臂 pool 均 ~1250 >> top_n=25**，被残差剔除的名字
  落在预热边界尾部、几乎不可能进动量 top-25 → 对选股影响可忽略，是残差信号定义的**内生特性非不公**；且变体 trailing，
  不构成任何掩盖。非缺陷。

### ★命门 3 — INCONCLUSIVE 与数字一致（独立逐位重算）：**PASS**

- **独立手算（几何 CAGR / Sharpe / MaxDD，非复用报告 helper）与报告逐位吻合：**

  | metric | BASELINE 独立算 | 报告 | VARIANT 独立算 | 报告 | Δ(V−B) |
  |---|---|---|---|---|---|
  | CAGR | **0.1719** | 0.172 | **0.1586** | 0.1587 | **−1.33pp** |
  | Sharpe | **0.640** | 0.64 | **0.608** | 0.608 | **−0.032** |
  | MaxDD | **−0.6210** | −0.621 | **−0.6114** | −0.6114 | +1.0pp |
  | ending(×start) | **3.1007** | 3.1007 | **2.8586** | 2.8586 | — |

- **裁定 INCONCLUSIVE 唯一正确：** 代码 verdict 逻辑 = GO 需 ΔCAGR≥+2% 且 ΔSharpe≥+0.15；NO-GO 需 ΔCAGR≤−3%
  且 ΔSharpe≤−0.1；此处 ΔCAGR=−1.3%（未达 −3%）→ 既非 GO 亦非 NO-GO → **INCONCLUSIVE**。措辞
  "does NOT materially beat (in fact marginally trails)" 与噪声级 Δ（单条 7 年路径，t~2 内）**匹配**。
- **诚实口径（无年聚合掩盖）：** year-by-year 显示残差仅 **2020 胜（+10.8pp）**，其余多数 trailing（最坏 2026 −9.8pp）；
  worst sub-window 残差在 quarter（−34.2 vs −33.3）、half-year（−44.4 vs −43.1）**略 worse** 且**如实披露未掩盖**（B084 教训）。
- **honest frame 引用经独立核对非编造：** 报告引 B085「残差 IC 0.0108 t=0.45；残差−裸 +0.0118 t=1.98 borderline」，
  与 `docs/test-reports/B085-residual-vs-raw-ic-screen.md`（L11/L13）**逐字一致**。
- **结论正确导向（verdict-gating，B069/B076）：** 结论明确 flagship **维持裸动量、不切残差**，
  「是否采纳 = 用户决策，非本批」——**不为用残差硬切一个并不更优的构造**。

### 命门 4 — 禁扫参 + 零回归 + L1 有牙 + CI + HEAD≡prod：**PASS**

- **禁扫参（grep 核）：** 研究脚本 + b085 + 测试 grep 无 `grid|sweep|optuna|tune|hyperparam|argmax(param)`；
  `top_n=25` / `max_position_weight` 均取 `CnAttackParameters` **冻结默认常量**（spec 的 top 20-30 / 单名 8% cap），
  非扫出；两臂、全期是全量报告非择优。**无过拟合。**
- **trial_registry：** research-only A/B 未注册 trial（与「不触 data_root / advisory-only」一致）；trial_registry 基础设施
  在 `workbench_api`（B080）存在，但研究 A/B 无生产落地预期，非违规。
- **零回归：** 产品码（`trade/` `workbench/`）0 文件改动（命门 1 已证）；无生产消费者。
- **L1 有牙：** 系统 venv（Python 3.11.15）独立复跑 `pytest tests/unit/test_b100_residual_engine_ab.py` = **8 passed**；
  ruff = **All checks passed**、mypy = **Success**。**变异检查**：把 `test_turnover_first_rebalance` 的 `assert turnover == 1.0`
  改 `== 2.0` → 该测 **FAILED**（`assert 1.0 == 2.0`）→ 断言有牙非空跑。
- **CI 绿（独立 gh 复核）：** `2579da5`（F001 impl）**Python CI = success + Workbench Backend CI = success**；
  `0daf6f6`（mark done）**Workbench Deploy = success**；最新 `c5694f7` Python CI + Prod Canary 亦 success。
- **HEAD≡prod：** 0 产品策略码改动 → 生产 flagship 与仓库 HEAD 逐字节等价（trivially，无产品码落地可部署）。

### 命门 5 — Workflow 对抗验证抽 1 复核：**PASS**

- generator 报「Workflow 3 子代理 build + 2 对抗验证 CONFIRMED（防前视/过拟合/双本金公平）」。我未止于抽查其记录，
  而是**独立复现**三项关键对抗——(a) 残差/裸信号对未来价格突变的不变性（无前视）；(b) 残差 β PIT 手工重算；
  (c) 两臂指标独立逐位重算。三项结论均与 generator 记录一致，且 (b)(c) 以**完整独立重算**超越了 journal 抽查。

---

## 4. 软观察（非阻断）

- **S1（scored-pool 计数差 ~1.5%）：** 残差臂因 252d β 窗比裸臂（126d）少 scored 少数预热边界名字（中位差 19/1250）。
  两臂均选 top-25 于 ~1250 名 pool，被剔除者在尾部不影响选股，是残差信号定义的内生差异非不公。若未来要给残差定论，
  可考虑对两臂强制 identical scored-pool（取交集）复核以彻底消歧。非本批缺陷。
- **S2（单条路径 t~2 内噪声）：** Δ CAGR −1.33pp 落在单条 7 年路径的噪声带内，INCONCLUSIVE 恰当；但这既不能
  证明残差劣于裸（可能只是这条路径），也不支持采纳。与 B085 前置筛（delta t=1.98 borderline）方向一致：edge 真实但边际。
- **S3（研究输出 json 本机 gitignored）：** `data/research/b070/b100_residual_engine_ab.json` 为本机复算产物（数据目录 gitignored），
  报告 md 已入 git 承载全部结论数字，可独立复现（脚本 + 缓存在本机齐）。非缺陷。

---

## 5. 最终裁定

| Feature | 裁定 |
|---|---|
| F001 — 残差动量完整引擎 A/B（INCONCLUSIVE，残差不胜裸/边际 trailing）| **PASS** |
| F002 — Codex 独立验收 + signoff | **PASS**（本报告）|

**全 PASS 2/2 → status=done。**

**含义：**
- 残差动量引擎 A/B = **INCONCLUSIVE**：在冻结 cn_attack 引擎上，残差动量**边际 trailing** 裸动量
  （Δ CAGR −1.33pp、Δ Sharpe −0.032、turnover 近同、worst sub-window 略 worse），**不支持把残差切入 flagship**。
- 与 B085 IC 前置筛（残差−裸 delta t=1.98 borderline）方向一致：残差 edge 真实但边际，全引擎测未能兑现为稳健改进——
  这是**预期且合法**的 INCONCLUSIVE（同 B083/B084）。
- **flagship 维持裸动量**（OOS red-card，冻结不变）；**是否采纳残差 = 用户决策，非本批**。research-only 边界全程未破。

---

## 6. 文件清单（本次验收产出/核对）

- 本 signoff：`docs/test-reports/B100-residual-momentum-engine-ab-signoff-2026-07-06.md`
- 核对：`docs/test-reports/B100-residual-engine-ab.md`（F001 报告）
- 核对：`scripts/research/b100_residual_engine_ab.py`（研究 A/B 引擎）、`scripts/research/b085_residual_momentum.py`（残差计算）
- 核对：`tests/unit/test_b100_residual_engine_ab.py`（8 单测，含 2 无前视不变量）
- 核对：`docs/test-reports/B085-residual-vs-raw-ic-screen.md`（honest frame 引用源）
- 独立复算数据：`data/research/b070/b100_residual_engine_ab.json`（gitignored 本机）+ `b081_prices_cache.pkl`（169 MB 真实面板）
