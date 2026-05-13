"""Manual-only public data import boundary.

This module intentionally does not download data. It documents the safe boundary for a future
manual importer while keeping required CI and default workflows offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PublicImportBoundary:
    enabled_by_default: bool
    ci_dependency: bool
    requires_credentials: bool
    output_directory: Path
    data_label: str
    limitation: str


def public_import_boundary() -> PublicImportBoundary:
    return PublicImportBoundary(
        enabled_by_default=False,
        ci_dependency=False,
        requires_credentials=False,
        output_directory=Path("data/public-cache"),
        data_label="optional_public_best_effort_non_pit",
        limitation="Manual research aid only; not point-in-time production data.",
    )


def import_public_data_stub() -> None:
    """Fail closed until a later spec authorizes a manual downloader implementation."""

    raise RuntimeError(
        "Public data import is intentionally disabled in B008. Required workflows use committed "
        "fixtures only; any future importer must be manual, credential-free, off-CI, and write "
        "only to gitignored local paths."
    )
