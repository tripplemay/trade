# B069 F003 Signoff — cn_attack 实盘 advisory 默认权重 NO-SWITCH 验收报告

**批次:** B069 / **Sprint:** F003 (Codex 验收)  
**验收日期:** 2026-06-19  
**Evaluator:** Andy (CLI 代 Codex)  
**HEAD≡Prod:** `a6b7d1d29e738e35ee6c0e8fe872f6c48ece8fc5` (feat(B069-F001,F002), VM API 实测确认)  
**批次性质:** NO-SWITCH — 验收「live advisory 维持 equal 权重（未切 inverse_vol）」  
**状态:** ✅ PASS

---

## §1 核心验收：live advisory 仍 equal（未切）

### 1.1 代码级实测

```python
# workbench/backend/workbench_api/strategy_modes/cn_attack_precompute.py:183
parameters = CnAttackParameters(factor_variant=factor_variant)
```

**`weighting_scheme` 参数缺失 → 使用默认值。**

```python
# trade/strategies/cn_attack_momentum_quality/parameters.py:49+80
DEFAULT_WEIGHTING_SCHEME = WEIGHTING_SCHEME_EQUAL   # = "equal"
weighting_scheme: str = DEFAULT_WEIGHTING_SCHEME    # CnAttackParameters 默认
```

live producer 构造的 `CnAttackParameters` 使用 `weighting_scheme="equal"`。未切 inverse_vol。✅

### 1.2 B069 守门单测（焊死 equal）

```
test_live_producer_keeps_equal_weighting_b069  PASSED
```

此测试拦截「误切 inverse_vol」——若有人在 precompute.py:183 加 `weighting_scheme="inverse_vol"` 即红。✅

---

## §2 F001 — 切换依据入 git（可审计）

文件：`docs/dev/B069-inverse-vol-default-decision.md`

**B068 committed harness 跑于全真宽数据的授权 OOS 数字：**

| 模式 | OOS Sharpe equal→inv | OOS CAGR equal→inv | OOS MaxDD |
|---|---|---|---|
| quality_momentum | 1.88 → **1.78** ↓ | 74.9% → **62.7%** ↓12pp | -23.9% → **-20.7%** 改善 |
| pure_momentum | 1.72 → **1.65** ↓ | 77.3% → **69.2%** ↓8pp | -27.6% → -27.7% ≈ 持平 |

**结论（已入 git）：** inverse_vol OOS Sharpe+CAGR 两口径均更差，仅 quality 回撤弱改善 (-3pp)。未达「确认改善」门禁 → 不切。OOS 数字本身亦受幸存者偏差+2024Q4 顺风双重高估。

**用户裁定（2026-06-19）：** 维持 equal。

B069 §0 「切换须有可审计依据」已满足。✅

---

## §3 L1 门禁全通 (实测证据)

| 测试集 | 结果 |
|--------|------|
| `trade/` pytest (含 wide comparison 7 项) | **983 passed** |
| workbench backend safety | **164 passed, 15 skipped** |
| backend precompute tests (11 项，含 B069 守门) | **11 passed** |
| cn_universe tests (B068 sina fallback) | **39 passed** |
| wide comparison unit tests | **7 passed** |

```
# trade/ (983)
983 passed in 139.11s

# backend safety (164)
164 passed, 15 skipped in 1.55s

# precompute (11, includes guard test)
11 passed in 0.39s
  test_live_producer_keeps_equal_weighting_b069  PASSED  ← B069 核心

# cn_universe (39)
39 passed in 0.29s
  test_discover_superset_sina_off_by_default_keeps_seed_b067_regression  PASSED  ← B067 零回归守门

# wide comparison (7)
7 passed in 56.76s
```

---

## §4 OOS 诚实红卡仍在位

```python
# cn_attack_precompute.py:80-87
CN_ATTACK_RESEARCH_CAVEAT: dict[str, Any] = {
    "validated": False,
    "oos_result": "negative",
    ...
}
```

B069 未修改 `cn_attack_precompute.py`，OOS 红卡（validated=False, oos_result=negative, -9%~-11%）不动。✅

---

## §5 零回归核验

**B069 改动范围（git diff vs B067 done）：**
- `docs/dev/` — 决策文档 + B068 对比报告（无产品影响）
- `docs/specs/` — spec 文档（无产品影响）
- `trade/` — construction.py（新增 weighting_scheme 参数，默认 equal；零回归）、parameters.py（DEFAULT_WEIGHTING_SCHEME=equal）、wide_comparison.py（研究报告，非生产路径）
- `workbench/backend/tests/unit/test_cn_attack_precompute.py` — 仅加 1 条 B069 守门测试
- `scripts/research/` — 研究脚本（非生产路径）

**cn_attack_precompute.py 未改动（字节级零回归）：**
```
git diff da24ed2..HEAD -- workbench/backend/workbench_api/strategy_modes/cn_attack_precompute.py
(无输出 = 文件未变)
```

B067 live advisory surface、B066 回测、US/HK 全栈：**零回归**。✅

---

## §6 VM HEAD≡Prod

```bash
GET https://trade.guangai.ai/api/health
{
  "status": "ok",
  "version": "a6b7d1d29e738e35ee6c0e8fe872f6c48ece8fc5",
  "db_connectivity": "ok",
  "uptime_seconds": 311.229
}
```

本地 git log:  
`a6b7d1d feat(B069-F001,F002): 诚实出口 — B068 证据不支持切 inverse_vol → 维持 equal 默认(不切)`

HEAD = B069 F001+F002。✅

---

## §7 签收结论

**B069 F001-F002 全部特性签收：PASS（NO-SWITCH 路径）**

| Feature | 内容 | 结论 |
|---------|------|------|
| F001 | B068 OOS 数字落 git + 「不切」决策可审计 | ✅ |
| F002 | 不改 precompute.py + 守门测试焊死 equal | ✅ |

**研究诚实约束核验（§0）：**
- 先有依据再做产品决策 ✅（B068 harness 跑真数据入 git，不盲切）
- OOS 红卡不动 ✅（validated=False，oos_result=negative）
- advisory-only / no 自动下单 / no-broker 不动 ✅

**→ status: verifying → done**
