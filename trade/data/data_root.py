"""B045 F002 — VM data-root override for the unified real-data CSVs.

The unified prices / fundamentals CSVs are read from one of two roots:

* **Local / CI** (env unset): under the repo root —
  ``<repo>/data/snapshots/{prices,fundamentals}/unified/…``. Every existing
  backtest and test keeps resolving exactly as before; this module is a
  no-op on that path.
* **VM** (``WORKBENCH_DATA_ROOT`` set): under that root —
  ``<root>/snapshots/{prices,fundamentals}/unified/…``. The workbench
  ``data-refresh`` / ``recommendations`` systemd units export
  ``WORKBENCH_DATA_ROOT=/var/lib/workbench/data`` — the same root the B045
  F001 refresh CLI *writes* under, so the loaders read precisely what the
  refresh job produced.

Note the layout: the VM root already *is* the data dir, so the override
joins ``snapshots/…`` directly (no extra ``data`` segment), matching the
F001 writer's relative paths
(``<data_root>/snapshots/prices/unified/prices_daily.csv``). The repo-root
default keeps its ``data/`` segment because that is the repo layout.

Only the **unified (real-data)** paths honour the override. The B025
synthetic fixtures stay repo-root bundled — the deterministic fall-back is
independent of where real data lives, so ``FORCE_FIXTURE_PATH`` and explicit
``fixture_dir`` arguments are unaffected by this module.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT_ENV = "WORKBENCH_DATA_ROOT"

# Relative path of each unified CSV beneath a data root. Mirrors the B045 F001
# writer (``workbench_api.data_refresh.refresh.{PRICES,FUNDAMENTALS}_RELPATH``);
# drift between the two means the loaders read a file the refresh job never
# wrote. The repo-root constants in ``loader`` / ``us_quality_universe`` prepend
# a ``data`` segment to these for the local layout.
UNIFIED_PRICES_RELPATH = ("snapshots", "prices", "unified", "prices_daily.csv")
UNIFIED_FUNDAMENTALS_RELPATH = ("snapshots", "fundamentals", "unified", "fundamentals.csv")


def data_root_override() -> Path | None:
    """Return the VM data root if ``WORKBENCH_DATA_ROOT`` is set, else ``None``.

    Whitespace-only values (a stray newline in an env file) count as unset so
    a malformed env never silently redirects the loaders to ``/``.
    """

    root = os.environ.get(DATA_ROOT_ENV, "").strip()
    return Path(root) if root else None


def unified_prices_path(repo_root_default: Path) -> Path:
    """Resolve the unified prices CSV: VM override if set, else the repo default."""

    override = data_root_override()
    if override is not None:
        return override.joinpath(*UNIFIED_PRICES_RELPATH)
    return repo_root_default


def unified_fundamentals_path(repo_root_default: Path) -> Path:
    """Resolve the unified fundamentals CSV: VM override if set, else repo default."""

    override = data_root_override()
    if override is not None:
        return override.joinpath(*UNIFIED_FUNDAMENTALS_RELPATH)
    return repo_root_default
