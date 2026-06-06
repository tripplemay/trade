"""B034 AI boundary (v0.9.28, first trigger — non-generative only).

B034 is the project's first AI-boundary touch: news → embedding. The
boundary (spec §3) is that this batch produces **vectors only**, never
user-facing AI text. Generative advice (``INSUFFICIENT_GROUNDING``
fallback, earnings-prediction ban, per-stock recommendation text) is
B036 scope.

This guard locks the non-generative property at the source level: no
module under ``workbench_api/news/`` may make a generative LLM call.
The embedding / association path calls ``LLMGateway.embed`` only —
never ``advise`` (chat completion). A future regression that wired a
generative call into the news pipeline fails here.

F003 extends this module with a response-field-set assertion on
``GET /recommendations/news`` (no free-form AI text field).
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
NEWS_PACKAGE = BACKEND_ROOT / "workbench_api" / "news"

# Generative call signatures the news pipeline must never use. ``advise``
# is the gateway's chat-completion entrypoint; ``ChatRequest`` is its
# request DTO; ``CHAT_ROUTE`` is the ``/v1/chat/completions`` path. Only
# ``embed`` (non-generative vectorisation) is allowed.
_FORBIDDEN_GENERATIVE_NAMES: frozenset[str] = frozenset(
    {"advise", "ChatRequest", "ChatResult", "CHAT_ROUTE"}
)


def _attr_and_name_tokens(py_path: Path) -> set[str]:
    """Return every attribute name and bare identifier referenced in the
    file (e.g. ``gateway.advise`` contributes ``advise``)."""

    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            tokens.add(node.attr)
        elif isinstance(node, ast.Name):
            tokens.add(node.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                tokens.add(alias.name)
    return tokens


def test_news_package_makes_no_generative_calls() -> None:
    """No file under ``workbench_api/news/`` references a generative LLM
    call surface — the embedding / association path is non-generative."""

    offending: dict[str, list[str]] = {}
    for path in NEWS_PACKAGE.rglob("*.py"):
        hits = sorted(_attr_and_name_tokens(path) & _FORBIDDEN_GENERATIVE_NAMES)
        if hits:
            offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "B034 AI boundary violated: a news-pipeline module references a "
        f"generative LLM call surface {offending}. The news embedding / "
        "association path must call LLMGateway.embed only (vectors, not "
        "AI text). Generative advice is B036 scope — add a boundary "
        "relaxation note in framework/proposed-learnings.md before merge."
    )


def test_embedder_imports_embed_not_advise() -> None:
    """The embedder module's gateway Protocol exposes ``embed`` only — a
    structural belt to the source-grep above."""

    embedder_src = (NEWS_PACKAGE / "embedder.py").read_text(encoding="utf-8")
    assert "def embed(" in embedder_src
    assert "advise" not in embedder_src
    assert "ChatRequest" not in embedder_src


def test_embedder_runs_with_gateway_lacking_advise() -> None:
    """The embedder must work against a gateway stub that exposes only
    ``embed`` — proving it never reaches for a generative method at
    runtime."""

    from workbench_api.news.embedder import NewsEmbedder

    class _EmbedOnlyGateway:
        def embed(self, texts: list[str], task: str = "embedding") -> list[list[float]]:  # noqa: ARG002
            return [[0.0, 1.0] for _ in texts]

    class _NoopRepo:
        def get_by_news_and_model(self, *_args: object, **_kw: object) -> None:
            return None

        def save_if_new(self, **_kw: object) -> object:
            return object()

    embedder = NewsEmbedder(_EmbedOnlyGateway(), _NoopRepo())  # type: ignore[arg-type]

    class _News:
        id = "n1"
        title = "Headline"
        summary = "Body"

    # Should not raise — no generative method is ever accessed.
    assert embedder.embed_pending([_News()]) == 1  # type: ignore[list-item]


def test_sleeve_news_response_has_no_free_form_text_field() -> None:
    """The ``/recommendations/news`` response item exposes exactly the
    structured field set — no free-form AI text field (e.g. ``advice`` /
    ``summary_text`` / ``rationale``) may slip in under B034's
    non-generative boundary. Generative advisory text is B036 scope."""

    from workbench_api.schemas.recommendations import (
        SleeveNewsItem,
        SleeveNewsResponse,
    )

    assert set(SleeveNewsItem.model_fields) == {
        "news_id",
        "title",
        "source",
        "url",
        "published_at",
        "content_sha256",
        "topics",
        "matched_tickers",
        "score",
    }
    assert set(SleeveNewsResponse.model_fields) == {"items"}


def test_latest_news_item_has_no_free_form_text_field() -> None:
    """B038 F001 — the Home ``GET /api/news/latest`` feed item exposes
    exactly the metadata + deterministic-topic field set. No free-form AI
    text field (``summary`` / ``advice`` / ``rationale``) may slip in under
    B034's non-generative boundary. Being a global (sleeve-less) feed it also
    drops ``matched_tickers`` / ``score`` — those are sleeve-relevance fields."""

    from workbench_api.schemas.news import LatestNewsItem, LatestNewsResponse

    assert set(LatestNewsItem.model_fields) == {
        "news_id",
        "title",
        "source",
        "url",
        "published_at",
        "topics",
    }
    assert set(LatestNewsResponse.model_fields) == {"items"}
