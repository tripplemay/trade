"""B080 F001 — OosVerificationCardRepository (DB-ized cn_attack red card read).

Pure DB (never imports ``trade``). :meth:`get_card` returns the 8 caveat keys as
a plain dict — a drop-in replacement for ``dict(CN_ATTACK_RESEARCH_CAVEAT)`` — or
``None`` when no card row exists (the producer then falls back to the in-code
constant, byte-identical). The frozen re-validation pipeline (F003) writes rows
via :meth:`upsert_card` (only ever more conservative — never flips validated True).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from workbench_api.db.models.oos_verification_card import OosVerificationCard
from workbench_api.db.repositories.base import Repository

# The 8 value columns, in the order they map onto the ResearchCaveat schema.
_CARD_FIELDS = (
    "validated",
    "oos_result",
    "oos_cagr_range",
    "headline_zh",
    "headline_en",
    "detail_zh",
    "detail_en",
    "backtest_ref",
)


class OosVerificationCardRepository(Repository[OosVerificationCard, str]):
    model = OosVerificationCard
    primary_key_attr = "strategy_id"

    def get_card(self, strategy_id: str) -> dict[str, Any] | None:
        """The stored card for ``strategy_id`` as the 8-key caveat dict, or None.

        A ``None`` return is the signal to fall back to ``CN_ATTACK_RESEARCH_CAVEAT``
        (byte-identical to the pre-B080 behaviour).
        """

        row = self._session.get(OosVerificationCard, strategy_id)
        if row is None:
            return None
        return {field: getattr(row, field) for field in _CARD_FIELDS}

    def upsert_card(
        self,
        strategy_id: str,
        card: dict[str, Any],
        *,
        source: str = "seed",
        updated_at: datetime | None = None,
    ) -> OosVerificationCard:
        """Insert / replace the card for ``strategy_id`` from an 8-key caveat dict.

        ``source`` is currently informational only (the re-validation pipeline may
        record provenance in ``notes``-style fields in a later feature). Used by
        the seed migration + the frozen re-validation pipeline.
        """

        stamp = updated_at or datetime.now(UTC)
        existing = self._session.get(OosVerificationCard, strategy_id)
        target = existing or OosVerificationCard(strategy_id=strategy_id)
        for field in _CARD_FIELDS:
            setattr(target, field, card[field])
        target.source = source
        target.updated_at = stamp
        if existing is None:
            self._session.add(target)
        self._session.flush()
        return target
