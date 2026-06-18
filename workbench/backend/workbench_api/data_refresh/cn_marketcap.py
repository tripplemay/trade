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
from datetime import date
from typing import Any

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

# stock_zh_a_spot_em column names (best-effort discovery).
_SPOT_COL_CODE = "代码"
_SPOT_COL_NAME = "名称"
_SPOT_COL_TOTAL_MV = "总市值"


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
    """6-digit A-share spot code → canonical (.SH for 6xx/9xx, else .SZ)."""

    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    suffix = "SH" if digits[0] in {"6", "9"} else "SZ"
    candidate = f"{digits}.{suffix}"
    try:
        return SymbolRef.parse(candidate).canonical
    except Exception:
        return None


def discover_ashare_superset(
    akshare_module: Any | None = None, *, top_n: int = 300
) -> tuple[tuple[str, ...], str]:
    """Best-effort current top-``top_n`` A-share names by market cap.

    Returns ``(symbols, provenance)`` where provenance is ``"bulk_spot"`` when
    the ``stock_zh_a_spot_em`` snapshot succeeded, else ``"seed"`` (the curated
    fallback — the §23-honest degrade when the push host is unreachable). ST /
    退市 risk-warning names are filtered out (B065 F001). The seed is always
    unioned in (it is curated non-ST) so discovery never drops a curated name."""

    akshare = akshare_module
    if akshare is None:
        try:
            akshare = importlib.import_module("akshare")
        except Exception:
            return CN_UNIVERSE_SEED, "seed"

    records, columns = frame_records(akshare, "stock_zh_a_spot_em")
    if not records or _SPOT_COL_CODE not in columns or _SPOT_COL_TOTAL_MV not in columns:
        logger.warning("cn_universe_superset_discovery_unreachable_using_seed")
        return CN_UNIVERSE_SEED, "seed"

    ranked: list[tuple[float, str]] = []
    for record in records:
        # B065 F001 — exclude ST / 退市 risk-warning names (protects the next
        # batch's pure-momentum variant from speculative ST momentum picks).
        if is_st_name(str(record.get(_SPOT_COL_NAME, ""))):
            continue
        canonical = _spot_code_to_canonical(record.get(_SPOT_COL_CODE, ""))
        total_mv = coerce_float(record.get(_SPOT_COL_TOTAL_MV))
        if canonical is None or total_mv is None or total_mv <= 0:
            continue
        ranked.append((total_mv, canonical))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    discovered = [canonical for _, canonical in ranked[:top_n]]
    # Union the curated seed so a hand-picked name is never dropped.
    union = list(dict.fromkeys([*discovered, *CN_UNIVERSE_SEED]))
    logger.info("cn_universe_superset_discovered", extra={"count": len(union)})
    return tuple(union), "bulk_spot"
