"""Rank-based standardization for the B025 factor zoo.

Spec recommends percent_rank: every raw factor value is mapped to ``[0, 1]``
by its position in the cross-section, ties get the average rank, and NaNs are
preserved (so missing tickers do not contaminate downstream weight sums).

No ``sklearn`` import here or anywhere in the strategy package; ML
``fit/predict`` paths are explicitly out of scope (B025 §3 ML boundary).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def percent_rank(series: pd.Series) -> pd.Series:
    """Map each value to ``[0, 1]`` by cross-sectional rank (NaN preserved).

    - Ties get the average rank, then averaged-rank / N for the percent.
    - All-equal input (zero variance) collapses to the midpoint ``0.5`` for
      every defined entry (pandas default for ``method='average'`` tie-break).
    - NaN entries stay NaN; they are excluded from the ranking denominator.
    - The result is always finite for finite inputs and shares the input's
      index so downstream combinators can align by ticker.
    """

    return series.rank(pct=True, method="average")


def standardize(series: pd.Series) -> pd.Series:
    """Strategy-doc-recommended rank-based standardizer (alias for ``percent_rank``).

    Kept as a separate name because the call sites in ``factors`` and the
    F003 score-combiner read more naturally as ``standardize(raw_factor)``.
    """

    return percent_rank(series)


def average_ranks(*series: pd.Series) -> pd.Series:
    """Average several percent-ranks across a shared index.

    Used by composite factors (``quality_score``, ``value_score``) that
    aggregate multiple sub-rankings. NaN-tolerant: tickers missing one
    sub-rank still contribute via the remaining ones (``Series.mean`` with
    ``skipna=True``). Returns NaN only when *every* sub-rank is NaN.
    """

    if not series:
        raise ValueError("average_ranks requires at least one series")
    frame = pd.concat(series, axis=1)
    return frame.mean(axis=1, skipna=True)


def safe_inverse(series: pd.Series) -> pd.Series:
    """Return ``1 / series`` while mapping non-positive / zero to NaN.

    Value ratios (1/PE, 1/PB, 1/EV-EBITDA) only make sense for positive
    denominators — negative or zero earnings/book/EV yield an undefined
    inverted yield. NaN propagation lets ``average_ranks`` skip the bad
    cell without polluting the composite.
    """

    safe = series.where(series > 0, np.nan)
    return 1.0 / safe
