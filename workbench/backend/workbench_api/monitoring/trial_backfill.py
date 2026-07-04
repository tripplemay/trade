"""B080 F001 — historical trial-registry backfill (B063–B077 signoff trials).

The Deflated Sharpe Ratio needs the number of configurations ever tried (``N``).
The registry starts empty, so this constant back-fills the strategy trials the
project already ran, transcribed VERBATIM from their signoff reports (each
``source_ref`` points at the report; numbers copied exactly — this is the honest
starting ``N``, not an invented one). The idempotent bootstrap seed upserts these
on a deterministic content id, so re-runs are no-ops.

Honesty notes carried in the data (mirrors the signoffs, matters for a real DSR):
- Many trials are entangled: B066's 6 variants collapse to 3 unique numeric
  results (pure==quality in the 43-seed universe); B076 "current 0.0" == B070 PIT;
  B063 matched_top_n=2 == top_n=6. Counted as distinct CONFIGS tried.
- Trials mix SURVIVOR-BIASED (B068 / B076-secondary — inflated Sharpe) and
  DE-BIASED (B070 / B076-primary) universes, and windows overlap heavily — so the
  *effective* number of independent tests is well below the row count. The
  ``universe`` / ``oos_split`` / ``notes`` fields preserve this so a DSR consumer
  can weight accordingly.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from typing import Any

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

# Fixed created_at for the backfill so re-runs (bootstrap CLI upsert + the
# auto-deploy data-migration) are byte-identical — same id + same timestamp →
# a true no-op on re-apply. B080 F005 fix: the migration imports this too.
TRIAL_BACKFILL_STAMP = datetime(2026, 7, 3, tzinfo=UTC)


def _window_dates(window: str) -> tuple[date | None, date | None]:
    """First / last full ISO date found in a window string (None when absent)."""

    found = [date.fromisoformat(m) for m in _ISO.findall(window)]
    if not found:
        return None, None
    return found[0], found[-1]


def trial_id(batch: str, strategy_id: str, params: str, universe: str, window: str) -> str:
    """Deterministic content id → idempotent backfill (same trial → same id)."""

    key = f"{batch}|{strategy_id}|{params}|{universe}|{window}".encode()
    return "bf-" + hashlib.sha256(key).hexdigest()[:16]


# (batch, strategy_id, params, universe, window, oos_split, metrics, verdict, source_ref)
_RAW: tuple[tuple[str, str, str, str, str, str, str, str, str], ...] = (
    # --- B066 (43-seed local WF; 2 factors x 3 exits; pure==quality in seed-43) ---
    ("B066", "cn_attack_quality_momentum", "factor=quality_momentum, exit=momentum_decay, no-trade band 20%, top-N", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18; bench HS300 CAGR 8.94%", "CAGR 10.20% / Sharpe 0.896 / MaxDD -12.4% / turnover 0.80 / IS_CAGR 20.7% / OOS_CAGR -10.8% / IS_Sharpe 1.64 / OOS_Sharpe -1.00", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    ("B066", "cn_attack_quality_momentum", "factor=quality_momentum, exit=trailing_stop, top-N", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18", "CAGR 9.00% / Sharpe 0.863 / MaxDD -9.7% / turnover 3.31 / IS_CAGR 17.6% / OOS_CAGR -8.5% / IS_Sharpe 1.47 / OOS_Sharpe -1.00", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    ("B066", "cn_attack_quality_momentum", "factor=quality_momentum, exit=hard_profit_target, top-N", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18", "CAGR 10.09% / Sharpe 1.007 / MaxDD -10.0% / turnover 3.75 / IS_CAGR 19.2% / OOS_CAGR -8.5% / IS_Sharpe 1.71 / OOS_Sharpe -0.99", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    ("B066", "cn_attack_pure_momentum", "factor=pure_momentum, exit=momentum_decay, no-trade band 20%, top-N (== quality in seed-43)", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18", "CAGR 10.20% / Sharpe 0.896 / MaxDD -12.4% / turnover 0.80 / OOS_CAGR -10.8% / OOS_Sharpe -1.00", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    ("B066", "cn_attack_pure_momentum", "factor=pure_momentum, exit=trailing_stop, top-N", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18", "CAGR 9.00% / Sharpe 0.863 / MaxDD -9.7% / turnover 3.31 / OOS_CAGR -8.5% / OOS_Sharpe -1.00", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    ("B066", "cn_attack_pure_momentum", "factor=pure_momentum, exit=hard_profit_target, top-N", "43-ticker PIT fixed seed (seed-43)", "2023-06-01 -> 2026-06-18", "walk-forward 70/30, IS end 2025-07-18", "CAGR 10.09% / Sharpe 1.007 / MaxDD -10.0% / turnover 3.75 / OOS_CAGR -8.5% / OOS_Sharpe -0.99", "INCONCLUSIVE", "docs/test-reports/B066-ashare-attack-momentum-quality-signoff-2026-06-18.md"),
    # --- B068 weighting A/B (numbers committed in the B069 no-switch signoff; survivor-biased) ---
    ("B068", "cn_attack_quality_momentum", "factor=quality_momentum, weighting=equal (baseline)", "full real WIDE data (survivor-biased; OOS double-inflated by survivorship + 2024Q4 tailwind)", "WF 70/30 OOS window", "walk-forward 70/30 OOS", "OOS Sharpe 1.88 / OOS CAGR 74.9% / OOS MaxDD -23.9%", "INCONCLUSIVE", "docs/test-reports/B069-cn-attack-no-switch-signoff-2026-06-19.md"),
    ("B068", "cn_attack_quality_momentum", "factor=quality_momentum, weighting=inverse_vol (candidate switch — rejected)", "full real WIDE data (survivor-biased)", "WF 70/30 OOS window", "walk-forward 70/30 OOS", "OOS Sharpe 1.78 (down from 1.88) / OOS CAGR 62.7% (down 12pp) / OOS MaxDD -20.7%", "NO_GO", "docs/test-reports/B069-cn-attack-no-switch-signoff-2026-06-19.md"),
    ("B068", "cn_attack_pure_momentum", "factor=pure_momentum, weighting=equal (baseline)", "full real WIDE data (survivor-biased)", "WF 70/30 OOS window", "walk-forward 70/30 OOS", "OOS Sharpe 1.72 / OOS CAGR 77.3% / OOS MaxDD -27.6%", "INCONCLUSIVE", "docs/test-reports/B069-cn-attack-no-switch-signoff-2026-06-19.md"),
    ("B068", "cn_attack_pure_momentum", "factor=pure_momentum, weighting=inverse_vol (candidate switch — rejected)", "full real WIDE data (survivor-biased)", "WF 70/30 OOS window", "walk-forward 70/30 OOS", "OOS Sharpe 1.65 (down from 1.72) / OOS CAGR 69.2% (down 8pp) / OOS MaxDD -27.7%", "NO_GO", "docs/test-reports/B069-cn-attack-no-switch-signoff-2026-06-19.md"),
    # --- B070 survivorship-free revalidation (first de-biased GO) + biased control ---
    ("B070", "cn_attack_pure_momentum", "factor=pure_momentum, weighting=equal, exit=momentum_decay; survivorship_free_pit", "survivorship-free PIT (HS300 ∪ ZZ500 ∪ SZ50; 1310 union incl. delisted)", "2019-04-01 .. 2026-06-19", "WF 70/30, IS split 2024-04-18", "rebal 639 / CAGR 13.1% / Sharpe 0.56 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / OOS_DD -27.8%; verdict SURVIVES_DEBIASING", "GO", "docs/test-reports/B070-ashare-survivorship-free-signoff-2026-06-19.md"),
    ("B070", "cn_attack_pure_momentum", "factor=pure_momentum, weighting=equal, exit=momentum_decay; biased_control (today's members all dates)", "current-members survivor-biased control", "2019-04-01 .. 2026-06-19", "WF 70/30, IS split 2024-04-18", "rebal 611 / CAGR 28.8% / Sharpe 0.93 / MaxDD -50.2% / OOS_CAGR 55.0% / OOS_Sharpe 1.45; survivorship bias +26.6pp OOS CAGR vs PIT", "NA", "docs/test-reports/B070-survivorship-comparison.md"),
    # --- B075 wide-universe live selection L2 (data verification, no return backtest) ---
    ("B075", "cn_attack_quality_momentum", "top-25 selection from wide PIT pool (composite momentum+quality); size_tilt=0", "wide PIT ~1490 distinct tickers (top ~1500 liquid)", "live precompute as_of 2026-06-18", "N/A (live selection verification, not a return backtest)", "positions=25 from 1490 stocks; top-25 overlaps seed-43 blue chips; paper rebalanced=0; wide_errors=0/2992; NO CAGR/Sharpe", "GO", "docs/test-reports/B075-ashare-wide-universe-signoff-2026-06-22.md"),
    ("B075", "cn_attack_pure_momentum", "top-25 selection from wide PIT pool (pure momentum); size_tilt=0", "wide PIT ~1490 distinct tickers", "live precompute as_of 2026-06-18", "N/A (live selection verification, not a return backtest)", "positions=25 from 1490 stocks; top-25 overlaps seed-43 blue chips; paper rebalanced=0; NO CAGR/Sharpe", "GO", "docs/test-reports/B075-ashare-wide-universe-signoff-2026-06-22.md"),
    # --- B076 size-tilt sweep: PRIMARY de-biased (adjudication) + SECONDARY survivor (directional only) ---
    ("B076", "cn_attack_pure_momentum", "PRIMARY de-biased, size_tilt_weight=0.0 (baseline == B070 PIT)", "B070 survivorship-free PIT (1310 incl. delisted)", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 639 / CAGR 13.1% / Sharpe 0.56 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / median mcap 13.5亿 / smallcap_frac 0.00", "NA", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_pure_momentum", "PRIMARY de-biased, size_tilt_weight=0.15 (light)", "B070 survivorship-free PIT (1310 incl. delisted)", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 799 / CAGR 2.2% / Sharpe 0.23 (deg -0.33 > tol 0.02) / MaxDD -62.6% / OOS_CAGR 14.6% / smallcap_frac 0.08", "NO_GO", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_pure_momentum", "PRIMARY de-biased, size_tilt_weight=0.3 (medium)", "B070 survivorship-free PIT (1310 incl. delisted)", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 812 / CAGR 5.9% / Sharpe 0.35 (deg -0.21) / MaxDD -51.3% / OOS_CAGR 20.5% / smallcap_frac 0.28", "NO_GO", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_pure_momentum", "PRIMARY de-biased, size_tilt_weight=0.5 (strong)", "B070 survivorship-free PIT (1310 incl. delisted)", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 738 / CAGR 7.5% / Sharpe 0.42 (deg -0.14) / MaxDD -51.5% / OOS_CAGR 22.5% / OOS_Sharpe 0.93 (window-luck) / smallcap_frac 0.64", "NO_GO", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_quality_momentum", "SECONDARY survivor-biased (directional only), size_tilt_weight=0.0", "B068 survivor-biased current top-N", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 415 / CAGR 28.3% / Sharpe 1.00 / MaxDD -45.9% / OOS_CAGR 74.9% / OOS_Sharpe 1.88 / median mcap 13.8亿", "NA", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_quality_momentum", "SECONDARY survivor-biased (directional only), size_tilt_weight=0.15", "B068 survivor-biased current top-N", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 414 / CAGR 30.7% / Sharpe 1.03 / MaxDD -49.0% / OOS_CAGR 80.7% / OOS_Sharpe 1.94 / median mcap 7.7亿", "NA", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_quality_momentum", "SECONDARY survivor-biased (directional only), size_tilt_weight=0.3", "B068 survivor-biased current top-N", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 408 / CAGR 36.6% / Sharpe 1.14 / MaxDD -46.7% / OOS_CAGR 83.4% / OOS_Sharpe 1.97 / median mcap 6.0亿", "NA", "docs/test-reports/B076-size-tilt-comparison.md"),
    ("B076", "cn_attack_quality_momentum", "SECONDARY survivor-biased (directional only), size_tilt_weight=0.5 (looks GO on survivor universe — EXCLUDED from adjudication)", "B068 survivor-biased current top-N", "2019-04-01 .. 2026-06-24", "WF 70/30", "rebal 327 / CAGR 43.3% / Sharpe 1.27 / MaxDD -51.5% / OOS_CAGR 101.4% / OOS_Sharpe 2.22 / smallcap_frac 0.48", "NA", "docs/test-reports/B076-size-tilt-comparison.md"),
    # --- B077 smart-money LHB institutional-seat factor first-look IC ---
    ("B077", "cn_attack_smart_money_lhb", "signal=机构买入净额 (institutional-seat net-buy amount); forward-return rank-IC, entry t+1", "B070 survivorship-free PIT; 11,365/59,090 LHB events = 19.2% coverage (80.8% small-cap uncovered)", "events 2019-01 -> 2026-06 (5,678 stocks)", "first-look forward-return IC, horizons N1/N5/N10/N20", "rank-IC N1 0.0201 / N5 0.0232 / N10 0.0176 / N20 0.0181 (4/4 same-sign, all < 0.03); group means hump-shaped non-monotonic", "INCONCLUSIVE", "docs/test-reports/B077-F002-first-look-ic.md"),
    ("B077", "cn_attack_smart_money_lhb", "signal=机构净买额占总成交额比 (net-buy share, size-normalized); forward-return rank-IC, entry t+1", "B070 survivorship-free PIT; 19.2% coverage", "events 2019-01 -> 2026-06", "first-look forward-return IC, horizons N1/N5/N10/N20", "rank-IC N1 0.0069 / N5 0.0130 / N10 0.0101 / N20 0.0010; top-bottom spread sign unstable; weaker than net-buy amount", "INCONCLUSIVE", "docs/test-reports/B077-F002-first-look-ic.md"),
    # --- B063 hk_china real-vs-proxy quarterly comparison (real held SGOV cash 20/20 → hypothesis untested) ---
    ("B063", "hk_china_proxy", "proxy ETF basket (MCHI/FXI/KWEB/ASHR), regional-risk-off gate, quarterly, 1bp cost + 2bp slippage", "proxy: MCHI/FXI/KWEB/ASHR US-listed ETFs", "2021-06-30 -> 2026-03-31 (20 quarters)", "N/A (full-period quarterly comparison, no IS/OOS split)", "CAGR +2.77% / Sharpe 0.550 / MaxDD -0.96% / ann.vol 5.21% / turnover 13.0 / defensive 12/20", "NA", "docs/test-reports/B063-hk-china-real-data-batch2-fx-backtest-comparison-report-2026-06-15.md"),
    ("B063", "hk_china_real", "real individual-stock, PIT rule selection, top_n=6, regional-risk-off gate, USD same-basis, quarterly", "real 26-name CN/HK PIT (listing_date <= as_of)", "2021-06-30 -> 2026-03-31 (20 quarters)", "N/A (full-period quarterly comparison)", "CAGR -0.06% / Sharpe -0.322 / MaxDD -0.42% / held SGOV cash 20/20 quarters (regional_risk_off); core 'real vs ETF' hypothesis NOT actually tested; Δ vs proxy CAGR -2.84pp", "NO_GO", "docs/test-reports/B063-hk-china-real-data-batch2-fx-backtest-comparison-report-2026-06-15.md"),
    ("B063", "hk_china_real", "real individual-stock, PIT rule selection, matched_top_n=2 (pinned to proxy), regional-risk-off gate, USD, quarterly", "real 26-name CN/HK PIT", "2021-06-30 -> 2026-03-31 (20 quarters)", "N/A (full-period quarterly comparison)", "IDENTICAL to top_n=6 (real selected 0 stocks 20/20 quarters → top_n has no effect; always SGOV only)", "NO_GO", "docs/test-reports/B063-hk-china-real-data-batch2-fx-backtest-comparison-report-2026-06-15.md"),
)


def _build(entry: tuple[str, ...]) -> dict[str, Any]:
    batch, strategy_id, params, universe, window, oos_split, metrics, verdict, source_ref = entry
    start, end = _window_dates(window)
    return {
        "id": trial_id(batch, strategy_id, params, universe, window),
        "batch": batch,
        "strategy_id": strategy_id,
        "params": {"description": params, "window": window},
        "universe": universe,
        "window_start": start,
        "window_end": end,
        "oos_split": oos_split,
        "metrics": {"summary": metrics},
        "verdict": verdict,
        "source_ref": source_ref,
    }


# 27 historical trials (B063–B077), verbatim from signoffs. The honest starting N.
HISTORICAL_TRIALS: tuple[dict[str, Any], ...] = tuple(_build(e) for e in _RAW)
