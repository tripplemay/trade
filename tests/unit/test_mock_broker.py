import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from trade.paper_prep.broker_adapter import JournalEntry
from trade.paper_prep.mock_broker import (
    DEFAULT_ACCOUNT_STATE_ID,
    DEFAULT_CASH,
    DEFAULT_JOURNAL_PATH,
    MockBroker,
    default_account_state,
)
from trade.paper_prep.target_positions import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AccountState,
    DefensiveAllocation,
    TargetPositionEntry,
    TargetPositions,
    TargetPositionsValidationError,
)


def _account() -> AccountState:
    return AccountState(
        account_state_id=DEFAULT_ACCOUNT_STATE_ID,
        cash=DEFAULT_CASH,
        equity_value=0.0,
        open_positions={},
    )


def _target_positions(**overrides: Any) -> TargetPositions:
    account = _account()
    base = TargetPositions(
        schema_version=SCHEMA_VERSION,
        target_positions_id="deadbeef",
        strategy_id=None,
        portfolio_id="master_portfolio_mvp",
        signal_date=date(2024, 6, 30),
        generation_timestamp=datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
        snapshot_id="fixture:test",
        snapshot_manifest_path=None,
        account_state_reference=account.account_state_id,
        entries=(
            TargetPositionEntry(
                symbol="SPY", target_weight=0.7, target_dollar_exposure=0.7 * DEFAULT_CASH
            ),
        ),
        defensive_allocation=DefensiveAllocation(
            symbol="SGOV", weight=0.3, dollar_exposure=0.3 * DEFAULT_CASH
        ),
        research_limitations=("research-only",),
        disclaimer=DISCLAIMER,
    )
    return replace(base, **overrides)


def _fixed_clock(value: datetime) -> Any:
    def clock() -> datetime:
        return value

    return clock


def test_default_account_state_has_fixed_research_balance() -> None:
    account = default_account_state()

    assert account.account_state_id == DEFAULT_ACCOUNT_STATE_ID
    assert account.cash == 250_000.0
    assert account.equity_value == 0.0
    assert account.open_positions == {}


def test_default_journal_path_is_under_data_paper_prep() -> None:
    assert DEFAULT_JOURNAL_PATH.parts[:2] == ("data", "paper-prep")
    assert DEFAULT_JOURNAL_PATH.suffix == ".jsonl"


def test_mock_broker_submits_target_positions_and_appends_journal_line(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    broker = MockBroker(
        account_state=_account(),
        journal_path=journal_path,
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    entry = broker.submit_target_positions(_target_positions())

    assert isinstance(entry, JournalEntry)
    assert journal_path.exists()
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["journal_entry_id"] == entry.journal_entry_id
    assert payload["target_positions"]["disclaimer"] == DISCLAIMER


def test_mock_broker_journal_id_is_deterministic_across_runs(tmp_path: Path) -> None:
    first_broker = MockBroker(
        account_state=_account(),
        journal_path=tmp_path / "first.jsonl",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )
    second_broker = MockBroker(
        account_state=_account(),
        journal_path=tmp_path / "second.jsonl",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    first_entry = first_broker.submit_target_positions(_target_positions())
    second_entry = second_broker.submit_target_positions(_target_positions())

    assert first_entry.journal_entry_id == second_entry.journal_entry_id


def test_mock_broker_appends_each_submission_as_a_new_line(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.jsonl"
    broker = MockBroker(
        account_state=_account(),
        journal_path=journal_path,
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    broker.submit_target_positions(_target_positions(target_positions_id="abc"))
    broker.submit_target_positions(_target_positions(target_positions_id="def"))

    lines = journal_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["target_positions"]["target_positions_id"] == "abc"
    assert json.loads(lines[1])["target_positions"]["target_positions_id"] == "def"


def test_mock_broker_rejects_invalid_target_positions(tmp_path: Path) -> None:
    broker = MockBroker(
        account_state=_account(),
        journal_path=tmp_path / "journal.jsonl",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )
    bad = _target_positions(disclaimer="trade away")

    with pytest.raises(TargetPositionsValidationError):
        broker.submit_target_positions(bad)

    assert not (tmp_path / "journal.jsonl").exists()


def test_mock_broker_get_account_state_passes_through_constructor_state() -> None:
    account = AccountState(
        account_state_id="custom-account",
        cash=100_000.0,
        equity_value=0.0,
        open_positions={},
    )
    broker = MockBroker(
        account_state=account,
        journal_path=Path("/tmp/should-not-be-touched.jsonl"),
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert broker.get_account_state() == account


def test_mock_broker_get_open_orders_is_empty() -> None:
    broker = MockBroker(
        account_state=_account(),
        journal_path=Path("/tmp/should-not-be-touched.jsonl"),
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert broker.get_open_orders() == ()


def test_mock_broker_construction_does_not_touch_filesystem_or_environment(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed")

    monkeypatch.setattr("socket.socket", _refuse_socket)
    monkeypatch.setattr("os.environ", {})

    journal_path = tmp_path / "subdir" / "journal.jsonl"
    broker = MockBroker(
        account_state=_account(),
        journal_path=journal_path,
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert not journal_path.exists()
    assert broker.get_account_state().cash == DEFAULT_CASH


def test_mock_broker_creates_parent_directories_on_first_submit(tmp_path: Path) -> None:
    journal_path = tmp_path / "nested" / "deeper" / "journal.jsonl"
    broker = MockBroker(
        account_state=_account(),
        journal_path=journal_path,
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    broker.submit_target_positions(_target_positions())

    assert journal_path.exists()


def test_mock_broker_journal_lines_carry_research_only_disclaimer(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.jsonl"
    broker = MockBroker(
        account_state=_account(),
        journal_path=journal_path,
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    broker.submit_target_positions(_target_positions())

    text = journal_path.read_text(encoding="utf-8").lower()
    assert "research-only" in text
    assert "paper execution" not in text
    assert "live execution" not in text
