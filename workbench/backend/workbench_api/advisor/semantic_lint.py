"""B095 F001 — deterministic semantic pre-filter for advisor output.

Test-automation roadmap **P4-F1** (``docs/dev/test-automation-roadmap.md``):
a *deterministic* (regex / word-list) pre-filter over the AI advisor's
Chinese ``advice`` / ``rationale`` text. It is the cheap first stage that
"吃掉 ~80%" of the LLM-judge's work (P4-F2, the fuzzy-residual judge, is out
of scope here). Two independent checks:

* :func:`detect_english_residual` — the advisor writes in Simplified
  Chinese (``service.SYSTEM_PROMPT``: "OUTPUT LANGUAGE ... zh-CN"), so a run
  of stray English *prose* words is a residual worth surfacing. A
  **whitelist** exempts the tokens that legitimately stay Latin: tickers
  (``SPY``/``AAPL``), ratios (``P/E``/``ROE``), the acronym ``ETF``, short
  units, ``sha256:`` hashes, URLs, and the handful of domain terms the real
  advisor genuinely emits in Chinese sentences (``quant`` — verified in the
  committed advisor cassette: "基于提供的 quant 信号").
* :func:`detect_banned_phrases` — the v0.9.28 no-AI boundary forbids the
  advisor from predicting returns / issuing execution instructions /
  presenting itself as a replacement for the quant engine. This flags the
  phrases that express those acts (``收益预测`` / ``执行指令`` / ``自动下单`` /
  ``替代quant`` …) — but **only when not negated**. The order-instruction
  forms are the *specific* ones (``自动下单`` / ``立即下单`` / ``下单买入`` …);
  the bare 2-char ``下单`` is deliberately NOT listed because 下 and 单 are
  high-frequency and collide across word boundaries in innocent Chinese
  ("当下单边行情" = 当下+单边). The codebase's own disclaimer language is full
  of *negated* forms ("非收益预测", "不自动下单", "难以预测收益"); those are the
  advisor correctly stating a boundary and MUST NOT be flagged. A short
  negation look-back window (incl. 难 for "cannot predict") distinguishes the
  two.

Design contract (why this is safe to add — B095 hard constraints):

* **Pure + deterministic + no I/O.** Just ``re`` + constant tables. Same
  input → same findings, everywhere.
* **False positives are the cardinal risk.** A lint that fires on
  legitimate grounded numeric Chinese advice is worse than no lint, so the
  whitelist and the negation guard are tuned to *under*-report rather than
  over-report. Where the two conflict, we accept a miss (a residual the
  judge still catches) over a false alarm.
* **Advisory only.** Nothing here raises or blocks at runtime; it returns
  findings for a caller (a test, a logger, or the P4-F2 judge stage) to act
  on. It does not touch the red-team hard gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "BANNED_PHRASES",
    "LOWER_ALLOWLIST",
    "NEGATION_CHARS",
    "NEGATION_WINDOW",
    "LintFinding",
    "detect_banned_phrases",
    "detect_english_residual",
    "lint_advice",
    "lint_text",
]


@dataclass(frozen=True, slots=True)
class LintFinding:
    """One deterministic finding.

    ``kind`` is ``"english_residual"`` or ``"banned_phrase"``. ``token`` is
    the offending substring, ``start`` its index in the scanned text, and
    ``context`` a short surrounding snippet for a human-readable report.
    """

    kind: str
    token: str
    start: int
    context: str


# --- English-residual whitelist ------------------------------------------

# Spans stripped wholesale before tokenising (their inner Latin letters are
# legitimate, not prose): full URLs and ``sha256:<hex>`` citation hashes.
_URL_RE = re.compile(r"https?://\S+")
_SHA_RE = re.compile(r"\bsha256:[0-9a-fA-F]+", re.IGNORECASE)

# A Latin token: starts with a letter, may contain the joiners used by
# tickers / ratios (``P/E``, ``S&P``, ``BRK.B``) and — crucially — the
# slash-joined compounds the advisor legitimately writes: valuation ratios
# (``EV/EBITDA``, ``P/S``) and multi-ticker lists (``SPY/QQQ/TLT``). Digits
# allowed inside so ``BRK.B`` / ``5G`` stay one token; a leading digit
# (``2026``, ``8``) never starts a token, so pure numbers / percentages are
# ignored entirely.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9./&_+-]*")

# An all-upper, ≤6-char *part* is a ticker / ratio-component / acronym (SPY,
# AAPL, P, E, S&P→S/P, ROE, ETF, NAV, USD, UTC, the ISO ``T``/``Z`` markers,
# …). A joined token (``EV/EBITDA``, ``SPY/QQQ/TLT``, ``BRK.B``) is whitelisted
# when EACH of its joiner-separated parts is such a part — we split on the
# joiners rather than concatenating and length-capping, so a standard ratio or
# a slash ticker list is not spuriously flagged just because the concatenation
# runs past 6 chars.
_ACRONYM_RE = re.compile(r"[A-Z][A-Z0-9]{0,5}$")
_JOINER_SPLIT_RE = re.compile(r"[./&_+-]")

# Longer financial ratio-components / acronyms that legitimately exceed the
# 6-char acronym cap and would otherwise fail :data:`_ACRONYM_RE`. Matched
# case-insensitively as a whole part (e.g. the ``EBITDA`` in ``EV/EBITDA``).
_RATIO_VOCAB: frozenset[str] = frozenset(
    {
        "EV",  # enterprise value (part of EV/EBITDA, EV/SALES, EV/EBIT)
        "EBITDA",
        "EBITDAR",
        "EBIT",
        "EBT",
        "SALES",
        "REVENUE",
        "NOPAT",
        "CAPEX",
    }
)

# Curated lower/mixed-case terms the *real* advisor legitimately emits in
# otherwise-Chinese text, plus short units. Kept deliberately small and
# evidence-based (each is either verified in a committed cassette / prompt or
# an explicit roadmap-named token). Case-insensitive.
LOWER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "quant",  # verified in advisor cassette: "基于提供的 quant 信号"
        "sleeve",  # grounding/label domain term (SLEEVE: … in the prompt)
        "advisory",  # boundary disclaimer term used throughout (advisory-only)
        "advisory-only",  # whole hyphenated token matched as one unit
        "etf",  # roadmap-named; ETF (upper) already exempt, etf/etfs are not
        "etfs",
        "bps",  # unit (basis points)
        "pct",  # unit (percent, spelled out)
        "sha",  # residual of a sha256 mention split off from its hex
        "sha256",
    }
)


def _masked_spans(text: str) -> list[tuple[int, int]]:
    """Char spans covered by a URL or sha256 hash (skipped when tokenising)."""

    spans: list[tuple[int, int]] = []
    for pattern in (_URL_RE, _SHA_RE):
        spans.extend((m.start(), m.end()) for m in pattern.finditer(text))
    return spans


def _in_masked(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < s_end and end > s_start for s_start, s_end in spans)


def _is_acronym_part(part: str) -> bool:
    """Return ``True`` iff a single joiner-separated ``part`` is a legitimate
    ticker / ratio-component / acronym (all-upper ≤6 chars, or a named longer
    ratio term such as ``EBITDA``)."""

    if not part:
        return False
    if _ACRONYM_RE.match(part):
        return True
    return part.upper() in _RATIO_VOCAB


def _is_whitelisted(token: str) -> bool:
    """Return ``True`` iff ``token`` is a legitimate non-prose Latin token.

    A curated whole-token allowlist term (``quant``, ``advisory-only`` …) is
    accepted as-is; otherwise the token is split on its joiner characters and
    accepted only when every non-empty part is an acronym / ticker /
    ratio-component. This whitelists compound ratios (``EV/EBITDA``) and
    slash-joined ticker lists (``SPY/QQQ/TLT``) while still flagging a
    slash-joined English fragment (``buy/hold`` → parts ``buy``/``hold`` are
    not acronyms)."""

    if token.lower() in LOWER_ALLOWLIST:
        return True
    parts = [p for p in _JOINER_SPLIT_RE.split(token) if p]
    return bool(parts) and all(_is_acronym_part(p) for p in parts)


def _context(text: str, start: int, end: int, radius: int = 12) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def detect_english_residual(text: str) -> list[LintFinding]:
    """Return findings for stray English prose tokens in Chinese advice text.

    Whitelisted (never flagged): URLs, ``sha256:`` hashes, all-upper ≤6-char
    tickers / ratios / acronyms (``SPY``, ``P/E``, ``ETF``, ``NAV``, the ISO
    ``T``/``Z`` markers), numbers / percentages (never token-start), and the
    small curated :data:`LOWER_ALLOWLIST` of domain terms / units the real
    advisor emits (``quant``, ``bps`` …). Everything else that is a run of
    Latin letters — ``the``, ``should``, ``buy``, ``Recommendation`` — is a
    residual.
    """

    spans = _masked_spans(text)
    findings: list[LintFinding] = []
    for match in _TOKEN_RE.finditer(text):
        start, end = match.start(), match.end()
        if _in_masked(start, end, spans):
            continue
        token = match.group()
        if _is_whitelisted(token):
            continue
        findings.append(
            LintFinding(
                kind="english_residual",
                token=token,
                start=start,
                context=_context(text, start, end),
            )
        )
    return findings


# --- No-AI boundary banned phrases ---------------------------------------

# Phrases that *express* a boundary-breaking act (predict returns / issue an
# execution instruction / replace the quant engine). Each is only a finding
# when NOT negated (see NEGATION_CHARS) — the advisor's own disclaimers use
# the negated forms and must pass clean. Variants cover the optional ASCII
# space some models put between Chinese and Latin ("替代quant" / "替代 quant").
BANNED_PHRASES: tuple[str, ...] = (
    "收益预测",
    "预测收益",
    "保证收益",
    "保证盈利",
    "执行指令",
    "交易指令",
    "买入卖出指令",
    "买卖指令",
    # Order-placement instructions. The banned CONCEPT is the AI *issuing an
    # order-placement instruction*; the bare 2-char "下单" was dropped because
    # 下 and 单 are extremely high-frequency and it collided across word
    # boundaries on legitimate text ("当下单边行情" = 当下+单边, "眼下单一因子" =
    # 眼下+单一, "背景下单纯依赖" = 下+单纯, "阁下单独持有" = 下+单独). These
    # unambiguous forms capture the act without the 下+单 collision.
    "自动下单",
    "一键下单",
    "立即下单",
    "为您下单",
    "为你下单",
    "下单买入",
    "下单卖出",
    "下单指令",
    "帮你下单",
    "替你下单",
    "替代quant",
    "替代 quant",
    "替代量化",
    "取代量化",
    "取代quant",
    "取代 quant",
)

# Negation markers. If any appears in the short window immediately before a
# banned phrase, the phrase is a *disclaimer* ("非收益预测", "不自动下单",
# "不构成收益预测", "无法保证收益", "难以预测收益") — not a violation. 难 covers
# the "cannot predict" disclaimer forms 难以 / 很难 / 较难 predict returns, a
# legitimate no-AI-boundary statement that the advisor CANNOT forecast.
NEGATION_CHARS: frozenset[str] = frozenset("不非未无勿禁毋别拒难")

# How many characters before a phrase to scan for a negation marker. 5 covers
# the real disclaimer forms ("不构成收益预测" → 不 at −3; "不予自动下单" → 不 at
# −4) with a small margin. Wider risks masking a genuine violation via an
# unrelated nearby 不; per the cardinal-risk ordering we bias toward missing a
# violation (the judge still sees it) over a false alarm on a disclaimer.
NEGATION_WINDOW = 5


def _is_negated(text: str, start: int) -> bool:
    window = text[max(0, start - NEGATION_WINDOW) : start]
    return any(ch in NEGATION_CHARS for ch in window)


def detect_banned_phrases(text: str) -> list[LintFinding]:
    """Return findings for un-negated no-AI-boundary banned phrases.

    A phrase from :data:`BANNED_PHRASES` is a finding only when it is not
    preceded (within :data:`NEGATION_WINDOW` chars) by a negation marker —
    so the advisor's own boundary disclaimers ("非收益预测", "不自动下单")
    produce zero findings, while an actual "为你下单" / "收益预测为8%" is caught.
    """

    findings: list[LintFinding] = []
    for phrase in BANNED_PHRASES:
        offset = 0
        while True:
            idx = text.find(phrase, offset)
            if idx == -1:
                break
            offset = idx + len(phrase)
            if _is_negated(text, idx):
                continue
            findings.append(
                LintFinding(
                    kind="banned_phrase",
                    token=phrase,
                    start=idx,
                    context=_context(text, idx, idx + len(phrase)),
                )
            )
    return findings


def lint_text(text: str) -> list[LintFinding]:
    """Run both deterministic checks over one text blob."""

    return detect_english_residual(text) + detect_banned_phrases(text)


def lint_advice(advice: str, rationale: str) -> list[LintFinding]:
    """Convenience: lint an advisor output's two human-facing text fields."""

    return lint_text(advice) + lint_text(rationale)
