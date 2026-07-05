# B082 红利低波防守腿 — 独立验收 SIGNOFF（Evaluator，代 Codex）

**日期：** 2026-07-05（UTC）
**验收者：** 独立 Evaluator（无实现上下文，最高怀疑度；授权=用户 /goal + B079–B081 先例）
**HEAD backend = 生产 release = `c53375f`**（其后 `7fe18dd`/`29ceab7`/`0b23e46` 均 chore/docs，paths-ignore 不部署 → 部署后端代码 ≡ HEAD 后端代码）
**裁定：PASS → done**（r1 ISSUE-1 已修复并生产实证；r1 全 PASS 项未被触及且保持）
**轮次：** verifying r1（FIXING）→ reverifying（本报告，round1 闭环）

---

## 0. 裁定摘要

| 维度 | r1 | reverifying |
|---|---|---|
| F002 回测研究员级审计（核心） | PASS | 未触及，保持 PASS |
| 利差三档阈值先验性（不变量①） | PASS | 未触及，保持 PASS |
| TR−PR 手算 / 2024-02 更正 / 探针重fetch | PASS | 未触及，保持 PASS |
| 单测/门禁/CI | PASS | **+2 隔离单测；c53375f CI 三绿** |
| 卡片/registry/migration | PASS | 未触及，保持 PASS |
| 零回归（cn_attack/master/regime） | PASS | **保持**（c53375f 仅触 cli.py+test） |
| **ISSUE-1 生产 live 数据落地** | **FAIL（不可观测）** | **✅ RESOLVED（生产实证 + 与预测逐位吻合）** |
| paper 建仓 | — | **PASS（前置全备+单测证明；激活=用户动作诚实边界）** |
| B081 carried soft-watch | 保留 | 保留（DB 卡片正确，live 快照待 03:40 timer 自愈） |

---

## 1. ISSUE-1 修复复验（本轮核心）

### 1.1 代码修复 + exit-code 语义不变（item ①）
- `data_refresh/cli.py::fetch_main`：`run_dividend_lowvol_refresh`（L250-253，akshare/Tiingo-独立）现调用于 `run_refresh`（Tiingo 价格，L262）**之前**。fx/benchmark/universe 按最小方案仍在其后（同病未治，见 §4 backlog）。
- **run_refresh 本体零改动**：`git show c53375f` 未触 `run_refresh` / `resolve_exit_decision`——exit-code 严格性字节级不变（只隔离不吞错）。
- **c53375f 改动范围仅 2 文件**：`cli.py`（±43）+ `test_data_refresh.py`（+74）。未触任何策略/卡片/paper/monitoring/cn_attack 产品码 → r1 零回归结论完好继承。
- **2 隔离单测（有牙）：**
  - `test_dividend_lowvol_runs_before_tiingo_run_refresh`：断言 `calls == ["dividend_lowvol","run_refresh"]`（顺序）。
  - `test_dividend_lowvol_lands_even_when_run_refresh_wedges`：令 run_refresh `raise RuntimeError("tiingo 429 storm")`，断言 fetch_main 仍 `pytest.raises`（传播不吞）**且** dividend_lowvol 已先运行。
  - `test_data_refresh.py` **39 passed**。

### 1.2 生产 artifact 独立核实（item ②，r1 不可观测项现全部可观测，VM 只读）
| artifact | r1 | reverifying（VM 实测） |
|---|---|---|
| `snapshots/dividend_lowvol/` 5 CSV | **目录不存在** | **✅ 全落地**：h20269 4982 行(2005-01-01起)/h30269 4981/cn_10y 5376/etf_512890 1806(2019-01-18起)/gxl 5221——与 F001 探针深度一致 |
| `recommendation_snapshot` cn_dividend_lowvol | 无 | **✅ 1 行 as_of 2026-06-30**：512890.SH weight 1.0；master_meta `tier=full / spread 2.7589% / divy 4.4919% / etf_weight 1.0 / data_source=real / research_only=True / signal_date 2026-06-30 / monitor 2026-07-03 2.9504%` |
| `price_snapshot` 512890.SH | 无 | **✅ 5 marks，source=`b082_dividend_lowvol_snapshot`**（71764e4 fix 生产生效） |

**★关键：生产快照 master_meta 与我 r1 本机端到端预测（tier=full/spread 2.7589%/monitor 2.95%）逐位吻合** —— 证明 fix 后生产真实数据路径产出 == 冻结数据本机路径 == F002 回测口径，三方自洽。data_source=real（非 fallback）。满配（spread 2.76%≥2.5）→ 100% 512890.SH，无 CASH 行。

### 1.3 paper 建仓裁定（item ③）
- **生产 paper_account cn_dividend_lowvol：不存在（未激活）。**
- **裁定：诚实边界，满足 F004 acceptance，非缺陷、非 soft-watch。** 理由：
  1. paper 激活是**设计上的用户/API 主动动作**（`POST /paper/activate` 路由 / `paper/cli.py`）——precompute/timer **从不自动激活**（自动为研究态模式起 paper 账户会违反 advisory-only/no-execution）。cn_attack/master/regime 账户亦为早前人工激活（2026-06-12/18）。
  2. **建仓前置条件生产端已全备**：真实 target 快照 + 512890.SH price_snapshot 5 marks（r1 缺失/会滞留现金的正是此项，71764e4 已修）。
  3. **建仓机制单测已证**：`test_paper_build_succeeds_once_etf_marked`（激活→512890.SH 建仓/build_complete/skipped=()/cash≈50%/CASH strip）+ `test_paper_and_benchmark_and_currency_wired`（CNY/CSI300）。
  4. 当前 tier=full → target 100% 512890.SH，无 CASH 残留，"不滞留现金"在满配下本就无从谈起；半/低配下 CASH 为**目标残额**非滞留（单测证 CASH strip）。
  - 与 B080 trial_registry=0 缺口**不同**：那是本应随部署自动回填却漏进部署链；这里 paper 激活本就是用户动作、永不自动 → 未激活是正确态。"待日刷自愈"式 soft-watch 亦不适用（无自动事件会触发激活；等的是用户主动动作，超出本批范围）。

---

## 2. r1 全 PASS 项（item ④，未被 c53375f 触及，保持）

c53375f 仅改 cli.py + test_data_refresh.py，未触及以下任一，r1 结论完好：
- **F002 回测（核心）**：独立脚本纯 pandas 从零重实现逐位复现（策略 7.4859%/−40.5072%、持有 10.6402%/−66.1655%、tier 79/32/124、2022/2024-02 DD 全对）；阈值无扫参路径；TR−PR 手算 divy 4.6967%/spread 2.95%；2024-02 真 HS300 −6.1% 独立复算证实。（详见 verifying-r1 §1）
- 探针重 fetch 512890 1805/CN10Y 1.7463 对上；生产 alembic 0037/trial B082=6 逐位吻合/OOS card validated=0·mixed。
- **零回归**：生产其他策略快照未扰动（cn_attack ×2 as_of 2026-07-03、master 2026-06-30、regime 2026-05-29，仅新增 cn_dividend_lowvol）；cohort 单测锁定 (quality,pure,dividend_lowvol)+Master/regime 排除；no-execution 守门。
- **面板**：monitored cohort 含 dividend_lowvol（单测锁定），面板经 registry/list_modes 自动派生。monitoring_metric 周 job 首跑 07-06 前偏疏（同 B080 诚实边界，不阻断）。

---

## 3. B081 carried soft-watch（item ⑤，顺带记录）
- 生产权威 DB 卡片 cn_attack_pure/quality = `source=b081_f005_capital_conditioned` + `oos_cagr_range="-16.0% @10万 / +27.1% @100万"` —— **资本条件化修复到位（不变）**。
- cn_attack **live 快照** master_meta.research_caveat 仍旧文案（`-9%~-11%`/B066）——VM 时 03:01，cn_attack 自愈 timer（03:30/03:40）本日未触发。**保留 soft-watch：DB 卡片正确，live 快照将于下次 03:40 timer 自愈**（非 B082 范围）。

---

## 4. 诚实边界 / 遗留
- **fx/benchmark/universe 同病未治**：仍排在 run_refresh 后（Tiingo 故障日同样被跳过）。planner 已在 `docs/research/`（commit 0b23e46）具体化并入 backlog；本批最小方案只治防守腿 dividend_lowvol，合理。
- **paper 激活** = 用户动作（未激活是正确态，见 §1.3）。
- **monitoring_metric** 周 job 首跑 07-06 前偏疏（B080 同边界）。
- **512890 ETF sina 未复权** = 可实施层口径 artifact（收益口径以 TR 指数为准，F002 §4 已标）。

---

## 5. 结论
**B082 红利低波防守腿 4 特性全 PASS → done。** r1 唯一阻断项 ISSUE-1（生产 live 数据落地）经 c53375f（Tiingo-独立化重排）修复，生产实测 5 CSV 落地 + 快照 data_source=real 且与预测逐位吻合 + 512890 marks 落地；paper 建仓前置全备+机制单测证，激活为用户动作诚实边界；r1 全 PASS 项未被触及。B081 live 快照自愈为 carried soft-watch（DB 正确）。

复现物：`scripts/research/b082_evaluator_independent_audit.py`、verifying-r1 报告、本 signoff。
