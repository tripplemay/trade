"""B050 F005 — defensive-rotation ticket share fidelity (CRITICAL).

Regression for the ~100× over-buy: the defensive SGOV buy line used to put the
**dollar amount in the share column** (``delta_shares = total_equity``). At
SGOV ~$100/share a user following the ticket would buy ~100× the intended
quantity. The fix sizes shares from the real SGOV mark
(``total_equity / mark``); with no mark it is honest (shares ``None``, dollar
only — never dollars-as-shares).
"""

from __future__ import annotations

from types import SimpleNamespace

from workbench_api.services.tickets import _defensive_diff_rows


def _snapshot(positions: list[dict[str, float | str]]) -> SimpleNamespace:
    return SimpleNamespace(positions=positions)


def test_defensive_sgov_shares_sized_from_mark_not_dollars() -> None:
    snap = _snapshot([{"symbol": "SPY", "shares": 50.0, "avg_cost": 500.0}])
    total_equity = 35_000.0
    sgov_mark = 100.25

    rows = _defensive_diff_rows(total_equity, snap, sgov_mark)
    sgov = next(r for r in rows if r["symbol"] == "SGOV")

    # The CRITICAL invariant: shares × mark ≈ equity, NOT shares == equity.
    assert sgov["delta_shares"] != total_equity
    assert sgov["delta_shares"] * sgov_mark == total_equity  # exact: equity/mark*mark
    assert abs(sgov["delta_shares"] * sgov_mark - total_equity) < 1e-6
    assert sgov["reference_price"] == sgov_mark
    assert sgov["delta_dollar"] == total_equity
    # The sell-to-zero leg for the existing holding is still present.
    spy = next(r for r in rows if r["symbol"] == "SPY")
    assert spy["delta_shares"] == -50.0


def test_defensive_sgov_without_mark_is_honest_no_dollars_as_shares() -> None:
    snap = _snapshot([])
    total_equity = 20_000.0

    rows = _defensive_diff_rows(total_equity, snap, None)
    sgov = next(r for r in rows if r["symbol"] == "SGOV")

    # No mark → shares stay None (sized at execution), never dollars-as-shares.
    assert sgov["delta_shares"] is None
    assert sgov["target_shares"] is None
    assert sgov["reference_price"] is None
    assert sgov["delta_dollar"] == total_equity
    assert "market price" in sgov["reason"]


def test_defensive_no_buy_line_when_zero_equity() -> None:
    rows = _defensive_diff_rows(0.0, _snapshot([]), 100.0)
    assert all(r["symbol"] != "SGOV" for r in rows)
