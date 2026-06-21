"""B071 F003 — deterministic real-data backtests on the golden fixture.

Runs the dispatched backtest engines (master + momentum + risk_parity +
hk_china + us_quality) on the committed golden real-data fixture through the
F003 ``fixture_dir`` injection seam and asserts:

* **determinism** — same fixture + same window → bit-identical results (the
  spec's "重跑 bit-identical"; CI has no random / no live wire);
* **N-strategy pairwise-distinct** — the B050 recurring invariant: N strategies
  over the same window produce pairwise-different, each non-degenerate results
  (golden makes this a permanent CI regression instead of a one-off Codex pass);
* **us_quality real-split fix regression** — golden's real splits (NVDA 4:1,
  AMZN 20:1; close/adj_close ~40x) exposed that the engine executed at raw
  ``open`` but valued at ``adj_close`` (a ~-99% phantom loss). The fix
  (``_wide_open`` → split/dividend-adjusted open) is pinned here so the bug
  cannot silently return.

The shared harness lives in ``tests/conftest.py`` (fixtures, reused by F004
acceptance). conftest helpers reach the tests via fixtures because the
no-``__init__`` ``tests/`` tree is not cross-importable.
"""

from __future__ import annotations

import itertools


def test_each_strategy_is_deterministic(
    golden_strategy_builder, golden_strategy_names, golden_fingerprint
) -> None:
    """Two independent builds on the same golden fixture are bit-identical."""
    run_a = golden_strategy_builder()
    run_b = golden_strategy_builder()
    assert set(run_a) == set(golden_strategy_names)
    for name in golden_strategy_names:
        fa = golden_fingerprint(run_a[name])
        fb = golden_fingerprint(run_b[name])
        assert fa == fb, f"{name} not deterministic: {fa} != {fb}"
        # Exact float equality — the headline "bit-identical" guarantee.
        assert run_a[name].ending_value == run_b[name].ending_value


def test_all_five_strategies_present(golden_strategy_results, golden_strategy_names) -> None:
    assert set(golden_strategy_results) == set(golden_strategy_names)


def test_strategies_are_pairwise_distinct(
    golden_strategy_results, golden_strategy_names
) -> None:
    """B050 recurring invariant: N strategies, same golden window → pairwise
    different results. Guards against the "every strategy returns the same
    thing" dispatch regression that B050 fixed."""
    endings = {name: res.ending_value for name, res in golden_strategy_results.items()}
    for left, right in itertools.combinations(golden_strategy_names, 2):
        assert endings[left] != endings[right], (
            f"{left} and {right} produced identical ending_value {endings[left]} — "
            "strategies are not distinguishable on golden (B050 regression)"
        )


def test_each_strategy_is_non_degenerate(golden_strategy_results) -> None:
    """Each strategy actually traded (ending value moved from the starting
    capital) — i.e. not an all-cash / no-op degenerate result."""
    for name, result in golden_strategy_results.items():
        assert result.ending_value > 0, f"{name} produced a non-positive ending value"
        assert abs(result.ending_value - result.starting_capital) > 1e-6, (
            f"{name} did not move from its starting capital — degenerate (all-cash?)"
        )


def test_us_quality_has_no_phantom_loss_on_real_splits(golden_strategy_results) -> None:
    """Regression guard for the B071 F003 fix.

    Before the fix, us_quality executed at raw ``open`` and valued at
    ``adj_close``; on golden's real split/dividend data (close/adj_close ~40x)
    that mismarked every holding into a ~-99% phantom loss (ending ≈ 557 from a
    100k start). The adjusted-open fix puts it back in a plausible band. A band
    assertion (not an exact number) keeps this robust across pandas/numpy
    versions while still catching a regression to the broken basis."""
    result = golden_strategy_results["us_quality"]
    # The broken engine returned ~557 (a -99.4% phantom loss). Anything above a
    # few % of starting capital proves the adjusted-open basis is in effect.
    assert result.ending_value > 40_000, (
        f"us_quality ending {result.ending_value:.2f} looks like the pre-fix "
        "raw-open / adj-close phantom loss (B071 F003 regression)"
    )
    # And it must not be implausibly high either — a sane real-data backtest.
    assert result.ending_value < 300_000
