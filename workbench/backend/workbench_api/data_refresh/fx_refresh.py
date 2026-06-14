"""B063 F001 — FX layer: FRED CNY/USD + HKD/USD historical rates into the pipeline.

Fetches the daily FX history from FRED (DEXCHUS = Chinese Yuan per USD, DEXHKUS =
HK Dollars per USD — central-bank authoritative, decades of history) and writes a
unified FX CSV (``snapshots/fx/unified/fx_daily.csv``; columns
``date,currency,rate``) that the ``trade`` engine reads offline for backtest USD
conversion (:mod:`trade.data.fx`). FRED runs only here in the workbench job —
``trade`` never imports it (offline edge).

The CSV stores the raw valid observations (FRED's ``"."`` missing points are
already skipped by the loader); calendar alignment + forward-fill is applied
**on read** by :class:`trade.data.fx.FxConverter` (as-of lookup), so the file
stays compact and any query date resolves to the most-recent prior rate.

For backtest USD conversion only (B063 §3.5); live multi-currency NAV is Batch 3.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Protocol

from workbench_api.data.market_context_common import ObservationPoint

logger = logging.getLogger(__name__)

# FRED series -> the LOCAL currency whose "units per USD" the series quotes.
# DEXCHUS = Chinese Yuan per 1 USD; DEXHKUS = HK Dollars per 1 USD.
FX_SERIES_CURRENCY: dict[str, str] = {"DEXCHUS": "CNY", "DEXHKUS": "HKD"}

# Mirrors trade.data.data_root.UNIFIED_FX_RELPATH (drift = trade reads a file
# this job never wrote). The writer joins it under the data root.
FX_RELPATH = ("snapshots", "fx", "unified", "fx_daily.csv")
FX_HEADER = ["date", "currency", "rate"]

# Backtests span years; pull a long daily history (FRED carries decades).
DEFAULT_FX_LIMIT = 8000


class FxSeriesLoader(Protocol):
    def fetch_fx(self, series_id: str, *, limit: int) -> list[ObservationPoint]: ...


class FredFxLoader:
    """Adapter: FREDMarketLoader -> FX observation points. Lazy-builds the FRED
    client on first fetch so constructing the loader needs no FRED_API_KEY (the
    key is only required when the VM job actually fetches)."""

    def __init__(self, fred: Any | None = None) -> None:
        self._fred = fred

    def fetch_fx(self, series_id: str, *, limit: int) -> list[ObservationPoint]:
        fred = self._fred
        if fred is None:
            from workbench_api.data.fred_loader import FREDMarketLoader

            fred = FREDMarketLoader()
            self._fred = fred
        _payload, points = fred.fetch_series(series_id, limit=limit)
        return points


def run_fx_refresh(
    *,
    data_root: Path,
    fx_loader: FxSeriesLoader,
    limit: int = DEFAULT_FX_LIMIT,
) -> int:
    """Fetch DEXCHUS/DEXHKUS and write ``fx_daily.csv`` under ``data_root``.

    Per-series failures are logged + skipped (best-effort) so one bad series
    never aborts the FX refresh. Returns the total rows written."""

    path = data_root.joinpath(*FX_RELPATH)
    rows: list[list[object]] = []
    for series_id, currency in FX_SERIES_CURRENCY.items():
        try:
            points = fx_loader.fetch_fx(series_id, limit=limit)
        except Exception:  # noqa: BLE001 — best-effort; skip a failing series
            logger.exception("fx_refresh_fetch_failure", extra={"series": series_id})
            continue
        for point in sorted(points, key=lambda p: p.obs_date):
            rows.append([point.obs_date.isoformat(), currency, point.value])

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FX_HEADER)
        writer.writerows(rows)
    logger.info("fx_refresh_done", extra={"fx_rows": len(rows), "path": str(path)})
    return len(rows)
