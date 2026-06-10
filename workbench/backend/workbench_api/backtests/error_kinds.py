"""B047-OPS2 F001 — structured backtest error-kind classification.

The worker raises ``BacktestWorkerError`` with a human English message when a
run cannot complete. This module maps those messages to a small set of stable
``error_kind`` codes stored on ``backtest_run.error_kind``. The frontend (F002)
maps each code to a bilingual friendly message — the raw English exception is
never shown to the user.

Pure string classification — no ``trade`` import, no DB — so it is cheap and
safe to call from the worker's failure path.
"""

from __future__ import annotations

# Stable codes the frontend i18n bundle keys on. Keep in sync with the
# backtest error-kind map in the frontend (F002).
INSUFFICIENT_HISTORY = "insufficient_history"
NO_SIGNAL_DATES = "no_signal_dates"
DATA_UNAVAILABLE = "data_unavailable"
INACTIVE_STRATEGY = "inactive_strategy"
# B053 F002 — a run left in ``running`` when the worker died mid-backtest (a
# crash or, most commonly, a deploy ``systemctl restart`` landing on an
# in-flight run). The worker reclaims these at startup and marks them with this
# kind so the frontend shows an honest "interrupted, please re-run" instead of
# the run spinning in ``running`` forever. Not produced by ``classify_error_kind``
# (it is set directly by the recovery path), but listed here so this set stays
# the single source the frontend i18n bundle mirrors.
INTERRUPTED = "interrupted"
UNKNOWN = "unknown"

ERROR_KINDS = frozenset(
    {
        INSUFFICIENT_HISTORY,
        NO_SIGNAL_DATES,
        DATA_UNAVAILABLE,
        INACTIVE_STRATEGY,
        INTERRUPTED,
        UNKNOWN,
    }
)

# Substrings the worker uses in its BacktestWorkerError messages, mapped to the
# structured kind. Ordered most-specific first; first match wins.
_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("no real price data available", DATA_UNAVAILABLE),
    ("unified price data yielded no rows", DATA_UNAVAILABLE),
    # B050 F001 — research-state strategy excluded from standalone backtest.
    ("is research-state", INACTIVE_STRATEGY),
    ("no quarter-end signal dates", NO_SIGNAL_DATES),
    ("no monthly signal dates", NO_SIGNAL_DATES),
    ("insufficient price history", INSUFFICIENT_HISTORY),
    ("no valid volatility estimates", INSUFFICIENT_HISTORY),
)


def classify_error_kind(exc: BaseException) -> str:
    """Map a backtest failure to a stable ``error_kind`` code.

    Classification is by the exception message text (where the worker encodes
    the structured cause). Anything unrecognised → :data:`UNKNOWN` so the
    frontend can still show a generic friendly message rather than the raw
    exception."""

    message = str(exc).lower()
    for needle, kind in _SIGNATURES:
        if needle in message:
            return kind
    return UNKNOWN
