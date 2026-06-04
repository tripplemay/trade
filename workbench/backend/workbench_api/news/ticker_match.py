"""B034 F002 — deterministic ticker mention matcher.

Scans a news ``title + summary`` for mentions of the B034 universe
(B025 US Quality 27 real tickers + the 4 master ETFs the news CLI
ingests: SPY / QQQ / EFA / EEM) and returns the matched tickers. This
is the **hard** half of the news↔ticker association (B034 spec §4.4);
the embedding cosine soft-rank in :mod:`association` complements it.

The matcher is fully deterministic (no LLM — B034 AI boundary §3). It
builds a ``{alias|symbol → ticker}`` dictionary from two grounded
sources:

* :data:`_UNIVERSE_NAMES` — the 27 real tickers' company names
  (e.g. ``"Apple Inc." → AAPL``), **materialised in code** so the
  runtime never reads a file. The constant mirrors
  ``data/fixtures/us_quality_momentum/universe.csv``; the guard test
  ``test_universe_constant_matches_csv`` fails CI if the two drift.
  History: F004 L2 (2026-06-04) caught a production 500 — the prior
  version read the repo-root fixture CSV at request time, but that
  fixture is **not** in the deploy artifact (only ``workbench_api/``
  package data ships). Hardcoding the universe makes the request path
  deploy-artifact-safe.
* a small hand-curated alias map for the 4 ETFs (which have no row in
  the equity universe CSV).

The synthetic ``ZQ*`` fixture tickers are deliberately excluded — they
have no real filings (B029) so a "mention" of them would be noise.

Matching rules (the precision contract the F002 tests pin):

* **Whole-word only.** ``"APP"`` never matches ``AAPL`` and ``"app"``
  never matches anything — boundaries are non-alphanumeric, so a ticker
  or alias must appear as its own token.
* **Case-insensitive** over the lowercased text, EXCEPT that a ticker
  *symbol* whose lowercased form collides with a common English word
  (``CAT`` → "cat", ``V`` → "v") is matched **only via its company
  alias**, never the bare symbol — otherwise "the cat sat" would flag
  Caterpillar. See :data:`_ENGLISH_WORD_TICKER_COLLISIONS`.

The dictionary is built once and memoised; ``match_mentions`` is a pure
function over the text + dictionary.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
UNIVERSE_CSV = (
    REPO_ROOT / "data" / "fixtures" / "us_quality_momentum" / "universe.csv"
)
"""Path to the B025 universe fixture. Used **only** by the
``test_universe_constant_matches_csv`` consistency guard — never read on
the runtime / request path (F004 L2 blocker fix, 2026-06-04). The
fixture is not shipped in the deploy artifact, so runtime reads from
:data:`_UNIVERSE_NAMES` instead."""

# B025 US Quality 27 real (non-synthetic) tickers → company name,
# materialised here so the runtime never depends on the un-deployed
# fixture CSV. Mirrors ``universe.csv`` exactly; the
# ``test_universe_constant_matches_csv`` guard fails CI on any drift.
_UNIVERSE_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth Group Incorporated",
    "JPM": "JPMorgan Chase & Co.",
    "BAC": "Bank of America Corporation",
    "V": "Visa Inc.",
    "AMZN": "Amazon.com, Inc.",
    "HD": "The Home Depot, Inc.",
    "GOOGL": "Alphabet Inc. Class A",
    "META": "Meta Platforms, Inc.",
    "HON": "Honeywell International Inc.",
    "UPS": "United Parcel Service, Inc.",
    "CAT": "Caterpillar Inc.",
    "PG": "The Procter & Gamble Company",
    "KO": "The Coca-Cola Company",
    "WMT": "Walmart Inc.",
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "NEE": "NextEra Energy, Inc.",
    "DUK": "Duke Energy Corporation",
    "PLD": "Prologis, Inc.",
    "AMT": "American Tower Corporation",
    "LIN": "Linde plc",
    "APD": "Air Products and Chemicals, Inc.",
    "ECL": "Ecolab Inc.",
}

# The 4 master ETFs the B033/B034 news CLI ingests alongside the equity
# universe (see ``news/cli.py``). They have no row in the equity
# universe CSV, so their aliases are curated here.
ETF_ALIASES: dict[str, tuple[str, ...]] = {
    "SPY": ("SPDR S&P 500", "S&P 500"),
    "QQQ": ("Invesco QQQ", "Nasdaq-100", "NASDAQ-100"),
    "EFA": ("iShares MSCI EAFE", "MSCI EAFE"),
    "EEM": ("iShares MSCI Emerging Markets", "MSCI Emerging Markets"),
}

# Synthetic B025 fixture tickers — never matched (no real filings).
_SYNTHETIC_PREFIX = "ZQ"

# Ticker symbols whose lowercased form is a common English word; for
# these we match the company alias only, never the bare symbol, to
# avoid flagging ordinary prose. Extend as the universe grows.
_ENGLISH_WORD_TICKER_COLLISIONS: frozenset[str] = frozenset({"cat", "v"})

# Corporate suffixes stripped to derive a short company alias
# (e.g. "Apple Inc." → "Apple"). Order-independent; applied as a set of
# trailing tokens. "&" forms ("Johnson & Johnson") are left intact —
# the full name is distinctive enough and over-trimming would create
# ambiguous one-word aliases.
_CORP_SUFFIX_RE = re.compile(
    r"\b(?:inc|incorporated|corporation|corp|company|co|plc|ltd|group|"
    r"holdings|international|class\s+[a-c])\b\.?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class TickerDictionary:
    """Compiled lookup: lowercased token → canonical ticker.

    ``tokens`` maps every matchable alias / symbol (lowercased) to its
    ticker. ``tickers`` is the canonical universe set (uppercase) for
    callers that want to validate membership.
    """

    tokens: dict[str, str]
    tickers: frozenset[str]


def _load_universe_names() -> dict[str, str]:
    """Return ``{ticker: company_name}`` for the real (non-synthetic)
    equity universe.

    Reads from the in-code :data:`_UNIVERSE_NAMES` constant — **no file
    I/O** — so the runtime / request path stays deploy-artifact-safe
    (F004 L2 blocker fix, 2026-06-04). A defensive copy keeps callers
    from mutating the module constant."""

    return dict(_UNIVERSE_NAMES)


def _parse_universe_csv() -> dict[str, str]:
    """Parse the B025 universe fixture CSV → ``{ticker: name}`` (real
    tickers only). Test-only helper backing the
    ``test_universe_constant_matches_csv`` drift guard; never called on
    the runtime path."""

    out: dict[str, str] = {}
    with UNIVERSE_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ticker = row["ticker"].strip().upper()
            if ticker.startswith(_SYNTHETIC_PREFIX):
                continue
            out[ticker] = row["name"].strip()
    return out


def _short_alias(name: str) -> str | None:
    """Derive a short alias by stripping corporate suffixes.

    Returns ``None`` when stripping leaves nothing distinctive (e.g. the
    name is only a suffix) or when the result still contains a comma /
    ``&`` (kept as the full-name alias instead, never split)."""

    stripped = _CORP_SUFFIX_RE.sub("", name)
    stripped = stripped.replace(",", " ")
    stripped = re.sub(r"\s+", " ", stripped).strip(" .")
    if not stripped or stripped.lower() == name.lower():
        return None
    # Skip a degenerate one-or-two char alias that would be noisy.
    if len(stripped) < 3:
        return None
    return stripped


@lru_cache(maxsize=1)
def build_ticker_dictionary() -> TickerDictionary:
    """Build (and memoise) the alias/symbol → ticker dictionary."""

    tokens: dict[str, str] = {}
    names = _load_universe_names()
    tickers = set(names) | set(ETF_ALIASES)

    def _register(token: str, ticker: str) -> None:
        key = token.strip().lower()
        if key:
            tokens.setdefault(key, ticker)

    for ticker, name in names.items():
        # Bare symbol — skip when it collides with an English word.
        if ticker.lower() not in _ENGLISH_WORD_TICKER_COLLISIONS:
            _register(ticker, ticker)
        _register(name, ticker)
        short = _short_alias(name)
        if short is not None:
            _register(short, ticker)

    for ticker, aliases in ETF_ALIASES.items():
        if ticker.lower() not in _ENGLISH_WORD_TICKER_COLLISIONS:
            _register(ticker, ticker)
        for alias in aliases:
            _register(alias, ticker)

    return TickerDictionary(tokens=tokens, tickers=frozenset(tickers))


def equity_universe_tickers() -> tuple[str, ...]:
    """The B025 US Quality real (non-synthetic) equity tickers, sorted.

    Derived from ``universe.csv`` via the stdlib ``csv`` loader — **no
    pandas / no ``scripts`` package import** — so it is safe to call on
    the API request path (the leaner production / frontend-CI backend
    install does not carry pandas). ``scripts.universe_us_quality`` holds
    the same set but pulls pandas at import time, which is fine for the
    CLI but must never land in a request handler."""

    return tuple(sorted(_load_universe_names()))


def match_mentions(
    text: str, *, dictionary: TickerDictionary | None = None
) -> list[str]:
    """Return the sorted, de-duplicated tickers mentioned in ``text``.

    Whole-word, case-insensitive (see module docstring for the symbol
    collision rule). ``dictionary`` defaults to the memoised universe
    dictionary; tests pass a custom one for isolation."""

    table = dictionary or build_ticker_dictionary()
    haystack = text.lower()
    found: set[str] = set()
    for token, ticker in table.tokens.items():
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
        if re.search(pattern, haystack):
            found.add(ticker)
    return sorted(found)


@lru_cache(maxsize=1)
def cik_to_ticker_map() -> dict[int, str]:
    """Return ``{cik: ticker}`` from the bundled SEC CIK fixture.

    Reuses B029's ``ticker_cik_map.json`` (the authoritative CIK source)
    so a filing referenced by CIK can resolve to its ticker without a
    second mapping to maintain. Synthetic ``ZQ*`` tickers have ``null``
    CIK and are skipped."""

    from workbench_api.data.sec_edgar_loader import _load_default_ticker_cik_map

    out: dict[int, str] = {}
    for ticker, cik in _load_default_ticker_cik_map().items():
        if cik is not None and not ticker.startswith(_SYNTHETIC_PREFIX):
            out[int(cik)] = ticker
    return out
