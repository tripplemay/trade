"""Hierarchical Risk Parity (HRP) algorithm per De Prado (2016).

Research-only. Pure-stdlib implementation: only ``math``, ``statistics``,
``dataclasses``, ``typing``, ``collections.abc``. No third-party numerical
libraries (``numpy`` / ``scipy`` / ``pandas`` / ``sklearn`` / ``networkx``).

Pipeline:

1. Correlation matrix from per-asset daily returns.
2. Correlation distance matrix ``d_ij = sqrt(0.5 * (1 - corr_ij))``.
3. Single-linkage agglomerative clustering on the distance matrix.
4. Quasi-diagonalization: walk the cluster tree to produce an asset ordering
   in which correlated assets land adjacent to each other.
5. Recursive bisection: at each split, allocate capital between the two
   child clusters inversely proportional to their inverse-variance-weighted
   portfolio variance.

The module intentionally exposes each pipeline step as a public function so
unit tests can exercise the pieces independently against canned reference
cases. The top-level entry is :func:`compute_hrp_weights`.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class ClusterNode:
    """Binary tree node for the HRP cluster hierarchy.

    A leaf carries ``leaf_index`` (the original asset index) and has
    ``left`` / ``right`` set to ``None``. An internal node carries
    ``left`` / ``right`` ClusterNodes and ``leaf_index = None``.
    """

    leaf_index: int | None = None
    left: ClusterNode | None = None
    right: ClusterNode | None = None
    members: tuple[int, ...] = field(default=())

    @property
    def is_leaf(self) -> bool:
        return self.leaf_index is not None


_CORRELATION_EPSILON: Final[float] = 1e-12


def _validate_returns(returns: Sequence[Sequence[float]]) -> int:
    """Validate the return matrix and return the observation count ``T``.

    Raises :class:`ValueError` if shapes are inconsistent or T < 2.
    """

    n = len(returns)
    if n == 0:
        raise ValueError("returns must contain at least one asset series")
    observations = len(returns[0])
    if observations < 2:
        raise ValueError(
            f"each return series must have at least 2 observations; got {observations}"
        )
    for i, series in enumerate(returns):
        if len(series) != observations:
            raise ValueError(
                f"returns[{i}] has length {len(series)}, expected {observations}"
            )
    return observations


def compute_correlation_matrix(
    returns: Sequence[Sequence[float]],
) -> list[list[float]]:
    """Compute the NxN Pearson correlation matrix of N return series.

    Raises :class:`ValueError` if any series has zero variance (because the
    correlation is undefined). Off-diagonal values are clamped to ``[-1, 1]``
    to absorb floating-point drift.
    """

    _validate_returns(returns)
    n = len(returns)
    means = [statistics.fmean(series) for series in returns]
    centered = [
        [value - means[i] for value in series] for i, series in enumerate(returns)
    ]
    sum_sq = [sum(v * v for v in centered[i]) for i in range(n)]
    for i, ssq in enumerate(sum_sq):
        if ssq <= _CORRELATION_EPSILON:
            raise ValueError(
                f"asset index {i} has zero variance; correlation undefined"
            )

    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
    for i in range(n):
        for j in range(i + 1, n):
            cov_ij = sum(centered[i][t] * centered[j][t] for t in range(len(centered[i])))
            denom = math.sqrt(sum_sq[i] * sum_sq[j])
            corr = cov_ij / denom if denom > 0 else 0.0
            if corr > 1.0:
                corr = 1.0
            elif corr < -1.0:
                corr = -1.0
            matrix[i][j] = corr
            matrix[j][i] = corr
    return matrix


def compute_distance_matrix(
    correlation: Sequence[Sequence[float]],
) -> list[list[float]]:
    """Map a correlation matrix to a distance matrix via ``sqrt(0.5*(1-corr))``."""

    n = len(correlation)
    if n == 0:
        return []
    for i, row in enumerate(correlation):
        if len(row) != n:
            raise ValueError(
                f"correlation matrix row {i} has length {len(row)}, expected {n}"
            )

    distance: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            raw = 0.5 * (1.0 - correlation[i][j])
            if raw < 0.0:
                raw = 0.0
            d = math.sqrt(raw)
            distance[i][j] = d
            distance[j][i] = d
    return distance


def single_linkage_clustering(
    distance: Sequence[Sequence[float]],
) -> ClusterNode:
    """Agglomerative single-linkage clustering of N points.

    Deterministic tie-breaking: when multiple cluster pairs share the
    minimum distance, the pair encountered first in iteration order is
    merged. Iteration order is monotone in the original leaf indices and
    appends merged-cluster ids at the end, so output is reproducible.
    """

    n = len(distance)
    if n == 0:
        raise ValueError("cannot cluster an empty distance matrix")
    if n == 1:
        return ClusterNode(leaf_index=0, members=(0,))

    nodes: dict[int, ClusterNode] = {
        i: ClusterNode(leaf_index=i, members=(i,)) for i in range(n)
    }
    dist: dict[int, dict[int, float]] = {
        i: {j: float(distance[i][j]) for j in range(n) if j != i} for i in range(n)
    }
    active: list[int] = list(range(n))
    next_id = n

    while len(active) > 1:
        best = math.inf
        best_pair: tuple[int, int] | None = None
        for idx_a in range(len(active)):
            for idx_b in range(idx_a + 1, len(active)):
                a, b = active[idx_a], active[idx_b]
                d = dist[a][b]
                if d < best:
                    best = d
                    best_pair = (a, b)
        assert best_pair is not None  # active has >= 2 elements
        a, b = best_pair

        merged_members = nodes[a].members + nodes[b].members
        nodes[next_id] = ClusterNode(
            left=nodes[a], right=nodes[b], members=merged_members
        )

        new_row: dict[int, float] = {}
        for k in active:
            if k in (a, b):
                continue
            new_row[k] = min(dist[a][k], dist[b][k])
            dist[k][next_id] = new_row[k]
            del dist[k][a]
            del dist[k][b]
        dist[next_id] = new_row
        del dist[a]
        del dist[b]

        active.remove(a)
        active.remove(b)
        active.append(next_id)
        next_id += 1

    return nodes[active[0]]


def quasi_diagonalize(root: ClusterNode) -> list[int]:
    """Pre-order tree traversal returning the ordered leaf indices."""

    order: list[int] = []
    stack: list[ClusterNode] = [root]
    while stack:
        node = stack.pop()
        if node.is_leaf:
            assert node.leaf_index is not None
            order.append(node.leaf_index)
            continue
        # Push right first so left is processed first (pre-order, left-then-right).
        if node.right is not None:
            stack.append(node.right)
        if node.left is not None:
            stack.append(node.left)
    return order


def _cluster_variance(
    indices: Sequence[int],
    variances: Sequence[float],
    correlations: Sequence[Sequence[float]],
) -> float:
    """Variance of an inverse-variance-weighted portfolio over ``indices``."""

    inv_vars = [1.0 / variances[i] for i in indices]
    total = sum(inv_vars)
    if total <= 0:
        raise ValueError("cluster has non-positive total inverse variance")
    weights = [iv / total for iv in inv_vars]
    portfolio_var = 0.0
    for a, i in enumerate(indices):
        for b, j in enumerate(indices):
            cov_ij = correlations[i][j] * math.sqrt(variances[i] * variances[j])
            portfolio_var += weights[a] * weights[b] * cov_ij
    if portfolio_var < 0.0:
        # Floating-point rounding can produce tiny negatives near zero variance.
        portfolio_var = 0.0
    return portfolio_var


def recursive_bisection(
    order: Sequence[int],
    variances: Sequence[float],
    correlations: Sequence[Sequence[float]],
) -> list[float]:
    """Recursively bisect the quasi-diagonal ordering and allocate weights.

    Returns a list of length ``len(variances)`` where entry ``i`` is the
    HRP weight for the original asset index ``i``. Weights sum to ``1.0``
    up to floating-point error.
    """

    n = len(variances)
    if n == 0:
        return []
    if len(order) != n:
        raise ValueError(
            f"order length {len(order)} != variances length {n}; expected a permutation"
        )

    weights: list[float] = [0.0] * n
    for i in order:
        weights[i] = 1.0

    def split(segment: Sequence[int]) -> None:
        if len(segment) <= 1:
            return
        half = len(segment) // 2
        left = list(segment[:half])
        right = list(segment[half:])
        v_left = _cluster_variance(left, variances, correlations)
        v_right = _cluster_variance(right, variances, correlations)
        total = v_left + v_right
        # Degenerate clusters (total variance == 0) split capital evenly.
        alpha = 0.5 if total <= 0 else 1.0 - v_left / total
        beta = 1.0 - alpha
        for i in left:
            weights[i] *= alpha
        for i in right:
            weights[i] *= beta
        split(left)
        split(right)

    split(list(order))
    return weights


def compute_hrp_weights(
    returns: Sequence[Sequence[float]],
    symbols: Sequence[str],
) -> dict[str, float]:
    """Hierarchical Risk Parity (De Prado, 2016) weights for ``symbols``.

    ``returns[i]`` is the daily-return time series for ``symbols[i]``. All
    series must share the same length and contain at least two observations.

    Edge cases:

    - ``n == 1``: trivially ``{symbols[0]: 1.0}``.
    - ``n == 2``: inverse-variance weights (clustering is degenerate; both
      methods agree).
    - Any asset with zero / non-positive variance raises :class:`ValueError`.
    """

    n = len(symbols)
    if n == 0:
        raise ValueError("symbols must contain at least one entry")
    if len(returns) != n:
        raise ValueError(
            f"returns count {len(returns)} does not match symbols count {n}"
        )
    if len(set(symbols)) != n:
        raise ValueError("symbols must be unique")

    if n == 1:
        _validate_returns(returns)
        # Sanity-check the single series has finite variance.
        variance = statistics.variance(returns[0])
        if variance <= 0:
            raise ValueError(
                f"asset {symbols[0]!r} has zero variance; cannot compute HRP"
            )
        return {symbols[0]: 1.0}

    _validate_returns(returns)
    variances = [statistics.variance(series) for series in returns]
    for symbol, variance in zip(symbols, variances, strict=True):
        if variance <= 0:
            raise ValueError(
                f"asset {symbol!r} has zero variance; cannot compute HRP"
            )

    if n == 2:
        inv = [1.0 / v for v in variances]
        total = sum(inv)
        weights = [iv / total for iv in inv]
        return {symbols[0]: weights[0], symbols[1]: weights[1]}

    correlations = compute_correlation_matrix(returns)
    distances = compute_distance_matrix(correlations)
    root = single_linkage_clustering(distances)
    order = quasi_diagonalize(root)
    raw_weights = recursive_bisection(order, variances, correlations)

    # Normalise to guard against floating-point drift; the algorithm already
    # produces a near-unit sum, but explicit normalisation keeps downstream
    # invariants tight.
    weight_sum = sum(raw_weights)
    if weight_sum <= 0:
        raise ValueError("HRP produced non-positive total weight")
    return {
        symbol: raw_weights[i] / weight_sum for i, symbol in enumerate(symbols)
    }
