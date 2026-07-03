"""B079 F001 — symbol_name table (lightweight symbol → display-name store).

A minimal, persistent (non-TTL) lookup mapping a canonical ticker to its
human-readable display name plus the feed that supplied it, so any display
surface can resolve ``600519.SH`` → ``贵州茅台`` (or ``AAPL`` → ``Apple Inc.``)
without loading the heavy ``symbol_fundamentals_cache`` snapshot.

Deliberately isolated (mirrors ``symbol_price_cache`` / ``symbol_fundamentals_cache``):
it holds only identity metadata, is written by the offline data-refresh job
(A-share names captured for free from the akshare spot 「名称」 column) and by an
idempotent curated seed (US / ETF / HK static names) — and is **never** read by
the recommendation / backtest / risk / account scoring layers. It is a pure
display concern (B079: 名称纯展示无执行 affordance).

``symbol`` is the natural primary key (one name per ticker, upserted); it is
stored canonical/uppercased (``600519.SH`` / ``0700.HK`` / ``AAPL``) so it keys
identically to every downstream surface. ``updated_at`` is stamped in Python on
each upsert (tz-aware UTC), matching the ``fetched_at`` convention of the
sibling cache tables. ``source`` records provenance (``curated`` /
``akshare_spot``) so a live-captured name can knowingly override a static seed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class SymbolName(Base):
    __tablename__ = "symbol_name"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"SymbolName(symbol={self.symbol!r}, name={self.name!r})"
