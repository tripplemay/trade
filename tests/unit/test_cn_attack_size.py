"""B076 F001 — unit tests for the PIT small-cap (size-tilt) factor."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trade.strategies.cn_attack_momentum_quality.size import (
    SizeFactorError,
    small_cap_score,
)


def _frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["data_date", "ticker", "market_cap"])


def test_smaller_cap_scores_higher() -> None:
    # SMALL → HIGH score (small-tilt): score = -log(mcap), monotone decreasing in cap.
    frame = _frame(
        [
            ("2025-03-31", "BIG", 1.0e12),
            ("2025-03-31", "MID", 1.0e10),
            ("2025-03-31", "SMALL", 1.0e9),
        ]
    )
    score = small_cap_score(frame, date(2025, 6, 1))
    assert score["SMALL"] > score["MID"] > score["BIG"]
    assert score["SMALL"] == pytest.approx(-np.log(1.0e9))


def test_point_in_time_uses_latest_on_or_before_as_of() -> None:
    # Two observations: the latest <= as_of wins; a later one is invisible (no look-ahead).
    frame = _frame(
        [
            ("2025-01-31", "T1", 2.0e10),
            ("2025-05-31", "T1", 1.0e10),  # latest <= 2025-06-01 → this one
            ("2025-08-31", "T1", 5.0e9),  # AFTER as_of → must be ignored
        ]
    )
    score = small_cap_score(frame, date(2025, 6, 1))
    assert score["T1"] == pytest.approx(-np.log(1.0e10))


def test_name_with_no_observation_before_as_of_is_absent() -> None:
    frame = _frame([("2025-08-31", "FUTURE", 1.0e10)])  # only after as_of
    score = small_cap_score(frame, date(2025, 6, 1))
    assert "FUTURE" not in score.index


def test_non_positive_cap_scores_nan() -> None:
    frame = _frame(
        [
            ("2025-03-31", "ZERO", 0.0),
            ("2025-03-31", "NEG", -5.0),
            ("2025-03-31", "OK", 1.0e10),
        ]
    )
    score = small_cap_score(frame, date(2025, 6, 1))
    # NaN so the composite drops the name (like a missing momentum/quality value).
    assert pd.isna(score["ZERO"])
    assert pd.isna(score["NEG"])
    assert score["OK"] == pytest.approx(-np.log(1.0e10))


def test_missing_columns_raises() -> None:
    bad = pd.DataFrame({"data_date": ["2025-03-31"], "ticker": ["T1"]})
    with pytest.raises(SizeFactorError, match="missing required columns"):
        small_cap_score(bad, date(2025, 6, 1))


def test_empty_frame_returns_empty_series() -> None:
    empty = _frame([])
    score = small_cap_score(empty, date(2025, 6, 1))
    assert score.empty


def test_all_observations_after_as_of_returns_empty() -> None:
    frame = _frame([("2026-01-31", "T1", 1.0e10), ("2026-02-28", "T2", 2.0e10)])
    score = small_cap_score(frame, date(2025, 6, 1))
    assert score.empty
