# B103 — LHB 机构买入 (institutional-buying) follow-signal FIRST-LOOK

**Probe:** `scripts/research/b103_lhb_inst_ic.py` · **Tests:** `tests/unit/test_b103_lhb_inst.py`
**Data (cached, reused from B094 — no re-fetch):** akshare full LHB, 52,337 events, all
A-shares, 2022-2024. **Status:** research-only, no production, no broker, no git commit.

> **This is the user's PRIMARY signal** — daily LHB 机构专用席位 net buying = 跟踪机构建仓.
> B077 probed it only on the b070 large-cap universe (~19% coverage → **INCONCLUSIVE**).
> B094 fetched the FULL free LHB but tested only 游资 (retail → **NO-GO**). The
> institutional signal on the full free LHB was **never tested** — B103 closes that gap.
> **Memory prior (stated once, NOT tuned):** LHB institutional seats are noisy / can be
> masked via proxy accounts (马甲). A NO-GO / INCONCLUSIVE is a plausible honest answer.

---

## 1. Institutional-signal parsing + coverage

The akshare **解读 (jiedu)** column tags each LHB event with `"N家机构买入"` or
`"N家机构卖出"` (N institutions net-bought / net-sold that day). Parsed via
`(\d+)家机构(买入|卖出)`:

| Signal | Definition | Events | Rate |
|---|---|---:|---:|
| `inst_buy_flag` | 1 iff `N家机构买入` (else 0: covers 卖出 + non-inst) | 9,795 buy | 18.7% |
| `inst_count` (signed) | `+N` buy, `-N` sell, `0` non-inst | — | — |
| **Any 机构 tag** | buy + sell | **15,474** | **29.57%** |
| — of which sell | `N家机构卖出` | 5,679 | 10.9% |

Parsing is clean: **all** 15,474 events containing the `机构` substring match the regex;
buy and sell **never co-occur** in one event (0 mixed). The other 70.4% are 普通席位 /
游资 / 卖方 / trigger-only tags → signal 0.

**Price coverage:** forward returns exist for **12,502 / 52,337 = 23.9%** of events (the
cached `prices.csv` covers the B094-fetched ticker subset, 2022-2024, qfq). IC/backtest
run on this covered slice across **35 monthly cohorts**.

**★No look-ahead (unit-tested):** the LHB list for day T is disclosed **after close of
T**, so the tag is known at close T. Entry = first trading day **strictly after T**
(`bisect_right`), forward return over T+1..T+1+N, strictly > T. Verified by
`test_entry_is_strictly_after_event_date`, `test_entry_uses_close_after_event_not_on_event_day`,
and an end-to-end `test_build_cohorts_entry_strictly_after_T` (event whose only data is
on/before T → **zero coverage**).

---

## 2. Forward-return rank-IC (monthly cohorts, entry T+1)

### 2a. `inst_buy_flag` — "did institutions buy?" (binary, full covered set)

| Horizon | mean monthly IC | t-stat | months | pooled |
|---|---:|---:|---:|---:|
| N=1  | **+0.0072** | 0.59 | 35 | 12,502 |
| N=5  | −0.0002 | −0.02 | 35 | 12,502 |
| N=10 | −0.0081 | −0.58 | 35 | 12,502 |

→ **Flat / zero.** The binary "institutions bought" flag carries **no** forward-return
information at any horizon (all |t| < 0.6).

### 2b. `inst_count` (signed institution count) — the graded magnitude signal

| Horizon | mean monthly IC | t-stat | months | pooled |
|---|---:|---:|---:|---:|
| N=1  | −0.0161 | −1.19 | 35 | 12,502 |
| N=5  | **−0.0446** | **−2.74** | 35 | 12,502 |
| N=10 | **−0.0541** | **−3.49** | 35 | 12,502 |

→ **Significantly NEGATIVE at N=5 and N=10.** The *more* institutions net-bought (and the
fewer net-sold) on the LHB, the *lower* the subsequent return — a **contrarian /
distribution** reading. Heavier free-LHB institutional buying is, if anything, a mild
*sell* tell over 1-2 weeks. This is the opposite of the "follow the institutions" thesis
on the free crude tag.

### 2c. `inst_buy_net` (exact per-event institutional ¥) — thin free sample

| Horizon | mean monthly IC | t-stat | months | pooled |
|---|---:|---:|---:|---:|
| N=1  | +0.137 | 1.69 | 26 | 232 |
| N=5  | **+0.205** | **2.22** | 26 | 232 |
| N=10 | **+0.170** | **2.10** | 26 | 232 |

→ **Positive and borderline-significant** — but on only **232 covered pairs / 26 months**
(~9 names/month). The *exact* institutional net-buy ¥ points the *opposite* way from the
crude signed count. This is the crux (see §5): the coarse free `N家` count destroys the
information that the exact ¥ amount preserves — and the exact amount at **full coverage**
is exactly what the paid feed provides.

### 2d. `lhb_net_buy` (raw LHB net, baseline signal) — flat

N1 +0.016 (t=1.07), N5 −0.013, N10 −0.020 — no edge, as expected.

---

## 3. Follow backtest vs all-LHB baseline

Each month: **FOLLOW** = equal-weight the `inst_buy_flag==1` names, hold N days;
**BASELINE** = equal-weight **ALL** covered LHB names that month. Edge = follow − baseline,
paired per-month t-stat.

| Horizon | follow ret | baseline ret | edge | edge t | months follow wins |
|---|---:|---:|---:|---:|---:|
| N=1  | −0.35% | −0.52% | **+0.17%** | 0.80 | 19/35 |
| N=5  | −2.42% | −2.02% | −0.40% | −1.03 | 17/35 |
| N=10 | −3.98% | −3.22% | **−0.76%** | −1.70 | 14/35 |

→ **No positive edge survives.** A tiny insignificant +0.17% at N=1 flips to a −0.76%
(t=−1.70, 14/35 months) *drag* by N=10. Following LHB institutional buys does **not** beat
just buying all LHB names — it mildly *lags* over 1-2 weeks. (Note: all baseline returns
are negative — LHB names are 异动-conditioned, already-moved, and mean-revert; the whole
LHB universe is a losing hold over this window. The question is only relative edge, and
there is none.)

---

## 4. inst_buy_net cross-check (parsing validation)

Joined the jiedu flag against the exact `inst_buy_net` on the seats sample (796 unique
seat keys → 1,081 event-rows matched; events.csv has duplicate same-day trigger rows):

| | inst_buy_net > 0 | inst_buy_net ≤ 0 |
|---|---:|---:|
| **jiedu flag = 1** | 158 | 21 |
| **jiedu flag = 0** | 95 | 807 |

- **Direction agreement: 89.3%.** rank-IC(signed count, exact net) = **+0.368**.
- → The free jiedu `N家机构买入` tag **faithfully encodes institutional net-buy direction**
  — parsing is sound. (Agreement validates the *label*, NOT any predictive edge.)
- The 95 flag-0-but-net-positive cases = institutions that net-bought a *small* amount
  below akshare's `N家机构` disclosure threshold — the free tag is coarser than the ¥.

---

## 5. Verdict — **INCONCLUSIVE, leaning NO-GO on the crude free tag**

Programmatic verdict (flag + follow-edge, same judge structure as B094): **INCONCLUSIVE**
(best flag IC +0.0081, best follow edge +0.00166 — both faint, sub-threshold). Honest
overall read across all three signals:

- **The free crude institutional tag has NO usable follow edge.** The binary buy-flag is
  flat (|t|<0.6); the graded institution *count* is **significantly NEGATIVE** at N5/N10
  (t=−2.74, −3.49) — heavier free-LHB institutional buying mildly *predicts
  underperformance*; the follow backtest edge is non-positive and trends to −0.76%
  (t=−1.70) by N10. On the free `N家机构` signal alone this is effectively a **NO-GO** —
  consistent with the memory prior (noisy seats / 马甲 / smart-money distributing into
  retail on the 龙虎榜).
- **BUT the *exact* institutional net-buy ¥ shows a positive, borderline-significant IC**
  (+0.14/+0.20/+0.17, t≈1.7-2.2) on a thin 232-pair / 26-month sample — pointing the
  *opposite* way from the coarse count. The free `N家` bucket is too crude; the ¥ amount
  carries the signal the count discards. **This does not settle it — it sharpens the case
  for the paid data.**

**Why not a clean NO-GO:** the one signal that most resembles the paid product (exact
per-event institutional ¥) is positive but statistically fragile (n≈232). Free data
cannot arbitrate between "the crude tag says no edge / contrarian" and "the exact ¥ says
positive on a thin sample." That is the definition of **INCONCLUSIVE for the primary
thesis**, with the deciding CLEAN test being the **paid Tushare ¥200 full-history LHB**
(2005+, delisted survivors, exact seat-level ¥ at full coverage — the `inst_buy_net`
signal at 50× the sample size and no survivorship gap).

### Relation to prior probes

| Probe | Universe | Coverage | Signal tested | Verdict |
|---|---|---:|---|---|
| **B077** | b070 large-cap | ~19% | inst LHB (limited) | INCONCLUSIVE |
| **B094** | full free LHB | 23.9% | 游资 (retail) | **NO-GO** |
| **B103** | full free LHB | 23.9% | **机构买入 (primary)** | **INCONCLUSIVE** (crude tag ≈ NO-GO; exact-¥ positive but thin) |

B103 broadens B077 (b070-only) to the full free LHB and, unlike B094 (游资), tests the
actual institutional primary signal. The free verdict: **the crude free 机构买入 tag is not
a tradeable follow signal (flat/contrarian), but the exact institutional ¥ hints at a real
positive signal that only the paid full-coverage feed can confirm or kill.** The ¥200 is
now a *targeted* test (validate `inst_buy_net`'s +0.20 IC at scale), not a fishing trip.

---

## 6. Honesty / caveats

- **Selection bias:** LHB events are 异动-conditioned (already-moved names); baseline
  returns are negative over the whole window. Only *relative* edge is claimed/denied.
- **Survivorship:** the free akshare feed omits delisted names → optimistic on the losers.
- **Coverage:** 23.9% price coverage; the exact-¥ IC rests on 232 pairs — treat §2c as a
  hypothesis, not a result.
- **No look-ahead:** entry strictly after T (bisect_right), unit-tested; no signal uses
  post-T information.
- **No tuning:** the memory prior was stated once; no threshold was fit to the outcome.

**Gates:** `ruff check` clean; `pytest tests/unit/test_b103_lhb_inst.py -q` → 16 passed.
