"""B065 F001 — akshare-backed historical market-cap loader + superset discovery.

The §23-verified data source for the point-in-time universe builder
(:mod:`workbench_api.data_refresh.cn_universe`):

* :class:`CnMarketCapLoader` wraps akshare ``stock_value_em(code)`` → a daily
  history of 总市值 / 流通市值 / 总股本 / 当日收盘价 (raw CNY) per A-share
  ticker. **Reachable from both the dev box and the prod VM** (eastmoney finance
  host) — verified by ``scripts/test/ashare_universe_probe.py``.
* :func:`discover_ashare_superset` is a **best-effort** bulk-snapshot widener
  (current top-N by market cap via ``stock_zh_a_spot_em``). That endpoint routes
  through an eastmoney *push* host which SSL-fails off-box and is unreliable on
  the VM (B062 lesson), so on ANY failure it degrades to the curated
  :data:`~workbench_api.data_refresh.cn_universe.CN_UNIVERSE_SEED`.

**akshare lives only in this workbench job** — lazy-imported inside the methods
so the module loads where the heavy lib is absent (tests inject a fake). This
module imports neither ``trade`` nor a broker SDK (the no-broker banlist is
futu / tiger / ib / alpaca / …, which this never touches).
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence
from datetime import date
from typing import Any

from workbench_api.data_refresh.call_timeout import FetchTimeoutError, call_with_timeout
from workbench_api.data_refresh.cn_universe import (
    CN_UNIVERSE_SEED,
    MarketCapBar,
    is_st_name,
)
from workbench_api.symbols.akshare_frames import coerce_date, coerce_float, frame_records
from workbench_api.symbols.symbol_ref import SymbolRef

logger = logging.getLogger(__name__)

# stock_value_em column names (Chinese headers, eastmoney finance host).
_COL_DATE = "数据日期"
_COL_CLOSE = "当日收盘价"
_COL_TOTAL_MV = "总市值"
_COL_CIRC_MV = "流通市值"
_COL_TOTAL_SHARES = "总股本"
_COL_PE_TTM = "PE(TTM)"
_COL_PB = "市净率"

# stock_zh_a_spot_em column names (eastmoney push host — best-effort discovery).
_SPOT_COL_CODE = "代码"
_SPOT_COL_NAME = "名称"
_SPOT_COL_TOTAL_MV = "总市值"

# stock_zh_a_spot (sina host) column names. B068 F001 §23: the sina spot is the
# bulk endpoint that actually answers on the prod VM (the eastmoney push hosts
# ConnectionError there). It carries NO 总市值, so 成交额 (today's turnover) is
# the only liquidity field available to bound the candidate pool — the
# point-in-time builder re-ranks on historical market cap afterwards. Its 代码 is
# exchange-prefixed (``sh600519`` / ``sz000858`` / ``bj920000``), unlike the
# eastmoney bare 6-digit code.
_SINA_COL_CODE = "代码"
_SINA_COL_NAME = "名称"
_SINA_COL_AMOUNT = "成交额"


def _bar_from_record(record: dict[str, Any], ticker: str) -> MarketCapBar | None:
    bar_date = coerce_date(record.get(_COL_DATE))
    total_mv = coerce_float(record.get(_COL_TOTAL_MV))
    if bar_date is None or total_mv is None:
        return None
    return MarketCapBar(
        ticker=ticker,
        bar_date=bar_date,
        total_mv=total_mv,
        circ_mv=coerce_float(record.get(_COL_CIRC_MV)),
        total_shares=coerce_float(record.get(_COL_TOTAL_SHARES)),
        close=coerce_float(record.get(_COL_CLOSE)),
        pe_ttm=coerce_float(record.get(_COL_PE_TTM)),
        pb=coerce_float(record.get(_COL_PB)),
    )


class CnMarketCapLoader:
    """akshare ``stock_value_em`` → daily :class:`MarketCapBar` history.

    Matches the ``cn_universe.MarketCapLoader`` Protocol. A network / host failure
    degrades to an empty list (the orchestrator counts it best-effort), never
    raises a 500-class error."""

    def __init__(self, akshare_module: Any | None = None) -> None:
        self._akshare = akshare_module

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def fetch_market_cap_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[MarketCapBar]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        code = SymbolRef.parse(ticker).code
        records, _ = frame_records(akshare, "stock_value_em", symbol=code)
        bars = [
            bar
            for record in records
            if (bar := _bar_from_record(record, ticker)) is not None
            and from_date <= bar.bar_date <= to_date
        ]
        bars.sort(key=lambda bar: bar.bar_date)
        return bars


def _spot_code_to_canonical(code: str) -> str | None:
    """6-digit eastmoney A-share spot code → canonical (.SH for 6xx/9xx, else .SZ)."""

    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    suffix = "SH" if digits[0] in {"6", "9"} else "SZ"
    candidate = f"{digits}.{suffix}"
    try:
        return SymbolRef.parse(candidate).canonical
    except Exception:
        return None


def _sina_code_to_canonical(code: str) -> str | None:
    """Exchange-prefixed sina spot code → canonical.

    ``sh600519`` → ``600519.SH``, ``sz000858`` → ``000858.SZ``. 北交所 (``bj``
    prefix) names have no ``.SH`` / ``.SZ`` canonical and are out of scope for
    this liquid large-cap universe, so they return ``None`` (B068 F001)."""

    raw = str(code).strip().lower()
    if len(raw) != 8:
        return None
    prefix, digits = raw[:2], raw[2:]
    if not digits.isdigit():
        return None
    suffix = {"sh": "SH", "sz": "SZ"}.get(prefix)
    if suffix is None:  # bj (北交所) or any unexpected prefix → out of scope
        return None
    try:
        return SymbolRef.parse(f"{digits}.{suffix}").canonical
    except Exception:
        return None


def _union_with_seed(discovered: Sequence[str]) -> tuple[str, ...]:
    """Discovered names with the curated seed appended (order-preserving dedupe).

    The seed is curated non-ST blue chips, so unioning it guarantees a
    hand-picked name is never dropped regardless of the snapshot's coverage."""

    return tuple(dict.fromkeys([*discovered, *CN_UNIVERSE_SEED]))


def _discover_from_eastmoney(
    akshare: Any, top_n: int, *, timeout_seconds: float = 0.0
) -> list[str] | None:
    """eastmoney ``stock_zh_a_spot_em`` ranked by 总市值 (market cap).

    Returns the top-``top_n`` canonical symbols, or ``None`` when the endpoint is
    unreachable / unparseable / times out (so the caller can try the next source).
    ST / 退市 names are filtered out (B065 F001). B078 F001: the bulk fetch is
    bounded by ``timeout_seconds`` (0 = inline) so a silent network hang on this
    eastmoney push host — documented unreliable off-box and on the VM — degrades
    to the next source / seed instead of wedging the daily refresh before any
    prices are written."""

    try:
        records, columns = call_with_timeout(
            timeout_seconds, frame_records, akshare, "stock_zh_a_spot_em"
        )
    except FetchTimeoutError:
        logger.warning("cn_universe_superset_eastmoney_timed_out")
        return None
    if not records or _SPOT_COL_CODE not in columns or _SPOT_COL_TOTAL_MV not in columns:
        return None
    ranked: list[tuple[float, str]] = []
    for record in records:
        if is_st_name(str(record.get(_SPOT_COL_NAME, ""))):
            continue
        canonical = _spot_code_to_canonical(record.get(_SPOT_COL_CODE, ""))
        total_mv = coerce_float(record.get(_SPOT_COL_TOTAL_MV))
        if canonical is None or total_mv is None or total_mv <= 0:
            continue
        ranked.append((total_mv, canonical))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [canonical for _, canonical in ranked[:top_n]]


def _discover_from_sina(
    akshare: Any, top_n: int, *, timeout_seconds: float = 0.0
) -> list[str] | None:
    """sina ``stock_zh_a_spot`` ranked by 成交额 (today's turnover).

    Returns the top-``top_n`` canonical symbols, or ``None`` when unreachable /
    unparseable / times out. The sina snapshot carries no 总市值, so turnover is the
    liquidity proxy that bounds the candidate pool; the point-in-time builder
    re-ranks on historical market cap afterwards, so this only decides *which*
    names are ever fetched. ST / 退市 and 北交所 (``bj``) names are filtered out
    (B068 F001). B078 F001: bounded by ``timeout_seconds`` (0 = inline) so a hang
    on the bulk fetch degrades to the curated seed rather than wedging the refresh."""

    try:
        records, columns = call_with_timeout(
            timeout_seconds, frame_records, akshare, "stock_zh_a_spot"
        )
    except FetchTimeoutError:
        logger.warning("cn_universe_superset_sina_timed_out")
        return None
    if not records or _SINA_COL_CODE not in columns or _SINA_COL_AMOUNT not in columns:
        return None
    ranked: list[tuple[float, str]] = []
    for record in records:
        if is_st_name(str(record.get(_SINA_COL_NAME, ""))):
            continue
        canonical = _sina_code_to_canonical(record.get(_SINA_COL_CODE, ""))
        turnover = coerce_float(record.get(_SINA_COL_AMOUNT))
        if canonical is None or turnover is None or turnover <= 0:
            continue
        ranked.append((turnover, canonical))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [canonical for _, canonical in ranked[:top_n]]


def discover_ashare_superset(
    akshare_module: Any | None = None,
    *,
    top_n: int = 300,
    allow_sina_fallback: bool = False,
    fetch_timeout_seconds: float | None = None,
) -> tuple[tuple[str, ...], str]:
    """Best-effort current top-``top_n`` A-share names by liquidity.

    Tries the widest reachable bulk-snapshot endpoint in turn, returning
    ``(symbols, provenance)``:

    * ``"bulk_spot"`` — eastmoney ``stock_zh_a_spot_em`` ranked by 总市值. The
      richest source, but it routes through an eastmoney *push* host that
      SSL-/Connection-fails off-box AND on the prod VM (B062/B065 lesson).
    * ``"sina_spot"`` — sina ``stock_zh_a_spot`` ranked by 成交额 turnover. **The
      §23-verified VM-reachable bulk endpoint** (B068 F001: the eastmoney push
      hosts ConnectionError on the VM while the sina spot answers with the full
      ~5500-name market). 北交所 (``bj``) + ST / 退市 names are filtered out.
      **Opt-in only** (see below).
    * ``"seed"`` — the curated :data:`CN_UNIVERSE_SEED` fallback when no bulk
      endpoint answers (the §23-honest degrade).

    ``allow_sina_fallback`` gates the sina branch and **defaults False so the
    production daily refresh's behaviour is byte-identical to B065/B067**: on the
    VM the eastmoney push host fails and discovery degrades to the curated seed,
    so B067's live cn_attack advisory keeps consuming the seed-43 universe it is
    calibrated to. Only the B068 research wide-universe build passes ``True`` (and
    writes to a research data root), so the wide universe never leaks into the
    live advisory surface (spec invariant #1, "不改 B067 surface").

    The seed is always unioned in (curated non-ST) so discovery never drops a
    curated name. The per-symbol historical-mcap fetch in
    :func:`~workbench_api.data_refresh.cn_universe.build_cn_universe` then re-ranks
    this candidate pool point-in-time."""

    # B078 F001 — bound each bulk akshare discovery call (0 / None = inline). This
    # is the LAST unbounded A-share network op on the daily critical path, and it
    # runs BEFORE the price refresh, so a silent hang here would re-freeze the daily
    # 命门 (no prices written) until the systemd watchdog. Per-source bound so a
    # hung eastmoney push host still lets the VM-reachable sina source run.
    timeout = fetch_timeout_seconds or 0.0
    akshare = akshare_module
    if akshare is None:
        try:
            akshare = importlib.import_module("akshare")
        except Exception:
            return CN_UNIVERSE_SEED, "seed"

    discovered = _discover_from_eastmoney(akshare, top_n, timeout_seconds=timeout)
    if discovered is not None:
        union = _union_with_seed(discovered)
        logger.info(
            "cn_universe_superset_discovered",
            extra={"count": len(union), "provenance": "bulk_spot"},
        )
        return union, "bulk_spot"

    if allow_sina_fallback:
        discovered = _discover_from_sina(akshare, top_n, timeout_seconds=timeout)
        if discovered is not None:
            union = _union_with_seed(discovered)
            logger.info(
                "cn_universe_superset_discovered",
                extra={"count": len(union), "provenance": "sina_spot"},
            )
            return union, "sina_spot"

    logger.warning("cn_universe_superset_discovery_unreachable_using_seed")
    return CN_UNIVERSE_SEED, "seed"
