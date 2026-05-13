"""Research-only ETF universe loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

UNIVERSE_FILE_NAME = "research_universe.json"
REQUIRED_UNIVERSE_FIELDS = (
    "ticker",
    "name",
    "asset_class",
    "region",
    "currency",
    "role",
    "data_source_policy",
    "research_notes",
)


@dataclass(frozen=True, slots=True)
class UniverseEntry:
    ticker: str
    name: str
    asset_class: str
    region: str
    currency: str
    role: str
    data_source_policy: str
    research_notes: str
    inception_date: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchUniverse:
    universe_id: str
    description: str
    data_source_policy: str
    entries: tuple[UniverseEntry, ...]


class UniverseError(ValueError):
    """Raised when the research universe config is invalid."""


def load_research_universe(path: Path | None = None) -> ResearchUniverse:
    if path is None:
        universe_file = resources.files("trade.data.fixtures").joinpath(UNIVERSE_FILE_NAME)
        with universe_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    else:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    if not isinstance(payload, dict):
        raise UniverseError("research universe payload must be a JSON object")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise UniverseError("research universe entries must be a non-empty list")
    parsed_entries = tuple(_parse_entry(entry, index) for index, entry in enumerate(entries))
    tickers = [entry.ticker for entry in parsed_entries]
    if len(tickers) != len(set(tickers)):
        raise UniverseError("research universe tickers must be unique")
    return ResearchUniverse(
        universe_id=_required_string(payload, "universe_id"),
        description=_required_string(payload, "description"),
        data_source_policy=_required_string(payload, "data_source_policy"),
        entries=parsed_entries,
    )


def _parse_entry(raw: object, index: int) -> UniverseEntry:
    if not isinstance(raw, dict):
        raise UniverseError(f"entry {index} must be a JSON object")
    missing = [field for field in REQUIRED_UNIVERSE_FIELDS if field not in raw]
    if missing:
        raise UniverseError(f"entry {index} missing fields: {', '.join(missing)}")
    inception_date = raw.get("inception_date")
    return UniverseEntry(
        ticker=_required_string(raw, "ticker"),
        name=_required_string(raw, "name"),
        asset_class=_required_string(raw, "asset_class"),
        region=_required_string(raw, "region"),
        currency=_required_string(raw, "currency"),
        role=_required_string(raw, "role"),
        data_source_policy=_required_string(raw, "data_source_policy"),
        research_notes=_required_string(raw, "research_notes"),
        inception_date=inception_date if isinstance(inception_date, str) else None,
    )


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UniverseError(f"{field} must be a non-empty string")
    return value.strip()
