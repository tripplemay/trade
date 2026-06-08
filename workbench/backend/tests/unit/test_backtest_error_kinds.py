"""B047-OPS2 F001 — structured backtest error-kind classification.

Pins the worker's three real failure messages to their stable ``error_kind``
codes (the frontend maps these to bilingual friendly copy), plus the
data-unavailable and unknown fallbacks.
"""

from __future__ import annotations

import pytest

from workbench_api.backtests.error_kinds import (
    DATA_UNAVAILABLE,
    INSUFFICIENT_HISTORY,
    NO_SIGNAL_DATES,
    UNKNOWN,
    classify_error_kind,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "insufficient price history for any signal date in range: no valid "
            "volatility estimates for risk assets",
            INSUFFICIENT_HISTORY,
        ),
        ("no valid volatility estimates for risk assets", INSUFFICIENT_HISTORY),
        (
            "no quarter-end signal dates available in the requested date range",
            NO_SIGNAL_DATES,
        ),
        (
            "no real price data available (unified daily CSV absent); run the "
            "data-refresh job first",
            DATA_UNAVAILABLE,
        ),
        ("unified price data yielded no rows", DATA_UNAVAILABLE),
        ("something nobody anticipated", UNKNOWN),
    ],
)
def test_classify_error_kind(message: str, expected: str) -> None:
    assert classify_error_kind(RuntimeError(message)) == expected


def test_classify_is_case_insensitive() -> None:
    assert (
        classify_error_kind(RuntimeError("INSUFFICIENT PRICE HISTORY for range"))
        == INSUFFICIENT_HISTORY
    )
