"""B104 unit tests — deterministic, offline (no network, no akshare).

Covers the three load-bearing guarantees of the B104 seat-expansion pressure-test:
  1. NO LOOK-AHEAD — entry is the first trading day STRICTLY AFTER the LHB date T
     (reused verbatim from B103/B094's forward_returns / bisect_right).
  2. EXPANDED-SAMPLE DETERMINISM — the seed-104 price-covered sample is reproducible,
     signal-independent (seed-only ordering), price-covered, and excludes already-fetched
     keys.
  3. IC COMPUTATION — inst_buy_net seat-net aggregation ("机构专用") and the rank-IC /
     holds-or-decays verdict logic behave as specified.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(_RESEARCH))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RESEARCH / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


fetch = _load("b104_seat_expand_fetch")
ic = _load("b104_inst_net_ic")
b094fetch = _load("b094_youzi_fetch")
b094ic = _load("b094_youzi_ic")


# --------------------------------------------------------------------------- #
# 1. NO LOOK-AHEAD (entry strictly after T) — reused machinery.
# --------------------------------------------------------------------------- #
def _series(days: list[str], closes: list[float]):
    return ([date.fromisoformat(d) for d in days], closes)


def test_entry_is_strictly_after_event_date():
    """Forward returns enter at the first bar STRICTLY after T; T itself is never entry."""
    dates = ["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    series = _series(dates, closes)
    # Event on 2023-01-03 (a bar that EXISTS) -> entry must be 2023-01-04 (index 2),
    # never 2023-01-03 (that close is known only after T, cannot be the entry price).
    rets = b094ic.forward_returns(series, date.fromisoformat("2023-01-03"), (1,))
    assert rets[1] == pytest.approx(closes[3] / closes[2] - 1.0)  # 13/12-1, entry=idx2


def test_no_lookahead_event_before_first_bar_enters_first_bar():
    dates = ["2023-03-01", "2023-03-02", "2023-03-03"]
    series = _series(dates, [5.0, 5.5, 6.0])
    rets = b094ic.forward_returns(series, date.fromisoformat("2023-02-28"), (1,))
    assert rets[1] == pytest.approx(5.5 / 5.0 - 1.0)  # entry = first bar (idx0)


def test_no_lookahead_insufficient_forward_bars_is_none():
    dates = ["2023-05-01", "2023-05-02"]
    series = _series(dates, [7.0, 7.7])
    # Entry after 2023-05-01 = idx1; need idx1+5 -> out of range -> None (no synthetic fill).
    rets = b094ic.forward_returns(series, date.fromisoformat("2023-05-01"), (5,))
    assert rets[5] is None


# --------------------------------------------------------------------------- #
# 2. EXPANDED-SAMPLE DETERMINISM (seed-104, price-covered, excludes fetched).
# --------------------------------------------------------------------------- #
def _events():
    return [
        {"event_date": "2023-01-05", "ticker": "000001.SZ", "code": "000001", "jiedu": "x"},
        {"event_date": "2023-01-06", "ticker": "600000.SH", "code": "600000", "jiedu": "y"},
        {"event_date": "2023-01-07", "ticker": "300001.SZ", "code": "300001", "jiedu": "z"},
        {"event_date": "2023-01-08", "ticker": "002001.SZ", "code": "002001", "jiedu": "w"},
        # Duplicate (date,ticker) key — same stock, two 上榜原因; must dedupe to one.
        {"event_date": "2023-01-05", "ticker": "000001.SZ", "code": "000001", "jiedu": "dup"},
        # Ticker WITHOUT price coverage — must be excluded.
        {"event_date": "2023-01-09", "ticker": "999999.SZ", "code": "999999", "jiedu": "q"},
    ]


_COVERED = {"000001.SZ", "600000.SH", "300001.SZ", "002001.SZ"}


def test_seed_sample_is_deterministic():
    a = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=3, seed=104)
    b = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=3, seed=104)
    assert [(r["event_date"], r["ticker"]) for r in a] == \
           [(r["event_date"], r["ticker"]) for r in b]


def test_seed_sample_excludes_uncovered_and_dedupes():
    got = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=99, seed=104)
    keys = [(r["event_date"], r["ticker"]) for r in got]
    assert ("2023-01-09", "999999.SZ") not in keys       # uncovered excluded
    assert keys.count(("2023-01-05", "000001.SZ")) == 1   # duplicate key deduped
    assert len(keys) == 4                                  # 4 unique covered keys


def test_seed_sample_excludes_already_fetched():
    already = {("2023-01-05", "000001.SZ"), ("2023-01-06", "600000.SH")}
    got = fetch.build_seed_sample(_events(), _COVERED, already, target_new=99, seed=104)
    keys = {(r["event_date"], r["ticker"]) for r in got}
    assert keys.isdisjoint(already)
    assert keys == {("2023-01-07", "300001.SZ"), ("2023-01-08", "002001.SZ")}


def test_seed_sample_is_signal_independent_seed_changes_order():
    """Different seeds shuffle differently -> ordering depends on seed only, not outcome."""
    a = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=4, seed=104)
    b = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=4, seed=1)
    # Same SET of keys (signal-independent membership), order may differ by seed.
    assert {(r["event_date"], r["ticker"]) for r in a} == \
           {(r["event_date"], r["ticker"]) for r in b}


def test_target_new_caps_sample_size():
    got = fetch.build_seed_sample(_events(), _COVERED, set(), target_new=2, seed=104)
    assert len(got) == 2


# --------------------------------------------------------------------------- #
# 3. IC / seat-net computation.
# --------------------------------------------------------------------------- #
def test_inst_seat_net_sums_only_jigou_seats():
    """inst_buy_net = sum of 净额 over '机构专用' seats; named 营业部 excluded."""
    buys = [
        {"交易营业部名称": "机构专用", "净额": 1_000_000.0},
        {"交易营业部名称": "机构专用", "净额": 500_000.0},
        {"交易营业部名称": "某某证券北京营业部", "净额": 9_000_000.0},  # 游资, not inst
        {"交易营业部名称": "深股通专用", "净额": 2_000_000.0},          # 股通, not inst
    ]
    row = fetch.seat_row_from_buys(
        {"event_date": "2023-01-05", "ticker": "000001.SZ", "jiedu": ""}, buys)
    # SEAT_HEADER index 4 = inst_buy_net.
    assert row[fetch.SEAT_HEADER.index("inst_buy_net")] == pytest.approx(1_500_000.0)


def test_seat_row_schema_matches_b094():
    """Expanded rows use the exact B094 seats schema so B103's loader reads inst_buy_net."""
    row = fetch.seat_row_from_buys(
        {"event_date": "2023-01-05", "ticker": "000001.SZ", "jiedu": ""},
        [{"交易营业部名称": "机构专用", "净额": 100.0}])
    assert len(row) == len(fetch.SEAT_HEADER)
    assert fetch.SEAT_HEADER == b094fetch.SEAT_HEADER


def test_rank_ic_perfect_monotonic_is_one():
    assert b094ic.rank_ic([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == pytest.approx(1.0)


def test_rank_ic_perfect_inverse_is_minus_one():
    assert b094ic.rank_ic([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == pytest.approx(-1.0)


def test_event_code_prefers_code_then_derives_from_ticker():
    assert fetch.event_code({"code": "600519", "ticker": "600519.SH"}) == "600519"
    assert fetch.event_code({"code": "", "ticker": "000001.SZ"}) == "000001"
    assert fetch.event_code({"code": "", "ticker": "bad"}) is None


# --------------------------------------------------------------------------- #
# holds_or_decays verdict logic.
# --------------------------------------------------------------------------- #
def _cell(ic_val, t, pairs, months=26):
    return {"mean_monthly_ic": ic_val, "t_stat": t, "n_pairs_pooled": pairs,
            "n_months": months}


def test_verdict_holds_when_ic_survives_on_more_pairs():
    baseline = {"ic_inst_buy_net": {"N5": _cell(0.205, 2.22, 232)}}
    expanded = {"ic_inst_buy_net": {"N5": _cell(0.18, 3.1, 1500)}}
    out = ic.holds_or_decays(baseline, expanded)
    assert out["verdict"] == "HOLDS"


def test_verdict_decays_when_t_drops_below_2():
    baseline = {"ic_inst_buy_net": {"N5": _cell(0.205, 2.22, 232)}}
    expanded = {"ic_inst_buy_net": {"N5": _cell(0.04, 1.1, 1500)}}
    out = ic.holds_or_decays(baseline, expanded)
    assert out["verdict"] == "DECAYS"


def test_verdict_decays_when_ic_flips_sign():
    baseline = {"ic_inst_buy_net": {"N5": _cell(0.205, 2.22, 232)}}
    expanded = {"ic_inst_buy_net": {"N5": _cell(-0.15, 2.5, 1500)}}
    out = ic.holds_or_decays(baseline, expanded)
    assert out["verdict"] == "DECAYS"


def test_verdict_inconclusive_when_pairs_barely_grow():
    baseline = {"ic_inst_buy_net": {"N5": _cell(0.205, 2.22, 232)}}
    expanded = {"ic_inst_buy_net": {"N5": _cell(0.21, 2.3, 250)}}  # +18 pairs only
    out = ic.holds_or_decays(baseline, expanded)
    assert out["verdict"] == "INCONCLUSIVE"
