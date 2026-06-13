"""B061 F001 / B062 F001 — market-qualified symbol identity (``SymbolRef``).

The single source of truth for "what market is this ticker, and how do we
canonicalise it" across the multi-market symbology layer (path-doc §9.3-9.4).

Design: a market-qualified **canonical string** is the identity — a US bare
ticker stays the default, a CN symbol is a 6-digit code + ``.SH`` / ``.SZ``
suffix, a HK symbol is a 1-5 digit code + ``.HK`` suffix (B062) — and the
structured market / currency / board / exchange are **derived** from that
string by :class:`SymbolRef`, not stored as required columns everywhere.

Why a derived value object rather than a schema migration: the system keys N
tables by a bare ``symbol`` string. A composite ``(symbol, market)`` key
migration would touch everything. Instead we add one parsing layer so:

* **US data is zero-migration** — a bare ticker parses as US (§9.4 铁律).
* **CN / HK symbols co-exist in the same tables** — a digit-code + suffix
  canonical never collides with a US alpha ticker.
* the market dimension stays **locked to the data / lookup layer** (§9.9 — P1
  does not touch accounts / NAV / execution / strategy).

Adding a market = one entry in :data:`_MARKET_BY_SUFFIX` (+ a code-length rule).

request-path safe: imports neither ``trade`` nor any broker SDK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from workbench_api.symbols.provider import InvalidSymbolError

Market = Literal["US", "CN", "HK"]

# A trailing ``.XX`` makes a symbol market-qualified ONLY when ``XX`` is a known
# market code. Each entry maps the suffix → (market, exchange MIC, currency).
# This is the disambiguation seam + the single extension point for new markets;
# never split a symbol on a dot that is not here (so ``BRK.B`` stays US).
_MARKET_BY_SUFFIX: dict[str, tuple[Market, str, str]] = {
    "SH": ("CN", "XSHG", "CNY"),  # Shanghai
    "SZ": ("CN", "XSHE", "CNY"),  # Shenzhen
    "HK": ("HK", "XHKG", "HKD"),  # B062 F001 — Hong Kong
}

# A market-qualified canonical is a digit code + '.' + a 2-letter market suffix.
# CN codes are exactly 6 digits; HK codes are 1-5 digits (e.g. 0700.HK). The
# per-market length rule is enforced after the suffix match.
_CANONICAL_RE = re.compile(r"^(?P<code>\d{1,6})\.(?P<suffix>[A-Z]{2})$")
_CN_CODE_LEN = 6
_HK_CODE_MIN, _HK_CODE_MAX = 1, 5

# US tickers: A-Z / digits / '.' (BRK.B) / '-' (BRK-B) / '^' (^GSPC index) /
# '=' (ES=F future), uppercased. This is the exact acceptance the B059 lookup
# already used, so every existing US symbol keeps validating identically.
_US_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,32}$")

# CN board inferred from the 6-digit code prefix. Reserved for FUTURE trading
# rules (T+1 / price limits / lot size / ST); **P1 does not consume it**.
_BOARD_PREFIXES: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"600", "601", "603", "605"}), "sh_main"),
    (frozenset({"688"}), "star"),
    (frozenset({"000", "001", "002", "003"}), "sz_main"),
    (frozenset({"300", "301"}), "chinext"),
)


def _infer_cn_board(code: str) -> str:
    """Best-effort CN board from the code prefix; unknown prefixes → ``cn_other``."""
    prefix = code[:3]
    for prefixes, board in _BOARD_PREFIXES:
        if prefix in prefixes:
            return board
    return "cn_other"


def _infer_board(market: Market, code: str) -> str:
    if market == "CN":
        return _infer_cn_board(code)
    if market == "HK":
        return "hk_main"
    return "us"


def _valid_code_length(market: Market, code: str) -> bool:
    if market == "CN":
        return len(code) == _CN_CODE_LEN
    if market == "HK":
        return _HK_CODE_MIN <= len(code) <= _HK_CODE_MAX
    return True


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """A parsed, market-qualified symbol identity (single source of truth)."""

    canonical: str
    code: str
    market: Market
    exchange: str | None
    currency: str
    board: str

    @classmethod
    def parse(cls, raw: str) -> SymbolRef:
        """Parse a raw ticker into a market-qualified identity.

        Disambiguation (§9.3 坑): a trailing ``.XX`` makes the symbol
        market-qualified ONLY when ``XX`` is a known market code (SH / SZ / HK).
        ``BRK.B`` (a US class share) therefore parses as **US** — we must not
        split on every dot. A bare ticker (no market suffix) defaults to US
        (§9.4), so every existing US symbol is unchanged.

        Raises :class:`InvalidSymbolError` for empty / over-long / illegal
        input (validated at the boundary so the external API is never hit for
        junk).
        """

        candidate = (raw or "").strip().upper()
        if not candidate:
            raise InvalidSymbolError(raw)

        qualified = _CANONICAL_RE.match(candidate)
        if qualified and qualified.group("suffix") in _MARKET_BY_SUFFIX:
            code = qualified.group("code")
            market, exchange, currency = _MARKET_BY_SUFFIX[qualified.group("suffix")]
            if not _valid_code_length(market, code):
                raise InvalidSymbolError(raw)
            return cls(
                canonical=candidate,
                code=code,
                market=market,
                exchange=exchange,
                currency=currency,
                board=_infer_board(market, code),
            )

        if _US_SYMBOL_RE.match(candidate):
            return cls(
                canonical=candidate,
                code=candidate,
                market="US",
                exchange=None,
                currency="USD",
                board="us",
            )

        raise InvalidSymbolError(raw)
