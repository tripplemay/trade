# B050 Backtest Per-Strategy Dispatch Signoff 2026-06-09

> 状态：**PASS**
> 触发：B050 F006 首轮验收

---

## Scope

B050 修复回测页「选任何策略结果都一样」+ 交易推荐保真度审查（defensive SGOV 股数 CRITICAL fix + as_of_date 真实化）。

---

## L1

```
backend pytest: 986 passed, 17 skipped
ruff: 0
mypy: 0
```

---

## L2: Per-Strategy Dispatch (核心反例证明)

Same date range (2024-12→2025-12), 3 different strategies:

| Strategy | CAGR | Trades | Equity Points |
|----------|------|--------|---------------|
| B006 momentum | +8.48% | 26 | 14 |
| B016 risk_parity | +1.57% | 65 | 14 |
| B025 us_quality | -6.98% | 0 | 359 |

**确证：不同策略→不同结果。** 缺陷已修复。

## L2: Defensive SGOV Shares Fidelity

$50K cash account, no positions → defensive buy:

```
SGOV: delta_usd=$10,976.15 shares=0→109.27 ref_price=$100.45
      109.27 × $100.45 = $10,976 ✓ (股数×市价≈权益，非USD当股数)
```

**CRITICAL fix confirmed：** SGOV shares correctly computed as equity / price, not USD as share count.

## Regression

| 项 | 结果 |
|---|---|
| recent-errors | {count:0} |
| HEAD vs prod | d89e2c6 (零 diff) |

