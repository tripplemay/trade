#!/usr/bin/env python
"""B104 — recompute the institutional net-buy (``inst_buy_net``) rank-IC on the EXPANDED
seat sample and compare it head-to-head with B103's 232-pair baseline.

B103 found ``inst_buy_net`` (per-event ¥ summed over "机构专用" seats) has a 5-day
forward-return rank-IC of +0.205 (t=2.22) on only 232 price-covered pairs / 26 months.
B104_seat_expand_fetch.py expands the seat sample (existing 800 + seed-104 price-covered
events). This script reruns the SAME VERIFIED no-look-ahead IC machinery (imported
verbatim from ``b103_lhb_inst_ic.py`` -> ``b094_youzi_ic.py``: bisect_right entry T+1,
forward_returns strictly > T, monthly cross-sectional rank-IC + t-stat, follow backtest)
on both the baseline (800) and the expanded seats, and asks the ONE question:

  Does +0.20 HOLD (t stays >=2 on the larger sample -> a REAL signal, strengthens the
  paid ¥200 case) or DECAY (t drops <2 -> thin-sample noise)?

No new statistics are invented — B104 reuses B103's exact ``run`` end to end so the only
difference is the seats file (more pairs). research-only / no broker / no production.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b103_lhb_inst_ic as b103  # noqa: E402
from b094_youzi_ic import HORIZONS  # noqa: E402

logger = logging.getLogger(__name__)

_HOLD_T = 2.0        # t-stat floor for a "holds" call
_HORIZON = "N5"      # the headline horizon B103 reported (+0.205, t=2.22)


def _inst_net_ic(events_csv: Path, prices_csv: Path, seats_csv: Path) -> dict[str, Any]:
    """Run B103's full pipeline and return just the inst_buy_net IC + coverage."""
    result = b103.run(events_csv=events_csv, prices_csv=prices_csv,
                      seats_csv=seats_csv if seats_csv.exists() else None)
    return {
        "ic_inst_buy_net": result["ic_inst_buy_net_sample"],
        "inst_net_sampled_events": result["counts"]["inst_net_sampled_events"],
        "coverage": result["coverage"],
        "follow_backtest": result["follow_backtest_vs_baseline"],
    }


def holds_or_decays(baseline: dict[str, Any], expanded: dict[str, Any],
                    horizon: str = _HORIZON) -> dict[str, Any]:
    """Compare the headline-horizon inst_buy_net IC: does +0.20 HOLD or DECAY?

    HOLDS  — expanded |t| >= 2 AND expanded IC keeps the same (positive) sign with
             |IC| >= 0.5 * baseline |IC| on materially MORE pairs. A real signal that
             survives sample expansion -> strengthens the paid ¥200 clean-test case.
    DECAYS — expanded |t| < 2 OR the IC collapses toward 0 / flips sign on more data
             -> the +0.20 was thin-sample noise; free data cannot support it.
    INCONCLUSIVE — the expanded pair count barely grew (fetch throttled) so the test is
             not materially more powerful than B103; the paid ¥200 remains decisive."""
    b_cell = baseline["ic_inst_buy_net"].get(horizon, {})
    e_cell = expanded["ic_inst_buy_net"].get(horizon, {})
    b_ic = b_cell.get("mean_monthly_ic")
    b_t = b_cell.get("t_stat")
    b_pairs = b_cell.get("n_pairs_pooled", 0)
    e_ic = e_cell.get("mean_monthly_ic")
    e_t = e_cell.get("t_stat")
    e_pairs = e_cell.get("n_pairs_pooled", 0)
    e_months = e_cell.get("n_months", 0)

    pairs_grew = e_pairs >= b_pairs * 1.5 and e_pairs - b_pairs >= 100
    materially_more = e_pairs >= b_pairs + 50

    if not materially_more:
        verdict = "INCONCLUSIVE"
        reason = (
            f"Expanded pairs ({e_pairs}) barely exceed B103's {b_pairs} — the seat fetch "
            "did not materially enlarge the usable sample (likely throttled). The test is "
            "no more powerful than B103; the paid Tushare ¥200 full-history LHB remains the "
            "decisive clean test."
        )
    elif (e_t is not None and abs(e_t) >= _HOLD_T and e_ic is not None
          and b_ic is not None and e_ic > 0 and b_ic > 0
          and abs(e_ic) >= 0.5 * abs(b_ic)):
        verdict = "HOLDS"
        reason = (
            f"On {e_pairs} pairs ({e_months} months) — {round(e_pairs / max(b_pairs, 1), 1)}x "
            f"B103's {b_pairs} — the inst_buy_net {horizon} rank-IC is {e_ic} (t={e_t}), "
            f"still positive with |t|>={_HOLD_T} and >= half the baseline |IC| ({b_ic}). The "
            "+0.20 SURVIVES sample expansion — evidence of a REAL institutional-net-buy "
            "signal on free data, which STRENGTHENS the case for the paid ¥200 clean test "
            "(full history 2005+, delisted names, cleaner seats). NOT yet a tradeable claim."
        )
    else:
        verdict = "DECAYS"
        reason = (
            f"On {e_pairs} pairs ({e_months} months) — {round(e_pairs / max(b_pairs, 1), 1)}x "
            f"B103's {b_pairs} — the inst_buy_net {horizon} rank-IC falls to {e_ic} (t={e_t}): "
            f"|t| dropped below {_HOLD_T} and/or the IC collapsed toward 0 / flipped sign. "
            "B103's +0.205 was largely THIN-SAMPLE NOISE that does not survive expansion. "
            "Free data cannot support the signal; only the paid ¥200 full-history clean-seat "
            "LHB could still settle it, but the free pre-check is discouraging."
        )
    return {
        "verdict": verdict,
        "horizon": horizon,
        "baseline_ic": b_ic,
        "baseline_t": b_t,
        "baseline_pairs": b_pairs,
        "expanded_ic": e_ic,
        "expanded_t": e_t,
        "expanded_pairs": e_pairs,
        "expanded_months": e_months,
        "pairs_multiple": round(e_pairs / b_pairs, 2) if b_pairs else None,
        "pairs_grew_materially": bool(pairs_grew),
        "reason": reason,
    }


def run(*, events_csv: Path, prices_csv: Path, baseline_seats: Path,
        expanded_seats: Path) -> dict[str, Any]:
    baseline = _inst_net_ic(events_csv, prices_csv, baseline_seats)
    expanded = _inst_net_ic(events_csv, prices_csv, expanded_seats)
    verdict = holds_or_decays(baseline, expanded)
    return {
        "probe": "b104_inst_net_ic",
        "question": ("Does B103's inst_buy_net +0.205 (t=2.22, 232 pairs) HOLD on an "
                     "EXPANDED free seat sample or DECAY (thin-sample noise)?"),
        "horizons": list(HORIZONS),
        "no_lookahead": ("reused verbatim from B103/B094: LHB list for T disclosed AFTER "
                         "close T; entry T+1 (bisect_right, strictly > T); fwd ret > T"),
        "baseline_b103": {
            "seats_file": str(baseline_seats),
            "ic_inst_buy_net": baseline["ic_inst_buy_net"],
            "coverage": baseline["coverage"],
            "follow_backtest": baseline["follow_backtest"],
        },
        "expanded_b104": {
            "seats_file": str(expanded_seats),
            "ic_inst_buy_net": expanded["ic_inst_buy_net"],
            "coverage": expanded["coverage"],
            "follow_backtest": expanded["follow_backtest"],
        },
        "holds_or_decays": verdict,
        "honesty": (
            "Expanded FREE sample is STILL 2022-2024 + survivorship-limited (akshare omits "
            "delisted names) + LHB-selection-conditioned (already-moved names). A HOLDS here "
            "is a stronger free signal but NOT a tradeable claim and NOT survivorship-clean. "
            "The paid Tushare ¥200 full-history LHB (2005+, delisted, ~50x sample, cleaner "
            "seats) remains the decisive clean test — B104 is only the free pre-check."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B104 inst_buy_net expanded-sample IC")
    parser.add_argument("--events", type=Path,
                        default=Path("data/research/b094_youzi/events.csv"))
    parser.add_argument("--prices", type=Path,
                        default=Path("data/research/b094_youzi/prices.csv"))
    parser.add_argument("--baseline-seats", type=Path,
                        default=Path("data/research/b094_youzi/seats_sample.csv"))
    parser.add_argument("--expanded-seats", type=Path,
                        default=Path("data/research/b104_seats/seats_expanded.csv"))
    parser.add_argument("--out", type=Path, default=None)
    cli = parser.parse_args(argv)

    result = run(events_csv=cli.events, prices_csv=cli.prices,
                 baseline_seats=cli.baseline_seats, expanded_seats=cli.expanded_seats)
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    print(text)
    if cli.out:
        cli.out.parent.mkdir(parents=True, exist_ok=True)
        cli.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
