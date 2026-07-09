# B106 组合层落地（红利低波并入 Master 杠铃 + 风险加权对照）Signoff 2026-07-09

> 状态：**Evaluator 独立验收通过（全 PASS 3/3）** → progress.json status=done
> 触发：B106 F003 独立验收（代 Codex，独立无实现上下文 agent；B079-B105 先例，守铁律 4 独立性）
> 边界：research-only / advisory-only / no-broker / 不碰真金；发现问题只记录不修复

---

## 0. TL;DR — 裁定 **PASS，接受 generator 的 NO-GO**

B106 把已验证的红利低波（cn_dividend_lowvol）防守腿作为组杠铃并入 Master、并用风险加权
（fixed/risk_parity/hrp/vol_target）对照固定 40/30/20/10，回测裁定 **NO-GO（保持现状 default
4-sleeve fixed）**。本次独立验收：

- **L1 全门禁绿**（mypy 0 err / ruff 净 / root pytest 1395 passed / backend 10 passed / 新单测 38 passed / 迁移单头 0042 / CI 三条绿）。
- **★核心不变量 byte-identical 零回归——独立证实（最强形式）**：用**前 B106 源码**（F001 parent `f7adc15`）计算默认 Master parameter_hash = `726f9ce6…` = 守门单测金值 = HEAD 默认 hash，三者逐位相等。不是新测试内部自洽，而是真等于 pre-B106 代码。
- **L2 独立复算（numpy 自写指标数学，不调 runner 内部函数）**：5 方案 CAGR/Sharpe/MaxDD/回本/NAV、verdict 双门槛、相关性、币种口径、FX 方向、回撤复利 **全部与报告一致，Δ≈1e-16（浮点噪声）**。
- **verdict 与数字一致**：最优 ③ risk_parity ΔSharpe 仅 +0.0117（< 0.15 门槛）且拖 CAGR −2.5pp，无方案过双门槛 → NO-GO 合法且诚实（B069/B076 先例）。
- **HEAD≡prod**：生产 version = `c7acc30`（含全部 B106 产品码），HEAD 差异仅 progress.json（状态机文件）→ 产品代码无漂移。

无 FAIL。3/3 features PASS。

---

## 1. 验收范围与 executor

| Feature | 标题 | executor | 判定 |
|---|---|---|---|
| F001 | Master 组合层扩展：防守腿 sleeve + 权重方案参数化（fixed/risk_parity/hrp） | generator | **PASS** |
| F002 | 组合回测对照（5 方案）+ verdict | generator | **PASS** |
| F003 | 独立验收 + signoff（本报告） | codex | **PASS** |

被验收产物：
- 代码：`trade/portfolio/master.py`（F001，commit `95202f3`）、`scripts/research/b106_portfolio_uplift_ab.py`（F002，commit `6dd0ec9`）
- 报告：`docs/test-reports/B106-portfolio-uplift-ab.md`（F002）
- trial registry：`workbench/backend/.../trial_backfill_b106.py` + migration `0042`（commit `c7acc30`）
- 独立复算脚本（本次新增）：`docs/test-cases/b106_independent_recompute.py`

---

## 2. L1 全门禁（逐条实测证据）

| 门禁 | 命令 | 结果 | 判定 |
|---|---|---|---|
| mypy trade | `.venv/bin/mypy trade` | `Success: no issues found in 103 source files` | ✓ PASS |
| ruff（根目录） | `.venv/bin/python -m ruff check .` | `All checks passed!` | ✓ PASS |
| root pytest 全量 | `.venv/bin/python -m pytest -q` | **1395 passed in 185.45s** | ✓ PASS |
| backend 重装 trade + 子集 | `cd workbench/backend && .venv/bin/python -m pip install ../..` 后 `pytest test_bootstrap_cli.py test_trial_registry.py` | **10 passed** | ✓ PASS |
| 新 B106 单测 | `pytest test_master_portfolio_weight_scheme.py test_b106_portfolio_uplift_ab.py` | **38 passed**（F001 守门 23 + F002 数学 15） | ✓ PASS |
| 迁移单头 | `alembic heads` | `0042_b106_portfolio_uplift_trial (head)`（chain 0041→0042 单头） | ✓ PASS |

### CI 状态核查（gh 逐 commit）

| commit | 内容 | CI runs |
|---|---|---|
| `95202f3`（F001） | master.py 扩展 | Python CI ✓ + Workbench Backend CI ✓ |
| `c7acc30`（F002 tip） | runner + trial_registry + migration | Python CI ✓ + Backend CI ✓ + Frontend CI ✓ + **Workbench Deploy ✓✓** |

CI 三条（Python / Backend / Frontend）+ Deploy 全绿。

---

## 3. ★核心不变量：现有 Master 4-sleeve fixed 默认零回归（byte-identical）

这是本批最高优先级不变量（生产 master_portfolio paper 不破）。独立验证（最强形式）：

```
前 B106 源码（F001 parent f7adc15）default_master_portfolio_parameters().parameter_hash()
  = 726f9ce6a4acd956dcde72f2bc32a9c1633ba5c23acfc359c7533aea6ea7a644
守门单测金值 GOLDEN_DEFAULT_PARAMETER_HASH
  = 726f9ce6a4acd956dcde72f2bc32a9c1633ba5c23acfc359c7533aea6ea7a644
HEAD default_master_portfolio_parameters().parameter_hash()
  = 726f9ce6a4acd956dcde72f2bc32a9c1633ba5c23acfc359c7533aea6ea7a644
→ 三者逐位相等；barbell(opt-in) hash 不同（可区分）
```

**关键判断点：** 守门单测金值不是新测试内部自洽（那样无法证明"真等于旧行为"），而是我独立从 pre-B106
源码算出同一 hash，证明 F001 的 `weight_scheme` 字段在默认 `fixed` 下从 hash payload 条件省略，
默认配置字节级不变。

**机制核查：**
- `master.py` F001 diff **纯 additive**（216 insertions，0 deletions）；F001 之后无任何 commit 再触碰 master.py（`git log -- trade/portfolio/master.py` 头即 `95202f3`）。
- barbell 构造器 `master_portfolio_parameters_with_defensive_barbell` 引用点仅在 research runner + 单测 + 本复算脚本——**未接入任何生产路径**（backend precompute/services 用的仍是 `default_master_portfolio_parameters`）。backend 唯一 "defensive_barbell" 字面是 trial_registry 的 NO-GO 标签，非策略接线。
- 结论：新防守腿 + 3 权重方案是纯 opt-in 研究对照，生产 paper 零回归 ✓。

---

## 4. L2 独立复算（numpy 自写，不依赖 runner 内部函数）

脚本 `docs/test-cases/b106_independent_recompute.py`：复用 runner 的 sleeve-return 重构（数据/策略层）与 F001 已测 `resolve_sleeve_weights`，但**独立自写**组合、窗口对齐、CAGR/Sharpe/MaxDD/相关性/回撤复利/verdict 门槛（scipy 本机无 → Pearson 自写）。

### 4.1 复现性

- runner 确定性重跑：`.venv/bin/python scripts/research/b106_portfolio_uplift_ab.py` 产出 `ab_results.json` 与已提交版本**逐字节相同**（`json canonical diff` = IDENTICAL）。

### 4.2 5 方案指标独立复算 vs 报告（全部 Δ≈1e-16）

| # | 方案 | CAGR | AnnVol | Sharpe | MaxDD | 独立复算 vs 报告 |
|---|---|---|---|---|---|---|
| ① | baseline 4-sleeve fixed | 10.46% | 8.46% | **1.2224** | −8.33% | 全项 Δ≈0 ✓ |
| ② | barbell + fixed | 9.33% | 8.13% | 1.1410 | −8.11% | 全项 Δ≈0 ✓ |
| ③ | barbell + risk_parity | 7.93% | 6.37% | **1.2341** | −7.03% | 全项 Δ≈0 ✓ |
| ④ | barbell + hrp | 6.91% | 5.88% | 1.1682 | −6.69% | 全项 Δ≈0 ✓ |
| ⑤ | barbell + vol_target | 8.24% | 7.54% | 1.0919 | −8.11% | 全项 Δ≈0 ✓ |

对齐窗口独立复现：sleeve 共同窗口 2015-03..2026-04（122m），5 方案对齐交集 2015-09..2026-04（**116m**）——与报告一致。**关键判断点**：窗口对齐到 5 方案共同交集（否则基线被多算 6 个月，虚高杠铃相对提升；此对齐把 risk_parity ΔSharpe 从虚假 +0.128 修正为真实 +0.012）——独立复现确认。

### 4.3 verdict 双门槛独立复算

预登记门槛 ΔSharpe ≥ +0.15 且 ΔMaxDD ≥ +3pp（双门）：

| 方案 | ΔSharpe（独立） | ΔMaxDD（独立） | 过门槛 |
|---|---|---|---|
| ③ barbell risk_parity | **+0.0117** | +1.31pp | ✗ |
| ④ barbell hrp | −0.0542 | +1.64pp | ✗ |
| ② barbell fixed | −0.0814 | +0.22pp | ✗ |
| ⑤ barbell vol_target | −0.1305 | +0.22pp | ✗ |

独立裁定 **NO-GO** = 报告裁定 ✓。最优 ③ 仅 +0.0117 Sharpe（靠砍波动 8.46%→6.37%，非防守腿分散）且拖 CAGR −2.5pp → 不落地，诚实保持现状。verdict 与数字一致 ✓。

### 4.4 相关性真实性（分散前提不成立）独立复算

| 防守腿 vs 进攻腿 | USD 换算（独立） | CNY 原生（独立） |
|---|---|---|
| ~ momentum | +0.270 | +0.178 |
| ~ risk_parity | +0.296 | +0.220 |
| ~ us_quality | +0.195 | +0.114 |
| ~ hk_china | +0.478 | +0.407 |

独立 Pearson 全部与报告一致（Δ≈1e-16）。**USD +0.195~+0.478 / CNY +0.114~+0.407 全弱正非负** ✓——spec 引用的"负相关"是 vs A股动量（本组不持），前提不迁移（市场错配）；FX 换算再把相关性推正约 +0.08（币种错配）。分散前提不成立，独立核实成立。

### 4.5 ★跨市场币种口径诚实性 + FX 方向正确性

| 口径 | CAGR | Sharpe | MaxDD | 独立 vs 报告 |
|---|---|---|---|---|
| 防守腿 CNY-native | 5.76% | 0.480 | −27.8% | Δ≈0 ✓ |
| 防守腿 USD-converted | 4.64% | 0.365 | −31.8% | Δ≈0 ✓ |

- **FX 拖累方向正确**：USD 换算 Sharpe 0.365 < CNY 原生 0.480、CAGR 4.64% < 5.76%——人民币贬值伤 USD 投资者，换算削收益 ✓。
- **FX 序列方向**：CNY per USD 2015 低点 6.19（实测 2015 min 6.187）→ 2024 约 7.17（实测 2024 区间 7.01–7.30），上升=人民币贬值 ~15%——报告描述数字**准确**（非误差）。
- **换算公式方向**（合成检验）：`(1+r_cny)·fx_prev/fx_now−1`，rate=CNY per USD 升 → USD 投资者亏；`(1+0.10)·(6.0/6.6)−1 = 0.0`（+10% CNY 恰被 10% 贬值抵消）✓。
- 报告 USD-primary + CNY-native 双列可分离，FX 拖累显式独立——口径诚实 ✓。

### 4.6 其余关键判断点

| 判断点 | 核查 | 结论 |
|---|---|---|
| combine_dynamic normalize=False（vol-target 残差进现金，否则 scale 被抵消） | 独立复算 ⑤ 用 normalize=False 得匹配数字；单测 `test_combine_dynamic_normalize_vs_cash_residual` 钉死 | ✓ |
| rolling 用 trailing d<t 无 look-ahead | runner 两处滚动窗口均 `if d < t`（严格小于） | ✓ |
| 回撤复利算术 recovery=|dd|/(1−|dd|) | 独立复算 ① ③ 逐项 Δ<1e-9 | ✓ |
| JSON 逐字节可复现 | 重跑 == 已提交 | ✓ |

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 生产 Master 默认配置（4-sleeve fixed） | parameter_hash byte-identical，`default_master_portfolio_parameters` 未触碰；生产 master_portfolio paper 零回归 |
| 生产 backend runtime | barbell/非默认 weight_scheme 未接入 precompute/services；仅 trial_registry 登记 NO-GO |
| 真金 / broker | research-only，无下单路径改动 |

---

## 类型检查 / CI

```
.venv/bin/mypy trade           → Success: no issues found in 103 source files
.venv/bin/python -m ruff check . → All checks passed!
.venv/bin/python -m pytest -q  → 1395 passed in 185.45s
alembic heads                  → 0042_b106_portfolio_uplift_trial (head)
gh run list --commit 95202f3   → Python CI success / Workbench Backend CI success
gh run list --commit c7acc30   → Python CI + Backend CI + Frontend CI + Workbench Deploy 全 success
```

---

## 实测证据（决策级/真数据批次必填）

| acceptance 项 | 实测证据 |
|---|---|
| 5 方案真数字 | ① 10.46%/1.222/−8.3% ② 9.33%/1.141/−8.1% ③ 7.93%/1.234/−7.0% ④ 6.91%/1.168/−6.7% ⑤ 8.24%/1.092/−8.1%（独立 numpy 复算 Δ≈1e-16，窗口 2015-09~2026-04 116m）|
| go/no-go 结论 | **NO-GO** — 无方案过 ΔSharpe≥0.15 且 ΔMaxDD≥3pp 双门槛；最优 ③ 仅 +0.0117 Sharpe 且拖 CAGR −2.5pp。诚实保持现状 default 4-sleeve fixed |
| 默认零回归 pre/post | 前 B106 源码 default hash = HEAD default hash = 金值 `726f9ce6…`（逐位相等）|
| 相关性决策依据 | 红利低波 vs 进攻腿 USD +0.195~+0.478 / CNY +0.114~+0.407（弱正非负）→ 分散前提不成立，加防守腿纯稀释高 Sharpe 进攻腿 |

---

## Ops 副作用记录

本批次无数据库 ops（migration 0042 由 CI/CD 部署时 alembic 落库，Evaluator 未手动执行 SQL）。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version（`trade.guangai.ai/api/health.version`） | `c7acc30b1a8a6cf3d6a59033942d0835a61441df` |
| Main HEAD（验收时） | `14f9d125fbf01ec9433da152f99a9b1235457b62` |
| Diff（`git diff c7acc30..HEAD --name-only`） | 仅 `progress.json`（1 commit，状态机文件） |

**判断：** 不同 SHA，但 diff 仅含 progress.json（状态机元数据，paths-ignore 不触发 CI/deploy）→ **接受不同步，产品代码无漂移**。生产 `c7acc30` 已含全部 B106 产品码（master.py 扩展 + migration 0042 + trial_backfill + bootstrap），HEAD≡prod 于产品层成立。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine`（本报告 + 独立复算脚本 + progress.json/project-status.md）|
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告 / 独立复算测试产物 / 状态机元数据，**未推任何 `trade/**` `workbench/**` production runtime 改动**；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。生产已在 `c7acc30` 持有全部 B106 产品码 |

---

## Soft-watch（不阻塞 done）

> 以下均为报告已诚实披露的方法学限制，非新发现 bug；列此保持问责账本。NO-GO 裁定对这些限制稳健（相对比较）。

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 绝对 Sharpe 水平偏高（基线 1.22）——sleeve-return 模型（月度调仓、adj_close 总收益、动量 top-2 + AGG 回落）平滑了部分真实摩擦。报告 §1.4 已声明"结论建立在方案间相对比较，不声称绝对 alpha" | low | 保持现状；若阶段 B 前向 paper 验证需绝对水平，另立真机口径 |
| S2 | sleeve-return 层重构是生产 Master 引擎的 proxy（引擎给所有 sleeve 喂同一 records，动量需月频 bar / risk_parity 需 120 日频观测，不兼容，无法在同一真实数据上诚实同跑）。报告 §1.2 已披露；A/B 只隔离杠铃效应 | low | 保持现状；NO-GO 是相对比较，proxy 不影响裁定方向 |
| S3 | 报告后续建议第 1 条"风险加权本身（不含 CNY 防守腿）值得单独测——只对现有 4 条 USD 腿做 risk_parity/HRP，尤其压低 hk_china 17.65% 波动权重"未在本批测；③ 的 Sharpe 微增+波动大降提示这可能才是真杠杆 | medium | 供负责人决策：下一批可补测 "4-sleeve risk_parity（无防守腿）" 隔离效应 |

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building F001→F002 → verifying F003 → done）交付。
`progress.json` 已设为 `status: "done"`，`docs.signoff` 已填入本报告路径。

---

## Framework Learnings

本批次无 framework learnings。（byte-identical 零回归的"用前版本源码独立算 hash 而非仅信新测试金值"做法已是 evaluator §30 独立对抗复审的既有实践，无需新沉淀。）
