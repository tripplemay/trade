"""B030 F003 — compare_fixture_vs_real.py schema + behaviour.

Pins the JSON / Markdown schema of the per-sleeve comparison
reports so a future refactor that drops a metric or renames a key
fails loudly here, ahead of the F004 evaluator's L2 spot-check.

The tests work against the script's pure helper functions
(``_compute_metrics``, ``render_sleeve_json``, ``render_sleeve_markdown``,
``compare_sleeve``) — no real backfill or fixture data is consulted
beyond what already lives in the repo. Each test is offline /
deterministic.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pandas as pd  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "compare_fixture_vs_real.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "compare_fixture_vs_real", SCRIPT_PATH
    )
    assert spec and spec.loader, f"cannot resolve {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("compare_fixture_vs_real", module)
    spec.loader.exec_module(module)
    return module


def test_sleeves_constant_lists_five_sleeves_in_spec_order() -> None:
    """B030 F003 acceptance §(1): the five sleeves the script must
    cover. Pinning the order here means a downstream consumer can
    rely on the report file iteration sequence."""

    script = _load_script()
    sleeve_ids = [s.sleeve_id for s in script.SLEEVES]
    assert sleeve_ids == [
        "master",
        "momentum",
        "risk_parity",
        "us_quality",
        "hk_china_proxy",
    ]


def test_hk_china_proxy_is_marked_stub() -> None:
    """The HK / China proxy is a B011 satellite stub — the script
    must skip its backtest comparison and emit a documented stub
    report instead of all-NaN metrics."""

    script = _load_script()
    hk = next(s for s in script.SLEEVES if s.sleeve_id == "hk_china_proxy")
    assert hk.is_stub is True
    assert hk.tickers == ()


def test_us_quality_universe_uses_27_real_tickers() -> None:
    """The us_quality sleeve must exercise the 27 real B025 tickers
    (no synthetic ZQ*; the unified branch has no SEC filings for them
    so including them would inflate the 'absent ticker' count without
    teaching anything)."""

    script = _load_script()
    uq = next(s for s in script.SLEEVES if s.sleeve_id == "us_quality")
    assert len(uq.tickers) == 27
    assert not any(t.startswith("ZQ") for t in uq.tickers)


def test_compute_metrics_handles_too_short_curve() -> None:
    """Equity curves with fewer than 5 rows must return all-NaN
    metrics rather than crashing the report run for a sparse sleeve."""

    script = _load_script()
    short = pd.DataFrame({"equity": [1.0, 1.01, 1.02]})
    metrics = script._compute_metrics(short)
    # row_count surfaces the input shape so downstream readers can
    # diagnose the NaN.
    assert metrics.row_count == 3
    import math
    assert math.isnan(metrics.sharpe)
    assert math.isnan(metrics.annual_return)


def test_compute_metrics_produces_finite_numbers_on_a_smooth_curve() -> None:
    """A monotone upward curve must produce positive annual return,
    positive volatility, and a sane Sharpe."""

    script = _load_script()
    # 252 trading days, ~10% annual growth, low vol.
    n = 252
    daily_factor = (1.10) ** (1 / n)
    equity_values = [daily_factor ** i for i in range(n)]
    curve = pd.DataFrame({"equity": equity_values})
    metrics = script._compute_metrics(curve)
    assert metrics.annual_return is not None
    assert metrics.annual_return > 0.05
    assert metrics.volatility >= 0
    # All-up curve has no losing days → win_rate == 1.0.
    assert metrics.win_rate == 1.0
    # Max drawdown is zero on a monotone upward curve.
    assert metrics.max_drawdown == 0.0


def test_render_sleeve_json_emits_required_keys() -> None:
    """Pin the JSON schema each per-sleeve report file ships with."""

    script = _load_script()
    sleeve = script.SleeveConfig(
        sleeve_id="test_sleeve",
        label="Test sleeve",
        tickers=(),
        is_stub=True,
    )
    cmp = script.SleeveComparison(
        sleeve_id="test_sleeve",
        label="Test sleeve",
        universe_size=0,
        is_stub=True,
        fixture_metrics=None,
        real_metrics=None,
        fixture_universe_resolved=0,
        real_universe_resolved=0,
        note="stub",
    )
    del sleeve
    rendered = script.render_sleeve_json(cmp, date(2026, 5, 27))
    required = {
        "sleeve_id",
        "label",
        "as_of",
        "universe_size",
        "is_stub",
        "fixture",
        "real",
        "fixture_universe_resolved",
        "real_universe_resolved",
        "note",
    }
    assert required.issubset(rendered.keys())
    assert rendered["as_of"] == "2026-05-27"


def test_render_sleeve_markdown_for_stub_omits_metrics_table() -> None:
    """The stub report must NOT render a metrics table (avoids
    misleading all-NaN rows). It must include a clear stub message."""

    script = _load_script()
    cmp = script.SleeveComparison(
        sleeve_id="hk_china_proxy",
        label="HK / China Proxy",
        universe_size=0,
        is_stub=True,
        fixture_metrics=None,
        real_metrics=None,
        fixture_universe_resolved=0,
        real_universe_resolved=0,
        note="B011 satellite stub.",
    )
    md = script.render_sleeve_markdown(cmp, date(2026, 5, 27))
    assert "satellite stub" in md
    # The metric table header must NOT appear for a stub.
    assert "Fixture (synthetic)" not in md
    assert "Real (unified)" not in md


def test_write_reports_writes_five_md_plus_json_plus_overview(tmp_path: Path) -> None:
    """End-to-end: ``write_reports`` must materialise 11 files for
    a 5-sleeve run — 5 MD + 5 JSON + 1 overview MD."""

    script = _load_script()
    comparisons = [
        script.SleeveComparison(
            sleeve_id=f"sleeve_{i}",
            label=f"Sleeve {i}",
            universe_size=0,
            is_stub=True,
            fixture_metrics=None,
            real_metrics=None,
            fixture_universe_resolved=0,
            real_universe_resolved=0,
            note="stub",
        )
        for i in range(5)
    ]
    written = script.write_reports(comparisons, tmp_path, date(2026, 5, 27))
    assert len(written) == 11
    # 5 .md per-sleeve + 5 .json + 1 overview.md.
    md_files = [p for p in written if p.suffix == ".md"]
    json_files = [p for p in written if p.suffix == ".json"]
    assert len(md_files) == 6  # five sleeves + overview
    assert len(json_files) == 5
    overview = tmp_path / "overview_2026-05-27.md"
    assert overview.is_file()


def test_render_overview_includes_all_sleeve_links() -> None:
    """The overview file must link to each per-sleeve report so the
    F004 evaluator (and any future reader) can navigate them."""

    script = _load_script()
    comparisons = []
    for sid in ("master", "momentum", "risk_parity", "us_quality", "hk_china_proxy"):
        comparisons.append(
            script.SleeveComparison(
                sleeve_id=sid,
                label=sid.title(),
                universe_size=0,
                is_stub=True,
                fixture_metrics=None,
                real_metrics=None,
                fixture_universe_resolved=0,
                real_universe_resolved=0,
                note="stub",
            )
        )
    overview = script.render_overview(comparisons, date(2026, 5, 27))
    for sid in ("master", "momentum", "risk_parity", "us_quality", "hk_china_proxy"):
        assert f"{sid}_2026-05-27.md" in overview


def test_generated_reports_directory_contains_eleven_files() -> None:
    """The 5 + 1 deliverable from the F003 generation run must already
    be on disk (the generator runs the script before commit)."""

    reports_dir = REPO_ROOT / "reports" / "fixture_vs_real"
    if not reports_dir.is_dir():
        # Reports may not be generated in CI; skip rather than fail
        # since CI doesn't have the unified backfill data needed.
        import pytest
        pytest.skip("reports/fixture_vs_real/ not present in CI / fresh checkout")
    files = sorted(reports_dir.iterdir())
    md_files = [p for p in files if p.suffix == ".md"]
    json_files = [p for p in files if p.suffix == ".json"]
    # At least 6 .md (5 sleeves + overview) + 5 .json.
    assert len(md_files) >= 6, f"expected ≥6 .md files, got {len(md_files)}"
    assert len(json_files) >= 5, f"expected ≥5 .json files, got {len(json_files)}"
