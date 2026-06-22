"""B073 F001 — shared VCR (vcrpy / pytest-recording) configuration.

The three httpx loaders (Tiingo / SEC EDGAR / LLM gateway) build a real
``httpx.Client`` at construction. pytest-recording patches httpx's transport
during a ``@pytest.mark.vcr`` test so the loader's real client is intercepted
and served from a committed cassette under ``tests/cassettes/<module>/`` — no
API key, no network, deterministic. The in-process fake-client unit tests stay
untouched (VCR is a *supplement* that catches API-shape drift, the B031 lesson,
not a replacement).

Why these settings:

* ``record_mode="none"`` — replay only. A request with no matching cassette
  entry raises ``CannotOverwriteExistingCassetteException`` instead of silently
  hitting the network. This is also what gives the F002 deterministic safety
  eval its teeth: a code change that fires an *extra* / *different* gateway call
  finds no cassette entry and reddens the gate.
* ``match_on`` excludes ``body`` deliberately. httpx serialises JSON bodies
  compactly (``{"a":1}``) and vcrpy matches bodies byte-for-byte, so a
  hand-authored body containing a multi-kB system prompt is unmaintainable.
  Two same-URL POSTs (the advisor haiku call then the Sonnet judge call) are
  instead disambiguated by *recorded order* — vcrpy serves matching
  interactions in sequence.
* ``filter_headers`` / ``filter_query_parameters`` scrub the API key/token on
  **record** so a re-recorded cassette never carries a secret into git.

See ``tests/cassettes/README.md`` for the re-record runbook.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Matchers that uniquely identify a recorded interaction without matching on the
# (compact, prompt-heavy) request body. Query params are compared parsed, so
# their order does not matter.
VCR_MATCH_ON = ["method", "scheme", "host", "port", "path", "query"]

# Header / query keys scrubbed to a placeholder when a cassette is (re-)recorded
# against a live API. Tiingo + gateway carry the secret in the Authorization
# header; a defensive query scrub covers vendors that put a token in the URL.
VCR_FILTER_HEADERS = ["authorization"]
VCR_FILTER_QUERY_PARAMETERS = ["token", "apikey", "api_key"]


@pytest.fixture
def vcr_config() -> dict[str, Any]:
    """VCR settings applied to every ``@pytest.mark.vcr`` test (pytest-recording)."""

    return {
        "record_mode": "none",
        "match_on": VCR_MATCH_ON,
        "filter_headers": VCR_FILTER_HEADERS,
        "filter_query_parameters": VCR_FILTER_QUERY_PARAMETERS,
    }


@pytest.fixture
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """Centralise cassettes under ``tests/cassettes/<test-module>/``.

    Overrides pytest-recording's default (a ``cassettes/`` dir next to the test
    file) so every committed cassette lives under the single ``tests/cassettes``
    hub the spec pins, namespaced by module so test names cannot collide.
    """

    module_name = request.module.__name__.rsplit(".", 1)[-1]
    return str(Path(__file__).parent / "cassettes" / module_name)
