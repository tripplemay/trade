"""SEC EDGAR companyfacts JSON → eight B025 fixture ratios.

B029 永久边界 (j): the eight formulas are locked per strategy doc
``docs/strategy/03-us-quality-momentum.md`` §6 and B029 spec §4.4 —
changes to any formula require a new batch with a deliberate Planner
review. Edit the implementation of an existing function only when the
companyfacts source field name changes; the math must stay verbatim.

Eight ratios + the auxiliary EBITDA helper:

* ``compute_roe(net_income, stockholders_equity)`` —
  NetIncomeLoss / StockholdersEquity. Caller passes the average of
  beginning + ending equity for a strict ROE; passing the period-end
  value is acceptable for a quick approximation.
* ``compute_gross_margin(revenues, cogs)`` —
  (Revenues - CostOfGoodsAndServicesSold) / Revenues.
* ``compute_fcf_yield(cfo, capex, market_cap)`` —
  (CashFlowFromOperatingActivities - CapitalExpenditures) / MarketCap.
  ``capex`` is the absolute outflow magnitude (positive number); SEC
  reports it positive under ``PaymentsToAcquirePropertyPlantAndEquipment``.
* ``compute_debt_to_assets(long_term_debt, assets)`` —
  LongTermDebt / Assets.
* ``compute_pe(market_cap, net_income_ttm)`` —
  MarketCap / NetIncomeLoss_TTM. Caller sums the four trailing
  quarters' ``NetIncomeLoss`` to get the TTM figure.
* ``compute_pb(market_cap, stockholders_equity)`` —
  MarketCap / StockholdersEquity.
* ``compute_ev_ebitda(market_cap, long_term_debt, cash, ebitda)`` —
  (MarketCap + LongTermDebt - Cash) / EBITDA.
* ``compute_earnings_yield(net_income_ttm, market_cap)`` —
  NetIncomeLoss_TTM / MarketCap. Reciprocal of P/E.
* ``compute_ebitda(operating_income, depreciation_amortization)`` —
  OperatingIncomeLoss + DepreciationDepletionAndAmortization. Helper
  for callers that need EBITDA before invoking ``compute_ev_ebitda``;
  not one of the eight ratios on its own but locked by the same edge.

Zero-denominator cases raise ``ValueError`` rather than returning
``inf`` / ``nan`` — SEC filings should never legitimately yield a
zero denominator for these metrics for a company in the B025 universe
(those are well-capitalised firms), so a zero is a signal that the
upstream extraction picked the wrong concept (e.g. ``Assets`` from a
non-consolidated subsidiary segment) and the caller should surface
the offending ticker/fiscal_quarter rather than silently bake an
invalid ratio into the unified CSV.
"""

from __future__ import annotations


def _require_nonzero(denominator: float, ratio_name: str, denominator_name: str) -> None:
    """Raise ``ValueError`` with a fix pointer when a denominator is zero.

    Centralised so the message format stays uniform across the eight
    ratio helpers — the test suite asserts ``ratio_name`` and
    ``denominator_name`` appear in the message so a future XBRL
    concept rename surfaces with the right context.
    """

    if denominator == 0:
        raise ValueError(
            f"{ratio_name}: {denominator_name} is zero; cannot compute ratio. "
            f"Check the upstream SEC companyfacts extraction for the offending "
            f"ticker / fiscal_quarter — a zero denominator typically means the "
            f"parser picked the wrong concept tag."
        )


def compute_roe(net_income: float, stockholders_equity: float) -> float:
    """Return Return-on-Equity. ``stockholders_equity`` may be the
    average of beginning + ending balances for a strict ROE; passing
    the period-end value is also acceptable.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(stockholders_equity, "roe", "stockholders_equity")
    return net_income / stockholders_equity


def compute_gross_margin(revenues: float, cogs: float) -> float:
    """Return Gross Margin = (Revenues - CostOfGoodsAndServicesSold) / Revenues.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(revenues, "gross_margin", "revenues")
    return (revenues - cogs) / revenues


def compute_fcf_yield(cfo: float, capex: float, market_cap: float) -> float:
    """Return Free-Cash-Flow Yield = (CFO - Capex) / MarketCap.

    ``capex`` is the absolute outflow magnitude (positive number).

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(market_cap, "fcf_yield", "market_cap")
    return (cfo - capex) / market_cap


def compute_debt_to_assets(long_term_debt: float, assets: float) -> float:
    """Return Debt-to-Assets = LongTermDebt / Assets.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(assets, "debt_to_assets", "assets")
    return long_term_debt / assets


def compute_pe(market_cap: float, net_income_ttm: float) -> float:
    """Return P/E ratio = MarketCap / NetIncomeLoss_TTM.

    Caller sums the four trailing quarters' NetIncomeLoss to get TTM.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(net_income_ttm, "pe", "net_income_ttm")
    return market_cap / net_income_ttm


def compute_pb(market_cap: float, stockholders_equity: float) -> float:
    """Return P/B ratio = MarketCap / StockholdersEquity.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(stockholders_equity, "pb", "stockholders_equity")
    return market_cap / stockholders_equity


def compute_ev_ebitda(
    market_cap: float,
    long_term_debt: float,
    cash: float,
    ebitda: float,
) -> float:
    """Return EV/EBITDA = (MarketCap + LongTermDebt - Cash) / EBITDA.

    Use :func:`compute_ebitda` to derive ``ebitda`` from OperatingIncome
    + D&A when the caller doesn't already have a pre-computed EBITDA.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(ebitda, "ev_ebitda", "ebitda")
    return (market_cap + long_term_debt - cash) / ebitda


def compute_earnings_yield(net_income_ttm: float, market_cap: float) -> float:
    """Return Earnings Yield = NetIncomeLoss_TTM / MarketCap. Reciprocal
    of P/E in the no-zero case.

    Formula locked by 永久边界 (j) — strategy doc §6 / B029 spec §4.4.
    """

    _require_nonzero(market_cap, "earnings_yield", "market_cap")
    return net_income_ttm / market_cap


def compute_ebitda(operating_income: float, depreciation_amortization: float) -> float:
    """Return EBITDA = OperatingIncomeLoss + DepreciationDepletionAndAmortization.

    Helper for the EV/EBITDA pipeline. Strategy doc §6 doesn't list
    EBITDA on its own as a B025 ratio, but the lock-edge applies to
    its definition too because it feeds ``compute_ev_ebitda``.
    """

    return operating_income + depreciation_amortization
