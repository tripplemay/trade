"""B061 F001 — market-qualified symbol identity (``SymbolRef`` value object).

The single source of truth for "what market is this ticker, and how do we
canonicalise it" across the multi-market symbology layer (path-doc §9.3-9.4).

Design: a market-qualified **canonical string** is the identity — a US bare
ticker stays the default, a CN symbol is a 6-digit code + ``.SH`` / ``.SZ``
suffix — and the structured market / currency / board / exchange are
**derived** from that string by :class:`SymbolRef`, not stored as required
columns everywhere.

Why a derived value object rather than a schema migration: the system keys N
tables by a bare ``symbol`` string. A composite ``(symbol, market)`` key
migration would touch everything. Instead we add one parsing layer so:

* **US data is zero-migration** — a bare ticker parses as US (§9.4 铁律).
* **CN symbols co-exist in the same tables** — a 6-digit + suffix canonical
  never collides with a US alpha ticker.
* the market dimension stays **locked to the data / lookup layer** (§9.9 — P1
  does not touch accounts / NAV / execution / strategy).

request-path safe: imports neither ``trade`` nor any broker SDK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from workbench_api.symbols.provider import InvalidSymbolError

Market = Literal["US", "CN"]

# A trailing ``.XX`` makes a symbol market-qualified ONLY when ``XX`` is a known
# market code. This is the disambiguation seam: extend this set when a new
# market lands (e.g. ``HK``); never split a symbol on a dot that is not here.
_CN_MARKET_CODES: frozenset[str] = frozenset({"SH", "SZ"})

# CN canonical shape: exactly 6 digits + '.' + a 2-letter suffix.
_CN_CANONICAL_RE = re.compile(r"^(?P<code>\d{6})\.(?P<suffix>[A-Z]{2})$")

# US tickers: A-Z / digits / '.' (BRK.B) / '-' (BRK-B) / '^' (^GSPC index) /
# '=' (ES=F future), uppercased. This is the exact acceptance the B059 lookup
# already used, so every existing US symbol keeps validating identically.
_US_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,32}$")

# Exchange MIC by CN suffix (best-effort identity metadata; optional).
_CN_EXCHANGE: dict[str, str] = {"SH": "XSHG", "SZ": "XSHE"}

# Board inferred from the 6-digit code prefix. Reserved for FUTURE trading
# rules (T+1 / price limits / lot size / ST); **P1 does not consume it**.
_BOARD_PREFIXES: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"600", "601", "603", "605"}), "sh_main"),
    (frozenset({"688"}), "star"),
    (frozenset({"000", "001", "002", "003"}), "sz_main"),
    (frozenset({"300", "301"}), "chinext"),
)


def _infer_cn_board(code: str) -> str:
    """Best-effort board from the code prefix; unknown prefixes → ``cn_other``."""
    prefix = code[:3]
    for prefixes, board in _BOARD_PREFIXES:
        if prefix in prefixes:
            return board
    return "cn_other"


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
        market-qualified ONLY when ``XX`` is a known market code (SH / SZ).
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

        cn = _CN_CANONICAL_RE.match(candidate)
        if cn and cn.group("suffix") in _CN_MARKET_CODES:
            code = cn.group("code")
            suffix = cn.group("suffix")
            return cls(
                canonical=candidate,
                code=code,
                market="CN",
                exchange=_CN_EXCHANGE[suffix],
                currency="CNY",
                board=_infer_cn_board(code),
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
