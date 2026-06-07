"""B045 F002 — ``WORKBENCH_DATA_ROOT`` override for the unified CSV loaders.

Pins the dual-path contract:

* **env unset** (local / CI) → the unified paths resolve under the repo root
  exactly as before; every existing backtest / test is untouched.
* **env set** (VM) → the unified paths resolve under
  ``<root>/snapshots/{prices,fundamentals}/unified/…`` — the same layout the
  B045 F001 refresh CLI writes, so the loaders read the refreshed real data.

The B025 fixture fall-back is preserved in both modes: a set-but-missing VM
root must fall back to the synthetic fixture, never crash.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trade.data import loader, us_quality_universe
from trade.data.data_root import (
    DATA_ROOT_ENV,
    UNIFIED_FUNDAMENTALS_RELPATH,
    UNIFIED_PRICES_RELPATH,
    data_root_override,
    unified_fundamentals_path,
    unified_prices_path,
)

_REPO_DEFAULT = Path("/repo/data/snapshots/prices/unified/prices_daily.csv")


# ---------------------------------------------------------------------------
# data_root_override / env parsing
# ---------------------------------------------------------------------------


def test_override_none_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    assert data_root_override() is None


def test_override_returns_path_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, "/var/lib/workbench/data")
    assert data_root_override() == Path("/var/lib/workbench/data")


def test_override_whitespace_only_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stray newline in an env file must not redirect the loaders to ``/``."""

    monkeypatch.setenv(DATA_ROOT_ENV, "  \n")
    assert data_root_override() is None


# ---------------------------------------------------------------------------
# unified_*_path — repo default vs VM override
# ---------------------------------------------------------------------------


def test_unified_prices_path_returns_repo_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    assert unified_prices_path(_REPO_DEFAULT) == _REPO_DEFAULT


def test_unified_prices_path_uses_vm_root_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, "/var/lib/workbench/data")
    expected = Path("/var/lib/workbench/data").joinpath(*UNIFIED_PRICES_RELPATH)
    assert unified_prices_path(_REPO_DEFAULT) == expected
    # No extra ``data`` segment — the VM root already IS the data dir.
    assert "data/snapshots" not in str(expected).replace("workbench/data", "workbench")


def test_unified_fundamentals_path_uses_vm_root_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, "/var/lib/workbench/data")
    expected = Path("/var/lib/workbench/data").joinpath(*UNIFIED_FUNDAMENTALS_RELPATH)
    assert unified_fundamentals_path(_REPO_DEFAULT) == expected


def test_relpaths_match_f001_writer_layout() -> None:
    """Drift guard: these relpaths must equal the B045 F001 refresh writer's
    so the loaders read precisely the file the refresh job wrote."""

    assert UNIFIED_PRICES_RELPATH == ("snapshots", "prices", "unified", "prices_daily.csv")
    assert UNIFIED_FUNDAMENTALS_RELPATH == (
        "snapshots",
        "fundamentals",
        "unified",
        "fundamentals.csv",
    )


# ---------------------------------------------------------------------------
# loader._resolve_*_source honours the override
# ---------------------------------------------------------------------------


def _write_prices_csv(path: Path, ticker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=(
                "date", "ticker", "open", "high", "low", "close", "adj_close", "volume",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2025-02-04", "ticker": ticker, "open": "99", "high": "101",
                "low": "98", "close": "100", "adj_close": "100", "volume": "1000000",
            }
        )


def test_loader_prices_source_reads_vm_root_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    vm_unified = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    _write_prices_csv(vm_unified, "ZVM_PRICE")
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    assert loader._resolve_prices_source() == vm_unified


def test_loader_prices_source_unchanged_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env unset → resolver uses the repo-root constant (monkeypatched here to
    a missing path) and falls back to the bundled B025 fixture, never the VM."""

    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    monkeypatch.setattr(loader, "UNIFIED_PRICES_PATH", tmp_path / "missing.csv")

    resolved = loader._resolve_prices_source()
    assert resolved == loader.B025_FIXTURE_PRICES_PATH


def test_loader_fundamentals_source_reads_vm_root_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    vm_unified = tmp_path.joinpath(*UNIFIED_FUNDAMENTALS_RELPATH)
    vm_unified.parent.mkdir(parents=True, exist_ok=True)
    vm_unified.write_text("report_date,ticker\n2025-02-04,ZVM\n", encoding="utf-8")
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    assert loader._resolve_fundamentals_source() == vm_unified


def test_loader_falls_back_to_fixture_when_vm_root_set_but_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env set but the VM file absent → fixture fall-back, not a crash."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "empty_root"))

    assert loader._resolve_prices_source() == loader.B025_FIXTURE_PRICES_PATH


# ---------------------------------------------------------------------------
# us_quality_universe resolvers + end-to-end load honour the override
# ---------------------------------------------------------------------------


def test_us_quality_prices_path_reads_vm_root_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    vm_unified = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    _write_prices_csv(vm_unified, "ZVM_UQ")
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    assert us_quality_universe._resolve_prices_path(None) == vm_unified


def test_us_quality_load_prices_reads_vm_store_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """E2E: a sentinel-only unified CSV under the VM root must surface through
    ``load_prices()`` — proving the override drives the real read path."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    vm_unified = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    _write_prices_csv(vm_unified, "ZVM_E2E")
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    frame = us_quality_universe.load_prices()
    assert set(frame["ticker"].astype(str).tolist()) == {"ZVM_E2E"}


def test_force_fixture_path_still_wins_over_vm_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``FORCE_FIXTURE_PATH=1`` must override even a present VM unified file —
    the B025 deterministic-backtest guarantee is independent of data root."""

    vm_unified = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    _write_prices_csv(vm_unified, "ZVM_SHOULD_NOT_WIN")
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    monkeypatch.setenv("FORCE_FIXTURE_PATH", "1")

    resolved = us_quality_universe._resolve_prices_path(None)
    expected = us_quality_universe.DEFAULT_FIXTURE_DIR / us_quality_universe.PRICES_FILE_NAME
    assert resolved == expected
