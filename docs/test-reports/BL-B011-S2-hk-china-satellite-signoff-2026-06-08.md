# BL-B011-S2 HK-China Satellite Signoff 2026-06-08

> 状态：**PARTIAL**（1 critical finding）
> 触发：BL-B011-S2 F004 首轮验收

---

## L1 结果

```
backend pytest: 787 passed, 2 skipped
ruff: 0 issues
mypy: trade 0, workbench 0
§12.10.2: 请求路径无 trade import 守门
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `version=26fa64b` db ok |
| HEAD | `c12d1ac` (1 test-fix commit diff — 接受不同步) |
| `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| Data-refresh | **price_symbols=37** (33→37, +MCHI/FXI/KWEB/ASHR), **price_rows=18463**, fundamentals=329, errors=0 |
| HK ETF data | MCHI/FXI/KWEB/ASHR 在 unified CSV 中有价格数据 |

### Precompute

```
Manual trigger → saved=6 as_of_date=2026-03-31 data_source=mixed error=None
2 sleeve_unavailable WARNINGs
```

**sleeve_status:**
```
momentum:          scored        ✓
risk_parity:       scored        ✓
satellite_us_quality: stubbed    ✗ (regression — was scoring in B045 R2)
satellite_hk_china:   stubbed    ✗ (not yet scoring)
```

### /api/recommendations/current

```
6 positions, data_source=mixed, kill_switch=pass
SGOV: tgt=0.4195 (satellite_us_quality) ← defensive fallback (us_quality stub)
GLD:  tgt=0.2209 (momentum)
JNJ:  tgt=0.2000 (momentum)
AGG:  tgt=0.0632 (risk_parity)
SPY:  tgt=0.0529 (risk_parity)
VEA:  tgt=0.0436 (risk_parity)
```

### Master 4/4 progress

| Sleeve | B045 R2 | BL-B011-S2 | Target |
|---|---|---|---|
| momentum | scored ✓ | scored ✓ | 4/4 |
| risk_parity | scored ✓ | scored ✓ | 4/4 |
| satellite_us_quality | scored ✓ | **stubbed** ✗ | 4/4 |
| satellite_hk_china | stubbed | **stubbed** | 4/4 needed |

---

## Finding #1 (critical): satellite_us_quality regression

**Evidence:** B045 R2 precompute had 1 sleeve_unavailable (hk_china only). After BL-B011-S2 F003 deploy, precompute shows **2 sleeve_unavailable** (us_quality + hk_china). us_quality went from scored→stubbed.

**Root cause hypothesis:** F003 modified `precompute.py` (line 141: added `hk_china = HkChinaMomentumParameters()`, line 160: passed `hk_china_params=hk_china` to `_resolve_child_weights`). The `_resolve_child_weights` signature in the trade wheel may have a mismatch — passing the new hk_china_params argument could shift positional args, breaking us_quality resolution.

**Impact:** data_source stuck at mixed (not reaching real). Master 2/4 real instead of 3/4 (regression from B045).

**Recommendation:** Generator verify `_resolve_child_weights` calling convention matches between precompute.py and master_portfolio.py after F003.

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production | `26fa64b` |
| HEAD | `c12d1ac` |
| Diff | 1 test fix commit (test_recommendations_precompute.py) |

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| Post-signoff dispatch | **否** |
| 接受不同步声明 | 状态机元数据 diff。Finding #1 需 Generator fix-round。 |

---

## Soft-watch

| ID | 描述 | 风险 | 处置 |
|---|---|---|---|
| S1 | trade wheel version 0.2.0 未递增，新模块可能未完整装。 | low | 后续批次 bump version。 |

---

## Conclusion

**PARTIAL — 1 critical finding 需 fix-round。** BL-B011-S2 F004 部分通过：

- L1: 787 passed ✓
- L2: data-refresh 拉 37 symbols 含 HK ETF ✓
- L2: hk_china sleeve STILL stubbed (未达 4/4)
- L2: us_quality regression (scored→stubbed, Finding #1)
- L2: /current 仍 6 positions mixed (未见 hk_china weights)
- L2: recent-errors=0 ✓

**Finding #1**（us_quality regression + hk_china not scoring）需 Generator 诊断和修复。
