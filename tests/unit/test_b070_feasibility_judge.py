"""B070 F001 — unit tests for the survivorship-free feasibility GO/PARTIAL/NO-GO judge.

The probe (`scripts/research/b070_feasibility_probe.py`) is a research spike, not
product code, but its *decision logic* — mapping gathered Gate A/B evidence to a
GO / PARTIAL / NO-GO verdict (spec §1) — is deterministic and must be locked so a
re-run on the VM (Codex F004) is graded by a stable rule, not a moving target.

These tests feed synthetic gate-evidence shapes and assert the verdict mapping.
No network. The real local run's raw returns live in the F001 report
(`docs/dev/B070-feasibility-report.md`) and `data/research/b070/` (gitignored).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_PROBE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "research" / "b070_feasibility_probe.py"
)


def _load_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("b070_feasibility_probe", _PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


def _gate_a(*, reachable: bool, changes: bool, delisted: int) -> dict:
    """Synthetic Gate A evidence: one index with controllable PIT signals."""
    return {
        "indexes": {
            "hs300": {
                "earliest_data_date": "2007-01-29" if reachable else None,
                "membership_change": {"left_index": 5 if changes else 0},
            }
        },
        "survivorship_test": {"n_delisted_confirmed": delisted},
    }


def _gate_b(*, reachable: int) -> dict:
    return {"n_reachable": reachable}


def test_go_when_gate_a_truly_pit_and_gate_b_reachable() -> None:
    result = probe.judge(
        _gate_a(reachable=True, changes=True, delisted=9),
        _gate_b(reachable=4),
    )
    assert result["verdict"] == "GO"
    assert result["signals"]["gate_a_truly_point_in_time"] is True
    assert result["signals"]["gate_b_delisted_prices_reachable"] is True


def test_partial_when_gate_a_pit_but_gate_b_missing() -> None:
    result = probe.judge(
        _gate_a(reachable=True, changes=True, delisted=9),
        _gate_b(reachable=0),
    )
    assert result["verdict"] == "PARTIAL"
    assert "delisted prices missing" in result["reason"]


def test_partial_when_reachable_but_not_demonstrably_survivorship_free() -> None:
    # Reachable + Gate B ok, but no membership change AND no delisted members found
    # → cannot claim survivorship-free → PARTIAL, not a false GO.
    result = probe.judge(
        _gate_a(reachable=True, changes=False, delisted=0),
        _gate_b(reachable=4),
    )
    assert result["verdict"] == "PARTIAL"
    assert result["signals"]["gate_a_truly_point_in_time"] is False


def test_no_go_when_gate_a_unreachable() -> None:
    result = probe.judge(
        _gate_a(reachable=False, changes=False, delisted=0),
        _gate_b(reachable=4),
    )
    assert result["verdict"] == "NO-GO"
    assert "research-only" in result["reason"]


@pytest.mark.parametrize(
    ("changes", "delisted", "expected_truly_pit"),
    [
        (True, 9, True),  # both PIT signals present → truly survivorship-free
        (True, 0, False),  # changes but no confirmed delisted member → not proven
        (False, 9, False),  # delisted present but no membership change → not proven
    ],
)
def test_truly_pit_requires_both_change_and_delisted(
    changes: bool, delisted: int, expected_truly_pit: bool
) -> None:
    result = probe.judge(
        _gate_a(reachable=True, changes=changes, delisted=delisted), _gate_b(reachable=4)
    )
    assert result["signals"]["gate_a_truly_point_in_time"] is expected_truly_pit
