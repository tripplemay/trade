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
