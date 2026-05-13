import json
from pathlib import Path

import pytest

from trade.data.public_import import (
    MANUAL_CONFIRM_FLAG,
    PublicImportRequest,
    build_arg_parser,
    import_public_data,
    import_public_data_stub,
    public_import_boundary,
)


def test_public_import_boundary_is_manual_disabled_and_off_ci() -> None:
    boundary = public_import_boundary()

    assert boundary.enabled_by_default is False
    assert boundary.ci_dependency is False
    assert boundary.requires_credentials is False
    assert str(boundary.output_directory).startswith("data/")
    assert boundary.data_label == "optional_public_best_effort_non_pit"
    assert "not point-in-time" in boundary.limitation


def test_public_import_stub_fails_closed_without_network() -> None:
    with pytest.raises(RuntimeError, match="disabled by default"):
        import_public_data_stub()


def test_public_import_requires_explicit_manual_confirmation(tmp_path: Path) -> None:
    source_file = tmp_path / "prices.csv"
    source_file.write_text("date,symbol,open,close,adjusted_close,volume\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="disabled by default"):
        import_public_data(
            PublicImportRequest(
                source_file=source_file,
                provider="stooq",
                output_directory=Path("data/public-cache"),
            )
        )


def test_public_import_copies_local_file_to_gitignored_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source_file = tmp_path / "manual-download.csv"
    source_file.write_text("date,symbol,open,close,adjusted_close,volume\n", encoding="utf-8")

    result = import_public_data(
        PublicImportRequest(
            source_file=source_file,
            provider="Public Provider",
            output_directory=Path("data/public-cache"),
            manual_confirmation=True,
        )
    )

    assert result.output_file == Path("data/public-cache/public-provider-manual-download.csv")
    assert result.output_file.read_text(encoding="utf-8") == source_file.read_text(encoding="utf-8")
    assert result.data_label == "optional_public_best_effort_non_pit"
    assert "not point-in-time" in result.limitation


def test_public_import_writes_snapshot_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source_file = tmp_path / "manual-download.csv"
    source_file.write_text(
        "date,symbol,open,close,adjusted_close,volume\n"
        "2024-01-31,SPY,100,101,101,1000\n"
        "2024-02-29,QQQ,200,202,202,2000\n",
        encoding="utf-8",
    )

    result = import_public_data(
        PublicImportRequest(
            source_file=source_file,
            provider="Public Provider",
            output_directory=Path("data/public-cache"),
            manual_confirmation=True,
        )
    )
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))

    assert result.manifest_file == Path(f"data/public-cache/{result.snapshot_id}-manifest.json")
    assert manifest["snapshot_id"] == result.snapshot_id
    assert manifest["source"] == "manual-public-data-import"
    assert manifest["provider"] == "Public Provider"
    assert manifest["tickers"] == ["QQQ", "SPY"]
    assert manifest["date_range"] == {"start": "2024-01-31", "end": "2024-02-29"}
    assert manifest["row_count"] == 2
    assert manifest["files"][0]["path"] == "data/public-cache/public-provider-manual-download.csv"
    assert len(manifest["files"][0]["sha256"]) == 64
    assert manifest["limitation_labels"] == [
        "public-best-effort",
        "non-PIT",
        "research-only",
        "not-live-trading-ready",
    ]


def test_public_import_rejects_output_outside_gitignored_data(tmp_path: Path) -> None:
    source_file = tmp_path / "prices.csv"
    source_file.write_text("date,symbol,open,close,adjusted_close,volume\n", encoding="utf-8")

    with pytest.raises(ValueError, match="under gitignored data/"):
        import_public_data(
            PublicImportRequest(
                source_file=source_file,
                provider="stooq",
                output_directory=Path("reports/public-cache"),
                manual_confirmation=True,
            )
        )


def test_public_import_cli_confirmation_flag_is_required() -> None:
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--source-file",
            "manual.csv",
            "--provider",
            "stooq",
            MANUAL_CONFIRM_FLAG,
        ]
    )

    assert args.manual_confirmation is True
