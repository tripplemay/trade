# B088 — Smoothed / feedback volatility targeting（BL-B013-D1, 基建/研究）Spec

> backlog `BL-B013-D1`（low, Phase 4 长尾）。文献（arxiv 2022 Smoothing vol-targeting / 2026 Adaptive Leveraged Vol Control）：
> **open-loop vol-targeting**（exposure ∝ 1/realized_var）导致 turnover / leverage spike。proportional-control 或 smoothing 显著减 turnover 并维持目标波动。
> 现状：`trade/strategies/risk_parity.py` 已有 open-loop（`min(target/realized, 1.0)`）。本批加 **feedback + smoothing 两变体 + turnover 对比**。

## 0. 设计要点（焊死）

- **零策略改动 / 零 flagship**：新建 `trade/analysis/vol_targeting.py` 研究模块（纯 numpy/pandas，无 akshare），**不改** risk_parity 产品默认。
- **三变体（先验定死，禁扫参）**：
  1. **open-loop**（baseline，同现状）：`e_t = min(target / rv_t, max)`。
  2. **smoothing**：`e_t = min(target / ewma(rv, halflife)_t, max)`——平滑 rv 估计 → 平滑 exposure。
  3. **feedback**（partial-adjustment 比例控制）：`e_t = e_{t-1} + k·(openloop_t − e_{t-1})`，`k∈(0,1]`——部分调整 → 减 exposure 突变。
  先验默认 `halflife=21 / k=0.5 / target=0.08`（禁扫参；先验来自 risk_parity + 文献口径）。
- **★turnover 减是控制律的机械性质**（可在任意 vol-varying 序列上证），故 **可测非主观 edge 判断**（避 B084 式过度乐观）：合成 regime-vol 序列即可客观展示 smoothing/feedback turnover < open-loop 且 realized vol 仍≈target。
- **诚实**：real-data 集成入策略 = 后续 follow-up；本批证控制律 + turnover 机械性质（合成可测）。

## 1. Feature 拆解（2：1 generator + 1 codex）

### F001 (g) — 三 vol-targeting 控制律 + 单测 + turnover 对比（可测）
- `trade/analysis/vol_targeting.py`：`open_loop_exposure` / `smoothed_exposure` / `feedback_exposure`（先验参，禁扫参）。
- **单测**：open-loop（rv=0.16→e=0.5；rv=0.04→capped 1.0）；smoothing（尖峰 rv → e turnover < open-loop）；feedback（k=1→==open-loop；k<1→turnover < open-loop）。
- **turnover 对比**（合成 regime-vol 序列，可测客观）：报告 smoothing/feedback turnover vs open-loop（降幅）+ realized vol 仍≈target（不牺牲控波）。docs/test-reports/B088-F001-vol-targeting.md。
- **零回归**：不改 risk_parity/策略产品码。Gates: mypy trade + 根 ruff + root pytest + CI 绿。

### F002 (codex) — 独立验收 + signoff
- Codex 独立：控制律公式核实（三变体先验口径）；turnover 减是否真（重算合成对比）；参数无扫参（grep 先验常量）；realized vol 仍≈target（不牺牲控波）；零回归（risk_parity 产品码字节不变）。signoff。

## 2. 验收（通用段）
- Gates：mypy + 根 ruff + root pytest + 单测（三控制律 + turnover）+ CI 绿。
- 诚实：turnover 减 = 控制律机械性质（合成可测）；real-data 策略集成留 follow-up；零回归。
