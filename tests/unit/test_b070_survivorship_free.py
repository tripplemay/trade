"""B070 F002 — unit tests for the survivorship-free PIT universe builder.

No network: the baostock loader is exercised through a fake cursor so the F001 §5
guards (band-assert + retry-on-transient-empty + memoisation) and the pure row
builders are locked deterministically. The real build's evidence (sample-date
members + delisted fraction) lives in the F002 report.
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.research.b070_survivorship_free import (
    ConstituentSnapshot,
    DatedConstituentLoader,
    TransientConstituentError,
    build_current_control_rows,
    build_pit_universe_rows,
    delisted_fraction,
    to_baostock,
    to_canonical,
    within_expected_band,
)


# --------------------------- code normalisation --------------------------- #
@pytest.mark.parametrize(
    ("baostock", "canonical"),
    [("sh.600519", "600519.SH"), ("sz.000001", "000001.SZ"), ("SH.600000", "600000.SH")],
)
def test_to_canonical_roundtrip(baostock: str, canonical: str) -> None:
    assert to_canonical(baostock) == canonical
    assert to_baostock(canonical) == baostock.lower()


@pytest.mark.parametrize("bad", ["600519", "x.600519", "sh.", ""])
def test_to_canonical_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        to_canonical(bad)


@pytest.mark.parametrize("bad", ["600519", "600519.US", ".SH", ""])
def test_to_baostock_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        to_baostock(bad)


# ----------------------------- band assert -------------------------------- #
def test_within_expected_band() -> None:
    assert within_expected_band("hs300", 300)
    assert within_expected_band("hs300", 290)  # within 10%
    assert not within_expected_band("hs300", 0)  # transient empty rejected
    assert not within_expected_band("zz500", 100)  # short pull rejected
    assert within_expected_band("unknown", 5)  # unknown index → any >0 ok
    assert not within_expected_band("unknown", 0)


# ------------------------ fake baostock cursor ---------------------------- #
class _FakeCursor:
    def __init__(self, rows: list[list[str]], error_code: str = "0") -> None:
        self._rows = list(rows)
        self.error_code = error_code
        self._i = -1

    def next(self) -> bool:
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._i]


class _FakeBaostock:
    """Returns a queued sequence of cursors per index fn (to script transient empties)."""

    def __init__(self, queues: dict[str, list[_FakeCursor]]) -> None:
        self._queues = queues
        self.calls: list[tuple[str, str]] = []

    def _make(self, index_fn: str, date: str) -> _FakeCursor:
        self.calls.append((index_fn, date))
        queue = self._queues[index_fn]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def query_hs300_stocks(self, date: str = "") -> _FakeCursor:
        return self._make("query_hs300_stocks", date)

    def query_zz500_stocks(self, date: str = "") -> _FakeCursor:
        return self._make("query_zz500_stocks", date)

    def query_sz50_stocks(self, date: str = "") -> _FakeCursor:
        return self._make("query_sz50_stocks", date)


def _full(index_key: str, n: int, prefix: int = 600000) -> _FakeCursor:
    rows = [["2019-01-28", f"sh.{prefix + i:06d}", f"name{i}"] for i in range(n)]
    return _FakeCursor(rows)


# ------------------------------ loader ------------------------------------ #
def test_loader_retries_transient_empty_then_succeeds() -> None:
    # first hs300 pull is empty (error_code 0!), second is full → guard retries.
    bs = _FakeBaostock(
        {
            "query_hs300_stocks": [_FakeCursor([]), _full("hs300", 300)],
            "query_zz500_stocks": [_full("zz500", 500, 600000)],
            "query_sz50_stocks": [_full("sz50", 50, 600000)],
        }
    )
    sleeps: list[float] = []
    loader = DatedConstituentLoader(bs, retries=3, sleeper=sleeps.append)
    snap = loader.fetch("hs300", date(2019, 1, 31))
    assert isinstance(snap, ConstituentSnapshot)
    assert len(snap.members) == 300
    assert snap.members[0] == "600000.SH"  # canonicalised + sorted
    assert sleeps  # backed off once before the successful retry


def test_loader_raises_after_exhausting_retries() -> None:
    bs = _FakeBaostock({"query_hs300_stocks": [_FakeCursor([])]})
    loader = DatedConstituentLoader(bs, retries=2, sleeper=lambda _s: None)
    with pytest.raises(TransientConstituentError):
        loader.fetch("hs300", date(2019, 1, 31))


def test_loader_memoises_per_date() -> None:
    bs = _FakeBaostock({"query_hs300_stocks": [_full("hs300", 300)]})
    loader = DatedConstituentLoader(bs, sleeper=lambda _s: None)
    loader.fetch("hs300", date(2019, 1, 31))
    loader.fetch("hs300", date(2019, 1, 31))
    assert len(bs.calls) == 1  # second call served from cache


def test_loader_pit_members_unions_three_indexes() -> None:
    bs = _FakeBaostock(
        {
            "query_hs300_stocks": [_full("hs300", 300, 600000)],
            "query_zz500_stocks": [_full("zz500", 500, 600300)],  # overlaps hs300 tail
            "query_sz50_stocks": [_full("sz50", 50, 600000)],  # subset of hs300
        }
    )
    loader = DatedConstituentLoader(bs, sleeper=lambda _s: None)
    members = loader.pit_members(date(2019, 1, 31))
    # union of 600000..600299 (hs300) and 600300..600799 (zz500) = 800 distinct
    assert len(members) == 800
    assert members == tuple(sorted(members))


# --------------------------- pure builders -------------------------------- #
def test_build_pit_universe_rows_shape_and_rank() -> None:
    members = {date(2019, 3, 31): ["600002.SH", "600001.SH"], date(2019, 6, 30): ["600003.SH"]}
    rows = build_pit_universe_rows(members)
    assert len(rows) == 3
    # block 1 sorted → 600001 rank 1, 600002 rank 2
    assert rows[0] == ("2019-03-31", "600001.SH", 1, "0.0", "0.0", "0.0")
    assert rows[1][2] == 2
    assert rows[2] == ("2019-06-30", "600003.SH", 1, "0.0", "0.0", "0.0")


def test_build_current_control_applies_today_members_to_all_dates() -> None:
    current = ["600001.SH", "600002.SH"]
    dates = [date(2019, 3, 31), date(2019, 6, 30)]
    rows = build_current_control_rows(current, dates)
    assert len(rows) == 4  # 2 members × 2 dates
    assert {r[0] for r in rows} == {"2019-03-31", "2019-06-30"}
    assert {r[1] for r in rows} == {"600001.SH", "600002.SH"}


def test_delisted_fraction() -> None:
    current_listed = frozenset({"600001.SH", "600002.SH"})
    members = ["600001.SH", "600002.SH", "600003.SH", "600004.SH"]  # 2 of 4 not listed
    assert delisted_fraction(members, current_listed) == 0.5
    assert delisted_fraction([], current_listed) == 0.0
