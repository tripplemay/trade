"""B072 F003 — shared ``--as-of`` injectable-clock helper for the timer CLIs.

Every scheduled job (``workbench-recommendations`` / ``-advisor`` / ``-prices`` /
``-data-refresh`` / ``-canonical`` / ``-paper-mtm`` / ``-news`` / ``-regime-precompute``)
anchors its run on a wall-clock ``datetime.now(UTC)`` read at the CLI top. That
hard read is why CI cannot fast-forward a timer to a fixed date to verify its
*scheduled* behaviour deterministically.

This helper adds an optional ``--as-of YYYY-MM-DD`` flag that, when present,
replaces that wall-clock read with the injected date — threaded into each job's
**existing** service-layer run-date seam (``today=`` / ``as_of=`` / ``on_date=`` +
``now=`` / the price-load cutoff). **Omitting the flag is byte-for-byte the old
behaviour** (``datetime.now(UTC)``), so production timers are unchanged — the
flag is CI / test fast-forward only.

Out of scope (no clean run-date seam): the backtest *worker* is a long-running
daemon with no per-run "as of" (its sibling timer ``canonical`` carries the
flag); ``cn_attack`` derives its as-of date from the scored data rather than a
top-level clock read, so a faithful injection needs a deeper CN-loader change
than this batch takes on.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

AS_OF_HELP = (
    "Run the job as of this ISO date (YYYY-MM-DD) instead of today (UTC). "
    "CI / test fast-forward only — production timers omit it and use the wall "
    "clock, so the default behaviour is unchanged."
)


def add_as_of_argument(parser: argparse.ArgumentParser) -> None:
    """Register the shared ``--as-of`` flag on ``parser`` (default ``None``).

    ``type=date.fromisoformat`` makes argparse reject a malformed date with a
    clear usage error and hand back a ``date`` (or ``None`` when omitted)."""

    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help=AS_OF_HELP,
    )


def resolve_now(as_of: date | None) -> datetime:
    """The job's wall-clock ``now``: the real ``datetime.now(UTC)`` when
    ``as_of`` is ``None`` (production), else midnight UTC of the injected date
    (CI fast-forward). Jobs that key off ``now.date()`` then run "as of" it."""

    if as_of is None:
        return datetime.now(UTC)
    return datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)
