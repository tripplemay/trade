"""B070 F002 — survivorship-free point-in-time A-share universe builder (research).

Builds a **survivorship-free** universe from baostock's *dated* index-constituent
endpoints (`query_{hs300,zz500,sz50}_stocks(date=)`, F001 §23 = GO): at each
rebalance date the universe is the **real** HS300∪ZZ500∪SZ50 membership *as known
at that date*, INCLUDING names that have since been delisted/removed. This is the
data the B068 current-only top-N universe was structurally blind to (the OOS
over-estimate root, B069 honest warning).

Design (B070 F001 verify-lens, user-confirmed 2026-06-19):
  * Universe = PIT index membership **directly** — NOT re-ranked by market cap.
    Delisted names have no free historical market cap (`query_stock_basic` carries
    no shares; `stock_value_em` is current-listed-only) → an mcap top-N re-rank
    would silently drop delisted names and re-create survivorship bias inside the
    de-biased universe. Membership is given by baostock for free, needs no mcap.
  * A **current-membership control** (today's index members applied to every
    historical rebalance date = survivors only) is written alongside, so F003 can
    isolate survivorship as the SINGLE variable (PIT vs control, composition held
    constant) rather than conflating it with a universe-definition change vs B068.
  * Honest ceiling (F001 §5): baostock exposes ONLY hs300/zz500/zz50 dated
    (no zz1000/zz800) → de-biasing is within the **index-eligible large/mid-cap
    band**; delisted micro/small-caps remain absent (residual bias, smaller than
    B068's, non-zero). Do NOT claim full de-biasing.

The strategy re-ranks the candidate set by its OWN momentum+quality factors
(`load_cn_universe` returns only tickers), so the universe CSV's rank/market_cap/
avg_turnover/composite_score columns are membership bookkeeping, filled with a
deterministic rank + zero placeholders (never read for selection).

gated / research-only: writes to a research data root, NEVER the production
`/var/lib/workbench/data` B067's live advisory reads. HARD BOUNDARY: baostock
only (no broker SDK). The network loader is injected so the pure builders test
without baostock.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

# baostock dated PIT index-constituent endpoints (F001 §23 = GO) + expected size.
PIT_INDEX_FNS: dict[str, str] = {
    "hs300": "query_hs300_stocks",
    "zz500": "query_zz500_stocks",
    "sz50": "query_sz50_stocks",
}
INDEX_EXPECTED_N: dict[str, int] = {"hs300": 300, "zz500": 500, "sz50": 50}

# Universe CSV schema (must match workbench_api.data_refresh.cn_universe.UNIVERSE_HEADER
# so trade.data.cn_attack_universe.load_cn_universe reads it unchanged).
UNIVERSE_HEADER: tuple[str, ...] = (
    "as_of_date",
    "ticker",
    "rank",
    "market_cap",
    "avg_turnover",
    "composite_score",
)


# --------------------------------------------------------------------------- #
# code-format normalisation (matches cn_provider._baostock_code, inverted)
# --------------------------------------------------------------------------- #
def to_canonical(baostock_code: str) -> str:
    """baostock ``sh.600519`` / ``sz.000001`` → canonical ``600519.SH`` / ``000001.SZ``."""
    raw = baostock_code.strip()
    prefix, _, digits = raw.partition(".")
    prefix = prefix.lower()
    if prefix not in ("sh", "sz") or not digits:
        raise ValueError(f"unrecognised baostock code: {baostock_code!r}")
    return f"{digits}.{prefix.upper()}"


def to_baostock(canonical: str) -> str:
    """canonical ``600519.SH`` → baostock ``sh.600519`` (matches cn_provider)."""
    raw = canonical.strip()
    code, _, suffix = raw.partition(".")
    suffix = suffix.upper()
    if suffix not in ("SH", "SZ") or not code:
        raise ValueError(f"unrecognised canonical code: {canonical!r}")
    return f"{suffix.lower()}.{code}"


# --------------------------------------------------------------------------- #
# constituent snapshot + the band-assert guard (F001 §5 #4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ConstituentSnapshot:
    """One index's real membership as known at ``update_date`` (canonical codes)."""

    index_key: str
    requested_date: date
    update_date: str  # baostock's actual reconstitution date (may precede requested)
    members: tuple[str, ...]


def within_expected_band(index_key: str, n: int, *, tolerance: float = 0.10) -> bool:
    """A dated-constituent pull is trustworthy when its size is near the index's
    nominal count. baostock returns transient empties with error_code '0'
    (F001 §5 #4) — a 0/short pull must never be written as a real rebalance row.
    """
    expected = INDEX_EXPECTED_N.get(index_key)
    if expected is None:
        return n > 0
    return abs(n - expected) <= max(1, round(expected * tolerance))


class TransientConstituentError(RuntimeError):
    """A dated-constituent pull stayed empty/short after all retries."""


# --------------------------------------------------------------------------- #
# network loader — one baostock session, retry-with-backoff on empty/short pulls,
# memoised per (index, requested_date). baostock injected so tests stay offline.
# --------------------------------------------------------------------------- #
class DatedConstituentLoader:
    """Fetch dated PIT index constituents with the F001 §5 guards.

    The baostock module is injected (``login`` already called by the caller, or
    call :meth:`login_scope`). Each pull is retried with backoff while empty/short
    so a transient miss is never silently written as a partial rebalance row.
    """

    def __init__(
        self,
        baostock: object,
        *,
        retries: int = 3,
        backoff_s: float = 2.0,
        sleeper: object | None = None,
    ) -> None:
        self._bs = baostock
        self._retries = max(1, retries)
        self._backoff_s = backoff_s
        self._sleep = sleeper or time.sleep
        self._cache: dict[tuple[str, str], ConstituentSnapshot] = {}

    def fetch(self, index_key: str, on_date: date) -> ConstituentSnapshot:
        key = (index_key, on_date.isoformat())
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        fn_name = PIT_INDEX_FNS[index_key]
        fn = getattr(self._bs, fn_name)
        last_n = 0
        for attempt in range(1, self._retries + 1):
            rs = fn(date=on_date.isoformat())
            rows: list[list[str]] = []
            while getattr(rs, "error_code", "0") == "0" and rs.next():
                rows.append(rs.get_row_data())
            last_n = len(rows)
            if within_expected_band(index_key, last_n):
                update_date = rows[0][0] if rows else on_date.isoformat()
                members = tuple(sorted(to_canonical(r[1]) for r in rows))
                snap = ConstituentSnapshot(index_key, on_date, update_date, members)
                self._cache[key] = snap
                return snap
            logger.warning(
                "%s(date=%s) returned %d (out of band) — retry %d/%d",
                fn_name, on_date.isoformat(), last_n, attempt, self._retries,
            )
            if attempt < self._retries:
                self._sleep(self._backoff_s * attempt)
        raise TransientConstituentError(
            f"{fn_name}(date={on_date.isoformat()}) stayed at {last_n} after {self._retries} tries"
        )

    def pit_members(self, on_date: date) -> tuple[str, ...]:
        """Union of all three indexes' real membership as known at ``on_date``."""
        union: set[str] = set()
        for index_key in PIT_INDEX_FNS:
            union |= set(self.fetch(index_key, on_date).members)
        return tuple(sorted(union))

    def current_members(self, today: date) -> tuple[str, ...]:
        """Union of the three indexes' membership as of ``today`` (survivor set)."""
        return self.pit_members(today)


# --------------------------------------------------------------------------- #
# pure builders (no baostock) — testable
# --------------------------------------------------------------------------- #
def _rows_for(as_of: date, members: Sequence[str]) -> list[tuple[str, str, int, str, str, str]]:
    """Universe CSV rows for one rebalance block. rank = deterministic 1-based
    order; market_cap/avg_turnover/composite_score = 0 placeholders (the strategy
    re-ranks by its own momentum+quality, so these are never read for selection)."""
    ordered = sorted(members)
    return [
        (as_of.isoformat(), ticker, rank, "0.0", "0.0", "0.0")
        for rank, ticker in enumerate(ordered, start=1)
    ]


def build_pit_universe_rows(
    members_by_rebalance: Mapping[date, Sequence[str]],
) -> list[tuple[str, str, int, str, str, str]]:
    """Survivorship-free rows: real PIT membership per rebalance date."""
    rows: list[tuple[str, str, int, str, str, str]] = []
    for as_of in sorted(members_by_rebalance):
        rows.extend(_rows_for(as_of, members_by_rebalance[as_of]))
    return rows


def build_current_control_rows(
    current_members: Sequence[str],
    rebalance_dates: Iterable[date],
) -> list[tuple[str, str, int, str, str, str]]:
    """Survivorship-BIASED control: today's index members applied to EVERY historical
    rebalance date (only names still in the index today = survivors). Composition is
    otherwise identical to the PIT universe, so a PIT-vs-control backtest isolates
    survivorship as the single variable (F001 §5 / user-confirmed design)."""
    rows: list[tuple[str, str, int, str, str, str]] = []
    for as_of in sorted(rebalance_dates):
        rows.extend(_rows_for(as_of, current_members))
    return rows


def delisted_fraction(members: Sequence[str], current_listed: frozenset[str]) -> float:
    """Fraction of a rebalance block's members that are NOT in the current-listed
    set (proxy for delisted/removed — the survivorship gap the universe recovers)."""
    if not members:
        return 0.0
    missing = sum(1 for ticker in members if ticker not in current_listed)
    return round(missing / len(members), 4)


def quarterly_rebalance_dates(from_date: date, to_date: date) -> list[date]:
    """Quarter-end calendar dates within ``[from_date, to_date]`` (rebalance grid).

    Replicates ``workbench_api.data_refresh.cn_universe.quarterly_rebalance_dates``
    so this research build runs from the root ``.venv`` (which has baostock) without
    importing ``workbench_api`` (which is not on the root path). The PIT builder
    resolves each to the latest reconstitution ``<= as_of``, so calendar quarter-ends
    (not trading days) are the right grid."""
    quarter_ends = ((3, 31), (6, 30), (9, 30), (12, 31))
    out: list[date] = []
    for year in range(from_date.year, to_date.year + 1):
        for month, day in quarter_ends:
            candidate = date(year, month, day)
            if from_date <= candidate <= to_date:
                out.append(candidate)
    return out
