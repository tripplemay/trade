"""Router for ``/api/symbols`` — B059 F001 on-demand symbol price lookup.

Research-only EOD price surface for *arbitrary* tickers. The request path
NEVER imports ``trade`` (§12.10.2) and never touches a broker SDK: it calls
the yfinance symbol provider (free EOD feed) behind a cache + rate-limit
guard and reads / writes only the isolated ``symbol_price_cache`` table.
There is **no execution / order entry of any kind** here (no-execution-buttons
/ no-broker red lines, B059 §4).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import t
from workbench_api.schemas.symbols import (
    SymbolFundamentals,
    SymbolNewsResponse,
    SymbolPriceDetail,
)
from workbench_api.symbols.fundamentals import get_symbol_fundamentals
from workbench_api.symbols.news import get_symbol_news
from workbench_api.symbols.provider import (
    InvalidSymbolError,
    SymbolNotFoundError,
    SymbolRateLimitedError,
)
from workbench_api.symbols.service import get_symbol_price_detail

router = APIRouter(prefix="/symbols", tags=["symbols"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/{symbol}/price", response_model=SymbolPriceDetail)
def get_symbol_price_route(
    symbol: str,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> SymbolPriceDetail:
    """Return EOD price detail (latest close + 52-week range + window returns
    + OHLCV series) for ``symbol``.

    Errors are actionable, never a generic 500: invalid ticker → 400,
    unknown / delisted / no-EOD-data → 404, rate-limited → 429.
    """

    try:
        return get_symbol_price_detail(session, symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("symbols.invalid_symbol", symbol=symbol),
        ) from exc
    except SymbolRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("symbols.rate_limited", symbol=symbol),
        ) from exc
    except SymbolNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("symbols.not_found", symbol=symbol),
        ) from exc


@router.get("/{symbol}/fundamentals", response_model=SymbolFundamentals)
def get_symbol_fundamentals_route(
    symbol: str,
    _user: AuthenticatedUserDep,
) -> SymbolFundamentals:
    """Return best-effort fundamentals for ``symbol`` (US-equity gated).

    Always 200 for a valid ticker: ``available`` + ``reason`` carry the honest
    US-only degradation (non-US / ETF / no-data) rather than a blank or a 500.
    A malformed ticker → 400.
    """

    try:
        return get_symbol_fundamentals(symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("symbols.invalid_symbol", symbol=symbol),
        ) from exc


@router.get("/{symbol}/news", response_model=SymbolNewsResponse)
def get_symbol_news_route(
    symbol: str,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> SymbolNewsResponse:
    """Return recent news for ``symbol`` (newest-first; empty list = no news).

    Reuses the B034/B035 news feed (Chinese ``title_zh`` + deterministic
    topics). A malformed ticker → 400; an unknown but valid ticker → 200 with
    an empty list (honest empty state)."""

    try:
        return get_symbol_news(session, symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("symbols.invalid_symbol", symbol=symbol),
        ) from exc
