#!/usr/bin/env python3
"""Opt-in CLI for importing the regime-adaptive 9-asset historical snapshot.

This research-only entry point copies user-supplied OHLCV CSV files into the gitignored
``data/public-cache/`` directory and writes a deterministic manifest at
``data/public-cache/regime-adaptive-prices-manifest.json``. The script never reaches out
to the network on its own: callers are expected to download the OHLCV files manually (for
example through their preferred public data provider) and place one ``<SYMBOL>.csv`` per
asset under the supplied source directory. The script is opt-in via an explicit
``--i-understand-this-is-manual-research-data`` flag and fails closed on missing tickers
or insufficient date coverage. No paper or live trading is authorized by these artifacts.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from trade.strategies.regime_adaptive.snapshot import (
    DEFAULT_OUTPUT_DIRECTORY,
    RegimeAdaptiveSnapshotRequest,
    import_regime_adaptive_snapshot,
)

MANUAL_CONFIRM_FLAG = "--i-understand-this-is-manual-research-data"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a manually-downloaded 9-asset OHLCV bundle into the local research "
            "cache. Research-only; never authorizes paper or live trading."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing one '<SYMBOL>.csv' file per regime-adaptive ticker.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Destination directory (default: data/public-cache, gitignored).",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=_parse_date,
        default=date(2018, 1, 1),
        help="Earliest date required in every input file (default: 2018-01-01).",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=_parse_date,
        default=date(2025, 12, 31),
        help="Latest date required in every input file (default: 2025-12-31).",
    )
    parser.add_argument(
        MANUAL_CONFIRM_FLAG,
        dest="manual_confirmation",
        action="store_true",
        help=(
            "Required acknowledgement that this is manual, best-effort, non-PIT research "
            "data and never authorizes paper or live trading."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=args.source_dir,
            output_dir=args.output_dir,
            date_from=args.date_from,
            date_to=args.date_to,
            manual_confirmation=args.manual_confirmation,
        )
    )
    print(f"snapshot_id   : {result.snapshot_id}")
    print(f"manifest_file : {result.manifest_file}")
    print(f"tickers       : {sorted(result.ticker_files)}")
    print(f"limitation    : {result.limitation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
