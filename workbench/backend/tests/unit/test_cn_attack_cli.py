"""B067 F002 — CN attack precompute CLI tests (dispatch + exit code + env guard).

The two daily ``workbench-cn-attack-*`` timers run this CLI (one per variant).
These tests exercise the variant dispatch, the exit-code contract, and the
§12.11.1 env hard-fail guard — all with an injected fake runner so no ``trade``
import / data load is needed.
"""

from __future__ import annotations

from datetime import date

import pytest

from workbench_api.db.require_production_db import ScratchDatabaseError
from workbench_api.strategy_modes import cn_attack_cli
from workbench_api.strategy_modes.cn_attack_precompute import CnAttackPrecomputeSummary
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
)

pytestmark = pytest.mark.usefixtures("initialised_db")


def _ok_summary(strategy_id: str) -> CnAttackPrecomputeSummary:
    return CnAttackPrecomputeSummary(
        saved=3, as_of_date=date(2025, 12, 31), data_source="fixture", error=None
    )


def _make_runner(calls: list[tuple[str, str]]):  # type: ignore[no-untyped-def]
    def runner(session, strategy_id, *, factor_variant):  # type: ignore[no-untyped-def]
        calls.append((strategy_id, factor_variant))
        return _ok_summary(strategy_id)

    return runner


def test_no_arg_runs_both_variants() -> None:
    calls: list[tuple[str, str]] = []
    rc = cn_attack_cli.main([], runner=_make_runner(calls))
    assert rc == 0
    assert calls == [
        (CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum"),
        (CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum"),
    ]


def test_variant_arg_runs_only_that_variant() -> None:
    calls: list[tuple[str, str]] = []
    rc = cn_attack_cli.main(["pure_momentum"], runner=_make_runner(calls))
    assert rc == 0
    assert calls == [(CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum")]


def test_unknown_variant_exits() -> None:
    with pytest.raises(SystemExit):
        cn_attack_cli.main(["sentiment_flip"], runner=_make_runner([]))


def test_nonzero_exit_when_a_variant_fails() -> None:
    def runner(session, strategy_id, *, factor_variant):  # type: ignore[no-untyped-def]
        if factor_variant == "pure_momentum":
            return CnAttackPrecomputeSummary(
                saved=0,
                as_of_date=None,
                data_source=None,
                error="data not covered",
                error_kind="data_not_covered",
            )
        return _ok_summary(strategy_id)

    rc = cn_attack_cli.main([], runner=runner)
    assert rc == 1


def test_env_guard_blocks_before_any_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # §12.11.1 — the scratch-DB guard must hard-fail BEFORE any precompute runs.
    def boom(*, entrypoint: str) -> str:
        raise ScratchDatabaseError(f"::error::{entrypoint}: scratch DB")

    monkeypatch.setattr(cn_attack_cli, "require_production_db", boom)
    calls: list[tuple[str, str]] = []
    rc = cn_attack_cli.main([], runner=_make_runner(calls))
    assert rc == 1
    assert calls == []  # never ran a variant
