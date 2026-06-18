# A股 进攻策略 宽宇宙重验 — 4 配置对比报告（研究态 research-only）

- 回测区间 / Window: 2019-04-01 → 2026-06-18
- 样本内/外切分 / In-sample split: 2024-04-18
- 宇宙广度 / Universe breadth: 每期最多 250 名 (B066 seed-43 → 本批宽宇宙)

> 研究纪律：4 配置（2 因子 × 2 权重，退出固定 momentum_decay）**全部披露**，不 cherry-pick 样本内赢家；判定以**样本外**为准。research-only / 无实盘 / 无执行。

## 全样本对比 / Full-sample comparison

| 因子 Factor | 权重 Weighting | CAGR | Sharpe | MaxDD | 换手 | 成本 | 调仓 |
|---|---|---|---|---|---|---|---|
| quality_momentum | equal | 28.33% | 1.00 | -45.90% | 116.16 | 29005 | 415 |
| quality_momentum | inverse_vol | 25.59% | 0.98 | -42.06% | 148.05 | 35448 | 528 |
| pure_momentum | equal | 32.48% | 0.98 | -45.60% | 153.88 | 42955 | 531 |
| pure_momentum | inverse_vol | 27.59% | 0.89 | -45.33% | 189.87 | 44387 | 648 |

## Walk-forward 样本外验证 / Out-of-sample validation

| Factor | Weighting | IS CAGR | IS Sharpe | OOS CAGR | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|---|
| quality_momentum | equal | 12.36% | 0.56 | 74.93% | 1.88 | -23.90% |
| quality_momentum | inverse_vol | 12.39% | 0.59 | 62.72% | 1.78 | -20.69% |
| pure_momentum | equal | 16.91% | 0.63 | 77.33% | 1.72 | -27.63% |
| pure_momentum | inverse_vol | 13.03% | 0.54 | 69.22% | 1.65 | -27.66% |

## 基准 / Benchmark — 沪深300 (CSI 300)

- CAGR 3.07% / Sharpe 0.26 / MaxDD -45.60%

## 三问 / The three questions（样本外为准）

**Q1 — 质量是否加值 / Does quality add value?** yes — quality adds OOS value in both weightings
  - 证据 / Evidence: [equal] OOS Sharpe Δ(quality−pure)=+0.15 (quality 1.88 vs pure 1.72), OOS CAGR Δ=-2.40%; [inverse_vol] OOS Sharpe Δ(quality−pure)=+0.13 (quality 1.78 vs pure 1.65), OOS CAGR Δ=-6.50%

**Q2 — 波动倒数能否驯服 OOS 崩盘 / Does inverse-vol tame the OOS crash?** mixed — inverse_vol helps the drawdown in one factor only
  - 证据 / Evidence: [quality_momentum] OOS MaxDD equal -23.90% → inverse_vol -20.69% (Δ=3.20%), OOS Sharpe Δ(iv−eq)=-0.09; [pure_momentum] OOS MaxDD equal -27.63% → inverse_vol -27.66% (Δ=-0.03%), OOS Sharpe Δ(iv−eq)=-0.07

**Q3 — 更宽/更长 OOS 是否仍脆弱 / Is the wider OOS still fragile?** no — the wider OOS is not uniformly fragile (OOS broadly holds up)
  - 证据 / Evidence: quality_momentum+equal IS Sharpe 0.56→OOS 1.88, OOS CAGR 74.93%; quality_momentum+inverse_vol IS Sharpe 0.59→OOS 1.78, OOS CAGR 62.72%; pure_momentum+equal IS Sharpe 0.63→OOS 1.72, OOS CAGR 77.33%; pure_momentum+inverse_vol IS Sharpe 0.54→OOS 1.65, OOS CAGR 69.22%

## 过拟合红旗 / Over-fitting red flags

- 🚩 in_sample_winner_not_out_of_sample: in-sample best (pure_momentum+equal) ≠ out-of-sample best (quality_momentum+equal) — do NOT cherry-pick the in-sample winner

## 研究判定指引 / Research verdict (F004 Codex 终判)

- 据**样本外**：(a) 质量是否加值 (b) 波动倒数是否值得换 (c) 是否建议调 B067 实盘默认配置。
- research-only：无实盘 / 无执行 / 无收益预测 / 不碰 live；本批不改 B067 surface。

---

## 分析师诚实警示 / Analyst honesty caveats（人工补注，读 OOS 数字前必看）

> 自动红旗只能捕捉**指标模式**；以下两条是**数据构造层**的偏差，自动检测看不到，但对 OOS 解读至关重要。

1. **★幸存者/上市偏差（OOS 数字很可能被高估）/ Survivorship bias.** 宽 universe 由 **当前在市** 的 sina spot 名单回溯构建（F001 §；`cn_universe.py` docstring 已记）——**2026-06 前已退市/出清的名字一律缺席**。于是 universe 系统性地**偏向幸存者**，而样本外段（2024-04→2026-06）的强劲表现（OOS CAGR 62~77%）**正由这批"活下来且近期上涨"的名字驱动 → OOS 很可能被显著高估**。PIT 排名本身无未来泄漏（只用 ≤as_of 市值，leakage=0 已验），但成分**池**的幸存者偏差是另一回事，需付费历史成分股 feed 才能消除。**结论：OOS 的高 CAGR/Sharpe 不能当作"策略稳健"的硬证据。**
2. **样本外恰逢顺风行情 / Favorable OOS regime.** OOS 段叠加 2024-09 政策刺激后的 A股 动量大涨；高 OOS 部分是**行情运气**，恰是 B066「2025H2 单段逆风 OOS −9~−11%」的**镜像**。单段顺风 ≠ 已证稳健，正如单段逆风 ≠ 已证脆弱（Q3 的"不脆弱"须打折扣）。
3. **IS≠OOS winner（见红旗）**：IS 最优 pure_momentum+equal，OOS 最优 quality_momentum+equal → 不得 cherry-pick。

### 三问的诚实读法 / Honest reading

- **Q1 质量加值**：是，但**仅风险调整维度**——质量在两种权重下 OOS Sharpe 均更高（+0.15/+0.13），代价是 OOS CAGR 略低（−2.4%/−6.5%）。即质量**降波动换不了更高绝对收益，但风险调整后更优**；方向支持"质量有用"，幅度温和且受幸存者偏差影响。
- **Q2 波动倒数是否值得换**：**否（不建议换）**。inverse_vol 仅对 quality 略降 OOS 回撤（−23.9%→−20.7%），对 pure 几乎无效（−27.63%→−27.66%），且两者 OOS Sharpe 均**略降**（−0.09/−0.07）、换手/成本更高。风控收益没兑现 → **印证分析师立场（DeMiguel 1/N 等权稳健基线难被打败）**。
- **Q3 更宽/更长 OOS 是否仍脆弱**：表面**不脆弱**（4 配置 OOS 全正），但**须扣除幸存者偏差 + 顺风行情**两重高估；保守结论是"B066 的 −9~−11% 脆弱**未在更宽更长 OOS 复现**，但本批 OOS 强劲**不足以反证脆弱**"。

### 对 B067 实盘默认的建议（本批不改，仅建议）/ B067 default recommendation

- **维持 equal 等权默认**：inverse_vol 在干净的 walk-forward OOS 上**未显出值得替换的优势**（Sharpe 略降、回撤改善微弱且不稳定）。
- 质量门槛**可保留/略偏好**（风险调整更优），但因幸存者偏差不宜据此做激进调参。
- 任何实盘调整都应先有**去幸存者偏差的成分股数据**再议。