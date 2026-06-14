"""B063 F001 — FX rate reader + USD converter (trade-side, offline CSV read).

Reads the unified FX CSV (``snapshots/fx/unified/fx_daily.csv``; columns
``date,currency,rate``) that the workbench ``data_refresh`` job writes from FRED
(DEXCHUS = CNY-per-USD, DEXHKUS = HKD-per-USD). ``trade`` only **reads** this CSV
— it never fetches FRED (offline edge, same as prices_daily.csv).

Conversion direction: the FRED rate quotes LOCAL-currency-per-USD, so
``usd = local_amount / rate``. Lookup is **as-of (forward-fill)**: the rate for a
query date is the most recent observation on-or-before it — covering FRED's
weekend / holiday gaps without a dense daily file. USD passes through unchanged.

This is for **backtest USD conversion only** (B063 §3.5); live multi-currency
NAV aggregation is Batch 3.
"""

from __future__ import annotations

import csv
from bisect import bisect_right
from datetime import date
from pathlib import Path

from trade.data.data_root import unified_fx_path

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Repo-root default (local / CI); the VM override is applied by unified_fx_path.
FX_PATH = _REPO_ROOT / "data" / "snapshots" / "fx" / "unified" / "fx_daily.csv"

_REQUIRED_COLUMNS = frozenset({"date", "currency", "rate"})


def load_fx_rates(path: Path | None = None) -> dict[str, list[tuple[date, float]]]:
    """Return ``{currency: [(date, rate)...]}`` sorted ascending per currency.

    Missing file → ``{}`` (callers treat USD-only / no-conversion). Malformed
    rows are skipped rather than aborting the load."""

    source = path or unified_fx_path(FX_PATH)
    if not source.exists():
        return {}
    out: dict[str, list[tuple[date, float]]] = {}
    with source.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not _REQUIRED_COLUMNS.issubset(reader.fieldnames):
            return {}
        for row in reader:
            try:
                obs = date.fromisoformat(str(row["date"]))
                rate = float(row["rate"])
            except (KeyError, ValueError):
                continue
            currency = str(row["currency"]).strip().upper()
            if not currency:
                continue
            out.setdefault(currency, []).append((obs, rate))
    for currency in out:
        out[currency].sort(key=lambda item: item[0])
    return out


class FxConverter:
    """As-of (forward-fill) FX conversion to USD; USD passes through."""

    def __init__(self, rates: dict[str, list[tuple[date, float]]]) -> None:
        self._rates = rates

    @classmethod
    def load(cls, path: Path | None = None) -> FxConverter:
        return cls(load_fx_rates(path))

    def rate_as_of(self, currency: str, as_of: date) -> float | None:
        """Most recent rate (local-per-USD) on-or-before ``as_of``; None if the
        currency is unknown or ``as_of`` precedes the first observation."""

        series = self._rates.get(currency.upper())
        if not series:
            return None
        dates = [obs for obs, _ in series]
        index = bisect_right(dates, as_of) - 1
        if index < 0:
            return None
        return series[index][1]

    def to_usd(self, amount: float, currency: str, as_of: date) -> float | None:
        """Convert ``amount`` of ``currency`` to USD at the as-of rate.

        USD → unchanged. Returns None when the rate is unavailable (so the
        caller degrades honestly rather than fabricating a converted value)."""

        if currency.upper() == "USD":
            return amount
        rate = self.rate_as_of(currency, as_of)
        if rate is None or rate == 0:
            return None
        return amount / rate
