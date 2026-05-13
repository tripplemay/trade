import ast
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from trade.paper_prep.broker_adapter import (
    FORBIDDEN_BROKER_SDK_MODULES,
    BrokerAdapter,
    JournalEntry,
    OpenOrder,
)
from trade.paper_prep.target_positions import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AccountState,
    DefensiveAllocation,
    TargetPositionEntry,
    TargetPositions,
)

PAPER_PREP_DIR = Path(__file__).resolve().parents[2] / "trade" / "paper_prep"


def _account() -> AccountState:
    return AccountState(
        account_state_id="research-account-default",
        cash=250_000.0,
        equity_value=0.0,
        open_positions={},
    )


def _target_positions() -> TargetPositions:
    account = _account()
    return TargetPositions(
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
            TargetPositionEntry(symbol="SPY", target_weight=0.7, target_dollar_exposure=175_000.0),
        ),
        defensive_allocation=DefensiveAllocation(
            symbol="SGOV", weight=0.3, dollar_exposure=75_000.0
        ),
        research_limitations=("research-only",),
        disclaimer=DISCLAIMER,
    )


def test_broker_adapter_abc_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        BrokerAdapter()  # type: ignore[abstract]


def test_partial_subclass_missing_methods_cannot_be_instantiated() -> None:
    class Partial(BrokerAdapter):
        def get_open_orders(self) -> Sequence[OpenOrder]:
            return ()

    with pytest.raises(TypeError, match="abstract"):
        Partial()  # type: ignore[abstract]


def test_full_subclass_satisfies_contract() -> None:
    class Stub(BrokerAdapter):
        def submit_target_positions(self, positions: TargetPositions) -> JournalEntry:
            return JournalEntry(
                journal_entry_id="stub",
                recorded_at=datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
                target_positions=positions,
            )

        def get_account_state(self) -> AccountState:
            return _account()

        def get_open_orders(self) -> Sequence[OpenOrder]:
            return ()

    adapter: BrokerAdapter = Stub()
    entry = adapter.submit_target_positions(_target_positions())
    assert isinstance(entry, JournalEntry)
    assert adapter.get_account_state() == _account()
    assert adapter.get_open_orders() == ()


def test_journal_entry_carries_target_positions_and_metadata() -> None:
    positions = _target_positions()
    entry = JournalEntry(
        journal_entry_id="abc123",
        recorded_at=datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
        target_positions=positions,
    )

    assert entry.journal_entry_id == "abc123"
    assert entry.target_positions is positions


def test_forbidden_broker_sdk_modules_list_covers_b012_decisions() -> None:
    expected = {
        "ib_insync",
        "alpaca",
        "alpaca_trade_api",
        "futu",
        "futu_api",
        "tiger",
        "tiger_api",
        "tradier",
        "polygon",
    }
    assert expected <= set(FORBIDDEN_BROKER_SDK_MODULES)


def test_paper_prep_modules_do_not_import_forbidden_broker_sdks() -> None:
    forbidden = set(FORBIDDEN_BROKER_SDK_MODULES)
    for source_path in PAPER_PREP_DIR.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        leaks = imported & forbidden
        assert leaks == set(), f"{source_path} imports forbidden broker SDK: {leaks}"


def test_broker_adapter_module_docstring_marks_b012_as_abstract_only() -> None:
    source = (PAPER_PREP_DIR / "broker_adapter.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    docstring = ast.get_docstring(module) or ""

    assert "abstract" in docstring.lower()
    assert "b012" in docstring.lower()
    assert "research-only" in docstring.lower() or "research only" in docstring.lower()
