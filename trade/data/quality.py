"""Data quality checks and research limitation markers."""

from __future__ import annotations

from dataclasses import dataclass

from trade.data.loader import DataSnapshot, PriceBar
from trade.data.public_import import public_import_boundary


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    quality_flags: tuple[str, ...]
    research_limitations: tuple[str, ...]


def evaluate_data_quality(snapshot: DataSnapshot) -> DataQualityReport:
    flags: list[str] = []
    seen: set[tuple[str, str]] = set()
    for record in snapshot.records:
        key = (record.date.isoformat(), record.symbol)
        if key in seen:
            flags.append(f"duplicate_date_symbol:{record.symbol}:{record.date.isoformat()}")
        seen.add(key)
        flags.extend(_record_flags(record))

    flags.extend(f"trading_calendar_gap:{gap}" for gap in snapshot.trading_calendar_gaps)
    flags.extend(_suspicious_jump_flags(snapshot.records))
    limitations = [
        f"sample_data_source:{snapshot.source}",
        "synthetic_fixture_data:not_investment_advice:not_live_trading_ready",
        "not_point_in_time_production_data",
        public_import_boundary().data_label,
    ]
    if _is_imported_snapshot(snapshot):
        limitations.extend(
            [
                "imported_snapshot_data",
                "public-best-effort",
                "non-PIT",
                "research-only",
                "not-live-trading-ready",
            ]
        )
    return DataQualityReport(
        quality_flags=tuple(flags),
        research_limitations=tuple(limitations),
    )


def _is_imported_snapshot(snapshot: DataSnapshot) -> bool:
    return snapshot.data_snapshot_id.startswith("snapshot:") or snapshot.source.startswith(
        "manual-public"
    )


def _record_flags(record: PriceBar) -> tuple[str, ...]:
    flags: list[str] = []
    if record.open <= 0:
        flags.append(f"non_positive_open:{record.symbol}:{record.date.isoformat()}")
    if record.close <= 0:
        flags.append(f"non_positive_close:{record.symbol}:{record.date.isoformat()}")
    if record.adjusted_close <= 0:
        flags.append(f"non_positive_adjusted_close:{record.symbol}:{record.date.isoformat()}")
    return tuple(flags)


def _suspicious_jump_flags(records: tuple[PriceBar, ...]) -> tuple[str, ...]:
    flags: list[str] = []
    by_symbol: dict[str, list[PriceBar]] = {}
    for record in records:
        by_symbol.setdefault(record.symbol, []).append(record)
    for symbol, symbol_records in by_symbol.items():
        ordered = sorted(symbol_records, key=lambda item: item.date)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            change = current.adjusted_close / previous.adjusted_close - 1.0
            if abs(change) > 0.35:
                flags.append(
                    f"suspicious_adjusted_close_jump:{symbol}:{previous.date.isoformat()}.."
                    f"{current.date.isoformat()}:{change:.4f}"
                )
    return tuple(flags)
