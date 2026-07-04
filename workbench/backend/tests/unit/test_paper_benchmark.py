"""B080 F004 fix ① — per-strategy paper benchmark (master SPY / cn_attack CSI300)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import PaperNavHistoryRepository
from workbench_api.paper.mtm import run_daily_mtm
from workbench_api.paper.service import activate_paper_account
from workbench_api.services.paper import build_paper_view
from workbench_api.services.prices_provider import PriceMark

_ON = date(2026, 6, 30)
_NOW = datetime(2026, 6, 30, 21, tzinfo=UTC)


class _FakeProvider:
    def __init__(self, marks: dict[str, float]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {
            s: PriceMark(self._marks[s], self._marks[s])
            for s in {x.upper() for x in symbols if x}
            if s in self._marks
        }


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    sess = sessionmaker(bind=get_engine(), autoflush=False, future=True)()
    yield sess
    sess.close()


def _last_benchmark(session: Session, account_id: str) -> float | None:
    rows = PaperNavHistoryRepository(session).list_by_account(account_id)
    return rows[-1].benchmark_close if rows else None


def test_master_benchmark_stays_spy_cn_attack_uses_csi300(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # cn_csi300.csv under a WORKBENCH_DATA_ROOT the job reads best-effort.
    csi = tmp_path / "snapshots" / "benchmark" / "cn_csi300.csv"
    csi.parent.mkdir(parents=True, exist_ok=True)
    csi.write_text("date,close\n2026-06-29,3900.0\n2026-06-30,3950.0\n", encoding="utf-8")
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))

    provider = _FakeProvider({"SPY": 500.0})
    # Master account (SPY benchmark) — no target → all-cash, still records a point.
    master, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=_ON, now=_NOW, provider=provider
    )
    # cn_attack account (CSI300 benchmark) — all-cash.
    cn, _ = activate_paper_account(
        session, strategy_id="cn_attack_pure_momentum", on_date=_ON, now=_NOW,
        provider=provider,
    )
    session.commit()

    run_daily_mtm(session, on_date=_ON, now=_NOW, provider=provider)

    # Master zero-regression: the live SPY mark is written, NOT CSI300.
    assert _last_benchmark(session, master.id) == 500.0
    # cn_attack reads the CSI300 close on/before on_date from the CSV.
    assert _last_benchmark(session, cn.id) == 3950.0


def test_cn_attack_benchmark_null_when_csv_absent(
    session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # No cn_csi300.csv → cn_attack records a null benchmark_close (honest degrade),
    # and the job does not crash.
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    provider = _FakeProvider({"SPY": 500.0})
    cn, _ = activate_paper_account(
        session, strategy_id="cn_attack_quality_momentum", on_date=_ON, now=_NOW,
        provider=provider,
    )
    session.commit()
    run_daily_mtm(session, on_date=_ON, now=_NOW, provider=provider)
    assert _last_benchmark(session, cn.id) is None


def test_summary_benchmark_label_and_first_day_caveat(
    session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # fix ③: the summary labels the benchmark + flags the CN-data-caliber caveat;
    # master stays SPY / uncaveated (zero-regression).
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    provider = _FakeProvider({"SPY": 500.0})
    activate_paper_account(
        session, strategy_id="master_portfolio", on_date=_ON, now=_NOW, provider=provider
    )
    activate_paper_account(
        session, strategy_id="cn_attack_pure_momentum", on_date=_ON, now=_NOW,
        provider=provider,
    )
    session.commit()

    master_view = build_paper_view(session, "master_portfolio", provider=provider)
    assert master_view.summary is not None
    assert master_view.summary.benchmark_symbol == "SPY"
    assert master_view.summary.first_day_caveat is False

    cn_view = build_paper_view(session, "cn_attack_pure_momentum", provider=provider)
    assert cn_view.summary is not None
    assert cn_view.summary.benchmark_symbol == "CSI300"
    assert cn_view.summary.first_day_caveat is True
