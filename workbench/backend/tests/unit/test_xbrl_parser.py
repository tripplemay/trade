"""B029 F001 — eight ratio computations and the EBITDA helper.

The formulas are locked by 永久边界 (j) (strategy doc §6 / B029 spec
§4.4). The tests assert each ratio against hand-computed AAPL-shape
numbers; a future change to a formula must fail one of these specs
loudly, which signals the change requires a new batch (and a
deliberate Planner review).

Zero-denominator behaviour is also pinned: each ratio raises
``ValueError`` with both the ratio name and the offending denominator
name in the message so a SEC concept-rename surfaces with full
context rather than a silent ``inf`` / ``nan`` slipping into the
unified CSV.
"""

from __future__ import annotations

import math

import pytest

from workbench_api.data.xbrl_parser import (
    SEC_CONCEPT_ALIASES_PER_SECTOR,
    SEC_CONCEPT_NAMES,
    compute_debt_to_assets,
    compute_earnings_yield,
    compute_ebitda,
    compute_ev_ebitda,
    compute_fcf_yield,
    compute_gross_margin,
    compute_pb,
    compute_pe,
    compute_roe,
    get_concept_alias_chain,
)


def test_compute_roe_matches_aapl_2014q4_fixture_value() -> None:
    """AAPL FY2014 NetIncomeLoss / StockholdersEquity ≈ 0.4469
    (matches data/fixtures/us_quality_momentum/fundamentals.csv row 2).
    Numbers chosen so the float ratio rounds cleanly."""

    roe = compute_roe(net_income=39_510, stockholders_equity=88_396)
    assert math.isclose(roe, 0.4469, abs_tol=0.0001)


def test_compute_gross_margin_handles_revenues_minus_cogs() -> None:
    """gross_margin = (Revenues - COGS) / Revenues. Verified against
    AAPL FY2014 ratio fixture value 0.4353."""

    gm = compute_gross_margin(revenues=182_795, cogs=103_236)
    assert math.isclose(gm, 0.4353, abs_tol=0.0001)


def test_compute_fcf_yield_subtracts_capex_from_cfo() -> None:
    """fcf_yield = (CFO - Capex) / MarketCap. The sign convention for
    capex is the absolute outflow magnitude (positive number) per the
    SEC ``PaymentsToAcquirePropertyPlantAndEquipment`` concept."""

    fcfy = compute_fcf_yield(cfo=59_713, capex=9_571, market_cap=1_200_000)
    assert math.isclose(fcfy, 0.0418, abs_tol=0.0001)


def test_compute_debt_to_assets_returns_ratio() -> None:
    da = compute_debt_to_assets(long_term_debt=66_924, assets=226_690)
    assert math.isclose(da, 0.2952, abs_tol=0.0001)


def test_compute_pe_returns_market_cap_over_ttm() -> None:
    pe = compute_pe(market_cap=812_705, net_income_ttm=39_510)
    assert math.isclose(pe, 20.57, abs_tol=0.05)


def test_compute_pb_returns_market_cap_over_equity() -> None:
    pb = compute_pb(market_cap=1_108_403, stockholders_equity=88_396)
    assert math.isclose(pb, 12.54, abs_tol=0.05)


def test_compute_ev_ebitda_adds_debt_subtracts_cash_over_ebitda() -> None:
    """ev_ebitda = (MarketCap + LongTermDebt - Cash) / EBITDA.

    Hand-computed: (812_705 + 66_924 - 13_844) / 51_785 ≈ 16.72,
    matching the AAPL FY2014 fixture row.
    """

    ev_ebitda = compute_ev_ebitda(
        market_cap=812_705,
        long_term_debt=66_924,
        cash=13_844,
        ebitda=51_785,
    )
    assert math.isclose(ev_ebitda, 16.72, abs_tol=0.05)


def test_compute_earnings_yield_is_reciprocal_of_pe() -> None:
    """earnings_yield = NetIncomeLoss_TTM / MarketCap; with non-zero
    inputs this is the reciprocal of P/E."""

    market_cap, ttm = 812_705, 39_510
    ey = compute_earnings_yield(net_income_ttm=ttm, market_cap=market_cap)
    pe = compute_pe(market_cap=market_cap, net_income_ttm=ttm)
    assert math.isclose(ey, 1.0 / pe, abs_tol=1e-9)


def test_compute_ebitda_sums_operating_income_and_da() -> None:
    """Helper: EBITDA = OperatingIncomeLoss + DepreciationDepletionAndAmortization."""

    ebitda = compute_ebitda(operating_income=51_500, depreciation_amortization=7_946)
    assert math.isclose(ebitda, 59_446, abs_tol=1e-6)


@pytest.mark.parametrize(
    "name, fn, args, denominator_name",
    [
        ("roe", compute_roe, (100.0, 0.0), "stockholders_equity"),
        ("gross_margin", compute_gross_margin, (0.0, 50.0), "revenues"),
        ("fcf_yield", compute_fcf_yield, (50.0, 10.0, 0.0), "market_cap"),
        ("debt_to_assets", compute_debt_to_assets, (100.0, 0.0), "assets"),
        ("pe", compute_pe, (1000.0, 0.0), "net_income_ttm"),
        ("pb", compute_pb, (1000.0, 0.0), "stockholders_equity"),
        ("earnings_yield", compute_earnings_yield, (100.0, 0.0), "market_cap"),
    ],
)
def test_zero_denominator_raises_value_error_with_context(
    name: str,
    fn: object,
    args: tuple[float, ...],
    denominator_name: str,
) -> None:
    """Each ratio raises ValueError with both the ratio name and the
    offending denominator name in the message so a SEC concept rename
    surfaces with context rather than producing ``inf`` / ``nan``."""

    with pytest.raises(ValueError) as exc_info:
        fn(*args)  # type: ignore[operator]
    msg = str(exc_info.value)
    assert name in msg
    assert denominator_name in msg


def test_ev_ebitda_zero_ebitda_raises() -> None:
    """``ev_ebitda`` has a 4-arg signature so it doesn't fit the
    parametrize table above cleanly; check it in isolation."""

    with pytest.raises(ValueError) as exc_info:
        compute_ev_ebitda(market_cap=1000.0, long_term_debt=200.0, cash=50.0, ebitda=0.0)
    msg = str(exc_info.value)
    assert "ev_ebitda" in msg
    assert "ebitda" in msg


# ---------------------------------------------------------------------------
# B030 F001 — SEC_CONCEPT_ALIASES_PER_SECTOR + get_concept_alias_chain
# ---------------------------------------------------------------------------


def test_per_sector_alias_map_covers_three_sectors() -> None:
    """B030 F001 acceptance — Financials / Utilities / Real Estate are
    the three sectors whose XBRL dialect drifts far enough from the
    default chain to need explicit overrides (B029 Soft-watch S1)."""

    assert set(SEC_CONCEPT_ALIASES_PER_SECTOR.keys()) == {
        "Financials",
        "Utilities",
        "Real Estate",
    }


@pytest.mark.parametrize(
    "sector",
    ["Financials", "Utilities", "Real Estate"],
)
def test_per_sector_alias_map_includes_eight_ratio_concepts(sector: str) -> None:
    """Each per-sector override must cover the concepts whose XBRL
    dialect actually drifts for that sector. The five
    ratio-input keys (revenues / cogs / long_term_debt / operating_income
    / depreciation_amortization) are exactly the ones identified in
    the B030 spec §4.2 sector-dialect table — net_income / assets /
    cash / cfo / capex / stockholders_equity are stable across the
    three sectors so they fall through to the default chain via
    :func:`get_concept_alias_chain`."""

    overrides = SEC_CONCEPT_ALIASES_PER_SECTOR[sector]
    must_have_overrides = {
        "revenues",
        "cogs",
        "long_term_debt",
        "operating_income",
        "depreciation_amortization",
    }
    assert must_have_overrides.issubset(set(overrides.keys()))
    # Any override key must exist in the default chain too — the
    # import-time sanity check in xbrl_parser enforces this, but a
    # belt-and-braces pin here catches a regression.
    for short_name in overrides:
        assert short_name in SEC_CONCEPT_NAMES


def test_get_concept_alias_chain_default_sector_returns_default_chain() -> None:
    """When ``sector=None`` (or an unrecognised sector), the helper
    returns the default :data:`SEC_CONCEPT_NAMES` chain unchanged.

    Pinned so adding a new per-sector override doesn't accidentally
    shadow the default for "Information Technology" / "Health Care" /
    other sectors that already work with the default chain.
    """

    default_chain = SEC_CONCEPT_NAMES["revenues"]
    assert get_concept_alias_chain("AAPL", "revenues", None) == default_chain
    assert (
        get_concept_alias_chain("AAPL", "revenues", "Information Technology")
        == default_chain
    )
    assert get_concept_alias_chain("JNJ", "revenues", "Health Care") == default_chain


def test_get_concept_alias_chain_financials_promotes_interest_revenue() -> None:
    """Acceptance §(7): Financials → ``InterestAndDividendIncomeOperating``
    must come first in the revenues chain (banks file this concept
    instead of ``Revenues``)."""

    chain = get_concept_alias_chain("JPM", "revenues", "Financials")
    assert chain[0] == "InterestAndDividendIncomeOperating"
    # The bank concept must be ahead of the default ``Revenues``.
    assert chain.index("InterestAndDividendIncomeOperating") < chain.index("Revenues")
    # And ``Revenues`` must still be in the chain so Visa (Financials but
    # uses ``Revenues``) resolves on the fallback.
    assert "Revenues" in chain


def test_get_concept_alias_chain_utilities_promotes_longtermdebtnoncurrent() -> None:
    """Utilities (NEE / DUK) file the noncurrent portion as the
    primary ``LongTermDebt`` concept; the chain must front-load it."""

    chain = get_concept_alias_chain("NEE", "long_term_debt", "Utilities")
    assert chain[0] == "LongTermDebtNoncurrent"
    assert chain.index("LongTermDebtNoncurrent") < chain.index("LongTermDebt")


def test_get_concept_alias_chain_real_estate_promotes_consolidated_debt() -> None:
    """REITs (PLD / AMT) file ``LongTermDebtCurrentAndNoncurrent`` as
    the consolidated balance line."""

    chain = get_concept_alias_chain("PLD", "long_term_debt", "Real Estate")
    assert chain[0] == "LongTermDebtCurrentAndNoncurrent"


def test_get_concept_alias_chain_falls_back_to_default_on_unlisted_concept() -> None:
    """An override sector with no entry for a particular concept must
    fall through to the default. ``assets`` is the same concept across
    all sectors so it has no per-sector override — the default chain
    must still be returned when sector=Financials."""

    assert (
        get_concept_alias_chain("JPM", "assets", "Financials")
        == SEC_CONCEPT_NAMES["assets"]
    )
    assert (
        get_concept_alias_chain("NEE", "net_income", "Utilities")
        == SEC_CONCEPT_NAMES["net_income"]
    )


def test_get_concept_alias_chain_returns_empty_list_for_unknown_concept() -> None:
    """Unknown short-name → empty list. The F002 driver treats an
    empty chain as "no matching concept" and skips the quarter with a
    documented reason."""

    assert get_concept_alias_chain("AAPL", "not_a_real_concept", None) == []
    # Per-sector lookup also falls through when the short-name is
    # absent both in the override and the default.
    assert get_concept_alias_chain("JPM", "not_a_real_concept", "Financials") == []


def test_get_concept_alias_chain_returns_a_copy_not_a_reference() -> None:
    """Mutating the returned list must not corrupt the module-level
    registry. The helper currently returns ``list(...)``; pin the
    invariant so a future refactor doesn't drop the copy."""

    chain = get_concept_alias_chain("JPM", "revenues", "Financials")
    chain.append("BOGUS_CONCEPT")
    # Refetching gives the original chain back.
    refetch = get_concept_alias_chain("JPM", "revenues", "Financials")
    assert "BOGUS_CONCEPT" not in refetch
