"""B034 F001 — generator for ``embeddings-bge-m3-sample.json``.

This script produces the offline embedding fixture the backend test
suite uses for **deterministic, reproducible cosine** without billing a
real embedding call. CI never runs this script — the generated JSON is
committed and loaded directly.

Why a generator instead of recorded real bge-m3 weights?
--------------------------------------------------------
The production embedder calls the real aigc-gateway bge-m3 model
(live-validated: ``GET /v1/embeddings`` returns the OpenAI-compatible
``{data:[{embedding,...}]}`` envelope with **dim=1024** — see
``tests/unit/test_news_embedder.py::test_bge_m3_dim_is_locked`` and the
B034 signoff). The fixture's only job is to let the offline test path
exercise the cosine ranker with vectors whose relative similarity is
*known and stable*. Committing real 1024-float arrays by hand is
impractical and brittle, so instead we synthesise **deterministic**
unit vectors in the same 1024-dim space, built from an orthonormal
topic basis so the cosine ordering between news and sleeve queries is
predictable. The vectors are NOT real bge-m3 activations and must not
be treated as such — they are an offline stand-in dimensioned to match
the live model.

Run ``python data/fixtures/news/generate_embeddings_fixture.py`` to
regenerate after changing the topic weights below. The seed is fixed so
the output is byte-stable across runs and machines.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

DIM = 1024
"""bge-m3 embedding dimension — live-validated against the production
aigc-gateway (B034 F001). The synthetic vectors match this so the
offline path and the production path agree on shape."""

SEED = 20260601
"""Fixed seed → byte-stable fixture across machines / reruns."""

# Topic axes the synthetic vectors are built from. An orthonormal basis
# over these names makes cosine(news, query) reduce to the dot product
# of their topic-weight vectors, so the intended ranking is exact and
# easy to reason about in tests.
AXES: tuple[str, ...] = (
    "technology",
    "energy",
    "financial_report",
    "insider_txn",
    "material_event",
)

# Each fixture item is a weighted blend over AXES. News ids mirror the
# B033 EDGAR/Yahoo fixtures so F002's association tests can line them up
# with the universe tickers. Sleeve queries are constructed so a
# tech-quality sleeve ranks the three tech filings above the energy one.
NEWS_WEIGHTS: dict[str, dict[str, float]] = {
    # Apple 10-K — tech + an annual financial report.
    "0000320193-26-000001": {"technology": 1.0, "financial_report": 0.6},
    # Microsoft Form 4 — tech + insider transaction.
    "0000789019-26-000045": {"technology": 0.9, "insider_txn": 0.7},
    # NVIDIA 8-K — tech + a material event.
    "0001045810-26-000012": {"technology": 1.0, "material_event": 0.5},
    # Exxon 8-K — energy + a material event (contrast row).
    "0000034088-26-000007": {"energy": 1.0, "material_event": 0.5},
}

SLEEVE_QUERY_WEIGHTS: dict[str, dict[str, float]] = {
    # US Quality tech-leaning sleeve query.
    "us_quality_tech": {"technology": 1.0, "financial_report": 0.2},
    # Energy-leaning sleeve query (contrast).
    "energy_majors": {"energy": 1.0, "material_event": 0.2},
}


def _random_unit_vector(rng: random.Random) -> list[float]:
    raw = [rng.gauss(0.0, 1.0) for _ in range(DIM)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


def _gram_schmidt(vectors: list[list[float]]) -> list[list[float]]:
    """Orthonormalise a list of vectors (classic Gram-Schmidt)."""

    basis: list[list[float]] = []
    for vec in vectors:
        residual = list(vec)
        for b in basis:
            dot = sum(r * bi for r, bi in zip(residual, b, strict=True))
            residual = [r - dot * bi for r, bi in zip(residual, b, strict=True)]
        norm = math.sqrt(sum(r * r for r in residual))
        basis.append([r / norm for r in residual])
    return basis


def _blend(weights: dict[str, float], basis: dict[str, list[float]]) -> list[float]:
    acc = [0.0] * DIM
    for axis, weight in weights.items():
        b = basis[axis]
        acc = [a + weight * bi for a, bi in zip(acc, b, strict=True)]
    norm = math.sqrt(sum(a * a for a in acc))
    return [a / norm for a in acc]


def build_fixture() -> dict[str, object]:
    rng = random.Random(SEED)
    raw_basis = [_random_unit_vector(rng) for _ in AXES]
    ortho = _gram_schmidt(raw_basis)
    basis = dict(zip(AXES, ortho, strict=True))

    news = {
        news_id: _blend(weights, basis)
        for news_id, weights in NEWS_WEIGHTS.items()
    }
    sleeve_queries = {
        label: _blend(weights, basis)
        for label, weights in SLEEVE_QUERY_WEIGHTS.items()
    }
    return {
        "model": "bge-m3",
        "dim": DIM,
        "note": (
            "OFFLINE DETERMINISTIC STAND-IN — not real bge-m3 activations. "
            "Synthetic unit vectors over an orthonormal topic basis, "
            "dimensioned to match the live-validated bge-m3 dim=1024, used "
            "for reproducible cosine in CI. Regenerate with "
            "data/fixtures/news/generate_embeddings_fixture.py."
        ),
        "axes": list(AXES),
        "news": news,
        "sleeve_queries": sleeve_queries,
    }


def main() -> None:
    out_path = Path(__file__).with_name("embeddings-bge-m3-sample.json")
    fixture = build_fixture()
    out_path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(fixture['news'])} news, "  # type: ignore[arg-type]
          f"{len(fixture['sleeve_queries'])} sleeve queries, dim={DIM})")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
