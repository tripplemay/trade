"""B031 F001 — permanent boundary (l) regression guard.

Business code MUST NOT hardcode LLM model names. Callers route by
task identifier through :data:`workbench_api.llm.routing.ROUTING_TABLE`,
and the routing table is the single source of truth for which model
serves which task. This indirection keeps a future provider switch
(Sonnet 4.6 → 4.8, or Anthropic → another vendor) a one-file change.

Detection scans every Python source under ``workbench/backend/`` for
known model-family substrings (``claude-haiku``, ``claude-sonnet``,
``claude-opus``, ``gpt-``, ``gemini-``, ``cohere-embed-``). The only
allow-listed callers are:

* :mod:`workbench_api.llm.routing` — the routing/price table itself
  is allowed to name models.
* :mod:`workbench_api.llm.gateway` — the gateway module references
  the default base URL constant which embeds the gateway hostname,
  not a model name; no actual model-name literals appear here.
* Test files under ``workbench/backend/tests/`` — fixtures and unit
  tests legitimately reference model names in expectations.
* JSON fixture files under ``workbench_api/llm/fixtures/`` — those
  are mocked aigc-gateway responses, not source code.

A red test here is a permanent-boundary breach. Add the routing key
+ update the routing table; do not whitelist the source file.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
LLM_DIR = BACKEND_ROOT / "workbench_api" / "llm"

FORBIDDEN_MODEL_PATTERNS: tuple[str, ...] = (
    r"claude-haiku-\d",
    r"claude-sonnet-\d",
    r"claude-opus-\d",
    r"gpt-[0-9]",
    r"gemini-\d",
    r"cohere-embed-",
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "node_modules",
        "tests",
        "fixtures",
    }
)

ALLOWED_FILES: frozenset[Path] = frozenset(
    {
        LLM_DIR / "routing.py",
        LLM_DIR / "__init__.py",
    }
)
"""Routing module + its public re-export are the only places allowed
to mention model names directly. Anything else triggers a boundary
breach."""


_PATTERN = re.compile("|".join(FORBIDDEN_MODEL_PATTERNS))


def _iter_python_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def test_no_hardcoded_model_names_outside_routing() -> None:
    """Business code must not name LLM models directly. Use
    :func:`workbench_api.llm.routing.route_task` instead — see
    permanent boundary (l) in the B031 spec."""

    offenders: list[tuple[str, str, int]] = []
    for source in _iter_python_sources(BACKEND_ROOT):
        if source in ALLOWED_FILES:
            continue
        text = source.read_text(encoding="utf-8")
        for match in _PATTERN.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            offenders.append(
                (
                    str(source.relative_to(BACKEND_ROOT)),
                    match.group(0),
                    line_number,
                )
            )
    assert offenders == [], (
        "Hardcoded LLM model name detected — permanent boundary (l) breach. "
        "Route via workbench_api.llm.routing.route_task(task=...) instead, "
        "and add the task to ROUTING_TABLE if missing. "
        f"Hits: {offenders}"
    )


def test_routing_module_is_the_only_allowed_caller() -> None:
    """Pin the allow-list so a future contributor cannot quietly add a
    file to it without updating this test. The set must stay minimal."""

    assert {
        LLM_DIR / "routing.py",
        LLM_DIR / "__init__.py",
    } == ALLOWED_FILES, (
        "ALLOWED_FILES must stay minimal. If a new allowlist entry is "
        "genuinely required, document the reason in the spec and update "
        "this assertion together with the addition."
    )
