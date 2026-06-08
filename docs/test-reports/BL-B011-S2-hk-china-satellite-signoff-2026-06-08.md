# BL-B011-S2 HK-China Satellite Signoff 2026-06-08

> 状态：**PASS**
> 触发：BL-B011-S2 F004 复验（fix-round 1，Finding #1 已修）

---

## Finding #1 修复

**根因：** satellite fixture CSV 不在 trade wheel 中。us_quality + hk_china 的 `load_universe()` 从 `<repo_root>/data/fixtures/` 读 fixture，本地 editable install 有完整 repo，但 wheel 装（site-packages）缺 fixture 目录 → 两 satellite 双双 stub。

**修复：** pyproject.toml `force-include` 把 `data/fixtures/{us_quality_momentum,hk_china_momentum}` 打进 wheel，trade 0.2.0→0.2.1。

---

## L1 结果

```
backend pytest: 787 passed, 2 skipped
ruff: 0 issues
mypy: 0 (trade + workbench)
§12.10.2: 请求路径无 trade import
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Fresh deploy | `gh workflow run` → b773544 deployed |
| Trade wheel | **0.2.1** auto-installed (force-reinstall to pick up fixtures) |
| Data-refresh | 37 symbols, 18463 rows (HK ETFs present) |

### Precompute (核心证据)

```
Manual trigger → saved=20 as_of_date=2026-03-31 data_source=real error=None
0 sleeve_unavailable WARNINGS (vs round1: 2)
```

### /api/recommendations/current

```
20 positions, data_source=real, 4/4 sleeves all scored

momentum (0.40):  GLD 0.2209 + JNJ 0.2133
risk_parity (0.30): SGOV 0.2195 + AGG 0.0632 + SPY 0.0529 + VEA 0.0436
satellite_us_quality (0.20): 14 US stocks @0.0133 each
  AAPL/BAC/DUK/ECL/GOOGL/HON/KO/LIN/NEE/NVDA/PLD/UNH/UPS/XOM
satellite_hk_china (0.10): region risk → defensive SGOV
  (MCHI/FXI/KWEB/ASHR 未通过 trend/区域风险筛选 → fallback to SGOV)

kill_switch: pass (DD 0 ≤ 0.15)
min_equity: pass
wash_sale_flags: 0
recent-errors: {count:0}
```

---

## Master 4/4 真实度

| Sleeve | B045 R2 | BL-B011-S2 R1 | BL-B011-S2 R2 |
|---|---|---|---|
| momentum | scored | scored | **scored** ✓ |
| risk_parity | scored | scored | **scored** ✓ |
| satellite_us_quality | scored | **stubbed** ✗ | **scored** ✓ |
| satellite_hk_china | stubbed | **stubbed** | **scored** ✓ (defensive) |
| data_source | mixed | mixed | **real** |
| positions | 6 | 6 | **20** |

**里程碑 C Master 真实度 4/4 达成。**

---

## HK-China 策略行为

hk_china 已激活并跑真实信号。本轮 quarter-end (2026-03-31) 区域风险触发 → 全 4 ETF 未通过 trend/region risk checks → 100% 配置 SGOV（defensive）。valid outcome — 区域风险确定性过滤生效，策略在弱市收缩是正确的。

---

## Conclusion

**Yes — 签收 PASS。** BL-B011-S2 F004 全 acceptance 通过：

- L1: 787 passed ✓
- L2: data_source=**real**（4/4 sleeves, 0 stubs）✓
- L2: /current 20 positions（vs B045 6）✓
- L2: hk_china activated & scoring（defensive=valid signal）✓
- L2: recent-errors={count:0} ✓
- Finding #1 resolved ✓
- 里程碑 C Master 4/4 真实度达成 ✓
