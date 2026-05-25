"""Unit tests for the B025 rank-based standardization helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trade.strategies.us_quality_momentum.ranking import (
    average_ranks,
    percent_rank,
    safe_inverse,
    standardize,
)


def test_percent_rank_maps_monotonic_input_to_unit_interval() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0], index=["A", "B", "C", "D"])
    result = percent_rank(series)
    assert (result.between(0.0, 1.0)).all()
    assert result["A"] < result["B"] < result["C"] < result["D"]
    assert result["D"] == pytest.approx(1.0)


def test_percent_rank_handles_all_equal_input_via_average_tiebreak() -> None:
    series = pd.Series([5.0, 5.0, 5.0, 5.0], index=["A", "B", "C", "D"])
    result = percent_rank(series)
    # Average-method on n equal values yields (n+1)/(2n) for every entry.
    n = len(series)
    expected = (n + 1) / (2 * n)
    np.testing.assert_allclose(result.to_numpy(), np.full(n, expected))
    assert result.std() == pytest.approx(0.0)
    assert result.isna().sum() == 0


def test_percent_rank_preserves_nan_entries() -> None:
    series = pd.Series([1.0, np.nan, 2.0, 3.0], index=["A", "B", "C", "D"])
    result = percent_rank(series)
    assert result.isna()["B"]
    assert not result.drop("B").isna().any()


def test_percent_rank_preserves_relative_order_with_ties() -> None:
    series = pd.Series([1.0, 2.0, 2.0, 3.0], index=["A", "B", "C", "D"])
    result = percent_rank(series)
    assert result["A"] < result["B"] == result["C"] < result["D"]


def test_standardize_is_alias_for_percent_rank() -> None:
    series = pd.Series([10.0, 20.0, 30.0])
    pd.testing.assert_series_equal(standardize(series), percent_rank(series))


def test_average_ranks_averages_multiple_series_with_nan_tolerance() -> None:
    a = pd.Series([0.0, 0.5, 1.0, np.nan], index=["A", "B", "C", "D"])
    b = pd.Series([0.2, 0.4, 0.6, 0.8], index=["A", "B", "C", "D"])
    result = average_ranks(a, b)
    assert result["A"] == pytest.approx(0.1)
    assert result["B"] == pytest.approx(0.45)
    assert result["C"] == pytest.approx(0.8)
    # NaN in one component is skipped; the other carries the average.
    assert result["D"] == pytest.approx(0.8)


def test_average_ranks_returns_nan_only_when_every_component_is_nan() -> None:
    a = pd.Series([np.nan, np.nan], index=["A", "B"])
    b = pd.Series([np.nan, 0.5], index=["A", "B"])
    result = average_ranks(a, b)
    assert pd.isna(result["A"])
    assert result["B"] == pytest.approx(0.5)


def test_average_ranks_raises_on_no_arguments() -> None:
    with pytest.raises(ValueError, match="at least one"):
        average_ranks()


def test_safe_inverse_maps_non_positive_to_nan() -> None:
    series = pd.Series([1.0, 0.0, -1.0, 2.0], index=["A", "B", "C", "D"])
    result = safe_inverse(series)
    assert result["A"] == pytest.approx(1.0)
    assert pd.isna(result["B"])
    assert pd.isna(result["C"])
    assert result["D"] == pytest.approx(0.5)


def test_safe_inverse_preserves_input_nan() -> None:
    series = pd.Series([1.0, np.nan, 4.0], index=["A", "B", "C"])
    result = safe_inverse(series)
    assert pd.isna(result["B"])
    assert result["A"] == pytest.approx(1.0)
    assert result["C"] == pytest.approx(0.25)
