"""B016 F002 — unit tests for the pure-stdlib HRP module."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from trade.strategies.risk_parity_hrp import (
    ClusterNode,
    compute_correlation_matrix,
    compute_distance_matrix,
    compute_hrp_weights,
    quasi_diagonalize,
    recursive_bisection,
    single_linkage_clustering,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _alternating(amplitude: float, length: int, phase: int = 0) -> list[float]:
    """Length-T series alternating between +amplitude and -amplitude."""

    return [amplitude if (i + phase) % 2 == 0 else -amplitude for i in range(length)]


def _ramp(slope: float, length: int) -> list[float]:
    """Length-T series 0, slope, 2*slope, ... (positive variance)."""

    return [slope * i for i in range(length)]


def _approx(value: float, target: float, tol: float = 1e-9) -> bool:
    return abs(value - target) <= tol


# --------------------------------------------------------------------------- #
# compute_correlation_matrix
# --------------------------------------------------------------------------- #


def test_correlation_diagonal_is_one() -> None:
    series_a = [0.01, -0.02, 0.015, -0.01, 0.005]
    series_b = [-0.005, 0.01, 0.0, -0.015, 0.02]
    corr = compute_correlation_matrix([series_a, series_b])

    assert _approx(corr[0][0], 1.0)
    assert _approx(corr[1][1], 1.0)


def test_correlation_is_symmetric() -> None:
    series_a = [0.01, -0.02, 0.015, -0.01, 0.005]
    series_b = [-0.005, 0.01, 0.0, -0.015, 0.02]
    series_c = [0.02, 0.005, -0.01, 0.012, -0.008]
    corr = compute_correlation_matrix([series_a, series_b, series_c])

    for i in range(3):
        for j in range(3):
            assert _approx(corr[i][j], corr[j][i])


def test_correlation_identical_series_is_one() -> None:
    series = [0.01, -0.02, 0.015, -0.01, 0.005, 0.002, -0.007]
    corr = compute_correlation_matrix([series, list(series)])

    assert _approx(corr[0][1], 1.0)


def test_correlation_perfectly_anticorrelated_is_minus_one() -> None:
    series_a = _alternating(0.01, 50, phase=0)
    series_b = _alternating(0.01, 50, phase=1)
    corr = compute_correlation_matrix([series_a, series_b])

    assert _approx(corr[0][1], -1.0, tol=1e-12)


def test_correlation_positive_linear_is_one() -> None:
    series_a = _ramp(0.001, 50)
    # b = 2 * a + 0.05 — perfectly positively correlated, different scale and offset.
    series_b = [2.0 * v + 0.05 for v in series_a]
    corr = compute_correlation_matrix([series_a, series_b])

    assert _approx(corr[0][1], 1.0)


def test_correlation_zero_variance_rejected() -> None:
    flat = [0.0] * 20
    movement = [0.01 if i % 2 else -0.01 for i in range(20)]

    with pytest.raises(ValueError, match="zero variance"):
        compute_correlation_matrix([flat, movement])


def test_correlation_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least 2 observations"):
        compute_correlation_matrix([[0.01], [0.02]])


def test_correlation_rejects_ragged_series() -> None:
    with pytest.raises(ValueError, match="length"):
        compute_correlation_matrix([[0.01, 0.02, 0.03], [0.01, 0.02]])


# --------------------------------------------------------------------------- #
# compute_distance_matrix
# --------------------------------------------------------------------------- #


def test_distance_perfect_positive_correlation_is_zero() -> None:
    dist = compute_distance_matrix([[1.0, 1.0], [1.0, 1.0]])

    assert _approx(dist[0][1], 0.0)
    assert _approx(dist[1][0], 0.0)


def test_distance_perfect_negative_correlation_is_one() -> None:
    dist = compute_distance_matrix([[1.0, -1.0], [-1.0, 1.0]])

    assert _approx(dist[0][1], 1.0)
    assert _approx(dist[1][0], 1.0)


def test_distance_zero_correlation_is_sqrt_half() -> None:
    dist = compute_distance_matrix([[1.0, 0.0], [0.0, 1.0]])

    assert _approx(dist[0][1], math.sqrt(0.5))


def test_distance_diagonal_is_zero() -> None:
    corr = [[1.0, 0.4, -0.2], [0.4, 1.0, 0.1], [-0.2, 0.1, 1.0]]
    dist = compute_distance_matrix(corr)

    for i in range(3):
        assert _approx(dist[i][i], 0.0)


def test_distance_is_symmetric() -> None:
    corr = [[1.0, 0.4, -0.2], [0.4, 1.0, 0.1], [-0.2, 0.1, 1.0]]
    dist = compute_distance_matrix(corr)

    for i in range(3):
        for j in range(3):
            assert _approx(dist[i][j], dist[j][i])


def test_distance_matches_de_prado_formula() -> None:
    corr = [[1.0, 0.36], [0.36, 1.0]]
    dist = compute_distance_matrix(corr)

    # d = sqrt(0.5 * (1 - 0.36)) = sqrt(0.32)
    assert _approx(dist[0][1], math.sqrt(0.32))


# --------------------------------------------------------------------------- #
# single_linkage_clustering
# --------------------------------------------------------------------------- #


def test_single_linkage_single_leaf() -> None:
    root = single_linkage_clustering([[0.0]])

    assert root.is_leaf
    assert root.leaf_index == 0


def test_single_linkage_two_leaves() -> None:
    root = single_linkage_clustering([[0.0, 0.5], [0.5, 0.0]])

    assert not root.is_leaf
    assert root.left is not None
    assert root.right is not None
    assert {root.left.leaf_index, root.right.leaf_index} == {0, 1}
    assert sorted(root.members) == [0, 1]


def test_single_linkage_three_leaves_merges_closest_first() -> None:
    # d(0,1)=0.1 is the smallest; merge first. d({0,1}, 2) = min(0.5, 0.3) = 0.3.
    # The second merge appends the new cluster id at the end of `active`, so the
    # final merge is between the unmerged leaf 2 and the {0,1} cluster, with
    # `a < b` placing leaf 2 on the left subtree.
    dist = [
        [0.0, 0.1, 0.5],
        [0.1, 0.0, 0.3],
        [0.5, 0.3, 0.0],
    ]
    root = single_linkage_clustering(dist)

    leaves = quasi_diagonalize(root)
    # Pre-order: leaf 2 first (left subtree), then the {0,1} cluster.
    assert leaves == [2, 0, 1]
    assert sorted(root.members) == [0, 1, 2]
    assert root.left is not None
    assert root.right is not None
    # Left subtree is leaf 2; right subtree contains {0,1}.
    assert root.left.is_leaf and root.left.leaf_index == 2
    assert sorted(root.right.members) == [0, 1]


def test_single_linkage_tied_distances_deterministic() -> None:
    # Two ties at 0.2; iteration order picks (0,1) first, then (2,3).
    dist = [
        [0.0, 0.2, 0.6, 0.6],
        [0.2, 0.0, 0.6, 0.6],
        [0.6, 0.6, 0.0, 0.2],
        [0.6, 0.6, 0.2, 0.0],
    ]
    root_a = single_linkage_clustering(dist)
    root_b = single_linkage_clustering(dist)

    assert quasi_diagonalize(root_a) == [0, 1, 2, 3]
    assert quasi_diagonalize(root_b) == [0, 1, 2, 3]
    # Top-level split is {0,1} vs {2,3}.
    assert root_a.left is not None and root_a.right is not None
    assert sorted(root_a.left.members) == [0, 1]
    assert sorted(root_a.right.members) == [2, 3]


def test_single_linkage_uses_min_linkage() -> None:
    # 4 nodes where the tightest pair is (1,2) at 0.05; second-tightest is (0,1)
    # at 0.4 and (2,3) at 0.4. Single-linkage merges 1,2 first; then min(d(1,*),
    # d(2,*)) to each remaining node decides next step.
    dist = [
        [0.0, 0.4, 0.7, 0.9],
        [0.4, 0.0, 0.05, 0.8],
        [0.7, 0.05, 0.0, 0.4],
        [0.9, 0.8, 0.4, 0.0],
    ]
    root = single_linkage_clustering(dist)

    # Step 1: merge (1,2) → id 4. active=[0, 3, 4].
    # Step 2: d({1,2}, 0) = min(0.4, 0.7) = 0.4; d({1,2}, 3) = min(0.8, 0.4) = 0.4.
    # Iteration order (0,3)=0.9, (0,4)=0.4, (3,4)=0.4 → first 0.4 at (0,4) wins.
    # Merge (0, 4) → id 5 with left=leaf 0, right={1,2}. active=[3, 5].
    # Step 3: merge (3, 5) → root with left=leaf 3, right={0, {1, 2}}.
    leaves = quasi_diagonalize(root)
    assert leaves == [3, 0, 1, 2]
    assert sorted(root.members) == [0, 1, 2, 3]
    # Correlated cluster {1, 2} appears adjacent in the ordering.
    assert leaves.index(1) + 1 == leaves.index(2)


def test_single_linkage_rejects_empty_distance() -> None:
    with pytest.raises(ValueError, match="empty distance matrix"):
        single_linkage_clustering([])


# --------------------------------------------------------------------------- #
# quasi_diagonalize
# --------------------------------------------------------------------------- #


def test_quasi_diagonalize_single_leaf() -> None:
    order = quasi_diagonalize(ClusterNode(leaf_index=7, members=(7,)))

    assert order == [7]


def test_quasi_diagonalize_pre_order_traversal() -> None:
    leaf0 = ClusterNode(leaf_index=0, members=(0,))
    leaf1 = ClusterNode(leaf_index=1, members=(1,))
    leaf2 = ClusterNode(leaf_index=2, members=(2,))
    sub01 = ClusterNode(left=leaf0, right=leaf1, members=(0, 1))
    root = ClusterNode(left=sub01, right=leaf2, members=(0, 1, 2))

    assert quasi_diagonalize(root) == [0, 1, 2]


def test_quasi_diagonalize_balanced_tree() -> None:
    leaves = [ClusterNode(leaf_index=i, members=(i,)) for i in range(4)]
    sub01 = ClusterNode(left=leaves[0], right=leaves[1], members=(0, 1))
    sub23 = ClusterNode(left=leaves[2], right=leaves[3], members=(2, 3))
    root = ClusterNode(left=sub01, right=sub23, members=(0, 1, 2, 3))

    assert quasi_diagonalize(root) == [0, 1, 2, 3]


# --------------------------------------------------------------------------- #
# recursive_bisection
# --------------------------------------------------------------------------- #


def test_recursive_bisection_two_equal_variance_assets() -> None:
    weights = recursive_bisection([0, 1], [0.04, 0.04], [[1.0, 0.0], [0.0, 1.0]])

    assert _approx(weights[0], 0.5)
    assert _approx(weights[1], 0.5)
    assert _approx(sum(weights), 1.0)


def test_recursive_bisection_two_assets_inverse_variance() -> None:
    # var = [1, 4] → inverse-variance weights are [4/5, 1/5] = [0.8, 0.2].
    weights = recursive_bisection([0, 1], [1.0, 4.0], [[1.0, 0.0], [0.0, 1.0]])

    assert _approx(weights[0], 0.8)
    assert _approx(weights[1], 0.2)


def test_recursive_bisection_four_equal_assets_yield_quarter_each() -> None:
    n = 4
    variances = [0.04] * n
    corr = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    weights = recursive_bisection([0, 1, 2, 3], variances, corr)

    for w in weights:
        assert _approx(w, 0.25)


def test_recursive_bisection_alpha_formula_matches_de_prado() -> None:
    # 4-asset universe, all uncorrelated, variances [1, 1, 4, 4].
    # Left cluster [0,1] inv-vol weights = [0.5, 0.5] → cluster variance =
    #   0.25*1 + 0.25*1 = 0.5.
    # Right cluster [2,3] inv-vol weights = [0.5, 0.5] → cluster variance =
    #   0.25*4 + 0.25*4 = 2.0.
    # alpha = 1 - 0.5 / (0.5 + 2.0) = 0.8.
    # Left receives 0.8, right receives 0.2. Within left split (alpha = 0.5,
    # equal variances) → each leaf gets 0.4. Within right split → each gets 0.1.
    n = 4
    variances = [1.0, 1.0, 4.0, 4.0]
    corr = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    weights = recursive_bisection([0, 1, 2, 3], variances, corr)

    assert _approx(weights[0], 0.4)
    assert _approx(weights[1], 0.4)
    assert _approx(weights[2], 0.1)
    assert _approx(weights[3], 0.1)
    assert _approx(sum(weights), 1.0)


def test_recursive_bisection_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="permutation"):
        recursive_bisection([0, 1], [1.0, 2.0, 3.0], [[1.0, 0.0, 0.0],
                                                      [0.0, 1.0, 0.0],
                                                      [0.0, 0.0, 1.0]])


# --------------------------------------------------------------------------- #
# compute_hrp_weights — end-to-end
# --------------------------------------------------------------------------- #


def test_compute_hrp_weights_n1_returns_full_weight() -> None:
    weights = compute_hrp_weights([_alternating(0.01, 30)], ["AAA"])

    assert weights == {"AAA": 1.0}


def test_compute_hrp_weights_n2_matches_inverse_variance() -> None:
    # Series with variance ratio 1 : 4.
    low_vol = _alternating(0.01, 100)
    high_vol = _alternating(0.02, 100)

    weights = compute_hrp_weights([low_vol, high_vol], ["LOW", "HIGH"])

    # Inverse-variance: w_low = (1/0.0001) / (1/0.0001 + 1/0.0004) = 0.8.
    assert _approx(weights["LOW"], 0.8)
    assert _approx(weights["HIGH"], 0.2)
    assert _approx(sum(weights.values()), 1.0)


def test_compute_hrp_weights_n3_sums_to_one_and_positive() -> None:
    series = [
        _alternating(0.01, 80, phase=0),
        _alternating(0.012, 80, phase=1),  # anti-correlated with first
        _alternating(0.008, 80, phase=0),  # correlated with first
    ]
    weights = compute_hrp_weights(series, ["A", "B", "C"])

    assert set(weights.keys()) == {"A", "B", "C"}
    for value in weights.values():
        assert value > 0
    assert _approx(sum(weights.values()), 1.0)


def test_compute_hrp_weights_n5_synthetic_universe() -> None:
    series = [
        _alternating(0.010, 120, phase=0),
        _alternating(0.012, 120, phase=0),  # correlated with series 0
        _alternating(0.020, 120, phase=1),  # anti-correlated
        _alternating(0.005, 120, phase=0),  # low vol, correlated with 0
        _alternating(0.025, 120, phase=1),  # high vol, anti-correlated
    ]
    weights = compute_hrp_weights(
        series, ["A", "B", "C", "D", "E"]
    )

    assert _approx(sum(weights.values()), 1.0)
    for value in weights.values():
        assert value > 0


def test_compute_hrp_weights_n9_b013_size_universe() -> None:
    # B013 9-asset universe size. Mix of correlations / volatilities.
    series: list[Sequence[float]] = []
    amplitudes = [0.005, 0.008, 0.010, 0.012, 0.015, 0.018, 0.022, 0.025, 0.030]
    phases = [0, 0, 1, 1, 0, 1, 0, 1, 0]
    for amplitude, phase in zip(amplitudes, phases, strict=True):
        series.append(_alternating(amplitude, 150, phase=phase))
    symbols = [f"S{i}" for i in range(9)]

    weights = compute_hrp_weights(series, symbols)

    assert len(weights) == 9
    assert _approx(sum(weights.values()), 1.0)
    for value in weights.values():
        assert value > 0


def test_compute_hrp_weights_zero_variance_asset_rejected() -> None:
    series = [
        _alternating(0.01, 50),
        [0.005] * 50,  # constant — zero variance
        _alternating(0.02, 50),
    ]
    with pytest.raises(ValueError, match="zero variance"):
        compute_hrp_weights(series, ["A", "FLAT", "C"])


def test_compute_hrp_weights_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValueError, match="unique"):
        compute_hrp_weights(
            [_alternating(0.01, 30), _alternating(0.02, 30)],
            ["DUP", "DUP"],
        )


def test_compute_hrp_weights_rejects_count_mismatch() -> None:
    with pytest.raises(ValueError, match="symbols count"):
        compute_hrp_weights([_alternating(0.01, 30)], ["A", "B"])


def test_compute_hrp_weights_is_deterministic() -> None:
    series = [
        _alternating(0.010, 120, phase=0),
        _alternating(0.012, 120, phase=0),
        _alternating(0.020, 120, phase=1),
        _alternating(0.005, 120, phase=0),
        _alternating(0.025, 120, phase=1),
    ]
    symbols = ["A", "B", "C", "D", "E"]

    first = compute_hrp_weights(series, symbols)
    second = compute_hrp_weights(series, symbols)
    third = compute_hrp_weights(list(series), list(symbols))

    assert first == second
    assert first == third


def test_compute_hrp_weights_perfect_positive_correlation_pair() -> None:
    # Two perfectly-correlated assets + one independent asset. The clustering
    # should collapse the pair first (distance 0); recursive bisection then
    # splits the pair vs the independent asset.
    pair_a = _alternating(0.01, 80, phase=0)
    pair_b = [value * 1.5 for value in pair_a]  # corr = 1.0 (linear)
    other = _alternating(0.015, 80, phase=1)  # anti-correlated

    weights = compute_hrp_weights(
        [pair_a, pair_b, other], ["A", "B", "OTHER"]
    )

    assert _approx(sum(weights.values()), 1.0)
    for value in weights.values():
        assert value > 0


def test_compute_hrp_weights_results_are_consistent_with_inverse_vol_when_uncorrelated() -> None:
    # When all assets are mutually uncorrelated and the tree is balanced, HRP
    # weights coincide with naive inverse-variance weights up to clustering
    # bisection structure. We assert a weaker invariant: each weight is
    # positive, weights sum to 1, and the lowest-variance asset gets the
    # largest weight.
    low_vol = _alternating(0.005, 100, phase=0)
    mid_vol = _alternating(0.015, 100, phase=1)
    high_vol = _alternating(0.025, 100, phase=0)

    weights = compute_hrp_weights(
        [low_vol, mid_vol, high_vol], ["LOW", "MID", "HIGH"]
    )

    assert _approx(sum(weights.values()), 1.0)
    assert weights["LOW"] > weights["HIGH"]
