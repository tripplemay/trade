"""B079 F001 — SymbolNameRepository (batch symbol → display-name resolution).

Two operations over the isolated ``symbol_name`` store, both **pure DB** (they
never touch the network):

- :meth:`get_names` — batch read ``{symbol: name}`` for the stored subset of a
  symbol list (missing symbols simply absent; the caller decides on misses).
  This is the F001 read contract the enrich layer builds on: one ``.in_()``
  query enriches N rows, never N per-symbol lookups.
- :meth:`upsert_names` — batch insert/replace a ``{symbol: name}`` mapping in a
  single flush (used by the daily data-refresh A-share capture + the curated
  seed).

The batch-dict read mirrors ``NewsEmbeddingRepository`` and the upsert mirrors
the ``symbol_*_cache`` upsert idiom (fetch-existing → update-or-add → flush;
the repo flushes, the session owner commits).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from workbench_api.db.models.symbol_name import SymbolName
from workbench_api.db.repositories.base import Repository


class SymbolNameRepository(Repository[SymbolName, str]):
    model = SymbolName
    primary_key_attr = "symbol"

    def get_names(self, symbols: Sequence[str]) -> dict[str, str]:
        """Return ``{symbol: name}`` for the stored subset of ``symbols``.

        Symbols with no stored name are simply absent from the result. An empty
        input short-circuits to ``{}`` without a query. Pure DB — no external
        fetch is ever triggered, so an enriched list response stays one query.
        """

        if not symbols:
            return {}
        stmt = select(SymbolName.symbol, SymbolName.name).where(
            SymbolName.symbol.in_(list(symbols))
        )
        rows = self._session.execute(stmt).all()
        return {symbol: name for symbol, name in rows}

    def upsert_names(
        self,
        names: Mapping[str, str],
        *,
        source: str,
        updated_at: datetime | None = None,
    ) -> int:
        """Insert/replace a name row for every ``{symbol: name}`` in ``names``.

        Fetches the existing rows in one ``.in_()`` query, then mutates or adds
        each and flushes once. ``updated_at`` defaults to now (UTC) and is
        overridable so tests pin a deterministic timestamp. Blank names are
        skipped (a missing name must fall back to the raw code, never store an
        empty string). Returns the number of rows written.
        """

        cleaned = {
            symbol: name.strip()
            for symbol, name in names.items()
            if symbol and name and name.strip()
        }
        if not cleaned:
            return 0
        stamp = updated_at or datetime.now(UTC)
        existing_stmt = select(SymbolName).where(
            SymbolName.symbol.in_(list(cleaned))
        )
        existing = {
            row.symbol: row
            for row in self._session.execute(existing_stmt).scalars().all()
        }
        for symbol, name in cleaned.items():
            row = existing.get(symbol)
            if row is None:
                self._session.add(
                    SymbolName(
                        symbol=symbol,
                        name=name,
                        source=source,
                        updated_at=stamp,
                    )
                )
            else:
                row.name = name
                row.source = source
                row.updated_at = stamp
        self._session.flush()
        return len(cleaned)
