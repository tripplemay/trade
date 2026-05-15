"""Paper and live broker API URLs are forbidden anywhere in the backend.

A simple substring scan over every source file under ``workbench/backend/``
(excluding the test file itself, which legitimately names the patterns it
guards against). The test trips the moment one of the canonical paper / live
endpoints lands in code.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SELF_PATH = Path(__file__).resolve()

FORBIDDEN_URL_FRAGMENTS: tuple[str, ...] = (
    "paper-api.alpaca.markets",
    "api.alpaca.markets",
    "paper.gateway.ibkr.com",
    "gw.gateway.ibkr.com",
    "api.futu.com",
    "api.tigerbrokers.com",
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

SCAN_SUFFIXES: frozenset[str] = frozenset({".py", ".toml", ".yml", ".yaml", ".cfg", ".ini"})


def _iter_scan_targets(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.resolve() == SELF_PATH:
            continue
        yield path


def test_no_paper_or_live_broker_urls_present() -> None:
    offenders: list[tuple[str, str]] = []
    for source in _iter_scan_targets(BACKEND_ROOT):
        text = source.read_text(encoding="utf-8", errors="replace")
        for fragment in FORBIDDEN_URL_FRAGMENTS:
            if fragment in text:
                offenders.append((str(source.relative_to(BACKEND_ROOT)), fragment))

    assert offenders == [], (
        "Forbidden broker API URL detected — workbench backend must not "
        f"reference paper or live endpoints. Hits: {offenders}"
    )
