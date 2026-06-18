"""B065 F001 — point-in-time A-share liquid universe builder.

Builds a WIDE A-share universe with **point-in-time membership**: at each
rebalance date, ranks candidate tickers by trailing market cap + turnover using
ONLY data dated ``<= as_of`` (no future leakage) and takes the top N. This is
the data foundation for the next batch's momentum+quality attack strategy —
selecting names *by rule, point-in-time* instead of backtesting hand-picked
winners (the survivorship / hindsight-bias hard lesson, B063 §2).

§23 (framework v0.9.45) reachability — verified by real akshare runs
(``scripts/test/ashare_universe_probe.py``; re-run on the VM by Codex for F004):

* **Historical market cap — REACHABLE.** ``stock_value_em(code)`` returns the
  full daily history of 总市值 (total market cap, raw CNY) + 总股本 (shares) +
  流通市值 from ~2018 to today, on the eastmoney *finance* host (reachable from
  both the dev box and the prod VM). This IS the point-in-time mcap source — the
  spec's fallback (volume×close + shares approximation) is not needed for mcap.
* **Turnover — offline / reachable.** ``成交额 ≈ volume × close`` is computed
  from the unified prices CSV the refresh already writes (spec §3 F001 blessed
  proxy), so it needs no extra endpoint.
* **Bulk superset discovery — BEST-EFFORT.** ``stock_zh_a_spot_em`` & friends
  route through the eastmoney *push* hosts (SSL-fail from the dev box, unreliable
  on the VM, B062 lesson). So discovery degrades to the curated
  :data:`CN_UNIVERSE_SEED`; see :mod:`workbench_api.data_refresh.cn_marketcap`.

Layering (§12.10.2 / §12.10.3): akshare lives only in the workbench job (the
loader is injected); ``trade`` stays offline and only reads the resulting CSVs.
This module imports neither ``trade`` nor a broker SDK — the akshare loader is a
``MarketCapLoader`` Protocol, faked in tests.

Survivorship bias (honest residual, B063 method discipline): the fetch superset
is current-listed liquid large-caps (the seed, or a VM bulk-spot snapshot). It
cannot include names delisted before today without a paid historical-constituents
feed, so the universe slightly over-represents survivors. The point-in-time
*ranking* within the superset is leakage-free (it ranks on data at the rebalance
date), which is the material anti-lookahead guarantee; the residual listing bias
is documented here and in the membership CSV header.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# --- the curated wide fetch superset (residual survivorship bias: current-listed
# liquid large-caps, CSI300-style across sectors — all non-ST blue chips). The
# point-in-time ranking below narrows this to the top-N at each rebalance; this
# set only bounds *which* names are ever considered. A VM bulk-spot snapshot can
# widen it (best-effort), with ST / 退市 names filtered out (:func:`is_st_name`).
CN_UNIVERSE_SEED: tuple[str, ...] = (
    # Shanghai (.SH)
    "600519.SH",  # 贵州茅台
    "601318.SH",  # 中国平安
    "600036.SH",  # 招商银行
    "601398.SH",  # 工商银行
    "601288.SH",  # 农业银行
    "601988.SH",  # 中国银行
    "601166.SH",  # 兴业银行
    "600000.SH",  # 浦发银行
    "600900.SH",  # 长江电力
    "600276.SH",  # 恒瑞医药
    "601012.SH",  # 隆基绿能
    "600028.SH",  # 中国石化
    "601857.SH",  # 中国石油
    "600585.SH",  # 海螺水泥
    "601899.SH",  # 紫金矿业
    "600309.SH",  # 万华化学
    "600887.SH",  # 伊利股份
    "603288.SH",  # 海天味业
    "600030.SH",  # 中信证券
    "601601.SH",  # 中国太保
    "600809.SH",  # 山西汾酒
    "601728.SH",  # 中国电信
    "600941.SH",  # 中国移动
    "688981.SH",  # 中芯国际
    "688111.SH",  # 金山办公
    "603501.SH",  # 韦尔股份
    "600196.SH",  # 复星医药
    "603259.SH",  # 药明康德
    "600031.SH",  # 三一重工
    # Shenzhen (.SZ)
    "000858.SZ",  # 五粮液
    "000333.SZ",  # 美的集团
    "300750.SZ",  # 宁德时代
    "000651.SZ",  # 格力电器
    "002594.SZ",  # 比亚迪
    "002415.SZ",  # 海康威视
    "000568.SZ",  # 泸州老窖
    "002304.SZ",  # 洋河股份
    "300760.SZ",  # 迈瑞医疗
    "300059.SZ",  # 东方财富
    "000001.SZ",  # 平安银行
    "000002.SZ",  # 万科A
    "002475.SZ",  # 立讯精密
    "000725.SZ",  # 京东方A
)

UNIVERSE_RELPATH = ("snapshots", "universe", "cn_pit_universe.csv")
MARKETCAP_RELPATH = ("snapshots", "universe", "cn_marketcap.csv")

UNIVERSE_HEADER = [
    "as_of_date",
    "ticker",
    "rank",
    "market_cap",
    "avg_turnover",
    "composite_score",
]
MARKETCAP_HEADER = ["data_date", "ticker", "total_mv", "circ_mv", "total_shares", "close"]

DEFAULT_TOP_N = 200
DEFAULT_TURNOVER_WINDOW = 60
# Equal weight on size + liquidity (spec §3 F001: "市值 + 成交额").
_MCAP_WEIGHT = 0.5
_TURNOVER_WEIGHT = 0.5


@dataclass(frozen=True, slots=True)
class MarketCapBar:
    """One daily valuation observation (from akshare ``stock_value_em``).

    The universe builder (F001) uses ``total_mv``; the CN fundamentals builder
    (F002) reuses the same series for ``close`` / ``pe_ttm`` / ``pb`` at each
    quarter's disclosure date (no second fetch)."""

    ticker: str  # canonical, e.g. 600519.SH
    bar_date: date
    total_mv: float  # 总市值, raw CNY
    circ_mv: float | None = None  # 流通市值
    total_shares: float | None = None  # 总股本
    close: float | None = None  # 当日收盘价
    pe_ttm: float | None = None  # PE(TTM)  — B065 F002
    pb: float | None = None  # 市净率     — B065 F002


@dataclass(frozen=True, slots=True)
class UniverseMember:
    """One point-in-time universe membership row for a rebalance date."""

    as_of: date
    ticker: str
    rank: int
    market_cap: float
    avg_turnover: float
    composite_score: float


class MarketCapLoader(Protocol):
    """Injected akshare-backed historical market-cap source (see cn_marketcap)."""

    def fetch_market_cap_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[MarketCapBar]: ...


# --------------------------------------------------------------------------- #
# Pure point-in-time ranking (no akshare, no IO — exhaustively unit-tested)
# --------------------------------------------------------------------------- #


def is_st_name(name: str) -> bool:
    """True for a China risk-warning / delisting stock name (B065 F001 feedback).

    ST / *ST (风险警示) and 退市 (delisting) names carry a name prefix in akshare's
    snapshot. The universe excludes them so the next batch's **pure-momentum**
    variant can't pick a speculative ST momentum name (2026-06-18 strategy
    decision). Detection is on the display name (``名称``): ``*`` stripped, an
    ``ST`` prefix (case-insensitive) or a ``退`` (退市) prefix marks it."""

    cleaned = (name or "").strip().upper().lstrip("*").strip()
    return cleaned.startswith("ST") or cleaned.startswith("退")


def percent_rank(values: Mapping[str, float]) -> dict[str, float]:
    """Cross-sectional percentile in ``[0, 1]``; ties share the average rank.

    Empty → ``{}``; a single value → ``0.5`` (mid). Deterministic."""

    items = list(values.items())
    n = len(items)
    if n == 0:
        return {}
    if n == 1:
        return {items[0][0]: 0.5}
    ordered = sorted(v for _, v in items)
    ranks: dict[str, float] = {}
    for ticker, value in items:
        less = sum(1 for x in ordered if x < value)
        equal = sum(1 for x in ordered if x == value)
        avg_position = less + (equal - 1) / 2.0
        ranks[ticker] = avg_position / (n - 1)
    return ranks


def latest_market_cap(bars: Sequence[MarketCapBar], as_of: date) -> MarketCapBar | None:
    """The most recent market-cap bar dated ``<= as_of`` (point-in-time)."""

    visible = [bar for bar in bars if bar.bar_date <= as_of]
    if not visible:
        return None
    return max(visible, key=lambda bar: bar.bar_date)


def trailing_avg_turnover(
    turnover_bars: Sequence[tuple[date, float]], as_of: date, window_days: int
) -> float | None:
    """Average of the last ``window_days`` turnover observations dated ``<= as_of``.

    ``None`` when no observation is visible at ``as_of`` (illiquid / not yet
    listed / suspended)."""

    visible = sorted((day, turnover) for day, turnover in turnover_bars if day <= as_of)
    if not visible:
        return None
    tail = visible[-window_days:] if window_days > 0 else visible
    return sum(turnover for _, turnover in tail) / len(tail)


def point_in_time_top_n(
    as_of: date,
    market_caps: Mapping[str, Sequence[MarketCapBar]],
    turnover_bars: Mapping[str, Sequence[tuple[date, float]]],
    *,
    top_n: int = DEFAULT_TOP_N,
    turnover_window_days: int = DEFAULT_TURNOVER_WINDOW,
) -> list[UniverseMember]:
    """Rank candidates by composite (market cap + trailing turnover) at ``as_of``.

    Uses ONLY data dated ``<= as_of`` — a ticker with no market-cap bar visible
    at ``as_of`` (not yet listed / no history) is excluded, which makes
    membership point-in-time and structurally leakage-free. Ties break on ticker
    for determinism. Returns at most ``top_n`` members, ranked 1..N."""

    mcap: dict[str, float] = {}
    turnover: dict[str, float] = {}
    for ticker, bars in market_caps.items():
        latest = latest_market_cap(bars, as_of)
        if latest is None or latest.total_mv <= 0:
            continue
        mcap[ticker] = latest.total_mv
        avg = trailing_avg_turnover(turnover_bars.get(ticker, ()), as_of, turnover_window_days)
        turnover[ticker] = avg if avg is not None else 0.0

    if not mcap:
        return []

    mcap_rank = percent_rank(mcap)
    turnover_rank = percent_rank(turnover)
    composite = {
        ticker: _MCAP_WEIGHT * mcap_rank[ticker] + _TURNOVER_WEIGHT * turnover_rank[ticker]
        for ticker in mcap
    }
    ordered = sorted(composite, key=lambda ticker: (-composite[ticker], ticker))[:top_n]
    return [
        UniverseMember(
            as_of=as_of,
            ticker=ticker,
            rank=index + 1,
            market_cap=mcap[ticker],
            avg_turnover=turnover[ticker],
            composite_score=round(composite[ticker], 6),
        )
        for index, ticker in enumerate(ordered)
    ]


def quarterly_rebalance_dates(from_date: date, to_date: date) -> list[date]:
    """Quarter-end calendar dates within ``[from_date, to_date]`` (rebalance grid).

    The point-in-time builder resolves each to the latest trading bar ``<= as_of``,
    so calendar quarter-ends (not trading days) are fine as the grid."""

    quarter_ends = ((3, 31), (6, 30), (9, 30), (12, 31))
    out: list[date] = []
    for year in range(from_date.year, to_date.year + 1):
        for month, day in quarter_ends:
            candidate = date(year, month, day)
            if from_date <= candidate <= to_date:
                out.append(candidate)
    return out


# --------------------------------------------------------------------------- #
# Turnover from the unified prices CSV (成交额 ≈ volume × close)
# --------------------------------------------------------------------------- #


def turnover_from_price_rows(
    rows: Sequence[Mapping[str, str]], members: Sequence[str]
) -> dict[str, list[tuple[date, float]]]:
    """``成交额 ≈ volume × close`` per (ticker, day) for the member tickers.

    ``rows`` are dict-rows of the unified prices CSV (header
    ``date,ticker,...,close,adj_close,volume``). Malformed rows are skipped."""

    wanted = set(members)
    out: dict[str, list[tuple[date, float]]] = {ticker: [] for ticker in wanted}
    for row in rows:
        ticker = row.get("ticker", "")
        if ticker not in wanted:
            continue
        try:
            day = date.fromisoformat(row["date"])
            turnover = float(row["close"]) * float(row["volume"])
        except (KeyError, ValueError, TypeError):
            continue
        out[ticker].append((day, turnover))
    return out


def _marketcap_to_row(bar: MarketCapBar) -> list[object]:
    return [
        bar.bar_date.isoformat(),
        bar.ticker,
        bar.total_mv,
        bar.circ_mv,
        bar.total_shares,
        bar.close,
    ]


def _read_price_rows(prices_path: Path) -> list[dict[str, str]]:
    if not prices_path.is_file():
        return []
    with prices_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


# --------------------------------------------------------------------------- #
# Orchestrator: fetch market caps + compute PIT membership + write the CSVs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CnUniverseSummary:
    superset_size: int
    marketcap_symbols: int
    marketcap_rows: int
    rebalance_dates: int
    universe_rows: int
    errors: int
    marketcap_path: str
    universe_path: str


def build_cn_universe(
    *,
    data_root: Path,
    prices_path: Path,
    marketcap_loader: MarketCapLoader,
    superset: Sequence[str],
    rebalance_dates: Sequence[date],
    from_date: date,
    to_date: date,
    top_n: int = DEFAULT_TOP_N,
    turnover_window_days: int = DEFAULT_TURNOVER_WINDOW,
) -> CnUniverseSummary:
    """Fetch historical market caps for ``superset`` (best-effort per symbol),
    compute point-in-time top-N membership for each rebalance date, and write
    ``cn_marketcap.csv`` + ``cn_pit_universe.csv`` under ``data_root``.

    Budget/duration aware: one ``stock_value_em`` call per superset symbol — the
    caller bounds ``superset`` size (the seed is ~40; a VM bulk-spot snapshot is
    capped). A per-symbol fetch failure is logged + counted, never fatal."""

    marketcap_path = data_root.joinpath(*MARKETCAP_RELPATH)
    universe_path = data_root.joinpath(*UNIVERSE_RELPATH)
    logger.info(
        "cn_universe_build_start",
        extra={"superset": len(superset), "rebalances": len(rebalance_dates), "top_n": top_n},
    )

    market_caps: dict[str, list[MarketCapBar]] = {}
    marketcap_rows: list[list[object]] = []
    errors = 0
    for ticker in superset:
        try:
            bars = marketcap_loader.fetch_market_cap_history(ticker, from_date, to_date)
        except Exception:  # noqa: BLE001 — best-effort; a bad symbol never aborts
            errors += 1
            logger.exception("cn_universe_marketcap_fetch_failure", extra={"ticker": ticker})
            continue
        if not bars:
            continue
        market_caps[ticker] = bars
        marketcap_rows.extend(_marketcap_to_row(bar) for bar in bars)
    _write_csv(marketcap_path, MARKETCAP_HEADER, marketcap_rows)

    turnover_bars = turnover_from_price_rows(_read_price_rows(prices_path), list(market_caps))

    universe_rows: list[list[object]] = []
    for as_of in rebalance_dates:
        members = point_in_time_top_n(
            as_of,
            market_caps,
            turnover_bars,
            top_n=top_n,
            turnover_window_days=turnover_window_days,
        )
        universe_rows.extend(
            [m.as_of.isoformat(), m.ticker, m.rank, m.market_cap, m.avg_turnover, m.composite_score]
            for m in members
        )
    _write_csv(universe_path, UNIVERSE_HEADER, universe_rows)

    summary = CnUniverseSummary(
        superset_size=len(superset),
        marketcap_symbols=len(market_caps),
        marketcap_rows=len(marketcap_rows),
        rebalance_dates=len(rebalance_dates),
        universe_rows=len(universe_rows),
        errors=errors,
        marketcap_path=str(marketcap_path),
        universe_path=str(universe_path),
    )
    logger.info(
        "cn_universe_build_done",
        extra={
            "marketcap_symbols": summary.marketcap_symbols,
            "universe_rows": summary.universe_rows,
            "errors": errors,
        },
    )
    return summary
