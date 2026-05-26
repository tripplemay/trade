"""SEC EDGAR companyfacts JSON → eight B025 fixture ratios.

B029 永久边界 (j): the eight formulas are locked per strategy doc
``docs/strategy/03-us-quality-momentum.md`` §6 and B029 spec §4.4 —
changes to any formula require a new batch with a deliberate Planner
review. Edit the implementation of an existing function only when the
companyfacts source field name changes; the math must stay verbatim.

B030 F001 — SEC concept name alias registry now lives in this module
(was previously in :mod:`sec_edgar_loader`). The default chain
:data:`SEC_CONCEPT_NAMES` covers a "typical" industrial / consumer /
tech filer; per-sector overrides in
:data:`SEC_CONCEPT_ALIASES_PER_SECTOR` cover the three sectors whose
XBRL dialect drifts far enough from the default that the B029 first-
run backfill produced 0 rows for them (Financials / Utilities / Real
Estate; B029 Soft-watch S1 — 6 ticker BAC/JPM/V/LIN/NEE/PLD). The
:func:`get_concept_alias_chain` helper resolves a sector-aware chain
or falls back to the default.

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


# ---------------------------------------------------------------------------
# SEC concept name alias registry (B030 F001 — moved from sec_edgar_loader)
# ---------------------------------------------------------------------------
#
# Each ratio input maps to an **ordered list** of SEC us-gaap concept
# names. The F002 backfill driver tries each in order and unions every
# matching entry before bucketing by calendar quarter; per-quarter
# bucketing then keeps the latest-filed entry, so an alias chain
# effectively stitches a single time series across the SEC's concept
# renaming history.
#
# Common drift causes the default chain addresses:
#
# * **Revenues** — pre-ASC 606 used ``Revenues`` / ``SalesRevenueNet``;
#   post-2018 ASC 606 switched to
#   ``RevenueFromContractWithCustomerExcludingAssessedTax``.
# * **COGS** — ``CostOfGoodsAndServicesSold`` vs ``CostOfRevenue`` vs
#   ``CostOfGoodsSold`` across filers.
# * **LongTermDebt** — sometimes filed as ``LongTermDebtNoncurrent``
#   for the non-current portion only.
# * **DepreciationDepletionAndAmortization** — sometimes
#   ``DepreciationAndAmortization`` or just ``Depreciation``.
# * **PaymentsToAcquirePropertyPlantAndEquipment** — sometimes
#   ``PaymentsToAcquireProductiveAssets``.
SEC_CONCEPT_NAMES: dict[str, list[str]] = {
    "net_income": ["NetIncomeLoss"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "revenues": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfServices",
        # Industrial gas / chemicals filers (LIN, APD, ECL) report COGS
        # excluding D&A as a separate concept; without this fallback
        # the default chain misses them and the quarter is dropped.
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        "CostsAndExpenses",
        # Utilities + service firms report operating expenses as a
        # single line item rather than splitting COGS / OpEx (e.g. NEE,
        # LIN, financial firms). Treating ``OperatingExpenses`` as a
        # COGS-equivalent imprecisely inflates gross_margin denominator
        # but unlocks ratio production for non-product filers.
        "OperatingExpenses",
        "OperatingCostsAndExpenses",
    ],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "assets": ["Assets"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        # Pre-tax income — not strictly equivalent (includes non-operating
        # interest income/expense), but the closest XBRL fallback for
        # filers that stop reporting OperatingIncomeLoss (e.g. JNJ
        # post-2015 transitions to this concept). Documented imprecision.
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
}
"""Default SEC us-gaap XBRL concept-name **alias chains** per ratio input.

For each input, the F002 driver tries every concept in order and
merges all matching entries before bucketing by calendar quarter. This
handles the common SEC concept drift between ASC standards / filer
preferences without forcing every filer to use one canonical name.
"""


# Eight ratio short names — the keys the backfill driver iterates and
# the keys used as the second arg to :func:`get_concept_alias_chain`.
# Pinned here so a typo in a per-sector override surfaces at import
# time via the assert below.
_RATIO_INPUT_NAMES: frozenset[str] = frozenset(SEC_CONCEPT_NAMES.keys())


# Per-sector overrides (B030 F001). Covers Financials / Utilities /
# Real Estate — the three sector groups whose XBRL dialect drifts far
# enough from the default that the B029 first-run backfill produced
# 0 rows for them (B029 Soft-watch S1).
#
# Each per-sector dict is a **partial** override of the default; any
# ratio input not listed falls through to the default chain via
# :func:`get_concept_alias_chain`. Override chains are designed to:
#
# 1. Front-load the sector-idiomatic concept (e.g. banks file
#    ``InterestAndDividendIncomeOperating`` instead of ``Revenues``).
# 2. Preserve the default concepts as later fallbacks so a mixed-
#    profile filer (e.g. V / Visa — classified Financials but uses
#    ``Revenues``) still resolves.
#
# Spec source: B030 spec §4.2 / B029 fundamentals snapshot signoff
# Soft-watch S1 root cause (6 ticker BAC/JPM/V/LIN/NEE/PLD).
SEC_CONCEPT_ALIASES_PER_SECTOR: dict[str, dict[str, list[str]]] = {
    "Financials": {
        # Banks (BAC / JPM) report ``InterestAndDividendIncomeOperating``
        # as their top-line revenue concept; Visa (payment processor,
        # also Financials per GICS) uses ``Revenues`` — front-load the
        # bank concept and fall back to defaults so both resolve.
        "revenues": [
            "InterestAndDividendIncomeOperating",
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "InterestAndDividendIncomeOperatingNonoperating",
            "NoninterestIncome",
            "SalesRevenueNet",
        ],
        # Bank COGS-equivalent is interest expense; non-bank Financials
        # (Visa) lacks a dedicated COGS concept entirely and uses the
        # generic ``CostsAndExpenses`` aggregate line. Both routes are
        # in the chain so the helper resolves whichever the filer
        # reports.
        "cogs": [
            "InterestExpense",
            "InterestExpenseOperating",
            "CostsAndExpenses",
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "NoninterestExpense",
            "OperatingExpenses",
        ],
        # Bank long-term debt: JPM filed plain ``LongTermDebt`` through
        # 2014 then switched to
        # ``LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities``
        # for all post-2014 quarters. V (payment processor) reports
        # the noncurrent portion only.
        "long_term_debt": [
            "LongTermDebt",
            "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
            "LongTermDebtNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
        # Same default OperatingIncome chain works for Financials but
        # the pre-tax-income fallback is more often used by banks.
        "operating_income": [
            "OperatingIncomeLoss",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        ],
        # Banks file D&A under a composite concept that bundles
        # accretion; without this alias the default chain misses them
        # for every quarter.
        "depreciation_amortization": [
            "DepreciationDepletionAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
            "DepreciationAndAmortization",
            "Depreciation",
        ],
        # Banks file cash under a bank-specific concept that includes
        # interbank deposits and reserves. Default ``CashAndCashEquivalents``
        # often has only annual snapshots for banks (16 entries for JPM
        # vs 222 for ``CashAndDueFromBanks``).
        "cash": [
            "CashAndDueFromBanks",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "CashAndCashEquivalentsAtCarryingValue",
            "Cash",
        ],
        # Banks don't file traditional PP&E capex; the closest proxy
        # is M&A spending (``PaymentsToAcquireBusinessesNetOfCashAcquired``)
        # for diversified banks, or ``PaymentsToAcquireProductiveAssets``
        # for payment processors (Visa). Listed as approximations —
        # downstream fcf_yield for banks is a documented approximation
        # rather than a precise free-cash-flow yield.
        "capex": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
            "PaymentsToAcquireBusinessesNetOfCashAcquired",
            "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
            "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        ],
    },
    "Utilities": {
        # Utilities (NEE / DUK) file the noncurrent portion of
        # long-term debt as the primary concept; LIN (industrial gases,
        # GICS Materials but uses Utilities-style XBRL) also benefits
        # from this chain.
        "long_term_debt": [
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtCurrentAndNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
        "revenues": [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RegulatedAndUnregulatedOperatingRevenue",
            "ElectricUtilityRevenue",
            "GasDistributionRevenue",
            "OperatingRevenuesNet",
        ],
        # Utilities report total operating expenses; the default chain
        # already includes ``OperatingExpenses`` but we promote it to
        # the front for this sector.
        "cogs": [
            "OperatingExpenses",
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "OperatingCostsAndExpenses",
            "CostsAndExpenses",
            "UtilitiesOperatingExpense",
        ],
        "operating_income": [
            "OperatingIncomeLoss",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ],
        "depreciation_amortization": [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "Depreciation",
            "UtilitiesOperatingExpenseDepreciationAndAmortization",
        ],
        # NEE doesn't file traditional ``PaymentsToAcquirePropertyPlantAndEquipment``;
        # the closest signal is ``CapitalExpendituresIncurredButNotYetPaid``
        # (the accrued-but-unpaid capex line; not exactly cash capex
        # but the best proxy NEE reports). Documented approximation —
        # fcf_yield for utilities under this chain is a regulated-utility-
        # specific signal rather than a generic free-cash-flow yield.
        "capex": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpendituresIncurredButNotYetPaid",
            "PaymentsToAcquireProductiveAssets",
            "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
            "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        ],
    },
    "Real Estate": {
        # REITs (PLD / AMT) file ``LongTermDebtCurrentAndNoncurrent``
        # as the consolidated balance line.
        "long_term_debt": [
            "LongTermDebtCurrentAndNoncurrent",
            "LongTermDebt",
            "LongTermDebtNoncurrent",
            "SecuredDebt",
            "SeniorNotes",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
        "revenues": [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RealEstateRevenueNet",
            "OperatingLeasesIncomeStatementLeaseRevenue",
            "RentalIncomeNonoperating",
        ],
        "cogs": [
            "OperatingExpenses",
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostsAndExpenses",
            "OperatingCostsAndExpenses",
            "DirectCostsOfLeasedAndRentedPropertyOrEquipment",
        ],
        "operating_income": [
            "OperatingIncomeLoss",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ],
        "depreciation_amortization": [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "Depreciation",
        ],
        # REIT capex is real-estate-acquisition spending. PLD files
        # ``PaymentsToAcquireRealEstate`` + ``PaymentsForCapitalImprovements``;
        # AMT (Telecom Tower REIT) uses ``PaymentsToAcquireBusinessesNetOfCashAcquired``
        # for tower acquisitions. Combine all REIT-relevant capex
        # concepts into one chain.
        "capex": [
            "PaymentsToAcquireRealEstate",
            "PaymentsToAcquireAndDevelopRealEstate",
            "PaymentsForCapitalImprovements",
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireBusinessesNetOfCashAcquired",
            "PaymentsToAcquireProductiveAssets",
        ],
    },
}
"""Per-sector SEC concept alias chains (B030 F001).

Covers Financials / Utilities / Real Estate — the three GICS sectors
whose XBRL dialect drifts far enough from the default
:data:`SEC_CONCEPT_NAMES` chain that the B029 first-run backfill
produced 0 rows for them (B029 Soft-watch S1 root cause).

Each per-sector dict is a partial override — concepts not listed
fall through to the default chain via :func:`get_concept_alias_chain`.
"""


# Import-time sanity check: any short-name key in a per-sector dict
# must also exist in the default chain. Catches a typo in a sector
# override (e.g. ``"revenue"`` instead of ``"revenues"``) before it
# silently bypasses the per-sector fallback at runtime.
for _sector, _aliases in SEC_CONCEPT_ALIASES_PER_SECTOR.items():
    for _short_name in _aliases:
        if _short_name not in _RATIO_INPUT_NAMES:
            raise RuntimeError(
                f"SEC_CONCEPT_ALIASES_PER_SECTOR[{_sector!r}][{_short_name!r}] "
                f"is not in SEC_CONCEPT_NAMES; check for a typo. Known "
                f"short names: {sorted(_RATIO_INPUT_NAMES)}"
            )


def get_concept_alias_chain(
    ticker: str,
    concept: str,
    sector: str | None = None,
) -> list[str]:
    """Return the ordered list of SEC us-gaap concept names to try for
    ``concept`` (one of the keys in :data:`SEC_CONCEPT_NAMES`).

    Sector-aware: if ``sector`` is in
    :data:`SEC_CONCEPT_ALIASES_PER_SECTOR` and the sector dict has an
    override for ``concept``, return that chain. Otherwise fall back
    to the default :data:`SEC_CONCEPT_NAMES` chain.

    Returns an empty list when ``concept`` is unknown in both the
    sector override and the default — the F002 driver treats an empty
    chain as "no matching concept" and skips the quarter with a
    documented reason.

    ``ticker`` is currently used only for diagnostics (caller logs);
    keep the parameter in the signature so a future per-ticker
    override (e.g. one-off corrections for a known filer outlier) can
    be wired in without breaking callers.
    """

    if sector and sector in SEC_CONCEPT_ALIASES_PER_SECTOR:
        sector_aliases = SEC_CONCEPT_ALIASES_PER_SECTOR[sector]
        if concept in sector_aliases:
            return list(sector_aliases[concept])
    return list(SEC_CONCEPT_NAMES.get(concept, []))
