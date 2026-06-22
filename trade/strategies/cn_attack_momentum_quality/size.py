"""B076 F001 — point-in-time small-cap (size-tilt) factor for the CN attack engine.

The size factor scores every A-share by its **circulating market cap** so a SMALLER
cap earns a HIGHER score: ``small_cap_score`` returns ``-log(circ_mv)``, which —
because the composite ranks factors by :func:`percent_rank` (rank-based, monotone) —
puts the smallest names at the top of the size dimension. Blended into the composite
with ``CnAttackParameters.size_tilt_weight`` it tilts selection toward small/mid-caps;
weight ``0`` (production default) means the factor is never scored at all
(zero-regression).

Point-in-time safety mirrors the momentum / quality factors: a ticker's score uses the
**latest market-cap observation on or before** ``as_of`` (no look-ahead). A name with no
observation ``<= as_of``, or a non-positive cap, scores NaN and is dropped by the
composite's all-active-factors-required rule — exactly how a missing momentum/quality
value drops a name. Surfacing that drop is the breadth metric's job, not a silent fill.

Pure pandas/numpy; the market-cap frame is injected (the backtest reads
``cn_size.csv`` derived from baostock turnover; production wiring is F002). No broker
SDK, no US-engine import (US zero-regression by construction).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

DATE_COLUMN = "data_date"
TICKER_COLUMN = "ticker"
MARKET_CAP_COLUMN = "market_cap"

_REQUIRED_COLUMNS = (DATE_COLUMN, TICKER_COLUMN, MARKET_CAP_COLUMN)


class SizeFactorError(ValueError):
    """Raised when the market-cap frame is missing required columns."""


def small_cap_score(marketcap: pd.DataFrame, as_of: date) -> pd.Series:
    """Per-ticker ``-log(circ_mv_as_of)`` — smaller cap ranks higher (small-tilt).

    ``marketcap`` is a long frame with ``data_date`` / ``ticker`` / ``market_cap``
    columns (the circulating market cap in raw CNY). For each ticker the latest row
    with ``data_date <= as_of`` supplies the cap; the score is its negative natural log
    so the cross-sectional :func:`percent_rank` puts the smallest names highest. A
    ticker with no observation on or before ``as_of`` — or a non-positive cap — is
    absent from / NaN in the result (the composite then drops it, like a missing
    momentum/quality value). The returned Series is indexed by ticker.
    """

    missing = [column for column in _REQUIRED_COLUMNS if column not in marketcap.columns]
    if missing:
        raise SizeFactorError(f"marketcap frame missing required columns: {missing}")
    if marketcap.empty:
        return pd.Series(dtype="float64")

    frame = marketcap.loc[:, list(_REQUIRED_COLUMNS)].copy()
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN])
    cutoff = pd.Timestamp(as_of)
    visible = frame.loc[frame[DATE_COLUMN] <= cutoff]
    if visible.empty:
        return pd.Series(dtype="float64")

    # Latest observation on/before as_of per ticker (stable sort → deterministic last).
    visible = visible.sort_values([TICKER_COLUMN, DATE_COLUMN], kind="mergesort")
    latest = visible.groupby(TICKER_COLUMN, sort=False).last()
    caps = pd.to_numeric(latest[MARKET_CAP_COLUMN], errors="coerce")
    # Non-positive / non-finite caps cannot be log-scored → NaN (dropped downstream).
    caps = caps.where(caps > 0.0)
    score = -np.log(caps)
    score.index.name = None
    return score


__all__ = [
    "DATE_COLUMN",
    "MARKET_CAP_COLUMN",
    "TICKER_COLUMN",
    "SizeFactorError",
    "small_cap_score",
]
