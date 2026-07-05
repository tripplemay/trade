"""B082 F003 — 红利低波 defensive-sleeve mode: registry + producer + wiring.

Offline unit coverage for the F003 deliverables:

* the registry row (research-state, monthly, CNY paper book, CSI300 benchmark);
* the target producer (the real F002 spread signal over frozen CSVs → 利差档位 target +
  CASH row + research caveat; data_not_covered when the frozen series are absent);
* the refresh-worker dispatch + the CLI exit-code logic (injected runner, no trade);
* the registry-driven monitored cohort (adds dividend_lowvol, keeps Master/regime out).

The real akshare/VM data is exercised at L2 (Codex F004); these assert logic / wiring.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.data_refresh.cn_dividend_lowvol import DIVIDEND_LOWVOL_SUBDIR
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.monitoring.metrics_job import monitored_strategy_ids
from workbench_api.monitoring.tracking import STRATEGY_BENCHMARK
from workbench_api.paper.service import resolve_base_currency
from workbench_api.paper.targets import PAPER_STRATEGIES, load_strategy_targets
from workbench_api.strategy_modes.cn_dividend_lowvol_cli import main as cli_main
from workbench_api.strategy_modes.cn_dividend_lowvol_precompute import (
    CN_DIVIDEND_LOWVOL_CASH_SYMBOL,
    CN_DIVIDEND_LOWVOL_ETF_SYMBOL,
    ERROR_KIND_DATA_NOT_COVERED,
    CnDividendLowvolPrecomputeError,
    CnDividendLowvolPrecomputeSummary,
    CnDividendLowvolTargetResult,
    run_cn_dividend_lowvol_precompute,
    score_cn_dividend_lowvol_target,
)
from workbench_api.strategy_modes.refresh_worker import _DISPATCH, run_refresh_job
from workbench_api.strategy_modes.registry import (
    CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    FUNDING_RESEARCH,
    get_mode,
    mode_for_strategy,
)


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


# --------------------------------------------------------------------------- #
# registry + per-strategy wiring
# --------------------------------------------------------------------------- #


def test_registry_has_dividend_lowvol_research_monthly_mode() -> None:
    mode = get_mode("cn_dividend_lowvol")
    assert mode is not None
    assert mode.strategy_id == CN_DIVIDEND_LOWVOL_STRATEGY_ID
    assert mode.funding_state == FUNDING_RESEARCH
    assert mode.is_research_state is True
    assert mode.cadence == "monthly"
    assert mode.backtest_key is None
    assert "研究态" in mode.display_name
    # Honesty (spec §3): the description carries the "no return uplift / instrument" caveat.
    assert "无收益增量" in mode.description
    assert mode_for_strategy(CN_DIVIDEND_LOWVOL_STRATEGY_ID) is mode


def test_paper_and_benchmark_and_currency_wired() -> None:
    # Paper selector auto-derives from the registry (B057) — the mode appears with no
    # per-strategy change to PAPER_STRATEGIES.
    assert CN_DIVIDEND_LOWVOL_STRATEGY_ID in {sid for sid, _ in PAPER_STRATEGIES}
    # CNY paper book (A-share ETF) + CSI300 benchmark (B080 F004 per-strategy maps).
    assert resolve_base_currency(CN_DIVIDEND_LOWVOL_STRATEGY_ID) == "CNY"
    assert STRATEGY_BENCHMARK[CN_DIVIDEND_LOWVOL_STRATEGY_ID] == "CSI300"


def test_refresh_worker_dispatch_includes_dividend_lowvol() -> None:
    assert CN_DIVIDEND_LOWVOL_STRATEGY_ID in _DISPATCH


def test_monitored_cohort_adds_dividend_lowvol_keeps_master_regime_out() -> None:
    cohort = monitored_strategy_ids()
    # The two cn_attack modes stay (byte-identical order: quality first), dividend_lowvol
    # is appended, and the funded / SPY modes are excluded (Master/regime zero-regression).
    assert cohort == (
        "cn_attack_quality_momentum",
        "cn_attack_pure_momentum",
        CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    )
    assert "master_portfolio" not in cohort
    assert "regime_adaptive" not in cohort


# --------------------------------------------------------------------------- #
# target producer — real F002 spread signal over frozen CSVs
# --------------------------------------------------------------------------- #


def _write_frozen_series(
    root: Path, *, dividend_pct: float, yield_pct: float, n: int = 320
) -> None:
    """Write TR/PR/10Y CSVs whose reconstructed 股息率 is ~``dividend_pct`` and the 10Y is
    a flat ``yield_pct`` — so the spread is a known constant → a deterministic tier.

    PR is flat (price return 0) and TR compounds at the daily rate that yields exactly
    ``dividend_pct`` over the 252-day lookback, so ``reconstruct_dividend_yield`` returns
    ``dividend_pct`` once the trailing window is full."""

    dates = pd.bdate_range("2023-06-01", periods=n)
    daily = (1.0 + dividend_pct / 100.0) ** (1.0 / 252.0)
    tr = [100.0 * daily**i for i in range(n)]
    base = root.joinpath(*DIVIDEND_LOWVOL_SUBDIR)
    base.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "close": tr}).to_csv(base / "index_h20269.csv", index=False)
    pd.DataFrame({"date": dates, "close": [100.0] * n}).to_csv(
        base / "index_h30269.csv", index=False
    )
    pd.DataFrame({"date": dates, "yield": [yield_pct] * n}).to_csv(
        base / "cn_10y_yield.csv", index=False
    )


def test_score_half_tier_appends_cash_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 股息率 3.0% − 10Y 1.0% = 2.0% spread → 半配 (>=1.5 & <2.5) → ETF 0.5 + CASH 0.5.
    _write_frozen_series(tmp_path, dividend_pct=3.0, yield_pct=1.0)
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    result = score_cn_dividend_lowvol_target(as_of=date(2024, 6, 28))
    assert result.target_weights[CN_DIVIDEND_LOWVOL_ETF_SYMBOL] == pytest.approx(0.5)
    assert result.target_weights[CN_DIVIDEND_LOWVOL_CASH_SYMBOL] == pytest.approx(0.5)
    assert sum(result.target_weights.values()) == pytest.approx(1.0)
    assert result.meta["tier"] == "half"
    assert result.meta["spread_pct"] == pytest.approx(2.0, abs=0.05)
    assert result.meta["etf_symbol"] == CN_DIVIDEND_LOWVOL_ETF_SYMBOL
    # ★ honesty caveat present + research_only flag (spec §3).
    assert result.meta["research_only"] is True
    assert result.meta["research_caveat"]["validated"] is False
    # Frozen thresholds denormalised (禁止扫参 — read, never tuned).
    assert result.meta["saturated_spread_pct"] == pytest.approx(2.5)
    assert result.meta["half_spread_pct"] == pytest.approx(1.5)


def test_score_full_tier_has_no_cash_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 股息率 3.0% − 10Y 0.2% = 2.8% spread → 满配 → ETF 1.0, no CASH row (sums 1.0).
    _write_frozen_series(tmp_path, dividend_pct=3.0, yield_pct=0.2)
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    result = score_cn_dividend_lowvol_target(as_of=date(2024, 6, 28))
    assert result.target_weights == {CN_DIVIDEND_LOWVOL_ETF_SYMBOL: pytest.approx(1.0)}
    assert CN_DIVIDEND_LOWVOL_CASH_SYMBOL not in result.target_weights
    assert result.meta["tier"] == "full"


def test_score_data_not_covered_without_data_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKBENCH_DATA_ROOT", raising=False)
    with pytest.raises(CnDividendLowvolPrecomputeError):
        score_cn_dividend_lowvol_target(as_of=date(2024, 6, 28))


# --------------------------------------------------------------------------- #
# producer persistence + graceful degrade (injected score_fn — no trade/CSV)
# --------------------------------------------------------------------------- #


def _fake_result() -> CnDividendLowvolTargetResult:
    return CnDividendLowvolTargetResult(
        as_of_date=date(2024, 6, 28),
        target_weights={CN_DIVIDEND_LOWVOL_ETF_SYMBOL: 0.5, CN_DIVIDEND_LOWVOL_CASH_SYMBOL: 0.5},
        symbol_sleeve={
            CN_DIVIDEND_LOWVOL_ETF_SYMBOL: "dividend_lowvol",
            CN_DIVIDEND_LOWVOL_CASH_SYMBOL: "cash",
        },
        meta={
            "data_source": "real",
            "cadence": "monthly",
            "tier": "half",
            "spread_pct": 2.0,
            "research_only": True,
            "research_caveat": {"validated": False, "oos_result": "mixed"},
        },
    )


def test_run_precompute_persists_snapshot_with_caveat(session: Session) -> None:
    summary = run_cn_dividend_lowvol_precompute(
        session, CN_DIVIDEND_LOWVOL_STRATEGY_ID, score_fn=_fake_result
    )
    assert summary.error is None
    assert summary.saved == 2
    assert summary.as_of_date == date(2024, 6, 28)

    # The paper engine strips CASH; the resolved target keeps the ETF at the tier weight.
    targets = load_strategy_targets(session, CN_DIVIDEND_LOWVOL_STRATEGY_ID)
    assert targets is not None
    assert targets.weights == {CN_DIVIDEND_LOWVOL_ETF_SYMBOL: pytest.approx(0.5)}

    rows = RecommendationSnapshotRepository(session).history_by_strategy(
        CN_DIVIDEND_LOWVOL_STRATEGY_ID
    )
    assert rows, "expected persisted snapshot rows"
    assert rows[0].master_meta["research_caveat"]["validated"] is False


def test_run_precompute_data_not_covered_leaves_snapshot_untouched(
    session: Session,
) -> None:
    def _raise() -> CnDividendLowvolTargetResult:
        raise CnDividendLowvolPrecomputeError("no data root")

    summary = run_cn_dividend_lowvol_precompute(
        session, CN_DIVIDEND_LOWVOL_STRATEGY_ID, score_fn=_raise
    )
    assert summary.saved == 0
    assert summary.error_kind == ERROR_KIND_DATA_NOT_COVERED
    assert (
        RecommendationSnapshotRepository(session).history_by_strategy(
            CN_DIVIDEND_LOWVOL_STRATEGY_ID
        )
        == []
    )


def test_refresh_job_routes_to_dividend_lowvol_producer(session: Session) -> None:
    """The generic refresh worker dispatches the mode's producer via an injected fake
    (no trade import) and normalises its summary."""

    def _fake_producer(_sess: Session):  # type: ignore[no-untyped-def]
        return run_cn_dividend_lowvol_precompute(
            _sess, CN_DIVIDEND_LOWVOL_STRATEGY_ID, score_fn=_fake_result
        )

    # run_refresh_job returns the producer's result unchanged when injected directly.
    result = run_refresh_job(
        session,
        CN_DIVIDEND_LOWVOL_STRATEGY_ID,
        dispatch={CN_DIVIDEND_LOWVOL_STRATEGY_ID: _fake_producer},
    )
    assert isinstance(result, CnDividendLowvolPrecomputeSummary)
    assert result.saved == 2


# --------------------------------------------------------------------------- #
# CLI exit-code logic (injected runner — no trade / DB scoring)
# --------------------------------------------------------------------------- #


def _summary(*, saved: int, error: str | None) -> CnDividendLowvolPrecomputeSummary:
    return CnDividendLowvolPrecomputeSummary(
        saved=saved, as_of_date=date(2024, 6, 28), data_source="real", error=error
    )


@pytest.mark.usefixtures("initialised_db")
def test_cli_returns_zero_on_success() -> None:
    rc = cli_main([], runner=lambda *_a, **_k: _summary(saved=2, error=None))
    assert rc == 0


@pytest.mark.usefixtures("initialised_db")
def test_cli_returns_nonzero_on_empty_or_error() -> None:
    assert cli_main([], runner=lambda *_a, **_k: _summary(saved=0, error=None)) == 1
    assert cli_main([], runner=lambda *_a, **_k: _summary(saved=1, error="boom")) == 1


def test_cli_env_guard_blocks_before_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """§12.11.1 — the scratch-DB guard hard-fails BEFORE the runner is called."""
    import workbench_api.strategy_modes.cn_dividend_lowvol_cli as cli_mod
    from workbench_api.db.require_production_db import ScratchDatabaseError

    def boom(*, entrypoint: str) -> str:
        raise ScratchDatabaseError(f"::error::{entrypoint}: scratch DB")

    monkeypatch.setattr(cli_mod, "require_production_db", boom)
    calls: list[int] = []

    def runner(*_a: object, **_k: object) -> CnDividendLowvolPrecomputeSummary:
        calls.append(1)
        return _summary(saved=2, error=None)

    assert cli_main([], runner=runner) == 1
    assert calls == []  # never ran
