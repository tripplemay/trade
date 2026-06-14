"""B063 F002 — wide CN/HK individual-stock universe + USD price conversion.

This is the **real-data** counterpart of :mod:`trade.data.hk_china_universe`
(which serves the *proxy* sleeve over the four US-listed ETFs
MCHI/FXI/KWEB/ASHR that the live Master still trades). It is **research-only**
and **purely additive**: nothing here feeds the Master or any live
recommendation — it exists so B063 can answer one question (is real A-share +
HK exposure worth the FX/concentration complexity vs the proxy?) with an
honest, point-in-time backtest.

Three jobs, all offline (``trade`` never fetches — akshare lives in the
workbench ``data_refresh`` job, which appends these tickers as new rows to the
same unified ``prices_daily.csv``):

1. :data:`REAL_HK_CHINA_UNIVERSE` — a **wide, multi-sector** candidate set
   (~26 liquid HK + A-share large caps spanning internet, banks, insurers,
   energy, telecom, consumer, new-energy, utilities, pharma). It is
   deliberately *not* the seven mega-cap winners (Tencent / Alibaba / Meituan /
   Xiaomi / Moutai / Wuliangye / CATL) the B062 pipeline first shipped: picking
   only those and backtesting is survivorship / hindsight bias (spec §2). The
   strategy must *select* from this broad set by rule, point-in-time — so banks
   and energy that lagged are in the running too.

2. :func:`load_real_universe` / :func:`load_real_prices` — point-in-time
   membership + offline price read. A name is a candidate only on/after its
   ``listing_date``; the **binding** PIT gate, though, is price-history
   availability — a name with no adjusted-close history on/before ``as_of``
   cannot be scored (the momentum factors return NaN and it is dropped), so
   even an imperfect ``listing_date`` can never leak a not-yet-investable name.

3. :func:`to_usd_prices` / :func:`usd_price_bars` — convert each row to USD at
   the **as-of (forward-filled) FX rate for that row's own date** (B063 F001
   :class:`~trade.data.fx.FxConverter`), so the real-data backtest is in the
   same USD caliber as the US-listed proxy (which already embeds the CNY|HKD →
   USD move). A row whose FX rate is unavailable is **dropped**, not fabricated
   (honest degradation) — FRED's DEXCHUS/DEXHKUS history spans the backtest
   window, so in practice nothing is dropped.

**Residual-bias honesty (spec §2 / §3).** The candidate set is chosen from
names liquid *today*; reconstructing historical index membership / liquidity is
out of scope, so a residual selection bias remains and must be flagged in the
B063 comparison report. The listing-date + price-history gates remove
*look-ahead* bias (no name is scored before it traded); they cannot remove the
*"which names did we put in the bowl"* bias.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import SupportsFloat, cast

import pandas as pd

from trade.data.data_root import unified_prices_path
from trade.data.fx import FxConverter
from trade.data.loader import PriceBar

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
UNIFIED_PRICES_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv"
)

PRICES_REQUIRED_COLUMNS: tuple[str, ...] = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)
# Columns converted to USD (volume is share count — left unchanged).
_PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "adj_close")

# Currency by canonical-ticker suffix — kept local so ``trade`` stays free of any
# ``workbench_api`` import (offline edge). HK = HKD, mainland A-share = CNY,
# everything else (bare US ticker) = USD.
HK_SUFFIX = ".HK"
CN_SUFFIXES: tuple[str, ...] = (".SH", ".SZ")


@dataclass(frozen=True, slots=True)
class RealUniverseEntry:
    """One candidate name's minimal metadata (price-only momentum strategy)."""

    ticker: str
    name: str
    sector: str
    currency: str
    listing_date: date


def currency_for(ticker: str) -> str:
    """Display/settlement currency for a canonical ticker (suffix-derived)."""

    upper = ticker.strip().upper()
    if upper.endswith(HK_SUFFIX):
        return "HKD"
    if upper.endswith(CN_SUFFIXES):
        return "CNY"
    return "USD"


def _entry(ticker: str, name: str, sector: str, listing: date) -> RealUniverseEntry:
    return RealUniverseEntry(
        ticker=ticker,
        name=name,
        sector=sector,
        currency=currency_for(ticker),
        listing_date=listing,
    )


# Wide, multi-sector candidate universe (spec §2). Listing dates are the public
# IPO dates; they are documentation + a belt-and-suspenders membership gate, the
# binding PIT gate being price-history availability (module docstring).
REAL_HK_CHINA_UNIVERSE: tuple[RealUniverseEntry, ...] = (
    # --- Hong Kong (HKD) ---
    _entry("0700.HK", "Tencent", "internet", date(2004, 6, 16)),
    _entry("9988.HK", "Alibaba (HK)", "internet", date(2019, 11, 26)),
    _entry("3690.HK", "Meituan", "internet", date(2018, 9, 20)),
    _entry("1810.HK", "Xiaomi", "hardware", date(2018, 7, 9)),
    _entry("9618.HK", "JD.com (HK)", "internet", date(2020, 6, 18)),
    _entry("9999.HK", "NetEase (HK)", "internet", date(2020, 6, 11)),
    _entry("0941.HK", "China Mobile", "telecom", date(1997, 10, 23)),
    _entry("0939.HK", "China Construction Bank", "bank", date(2005, 10, 27)),
    _entry("1398.HK", "ICBC", "bank", date(2006, 10, 27)),
    _entry("1288.HK", "Agricultural Bank of China", "bank", date(2010, 7, 16)),
    _entry("2318.HK", "Ping An Insurance (H)", "insurance", date(2004, 6, 24)),
    _entry("2628.HK", "China Life (H)", "insurance", date(2003, 12, 18)),
    _entry("1299.HK", "AIA Group", "insurance", date(2010, 10, 29)),
    _entry("0883.HK", "CNOOC", "energy", date(2001, 2, 28)),
    _entry("0386.HK", "Sinopec", "energy", date(2000, 10, 19)),
    _entry("0388.HK", "Hong Kong Exchanges", "exchange", date(2000, 6, 27)),
    # --- Mainland A-share (CNY) ---
    _entry("600519.SH", "Kweichow Moutai", "consumer", date(2001, 8, 27)),
    _entry("000858.SZ", "Wuliangye", "consumer", date(1998, 4, 27)),
    _entry("000333.SZ", "Midea Group", "consumer", date(2013, 9, 18)),
    _entry("300750.SZ", "CATL", "new_energy", date(2018, 6, 11)),
    _entry("601012.SH", "LONGi Green Energy", "new_energy", date(2012, 4, 11)),
    _entry("601318.SH", "Ping An Insurance (A)", "insurance", date(2007, 3, 1)),
    _entry("600036.SH", "China Merchants Bank", "bank", date(2002, 4, 9)),
    _entry("601398.SH", "ICBC (A)", "bank", date(2006, 10, 27)),
    _entry("600900.SH", "China Yangtze Power", "utility", date(2003, 11, 18)),
    _entry("600276.SH", "Hengrui Medicine", "pharma", date(2000, 10, 18)),
)

# Bellwether names for the regional-risk-off gate (the real-universe analog of
# the proxy strategy's KWEB/MCHI/FXI proxies): the largest, most liquid HK +
# A-share large caps. If all of these are below their 200D MA the whole region
# is treated as risk-off (see :mod:`trade.strategies.hk_china_real.construction`).
REAL_RISK_PROXIES: tuple[str, ...] = ("0700.HK", "9988.HK", "600519.SH")

REAL_UNIVERSE_TICKERS: tuple[str, ...] = tuple(
    entry.ticker for entry in REAL_HK_CHINA_UNIVERSE
)


class RealUniverseError(ValueError):
    """Raised when the offline price CSV is present but fails schema validation."""


def load_real_universe(as_of: date | None = None) -> tuple[RealUniverseEntry, ...]:
    """Candidate names visible on ``as_of`` (all if None).

    A name whose ``listing_date`` is strictly after ``as_of`` is excluded —
    point-in-time membership so the strategy never considers a name before it
    was investable."""

    if as_of is None:
        return REAL_HK_CHINA_UNIVERSE
    return tuple(
        entry for entry in REAL_HK_CHINA_UNIVERSE if entry.listing_date <= as_of
    )


def _resolve_prices_path(path: Path | None) -> Path:
    """Highest-priority on-disk source: explicit ``path`` else the unified CSV
    (``WORKBENCH_DATA_ROOT`` aware). No synthetic fixture fall-back — real CN/HK
    data only exists on the VM; offline callers inject a frame or pass ``path``."""

    if path is not None:
        return path
    return unified_prices_path(UNIFIED_PRICES_PATH)


def load_real_prices(
    as_of: date | None = None,
    *,
    path: Path | None = None,
) -> pd.DataFrame:
    """Long-format daily OHLCV (LOCAL currency) for the real CN/HK universe.

    Reads the unified real-data CSV (or an explicit ``path`` for tests),
    filters to :data:`REAL_UNIVERSE_TICKERS` and to ``date <= as_of``. Returns
    an **empty** frame (correct columns) when the source is absent — offline
    ``trade`` has no real CN/HK data, so the strategy then degrades honestly
    (fully defensive) rather than inventing prices."""

    source = _resolve_prices_path(path)
    empty = pd.DataFrame(columns=list(PRICES_REQUIRED_COLUMNS))
    if not source.is_file():
        return empty
    frame = pd.read_csv(source)
    missing = [c for c in PRICES_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise RealUniverseError(
            f"prices source {source} missing required columns {missing}"
        )
    frame = frame[frame["ticker"].isin(REAL_UNIVERSE_TICKERS)].copy()
    if frame.empty:
        return empty
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    if as_of is not None:
        frame = frame[frame["date"] <= pd.Timestamp(as_of)]
    return frame.reset_index(drop=True)


def to_usd_prices(prices: pd.DataFrame, converter: FxConverter) -> pd.DataFrame:
    """Convert every price column to USD at each row's as-of FX rate.

    The CNY|HKD → USD rate is taken **as-of the row's own ``date``** (the FX
    layer forward-fills across FRED weekend/holiday gaps), so no future rate
    ever leaks into a historical bar. A single rate scales open/high/low/
    close/adj_close together, preserving intraday relationships; ``volume`` is
    a share count and is untouched. A row whose currency has no rate on/before
    its date is **dropped** (honest — never a fabricated conversion).

    USD-quoted rows pass through unchanged. Returns a new frame (no mutation)."""

    if prices.empty:
        return prices.copy()
    rows: list[dict[str, object]] = []
    for record in prices.itertuples(index=False):
        row = record._asdict()
        ticker = str(row["ticker"])
        currency = currency_for(ticker)
        as_of = _row_date(row["date"])
        converted = _convert_row(row, currency, as_of, converter)
        if converted is not None:
            rows.append(converted)
    return pd.DataFrame(rows, columns=list(PRICES_REQUIRED_COLUMNS))


def _convert_row(
    row: dict[str, object],
    currency: str,
    as_of: date,
    converter: FxConverter,
) -> dict[str, object] | None:
    """USD copy of one price row, or None when the rate is unavailable."""

    converted: dict[str, object] = {"date": row["date"], "ticker": row["ticker"]}
    for column in _PRICE_COLUMNS:
        usd = converter.to_usd(float(cast(SupportsFloat, row[column])), currency, as_of)
        if usd is None:
            return None
        converted[column] = usd
    converted["volume"] = row["volume"]
    return converted


def _row_date(value: object) -> date:
    """Coerce a frame ``date`` cell (Timestamp / date / ISO string) to ``date``.

    ``pd.Timestamp`` is a ``datetime`` subclass, so the ``datetime`` branch
    handles it (checked before ``date`` since ``datetime`` subclasses ``date``)."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def usd_price_bars(usd_prices: pd.DataFrame) -> tuple[PriceBar, ...]:
    """:class:`PriceBar` records (USD) from a :func:`to_usd_prices` frame.

    Sorted by (date, symbol) to mirror the unified CSV layout the other
    backtest engines consume. The frame must already be USD-converted; this is
    a pure projection (``adj_close`` → ``adjusted_close``, ``ticker`` →
    ``symbol``) used by the B063 F003 comparison harness."""

    if usd_prices.empty:
        return ()
    bars: list[PriceBar] = []
    for record in usd_prices.itertuples(index=False):
        row = record._asdict()
        bars.append(
            PriceBar(
                date=_row_date(row["date"]),
                symbol=str(row["ticker"]),
                open=float(row["open"]),
                close=float(row["close"]),
                adjusted_close=float(row["adj_close"]),
                volume=int(row["volume"]),
            )
        )
    bars.sort(key=lambda bar: (bar.date, bar.symbol))
    return tuple(bars)
