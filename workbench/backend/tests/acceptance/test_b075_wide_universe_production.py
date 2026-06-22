"""B075 F002 — permanent acceptance guards: wide A-share universe goes to production.

Turns this batch's novel production wiring into permanent CI regressions
(验收即代码, framework v0.9.49 §31):

1. **The DAILY data-refresh wires WIDE prices but DECOUPLES the heavy build.** The
   daily timer must fetch the wide A-share universe (``--cn-universe-sina-fallback``,
   the §23 VM-reachable bulk discovery) at the feasibility-gated target N, while
   skipping the ~2h historical-mcap build + ~2h CAS fundamentals
   (``--no-cn-universe-build --no-cn-fundamentals``) so it stays the ~33min daily
   命门 the VM probe measured. If a future edit drops a flag, this goes red.
2. **The WEEKLY cn-universe timer carries the heavy build + fundamentals.** A
   separate weekly unit must exist, ungate the wide discovery, and run the build +
   fundamentals (NO ``--no-*`` decouple flags) so the wide PIT universe +
   fundamentals are actually produced for cn_attack.
3. **price_snapshot sync covers the WIDE set.** B074's ``cn_snapshot_sync`` reads
   every A-share row in the unified CSV — so a wide (~hundreds) CSV makes the whole
   wide universe markable for the paper books, not just a curated handful.

The systemd checks parse the shipped unit files (no VM); the sync check runs the
real CSV→price_snapshot path against the test DB.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.data_refresh.cli import WIDE_UNIVERSE_TARGET_N
from workbench_api.db.engine import get_engine
from workbench_api.prices.cn_snapshot_sync import sync_cn_closes_from_csv
from workbench_api.services.prices_provider import DbPriceProvider

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SYSTEMD = _REPO_ROOT / "workbench" / "deploy" / "systemd"
_DAILY_SERVICE = _SYSTEMD / "workbench-data-refresh.service"
_WEEKLY_SERVICE = _SYSTEMD / "workbench-cn-universe.service"
_WEEKLY_TIMER = _SYSTEMD / "workbench-cn-universe.timer"

_CN_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _execstart(service_unit: Path) -> str:
    assert service_unit.is_file(), f"missing {service_unit}"
    lines = [
        ln
        for ln in service_unit.read_text(encoding="utf-8").splitlines()
        if ln.strip().startswith("ExecStart=")
    ]
    assert len(lines) == 1, f"{service_unit.name} must have exactly one ExecStart"
    return lines[0]


# --- 1. daily refresh = wide prices, build + fundamentals decoupled ----------


def test_daily_refresh_wires_wide_prices_and_decouples_heavy_blocks() -> None:
    execstart = _execstart(_DAILY_SERVICE)
    assert "workbench_api.data_refresh.cli fetch" in execstart
    # Wide discovery ungated at the feasibility-gated target N.
    assert "--cn-universe-sina-fallback" in execstart
    assert f"--cn-universe-top-n {WIDE_UNIVERSE_TARGET_N}" in execstart
    assert f"--cn-universe-max-superset {WIDE_UNIVERSE_TARGET_N}" in execstart
    # The two heavy cost centres are decoupled OFF the daily job.
    assert "--no-cn-universe-build" in execstart
    assert "--no-cn-fundamentals" in execstart


# --- 2. weekly cn-universe = the heavy build + fundamentals -------------------


def test_weekly_cn_universe_builds_wide_with_fundamentals() -> None:
    execstart = _execstart(_WEEKLY_SERVICE)
    assert "workbench_api.data_refresh.cli fetch" in execstart
    assert "--cn-universe-sina-fallback" in execstart
    assert f"--cn-universe-top-n {WIDE_UNIVERSE_TARGET_N}" in execstart
    # The weekly job must NOT decouple — it is the one that builds + fetches CAS.
    assert "--no-cn-universe-build" not in execstart
    assert "--no-cn-fundamentals" not in execstart


def test_weekly_cn_universe_timer_is_weekly() -> None:
    assert _WEEKLY_TIMER.is_file(), f"missing {_WEEKLY_TIMER}"
    text = _WEEKLY_TIMER.read_text(encoding="utf-8")
    # Weekly cadence (Sunday) — the quarterly-relevant build does not need daily.
    assert "OnCalendar=Sun" in text
    assert "Unit=workbench-cn-universe.service" in text
    assert "WantedBy=timers.target" in text


def test_weekly_cn_universe_service_stays_read_only() -> None:
    directives = "\n".join(
        ln
        for ln in _WEEKLY_SERVICE.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "execution", "ticket", "fills"):
        assert frag not in directives, (
            f"cn-universe .service directive references trade-execution {frag!r}"
        )
    assert "EnvironmentFile=/etc/workbench/workbench.env" in _WEEKLY_SERVICE.read_text(
        encoding="utf-8"
    )


# --- 3. price_snapshot sync covers the WIDE A-share set ----------------------


def test_cn_snapshot_sync_covers_a_wide_aset(session: Session, tmp_path: Path) -> None:
    """A wide unified CSV (hundreds of A-shares) → every name becomes markable.

    Proves the B074 sync scales to the B075 wide universe: there is no cap, so the
    whole liquid market the daily refresh writes flows into price_snapshot and the
    cn_attack paper books can mark wide selections (not just a curated handful)."""

    # 300 synthetic A-shares (mix of .SH / .SZ), two closes each = markable.
    symbols = [
        f"6{i:05d}.SH" if i % 2 == 0 else f"0{i:05d}.SZ" for i in range(1, 301)
    ]
    csv_path = tmp_path / "prices_daily.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_CN_HEADER)
        for sym in symbols:
            for d, close in (("2026-06-17", 100.0), ("2026-06-18", 101.0)):
                writer.writerow([d, sym, close, close, close, close, close, 1000])

    summary = sync_cn_closes_from_csv(session, prices_path=csv_path)
    assert summary.symbols == len(symbols)  # no silent cap on the wide set
    assert summary.saved == len(symbols) * 2

    # Every wide name is markable through the SAME provider the paper engine uses.
    provider = DbPriceProvider(session)
    marked = provider.get_marks(set(symbols))
    assert set(marked) == set(symbols)
