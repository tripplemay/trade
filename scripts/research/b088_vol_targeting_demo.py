#!/usr/bin/env python
"""B088 F001 — turnover demonstration for the vol-targeting control laws.

Reproducible (seeded) synthetic regime-vol series → shows smoothing/feedback reduce
exposure turnover vs open-loop while realized vol stays ≈ target. The turnover reduction
is a mechanical property of the control laws, so this is objectively measurable (not a
subtle-edge claim). Real-strategy integration is a follow-up.
"""

from __future__ import annotations

from typing import Any

_N = 600
_REGIME_BLOCK = 50
_CALM_VOL = 0.06
_STRESS_VOL = 0.24
_SEED = 42


def run_demo() -> list[dict[str, Any]]:
    import numpy as np
    import pandas as pd

    from trade.analysis.vol_targeting import (
        TARGET_VOL,
        exposure_turnover,
        feedback_exposure,
        open_loop_exposure,
        smoothed_exposure,
    )

    rng = np.random.default_rng(_SEED)
    # alternating calm / stressed vol blocks (annualised → daily)
    daily_vol = np.where(
        (np.arange(_N) // _REGIME_BLOCK) % 2 == 0,
        _CALM_VOL / np.sqrt(252),
        _STRESS_VOL / np.sqrt(252),
    )
    returns = pd.Series(rng.normal(0.0, daily_vol))
    realized_vol = (returns.rolling(21).std() * np.sqrt(252)).dropna()
    ret = returns.loc[realized_vol.index]

    rows = []
    variants = {
        "open_loop": open_loop_exposure(realized_vol),
        "smoothed": smoothed_exposure(realized_vol),
        "feedback": feedback_exposure(realized_vol),
    }
    base_turnover = exposure_turnover(variants["open_loop"])
    for name, exposure in variants.items():
        port_ret = exposure.shift(1) * ret
        rows.append(
            {
                "variant": name,
                "turnover": round(exposure_turnover(exposure), 2),
                "turnover_pct_of_open_loop": round(
                    100 * exposure_turnover(exposure) / base_turnover
                ),
                "realized_vol": round(float(port_ret.std() * np.sqrt(252)), 4),
                "vs_target": round(float(port_ret.std() * np.sqrt(252)) / TARGET_VOL, 2),
            }
        )
    return rows


def main() -> int:
    import json

    rows = run_demo()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
