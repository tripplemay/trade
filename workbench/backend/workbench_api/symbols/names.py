"""B079 F001 — curated static symbol → display-name seed + resolver.

The display layer wants a name for **every** ticker it shows (name primary,
code secondary — ``贵州茅台  600519.SH``). Two complementary sources feed the
``symbol_name`` store:

* **Curated static seed** (:data:`CURATED_SYMBOL_NAMES`) — the bounded, stable
  universes whose names never change day-to-day: the 27 US-quality equities
  (single-source-of-truth import of :data:`news.ticker_match._UNIVERSE_NAMES`),
  the 15 satellite/regime ETFs (hand-curated here — ETFs carry no name anywhere
  else in the repo), and the 26 CN/HK large caps (English names, kept in lockstep
  with the trade-side authority ``trade.data.hk_china_real_universe`` by a guard
  test — copied locally rather than imported so this display module stays free of
  the heavy ``trade``/pandas backtest deps, matching the lazy-``trade`` convention
  the rest of ``workbench_api`` follows). Seeded into the DB by
  ``workbench-bootstrap`` and always available in-process via the resolver below,
  so coverage never depends on a seed job having run.
* **Live A-share capture** — Chinese names (``贵州茅台``) harvested for free from
  the akshare spot 「名称」 column already fetched daily by the data-refresh job,
  written with ``source="akshare_spot"``. These are *fresher and better* than
  the static English CN fallback, so the resolver lets the DB row win.

:func:`resolve_symbol_names` is the single enrich entry point used by the
response-model assemblers (F002): it merges the curated static names with the
pure-DB batch read, DB taking precedence. Missing symbols are simply absent —
the caller falls back to the raw code (B079 invariant ③: 缺失优雅 fallback 纯 code).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from workbench_api.db.repositories.symbol_name import SymbolNameRepository
from workbench_api.news.ticker_match import _UNIVERSE_NAMES

# The 26 CN/HK large caps (``data_refresh.refresh.CN_HK_UNIVERSE``), English
# display names. Copied verbatim from ``trade.data.hk_china_real_universe`` —
# ``test_cn_hk_curated_names_match_trade_authority`` fails on any drift — rather
# than imported, so this display module stays free of the heavy trade/pandas
# backtest deps. Live akshare capture layers the Chinese A-share names on top.
_CN_HK_NAMES: dict[str, str] = {
    # Hong Kong (HKD)
    "0700.HK": "Tencent",
    "9988.HK": "Alibaba (HK)",
    "3690.HK": "Meituan",
    "1810.HK": "Xiaomi",
    "9618.HK": "JD.com (HK)",
    "9999.HK": "NetEase (HK)",
    "0941.HK": "China Mobile",
    "0939.HK": "China Construction Bank",
    "1398.HK": "ICBC",
    "1288.HK": "Agricultural Bank of China",
    "2318.HK": "Ping An Insurance (H)",
    "2628.HK": "China Life (H)",
    "1299.HK": "AIA Group",
    "0883.HK": "CNOOC",
    "0386.HK": "Sinopec",
    "0388.HK": "Hong Kong Exchanges",
    # Mainland A-share (CNY)
    "600519.SH": "Kweichow Moutai",
    "000858.SZ": "Wuliangye",
    "000333.SZ": "Midea Group",
    "300750.SZ": "CATL",
    "601012.SH": "LONGi Green Energy",
    "601318.SH": "Ping An Insurance (A)",
    "600036.SH": "China Merchants Bank",
    "601398.SH": "ICBC (A)",
    "600900.SH": "China Yangtze Power",
    "600276.SH": "Hengrui Medicine",
}

# The 15 satellite/regime ETFs (``data_refresh.refresh.ETF_UNIVERSE``). ETFs
# have no SEC fundamentals and no name row anywhere else in the repo, so their
# official fund names are curated here (bounded, stable set).
_ETF_NAMES: dict[str, str] = {
    "AGG": "iShares Core U.S. Aggregate Bond ETF",
    "ASHR": "Xtrackers Harvest CSI 300 China A-Shares ETF",
    "DBC": "Invesco DB Commodity Index Tracking Fund",
    "EEM": "iShares MSCI Emerging Markets ETF",
    "FXI": "iShares China Large-Cap ETF",
    "GLD": "SPDR Gold Shares",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "KWEB": "KraneShares CSI China Internet ETF",
    "MCHI": "iShares MSCI China ETF",
    "QQQ": "Invesco QQQ Trust",
    "SGOV": "iShares 0-3 Month Treasury Bond ETF",
    "SPY": "SPDR S&P 500 ETF Trust",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "VEA": "Vanguard FTSE Developed Markets ETF",
    "VWO": "Vanguard FTSE Emerging Markets ETF",
}


def normalize_symbol(symbol: str) -> str:
    """Canonical store key: trimmed + uppercased.

    Keys the whole surface identically — ``aapl`` → ``AAPL``, ``600519.sh`` →
    ``600519.SH``, ``0700.hk`` → ``0700.HK`` — matching the akshare-captured
    canonical form and every downstream ticker string.
    """

    return symbol.strip().upper()


def _build_curated() -> dict[str, str]:
    """Merge the three static name sources into one uppercased mapping."""

    curated: dict[str, str] = {}
    curated.update({normalize_symbol(t): n for t, n in _UNIVERSE_NAMES.items()})
    curated.update({normalize_symbol(t): n for t, n in _ETF_NAMES.items()})
    curated.update({normalize_symbol(t): n for t, n in _CN_HK_NAMES.items()})
    return curated


# Bounded curated static name map (US 27 + ETF 15 + CN/HK 26 ≈ 68 symbols),
# keyed by normalized (uppercased) symbol. Immutable snapshot at import time.
CURATED_SYMBOL_NAMES: dict[str, str] = _build_curated()


def resolve_symbol_names(
    session: Session, symbols: Iterable[str]
) -> dict[str, str]:
    """Batch-resolve display names for ``symbols`` → ``{normalized_symbol: name}``.

    Merges the curated static seed with a single pure-DB batch read
    (:meth:`SymbolNameRepository.get_names`); the DB row wins on conflict so a
    live-captured A-share Chinese name (``贵州茅台``) overrides the static English
    fallback (``Kweichow Moutai``). Symbols with no name in either source are
    absent from the result — the caller renders the raw code.

    Keys are normalized (uppercased); look up with ``normalize_symbol(sym)`` or
    an already-uppercased ticker.
    """

    wanted = sorted({normalize_symbol(s) for s in symbols if s and s.strip()})
    if not wanted:
        return {}
    curated = {s: CURATED_SYMBOL_NAMES[s] for s in wanted if s in CURATED_SYMBOL_NAMES}
    live = SymbolNameRepository(session).get_names(wanted)
    return {**curated, **live}
