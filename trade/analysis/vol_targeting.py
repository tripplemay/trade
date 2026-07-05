"""B088 F001 — volatility-targeting exposure control laws (open-loop / smoothing / feedback).

open-loop vol-targeting (``exposure ∝ 1/realized_vol``) hits the target volatility but with
**turnover / leverage spikes** every time the vol estimate jumps (arxiv 2022 "Smoothing
volatility targeting"). Two variants damp that:

* **smoothing** — target the *EWMA-smoothed* vol estimate → a smoother exposure path.
* **feedback** — partial-adjustment (proportional) control: move only a fraction ``k`` of the
  way toward the open-loop target each step → damped exposure changes.

The turnover reduction is a **mechanical property** of the control laws (provable on any
vol-varying series), so it is objectively measurable — not a subtle-edge claim. This is a
research module (pure numpy/pandas): it does NOT touch ``risk_parity`` or any strategy's
product code; those keep their existing open-loop behaviour.

Prior parameters (禁扫参 — from risk_parity + the smoothing literature):
``TARGET_VOL=0.08``, ``SMOOTH_HALFLIFE=21`` (≈1 trading month), ``FEEDBACK_K=0.5``.
"""

from __future__ import annotations

from typing import Any

TARGET_VOL = 0.08
SMOOTH_HALFLIFE = 21
FEEDBACK_K = 0.5
MAX_EXPOSURE = 1.0


def open_loop_exposure(
    realized_vol: Any, target_vol: float = TARGET_VOL, max_exposure: float = MAX_EXPOSURE
) -> Any:
    """Baseline (same as risk_parity): ``e_t = min(target / realized_vol_t, max)``."""

    return (target_vol / realized_vol).clip(upper=max_exposure)


def smoothed_exposure(
    realized_vol: Any,
    target_vol: float = TARGET_VOL,
    halflife: int = SMOOTH_HALFLIFE,
    max_exposure: float = MAX_EXPOSURE,
) -> Any:
    """Open-loop on an EWMA-smoothed vol estimate → smoother exposure, less turnover."""

    smoothed = realized_vol.ewm(halflife=halflife).mean()
    return (target_vol / smoothed).clip(upper=max_exposure)


def feedback_exposure(
    realized_vol: Any,
    target_vol: float = TARGET_VOL,
    k: float = FEEDBACK_K,
    max_exposure: float = MAX_EXPOSURE,
) -> Any:
    """Partial-adjustment (proportional) control toward the open-loop target:
    ``e_t = e_{t-1} + k·(open_loop_t − e_{t-1})``. ``k=1`` recovers open-loop; ``k<1`` damps
    exposure changes → less turnover."""

    import pandas as pd

    target = open_loop_exposure(realized_vol, target_vol, max_exposure)
    out: list[float] = []
    prev = float(target.iloc[0])
    for value in target:
        prev = prev + k * (float(value) - prev)
        out.append(prev)
    return pd.Series(out, index=realized_vol.index, name="feedback_exposure")


def exposure_turnover(exposure: Any) -> float:
    """Total absolute exposure change = Σ|Δe_t| (the cost the smoothing/feedback reduce)."""

    return float(exposure.diff().abs().sum())
