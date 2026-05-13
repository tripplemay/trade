"""Manual-only public data import boundary.

This module never downloads data. It only provides an explicit local-file import boundary for
research users who already obtained public data outside the required CI/default workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIRECTORY = Path("data/public-cache")
MANUAL_CONFIRM_FLAG = "--i-understand-this-is-manual-research-data"
LIMITATION_LABELS = (
    "public-best-effort",
    "non-PIT",
    "research-only",
    "not-live-trading-ready",
)


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
    manifest_file: Path
    snapshot_id: str
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
    manifest = _build_manifest(output_file, request.provider.strip())
    manifest_file = output_directory / f"{manifest['snapshot_id']}-manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return PublicImportResult(
        provider=request.provider.strip(),
        source_file=source_file,
        output_file=output_file,
        manifest_file=manifest_file,
        snapshot_id=str(manifest["snapshot_id"]),
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
    print(f"Snapshot manifest: {result.manifest_file}")
    print(f"Snapshot ID: {result.snapshot_id}")
    print(f"Label: {result.data_label}")
    print(f"Limitation: {result.limitation}")
    return 0


def _build_manifest(output_file: Path, provider: str) -> dict[str, Any]:
    file_hash = _sha256_file(output_file)
    csv_summary = _summarize_csv(output_file)
    snapshot_id = f"public:{provider.lower().replace(' ', '-')}:{file_hash[:16]}"
    return {
        "snapshot_id": snapshot_id,
        "source": "manual-public-data-import",
        "provider": provider,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "tickers": csv_summary["tickers"],
        "date_range": csv_summary["date_range"],
        "row_count": csv_summary["row_count"],
        "files": [
            {
                "path": output_file.as_posix(),
                "sha256": file_hash,
            }
        ],
        "data_source_policy": "manual credential-free public data import",
        "limitation_labels": list(LIMITATION_LABELS),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summarize_csv(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        tickers: set[str] = set()
        dates: list[str] = []
        row_count = 0
        for row in reader:
            row_count += 1
            symbol = (row.get("symbol") or row.get("ticker") or "").strip()
            if symbol:
                tickers.add(symbol)
            row_date = (row.get("date") or "").strip()
            if row_date:
                dates.append(row_date)

    return {
        "tickers": sorted(tickers),
        "date_range": {
            "start": min(dates) if dates else None,
            "end": max(dates) if dates else None,
        },
        "row_count": row_count,
    }


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
