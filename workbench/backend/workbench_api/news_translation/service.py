"""B054 F-news — NewsTranslationService: English headline → Simplified Chinese.

A thin, guarded wrapper over the LLM gateway's chat completion. It exists so
the *news titles* surfaced on the Home feed and the Recommendations sleeve-news
panel render in Chinese alongside the rest of the B054-localized UI, while the
source snapshot and the deterministic topic/embedding paths keep the original
English (boundary preservation — only the user-visible headline is localized).

Boundary posture:

* This is no-AI boundary rule **(e)**: translate only. The system prompt
  forbids adding, interpreting, predicting, summarizing, or advising; the
  guard rejects any output that grows implausibly long (a model that ignored
  "output only the translation" and appended commentary) so a malformed run
  leaves ``title_zh`` NULL rather than leaking free-form text.
* ``gateway.advise`` already runs the monthly cost guard (boundary (m)) before
  the HTTP call, so this adds no extra cost wiring.
* Never raises on model misbehaviour — a refusal / unparseable / over-long
  output returns ``None`` (the caller leaves ``title_zh`` NULL to retry next
  run). A cost-guard trip / HTTP error DOES propagate so the batch records it.
"""

from __future__ import annotations

import logging
from typing import Protocol

from workbench_api.llm.gateway import ChatRequest, ChatResult

logger = logging.getLogger(__name__)

NEWS_TRANSLATE_TASK = "news_translate"

# Upper bound on a translated headline. A real Chinese headline is short
# (source headlines are well under 512 chars and Chinese is typically more
# compact than English); anything longer means the model appended commentary
# despite the instruction, so we reject it. Combined with the small
# ``max_tokens`` cap this structurally bounds free-form leakage.
_MAX_TRANSLATION_CHARS = 300

SYSTEM_PROMPT = (
    "You are a translation layer for a single-user, research-only portfolio "
    "decision-support tool. You translate short English financial news "
    "headlines into Simplified Chinese (zh-CN). You are NOT a financial "
    "advisor and you do NOT predict, interpret, summarize, or advise.\n"
    "\n"
    "Rules (you MUST follow all):\n"
    "(1) Output ONLY the Simplified-Chinese translation of the given "
    "headline. No preamble, no surrounding quotes, no explanation, no extra "
    "sentence, no notes.\n"
    "(2) Translate faithfully and concisely. Never add information that is "
    "not in the headline.\n"
    "(3) Keep ticker symbols, numbers, percentages, currency amounts, and "
    "dates exactly as given — do not localize or convert them.\n"
    "(4) Never add any buy/sell/hold suggestion, price target, or "
    "return/earnings prediction.\n"
    "(5) If the headline is already in Chinese, return it unchanged.\n"
)


class _AdviseGateway(Protocol):
    """Subset of :class:`~workbench_api.llm.gateway.LLMGateway` used here — a
    Protocol so tests inject a stub returning recorded text without the HTTP
    client / cost-guard DB."""

    def advise(self, request: ChatRequest) -> ChatResult: ...


class NewsTranslationService:
    def __init__(self, gateway: _AdviseGateway) -> None:
        self._gateway = gateway

    def translate_title(self, title: str, *, max_tokens: int = 200) -> str | None:
        """Translate one English headline to Simplified Chinese.

        Returns the translated headline, or ``None`` when the title is empty
        or the model misbehaves (empty / over-long output). Never raises on
        model output — only a cost-guard trip / HTTP error propagates.
        """

        source = title.strip()
        if not source:
            return None

        result = self._gateway.advise(
            ChatRequest(
                task=NEWS_TRANSLATE_TASK,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": source},
                ],
                max_tokens=max_tokens,
                temperature=0.0,
            )
        )
        return self._clean(result.content, source=source)

    @staticmethod
    def _clean(content: str, *, source: str) -> str | None:
        """Strip wrapping whitespace / quotes and reject implausible output."""

        zh = content.strip().strip('"').strip("“”").strip()
        if not zh:
            logger.info("news_translate_empty_output", extra={"source": source})
            return None
        if len(zh) > _MAX_TRANSLATION_CHARS:
            logger.warning(
                "news_translate_output_too_long",
                extra={"source": source, "length": len(zh)},
            )
            return None
        return zh


def build_default_translator() -> NewsTranslationService | None:
    """Construct the production translator, or ``None`` when unavailable.

    Returns ``None`` (the batch job logs and exits cleanly) when the AIGC
    gateway key is unset (local / CI) so offline runs never touch the
    network. Like the B043 explainer, translation is an enhancement, not a
    hard dependency: an un-translated headline simply falls back to its
    English ``title`` on the serving path."""

    try:
        from workbench_api.llm.gateway import LLMGateway

        return NewsTranslationService(LLMGateway())
    except Exception as exc:  # noqa: BLE001 — no key / import issue → degrade
        logger.info("news_translate_llm_unavailable", extra={"reason": str(exc)})
        return None
