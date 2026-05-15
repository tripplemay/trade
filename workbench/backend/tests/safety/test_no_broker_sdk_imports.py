"""Broker SDK imports are forbidden in the workbench backend.

Detection scans every Python source file under ``workbench/backend/`` for an
actual import statement referencing a known broker SDK module name. String
literals that happen to contain a forbidden name (e.g., the patterns listed in
this very file) are deliberately ignored so the safety tests do not self-trip.

A red test here is a boundary breach, not a regression. Investigate before
adding any exception.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_BROKER_MODULES: tuple[str, ...] = (
    "ib_insync",
    "alpaca",
    "alpaca_trade_api",
    "futu",
    "tiger",
    "tradier",
    "polygon",
    "oandapy",
    "tradeapi",
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "node_modules",
    }
)

IMPORT_RE = re.compile(
    rf"^\s*(?:from|import)\s+({'|'.join(re.escape(m) for m in FORBIDDEN_BROKER_MODULES)})\b",
    re.MULTILINE,
)


def _iter_python_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def test_no_broker_sdk_modules_imported() -> None:
    offenders: list[tuple[str, str, int]] = []
    for source in _iter_python_sources(BACKEND_ROOT):
        text = source.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            offenders.append((str(source.relative_to(BACKEND_ROOT)), match.group(1), line_number))

    assert offenders == [], (
        "Forbidden broker SDK import detected — workbench backend must remain "
        f"broker-free. Hits: {offenders}"
    )
