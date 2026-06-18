# B069 F001 — cn_attack 实盘默认权重切换依据 + 决策（可审计）

**决策：不切。维持 `weighting_scheme=equal`（等权）为 cn_attack 两模式 live advisory 默认。**

**依据来源：** B068 committed harness（`scripts/research/run_cn_wide_backtest.py` →
`trade.reporting.cn_attack_wide_comparison`）跑于**全真宽数据**（F001 宽 PIT universe
393 名/250 期 + F003 宽 prices/fundamentals + CSI300），区间 2019-04-01→2026-06-18，
walk-forward IS/OOS（70/30，OOS=2024-04-18→2026-06-18）。完整对比报告：
[`docs/dev/B068-wide-comparison-report.md`](./B068-wide-comparison-report.md)。

这填补了 B069 §0 诚实前提要求的「切换依据入 git」——B068 数字此前仅用户本地自验、未入 git。

---

## 核心：inverse_vol vs equal 的 OOS 真数字（Q2）

| 模式 | OOS Sharpe equal→inv | OOS CAGR equal→inv | OOS MaxDD equal→inv |
|---|---|---|---|
| quality_momentum | 1.88 → **1.78** ↓ | 74.9% → **62.7%** ↓12pp | -23.9% → **-20.7%** ↑3.2pp（改善）|
| pure_momentum | 1.72 → **1.65** ↓ | 77.3% → **69.2%** ↓8pp | -27.6% → -27.7%（≈持平）|

全样本同向：inverse_vol 两模式 CAGR 更低、Sharpe 持平/更低、换手与成本更高
（见 B068 报告全样本表）。

**读法：** inverse_vol 的**唯一**真实收益 = quality 模式回撤少挖 ~3pp（pure 模式无收益）；
代价 = OOS Sharpe ↓~0.1 + OOS CAGR ↓8~12pp + 换手/成本↑。这是「拿收益与风险调整收益
换一点（且仅 quality 模式）回撤保护」的取舍，**不是干净的 OOS 改善**。

## 结论：是否支持切 inverse_vol → **不支持**

- 按 B069 §0/§3 门禁「确认改善才切，没改善/更差则不切」：OOS 上 inverse_vol 在
  **Sharpe 与 CAGR 两个主口径均更差**，仅回撤对 quality 模式有弱改善 → **未达「确认改善」**。
- **印证分析师立场（spec §2 / DeMiguel 2009 1/N）**：A股 短史高噪场景下，等权稳健基线
  难被权重优化干净打败；inverse_vol 的风控收益在干净 walk-forward OOS 上没兑现。
- **诚实警示（压在结论上）**：B068 OOS 强劲（62~77%）本身很可能被**幸存者偏差**
  （宽 universe 由当前在市名单回溯，已退市名缺席）+ **2024Q4 顺风行情**双重高估 →
  任何 OOS 权重对比都不稳，更不宜据此对实盘做激进调参。
- §29 红旗：IS 最优 = pure+equal ≠ OOS 最优 = quality+equal → 不得 cherry-pick。

**用户裁定（2026-06-19）：** 维持 equal，不切。

---

## F002 落地（据本结论）

- **不改** `cn_attack_precompute.py:183`（`CnAttackParameters(factor_variant=...)` 续用默认 equal）。
- **不改** 全局 `DEFAULT_WEIGHTING_SCHEME = equal`。
- live advisory 两模式默认权重保持 **equal** → B067 surface / B066+B068 回测对照基线**字节级零回归**（产品无变更）。
- 新增回归守门单测：live producer 构造的 `CnAttackParameters.weighting_scheme == "equal"`
  （把「维持 equal」决策**焊进测试**，未来若有人误切 inverse_vol 即红）。
- OOS 负/未验证诚实红卡、research-only / advisory-only / no 自动下单：全部不动。

## Follow-up（不在本批）

- 若将来要重议 inverse_vol，需先有**去幸存者偏差的历史成分股数据**（付费 feed），
  否则 OOS 对比不可靠。
- inverse_vol 的能力已落代码（F002 weighting_scheme，默认 equal），随时可在依据充分时启用。
