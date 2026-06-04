"""B035 F002 — market-context CLI (offline, injected fake loaders).

Pins the flag contract, source dispatch over the 6 series, snapshot-dir
creation, the env-var snapshot root, and error aggregation — all without
real API keys or network (loaders injected via ``loader_factory``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workbench_api.data.market_context_common import (
    SOURCE_ALPHA_VANTAGE,
    SOURCE_FRED,
)
from workbench_api.market.cli import (
    REPO_ROOT,
    FetchSummary,
    _default_snapshot_root,
    fetch_main,
    parse_args,
)


class _FakeLoader:
    def __init__(self, *, saved_per_series: int = 1, raise_on: str | None = None) -> None:
        self._saved = saved_per_series
        self._raise_on = raise_on
        self.calls: list[str] = []

    def fetch_and_store(self, series_id: str, *, repo: object, writer: object) -> int:  # noqa: ARG002
        self.calls.append(series_id)
        if series_id == self._raise_on:
            raise RuntimeError(f"boom {series_id}")
        return self._saved


def test_parse_args_defaults() -> None:
    args = parse_args(["fetch"])
    assert args.command == "fetch"
    assert args.source == "all"


def test_parse_args_source_choice() -> None:
    assert parse_args(["fetch", "--source", "fred"]).source == "fred"


def test_default_snapshot_root_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    persistent = tmp_path / "var" / "lib" / "workbench" / "data" / "snapshots" / "market-context"
    monkeypatch.setenv("WORKBENCH_MARKET_SNAPSHOT_DIR", str(persistent))
    assert _default_snapshot_root() == persistent


def test_default_snapshot_root_repo_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_MARKET_SNAPSHOT_DIR", raising=False)
    assert _default_snapshot_root() == REPO_ROOT / "data" / "snapshots" / "market-context"


def test_fetch_main_dispatches_all_six_series(
    initialised_db: str, tmp_path: Path  # noqa: ARG001
) -> None:
    fred = _FakeLoader()
    av = _FakeLoader()

    def factory(*, source_arg: str) -> dict[str, object]:  # noqa: ARG001
        return {SOURCE_FRED: fred, SOURCE_ALPHA_VANTAGE: av}

    args = parse_args(["fetch", "--snapshot-root", str(tmp_path / "snaps")])
    summary = fetch_main(args, loader_factory=factory)  # type: ignore[arg-type]
    assert isinstance(summary, FetchSummary)
    assert summary.errors == 0
    assert summary.saved == 6  # 3 FRED + 3 AV, 1 each
    assert fred.calls == ["DGS10", "VIXCLS", "CPIAUCSL"]
    assert av.calls == ["SPY", "QQQ", "UUP"]


def test_fetch_main_source_subset(initialised_db: str, tmp_path: Path) -> None:  # noqa: ARG001
    fred = _FakeLoader()

    def factory(*, source_arg: str) -> dict[str, object]:  # noqa: ARG001
        return {SOURCE_FRED: fred}

    args = parse_args(["fetch", "--source", "fred", "--snapshot-root", str(tmp_path / "s")])
    summary = fetch_main(args, loader_factory=factory)  # type: ignore[arg-type]
    assert summary.saved == 3
    assert fred.calls == ["DGS10", "VIXCLS", "CPIAUCSL"]


def test_fetch_main_creates_snapshot_dirs(
    initialised_db: str, tmp_path: Path  # noqa: ARG001
) -> None:
    root = tmp_path / "snaps"

    def factory(*, source_arg: str) -> dict[str, object]:  # noqa: ARG001
        return {}

    fetch_main(parse_args(["fetch", "--snapshot-root", str(root)]), loader_factory=factory)  # type: ignore[arg-type]
    assert (root / SOURCE_FRED).is_dir()
    assert (root / SOURCE_ALPHA_VANTAGE).is_dir()


def test_fetch_main_counts_errors(
    initialised_db: str, tmp_path: Path  # noqa: ARG001
) -> None:
    fred = _FakeLoader(raise_on="VIXCLS")

    def factory(*, source_arg: str) -> dict[str, object]:  # noqa: ARG001
        return {SOURCE_FRED: fred}

    args = parse_args(["fetch", "--source", "fred", "--snapshot-root", str(tmp_path / "s")])
    summary = fetch_main(args, loader_factory=factory)  # type: ignore[arg-type]
    assert summary.errors == 1
    assert summary.saved == 2  # DGS10 + CPIAUCSL succeed, VIXCLS raises
