"""Manual-only public data import boundary.

This module never downloads data. It only provides an explicit local-file import boundary for
research users who already obtained public data outside the required CI/default workflow.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT_DIRECTORY = Path("data/public-cache")
MANUAL_CONFIRM_FLAG = "--i-understand-this-is-manual-research-data"


@dataclass(frozen=True, slots=True)
class PublicImportBoundary:
    enabled_by_default: bool
    ci_dependency: bool
    requires_credentials: bool
    output_directory: Path
    data_label: str
    limitation: str


@dataclass(frozen=True, slots=True)
class PublicImportRequest:
    source_file: Path
    provider: str
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY
    manual_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class PublicImportResult:
    provider: str
    source_file: Path
    output_file: Path
    data_label: str
    limitation: str


def public_import_boundary() -> PublicImportBoundary:
    return PublicImportBoundary(
        enabled_by_default=False,
        ci_dependency=False,
        requires_credentials=False,
        output_directory=DEFAULT_OUTPUT_DIRECTORY,
        data_label="optional_public_best_effort_non_pit",
        limitation="Manual research aid only; not point-in-time production data.",
    )


def import_public_data_stub() -> None:
    """Fail closed for legacy/default callers that did not make an explicit manual request."""

    raise RuntimeError(
        "Public data import is disabled by default. Required workflows use committed fixtures "
        "only; manual research imports must pass an explicit confirmation flag, require no "
        "credentials, perform no network calls, and write only to gitignored local paths."
    )


def import_public_data(request: PublicImportRequest) -> PublicImportResult:
    """Copy a local public-data file into the gitignored research cache after explicit consent."""

    boundary = public_import_boundary()
    if not request.manual_confirmation:
        import_public_data_stub()

    source_file = request.source_file.expanduser()
    if not source_file.is_file():
        raise FileNotFoundError(f"public data source file does not exist: {source_file}")

    output_directory = request.output_directory.expanduser()
    _validate_gitignored_output_directory(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    provider_slug = _slugify_provider(request.provider)
    output_file = output_directory / f"{provider_slug}-{source_file.name}"
    shutil.copyfile(source_file, output_file)

    return PublicImportResult(
        provider=request.provider.strip(),
        source_file=source_file,
        output_file=output_file,
        data_label=boundary.data_label,
        limitation=boundary.limitation,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manually copy an already-downloaded public data file into the local research cache."
        )
    )
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        MANUAL_CONFIRM_FLAG,
        dest="manual_confirmation",
        action="store_true",
        help="Required acknowledgement that this is manual, best-effort, non-PIT research data.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = import_public_data(
        PublicImportRequest(
            source_file=args.source_file,
            provider=args.provider,
            output_directory=args.output_directory,
            manual_confirmation=args.manual_confirmation,
        )
    )
    print(f"Imported manual research data to {result.output_file}")
    print(f"Label: {result.data_label}")
    print(f"Limitation: {result.limitation}")
    return 0


def _validate_gitignored_output_directory(output_directory: Path) -> None:
    parts = output_directory.parts
    if not parts or parts[0] != "data":
        raise ValueError("public import output_directory must be under gitignored data/")


def _slugify_provider(provider: str) -> str:
    slug = "-".join(provider.strip().lower().replace("_", "-").split())
    if not slug:
        raise ValueError("provider must be a non-empty string")
    if any(char in slug for char in ("/", "\\")):
        raise ValueError("provider must not contain path separators")
    return slug


if __name__ == "__main__":
    raise SystemExit(main())
