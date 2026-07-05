"""B088 F001 — vol-targeting control laws: exposure math + turnover reduction (mechanical)."""

from __future__ import annotations

import pandas as pd

from trade.analysis.vol_targeting import (
    exposure_turnover,
    feedback_exposure,
    open_loop_exposure,
    smoothed_exposure,
)


def test_open_loop_scales_inverse_to_vol_and_caps() -> None:
    rv = pd.Series([0.16, 0.08, 0.04])
    e = open_loop_exposure(rv, target_vol=0.08)
    assert e.iloc[0] == 0.5  # target/rv = 0.08/0.16
    assert e.iloc[1] == 1.0  # target/rv = 1.0
    assert e.iloc[2] == 1.0  # 0.08/0.04 = 2.0 → capped at max_exposure


def test_smoothing_reduces_turnover_on_a_vol_spike() -> None:
    # a transient 1-period vol spike: open-loop dips full, smoothing dampens it
    rv = pd.Series([0.08] * 10 + [0.16] + [0.08] * 10)
    ol = open_loop_exposure(rv)
    sm = smoothed_exposure(rv, halflife=5)
    assert exposure_turnover(sm) < exposure_turnover(ol)


def test_feedback_k1_recovers_open_loop() -> None:
    rv = pd.Series([0.08, 0.16, 0.08, 0.10, 0.20])
    fb = feedback_exposure(rv, k=1.0)  # full adjustment = open-loop
    ol = open_loop_exposure(rv)
    assert (fb.to_numpy() == ol.to_numpy()).all()


def test_feedback_partial_reduces_turnover() -> None:
    rv = pd.Series([0.08] * 10 + [0.16] + [0.08] * 10)
    ol = open_loop_exposure(rv)
    fb = feedback_exposure(rv, k=0.5)  # partial adjustment damps changes
    assert exposure_turnover(fb) < exposure_turnover(ol)
