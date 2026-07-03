"""B080 F001 — oos_verification_card: repo round-trip + byte-identical fallback.

Guards the DB-ization of the cn_attack OOS "red card": the repo returns the 8
caveat keys as a drop-in dict, an empty store falls back byte-identically to the
in-code ``CN_ATTACK_RESEARCH_CAVEAT`` (zero regression — the guard the spec §2 F001
acceptance mandates), and a stored card overrides. The repo upsert round-trip
also pins the seed VALUE contract: the migration seeds from the same constant, so
a round-trip proving equality proves the seed is byte-identical (U+2212 / U+2014 /
fullwidth punctuation intact).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.strategy_modes.cn_attack_precompute import (
    CN_ATTACK_RESEARCH_CAVEAT,
    _build_target_result,
)
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
)

_AS_OF = date(2026, 7, 3)


def _fake_live() -> object:
    from trade.backtest.cn_attack_momentum_quality.live import (  # type: ignore[import-untyped]
        CnAttackLiveTarget,
    )

    return CnAttackLiveTarget(
        as_of_date=_AS_OF,
        signal_date=_AS_OF,
        factor_variant="quality_momentum",
        target_weights={"600519.SH": 0.6, "000858.SZ": 0.4},
        cash_weight=0.0,
        rebalanced=True,
        profit_take=(),
        would_be_turnover=0.1,
        no_trade_band=0.20,
        top_n=25,
    )


def test_get_card_none_when_store_empty(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        assert OosVerificationCardRepository(session).get_card("cn_attack_pure_momentum") is None


def test_upsert_roundtrips_caveat_byte_identical(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = OosVerificationCardRepository(session)
        # This is exactly what the seed migration writes (from the same constant).
        repo.upsert_card(
            CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, CN_ATTACK_RESEARCH_CAVEAT
        )
        session.commit()
        got = repo.get_card(CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID)
        # Byte-identical to the constant across every U+2212/U+2014/fullwidth char.
        assert got == CN_ATTACK_RESEARCH_CAVEAT


def test_build_target_result_no_card_is_byte_identical_fallback() -> None:
    # No caveat threaded → byte-identical to the in-code constant (zero regression).
    result = _build_target_result(
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum", "real", _fake_live()
    )
    assert result.meta["research_caveat"] == CN_ATTACK_RESEARCH_CAVEAT


def test_build_target_result_uses_db_card_when_present() -> None:
    # A resolved DB card (more conservative / updated) overrides the fallback.
    card = {
        "validated": False,
        "oos_result": "negative",
        "oos_cagr_range": "-12% ~ -14%",
        "headline_zh": "重验证更新的样本外披露。",
        "headline_en": "Re-validation-updated OOS disclosure.",
        "detail_zh": "advisory-only。",
        "detail_en": "Advisory-only.",
        "backtest_ref": "docs/test-reports/auto/reverify-x.md",
    }
    result = _build_target_result(
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum", "real", _fake_live(), card
    )
    assert result.meta["research_caveat"] == card
    assert result.meta["research_caveat"]["oos_cagr_range"] == "-12% ~ -14%"
