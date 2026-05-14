"""Regime-Adaptive historical public-data snapshot acquisition.

This module imports user-supplied OHLCV CSV files for the 9-asset regime-adaptive universe
into the gitignored ``data/public-cache/`` directory and emits a research-only manifest at
``data/public-cache/regime-adaptive-prices-manifest.json``. The import is opt-in (an
explicit manual-confirmation flag must be set), fails closed on missing tickers or
insufficient date coverage, and performs no network I/O. The artifact is research-only and
never authorizes any paper or production order flow.

The coverage gate is parameterised so that real public-data acquisitions can pass even
when (a) the requested ``date_from`` lands on a market holiday and the first trading day
falls a few business days later, or (b) a late-inception ticker (e.g. SGOV, real first
available date around 2020-06) cannot supply data back to ``date_from``. See
``RegimeAdaptiveSnapshotRequest.allow_short_history`` and
``RegimeAdaptiveSnapshotRequest.start_tolerance_business_days``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIRECTORY = Path("data") / "public-cache"
REQUIRED_TICKERS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "VEA",
    "VWO",
    "IEF",
    "TLT",
    "GLD",
    "DBC",
    "SGOV",
)
REGIME_ADAPTIVE_SNAPSHOT_FILENAME_PREFIX = "regime-adaptive-"
REGIME_ADAPTIVE_SNAPSHOT_MANIFEST_NAME = "regime-adaptive-prices-manifest.json"
RESEARCH_ONLY_DISCLAIMER = (
    "research-only public-best-effort non-PIT snapshot; not a trading instruction"
)
DEFAULT_START_TOLERANCE_BUSINESS_DAYS = 5
DEFAULT_SHORT_HISTORY_ALLOWANCE: frozenset[str] = frozenset({"SGOV"})


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveSnapshotRequest:
    source_dir: Path
    output_dir: Path = DEFAULT_OUTPUT_DIRECTORY
    date_from: date | None = None
    date_to: date | None = None
    manual_confirmation: bool = False
    extra_limitations: tuple[str, ...] = field(default_factory=tuple)
    allow_short_history: frozenset[str] = DEFAULT_SHORT_HISTORY_ALLOWANCE
    start_tolerance_business_days: int = DEFAULT_START_TOLERANCE_BUSINESS_DAYS


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveSnapshotResult:
    manifest_file: Path
    snapshot_id: str
    ticker_files: dict[str, Path]
    date_range: tuple[date, date]
    data_label: str
    limitation: str


class RegimeAdaptiveSnapshotError(ValueError):
    """Raised when the regime-adaptive snapshot import cannot complete."""


def import_regime_adaptive_snapshot(
    request: RegimeAdaptiveSnapshotRequest,
) -> RegimeAdaptiveSnapshotResult:
    if not request.manual_confirmation:
        raise RegimeAdaptiveSnapshotError(
            "manual confirmation flag required; snapshot import is opt-in research-only"
        )
    source_dir = request.source_dir.expanduser()
    if not source_dir.is_dir():
        raise RegimeAdaptiveSnapshotError(
            f"source_dir does not exist or is not a directory: {source_dir}"
        )
    if request.date_from is None or request.date_to is None:
        raise RegimeAdaptiveSnapshotError(
            "date_from and date_to must both be supplied to validate coverage"
        )
    if request.date_to < request.date_from:
        raise RegimeAdaptiveSnapshotError(
            "date_to must not precede date_from"
        )

    if request.start_tolerance_business_days < 0:
        raise RegimeAdaptiveSnapshotError(
            "start_tolerance_business_days must be non-negative; got "
            f"{request.start_tolerance_business_days}"
        )

    per_ticker_payloads = _read_required_tickers(source_dir)
    short_history_exempt: dict[str, bool] = {}
    for ticker, payload in per_ticker_payloads.items():
        short_history_exempt[ticker] = _ensure_coverage(
            ticker,
            payload["start"],
            payload["end"],
            request.date_from,
            request.date_to,
            allow_short_history=request.allow_short_history,
            start_tolerance_business_days=request.start_tolerance_business_days,
        )

    output_dir = request.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    ticker_files: dict[str, Path] = {}
    manifest_files: list[dict[str, Any]] = []
    for ticker, payload in per_ticker_payloads.items():
        destination = output_dir / f"{REGIME_ADAPTIVE_SNAPSHOT_FILENAME_PREFIX}{ticker}.csv"
        shutil.copyfile(payload["source_file"], destination)
        ticker_files[ticker] = destination
        manifest_files.append(
            {
                "ticker": ticker,
                "path": destination.as_posix(),
                "sha256": _sha256_file(destination),
                "row_count": payload["row_count"],
                "start": payload["start"].isoformat(),
                "end": payload["end"].isoformat(),
                "short_history_exempt": short_history_exempt[ticker],
            }
        )

    snapshot_id = _build_snapshot_id(
        request.date_from, request.date_to, manifest_files
    )
    manifest_file = output_dir / REGIME_ADAPTIVE_SNAPSHOT_MANIFEST_NAME
    manifest_payload = {
        "snapshot_id": snapshot_id,
        "source": "regime-adaptive-public-import",
        "tickers": list(REQUIRED_TICKERS),
        "date_range": {
            "start": request.date_from.isoformat(),
            "end": request.date_to.isoformat(),
        },
        "files": manifest_files,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "limitations": {
            "disclaimer": RESEARCH_ONLY_DISCLAIMER,
            "data_label": "optional_public_best_effort_non_pit",
            "extra": list(request.extra_limitations),
        },
    }
    manifest_file.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return RegimeAdaptiveSnapshotResult(
        manifest_file=manifest_file,
        snapshot_id=snapshot_id,
        ticker_files=ticker_files,
        date_range=(request.date_from, request.date_to),
        data_label="optional_public_best_effort_non_pit",
        limitation=RESEARCH_ONLY_DISCLAIMER,
    )


def _read_required_tickers(source_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for ticker in REQUIRED_TICKERS:
        path = source_dir / f"{ticker}.csv"
        if not path.is_file():
            missing.append(ticker)
            continue
        summary = _summarize_csv(path)
        payloads[ticker] = {
            "source_file": path,
            "start": summary["start"],
            "end": summary["end"],
            "row_count": summary["row_count"],
        }
    if missing:
        raise RegimeAdaptiveSnapshotError(
            f"missing required ticker files in source_dir: {missing}"
        )
    return payloads


def _ensure_coverage(
    ticker: str,
    actual_start: date,
    actual_end: date,
    required_from: date,
    required_to: date,
    *,
    allow_short_history: frozenset[str],
    start_tolerance_business_days: int,
) -> bool:
    """Validate coverage. Returns True when the ticker is short-history exempt."""

    short_history_exempt = False
    if actual_start > required_from:
        business_day_gap = _count_business_days_in_range(required_from, actual_start)
        if business_day_gap <= start_tolerance_business_days:
            # Accepted by holiday/first-trading-day tolerance; not a late-inception case.
            pass
        elif ticker in allow_short_history:
            short_history_exempt = True
        else:
            raise RegimeAdaptiveSnapshotError(
                f"date_range coverage gap for {ticker}: starts "
                f"{actual_start.isoformat()} which is {business_day_gap} business "
                f"days after required {required_from.isoformat()} (tolerance "
                f"{start_tolerance_business_days})"
            )
    if actual_end < required_to:
        raise RegimeAdaptiveSnapshotError(
            f"date_range coverage gap for {ticker}: ends {actual_end.isoformat()} "
            f"but required {required_to.isoformat()}"
        )
    return short_history_exempt


def _count_business_days_in_range(start: date, end_exclusive: date) -> int:
    """Count weekdays in the half-open interval ``[start, end_exclusive)``.

    Used to measure how many trading-eligible days are missing between
    ``required_from`` and the first available actual trading day.
    """

    if end_exclusive <= start:
        return 0
    count = 0
    current = start
    while current < end_exclusive:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _summarize_csv(path: Path) -> dict[str, Any]:
    dates: list[date] = []
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "date" not in reader.fieldnames:
            raise RegimeAdaptiveSnapshotError(f"{path} is missing the 'date' column")
        for row in reader:
            row_count += 1
            try:
                dates.append(date.fromisoformat(row["date"]))
            except (KeyError, ValueError) as exc:
                raise RegimeAdaptiveSnapshotError(
                    f"{path} contains an invalid date entry: {row.get('date')}"
                ) from exc
    if not dates:
        raise RegimeAdaptiveSnapshotError(f"{path} contains no data rows")
    return {"start": min(dates), "end": max(dates), "row_count": row_count}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_snapshot_id(
    date_from: date, date_to: date, manifest_files: list[dict[str, Any]]
) -> str:
    payload = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "files": sorted(
            ({"ticker": entry["ticker"], "sha256": entry["sha256"]} for entry in manifest_files),
            key=lambda item: item["ticker"],
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"regime-adaptive:{hashlib.sha256(canonical).hexdigest()[:16]}"
