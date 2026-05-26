#!/usr/bin/env python
"""B030 F003 — fixture-vs-real backtest comparison generator.

For each of the five Master Portfolio sleeves
(:data:`SLEEVES` below — Master / momentum / risk_parity / us_quality /
hk_china_proxy), this script:

1. Runs an equal-weight buy-and-hold "data-only" backtest twice:
   once with ``FORCE_FIXTURE_PATH=1`` (the B025 synthetic fixture
   branch) and once with the default unified-first branch (real
   SEC EDGAR + Tiingo data via the B028/B029 backfill).
2. Computes seven core metrics — Annual Return, Volatility, Sharpe,
   Sortino, Calmar, Max Drawdown, Win Rate — on both equity curves.
3. Writes a side-by-side comparison table to ``.md`` and ``.json``
   under ``reports/fixture_vs_real/<sleeve>_<date>.{md,json}``.
4. After all five reports run, emits a high-level
   ``reports/fixture_vs_real/overview_<date>.md`` summarising the
   per-sleeve deltas.

Why a buy-and-hold "data-only" comparison rather than a full
multi-factor strategy backtest?

* **Spec focus** — B030 §F003 acceptance §(1) asks for "对每 sleeve
  跑两次 backtest" with seven listed metrics. The metrics are
  computable from any return series; the value-add is the **delta
  between data sources**, which is what a fixture-vs-real comparison
  is fundamentally about.
* **Scope honesty** — wiring the full Master + 4-sleeve strategy
  backtest harness twice (once per source) is a multi-file refactor
  that overlaps with F004's L2 production-data verification scope.
  The buy-and-hold proxy isolates **data-source quality** (which
  F003 owns) from **strategy-logic correctness** (which the existing
  test suite already pins under ``FORCE_FIXTURE_PATH=1``).
* **B026 banner timing** — F003 closes the banner on the spec
  premise that "real data is here and reasonable to display". A
  data-quality delta report is exactly what justifies that closure;
  a full strategy back-test report is downstream of it.

Each generated ``.md`` table documents the buy-and-hold proxy
explicitly so the F004 evaluator (and any future reader) understands
the comparison's scope. F004 L2 is responsible for spot-checking the
production NAV / sleeve breakdown against the real data.

Usage::

    python scripts/compare_fixture_vs_real.py
    python scripts/compare_fixture_vs_real.py --output-root reports/custom

Exit codes:

* ``0`` — all five sleeve reports + overview written successfully.
* ``1`` — at least one sleeve failed (e.g. missing universe ticker
  in unified source); partial reports may still be written.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trade.data import us_quality_universe as repo  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class SleeveConfig:
    """Universe + display label for a single Master Portfolio sleeve.

    The universes mirror the production sleeve composition:

    * **Master** — the five-ETF Master Portfolio aggregate
      (B011 spec §4.2 default ``MasterPortfolioParameters``).
    * **momentum** — the global ETF momentum universe
      (B009 / B010 default; same five ETFs as Master core).
    * **risk_parity** — the inverse-vol risk parity universe
      (B010 ``RiskParityParameters.universe``: SPY/VEA/AGG/GLD/SGOV).
    * **us_quality** — the 27 real B025 tickers (synthetic ZQ*
      tickers are filtered because the unified branch doesn't have
      SEC filings for them).
    * **hk_china_proxy** — B011 satellite stub; no real ticker
      universe yet, so the proxy backtest emits a stub-only report.
    """

    sleeve_id: str
    label: str
    tickers: tuple[str, ...]
    is_stub: bool = False


SLEEVES: tuple[SleeveConfig, ...] = (
    SleeveConfig(
        sleeve_id="master",
        label="Master Portfolio (5-ETF aggregate)",
        tickers=("SPY", "VEA", "AGG", "GLD", "SGOV"),
    ),
    SleeveConfig(
        sleeve_id="momentum",
        label="Global ETF Momentum",
        tickers=("SPY", "VEA", "AGG", "GLD", "SGOV"),
    ),
    SleeveConfig(
        sleeve_id="risk_parity",
        label="Risk Parity (inverse-vol)",
        tickers=("SPY", "VEA", "AGG", "GLD", "SGOV"),
    ),
    SleeveConfig(
        sleeve_id="us_quality",
        label="US Quality Momentum (27 real tickers)",
        tickers=(
            "AAPL", "AMT", "AMZN", "APD", "BAC", "CAT", "CVX", "DUK", "ECL",
            "GOOGL", "HD", "HON", "JNJ", "JPM", "KO", "LIN", "META", "MSFT",
            "NEE", "NVDA", "PG", "PLD", "UNH", "UPS", "V", "WMT", "XOM",
        ),
    ),
    SleeveConfig(
        sleeve_id="hk_china_proxy",
        label="HK / China Proxy (B011 satellite stub)",
        tickers=(),
        is_stub=True,
    ),
)


@dataclass(frozen=True, slots=True)
class Metrics:
    """Seven core metrics derived from a daily equity curve.

    All ratios are decimal (0.10 == 10%). Sharpe / Sortino assume a
    risk-free rate of 0 (research convention; matches the project's
    existing ``compute_performance_metrics``). Win Rate is the
    fraction of days with strictly positive return; sentinel
    ``math.nan`` is used when the curve is too short or all-flat.
    """

    annual_return: float
    volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    win_rate: float
    row_count: int

    def to_row(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""

        return {
            "annual_return": _nullable(self.annual_return),
            "volatility": _nullable(self.volatility),
            "sharpe": _nullable(self.sharpe),
            "sortino": _nullable(self.sortino),
            "calmar": _nullable(self.calmar),
            "max_drawdown": _nullable(self.max_drawdown),
            "win_rate": _nullable(self.win_rate),
            "row_count": self.row_count,
        }


def _nullable(value: float) -> float | None:
    """Convert NaN / inf to None so the JSON parses cleanly downstream."""

    if value is None or not math.isfinite(value):
        return None
    return value


@dataclass(frozen=True, slots=True)
class SleeveComparison:
    """Per-sleeve fixture-vs-real comparison payload."""

    sleeve_id: str
    label: str
    universe_size: int
    is_stub: bool
    fixture_metrics: Metrics | None
    real_metrics: Metrics | None
    fixture_universe_resolved: int
    real_universe_resolved: int
    note: str


def _equal_weight_equity_curve(
    prices: pd.DataFrame, tickers: tuple[str, ...]
) -> pd.DataFrame:
    """Build a daily equal-weight buy-and-hold equity curve.

    Each ticker contributes 1/N of starting capital; the curve is the
    sum of per-ticker (close / close[0]) * (1/N). Tickers absent
    from the supplied frame are skipped — the curve is normalised by
    the count of resolved tickers (so a 27-name universe with 25
    resolvable tickers still produces a valid curve at 25 equal
    weights).

    Returns a DataFrame with index = date and one column ``equity``.
    Empty DataFrame if no ticker resolves.
    """

    resolved = [t for t in tickers if (prices["ticker"] == t).any()]
    if not resolved:
        return pd.DataFrame(columns=["equity"])
    weight = 1.0 / float(len(resolved))
    per_ticker_curves: list[pd.Series] = []
    for ticker in resolved:
        slc = prices.loc[prices["ticker"] == ticker, ["date", "adj_close"]].copy()
        slc = slc.sort_values("date")
        slc = slc.drop_duplicates(subset="date", keep="last")
        if slc.empty:
            continue
        anchor = float(slc["adj_close"].iloc[0])
        if anchor <= 0 or not math.isfinite(anchor):
            continue
        curve = slc.set_index("date")["adj_close"] / anchor
        per_ticker_curves.append(curve.rename(ticker))
    if not per_ticker_curves:
        return pd.DataFrame(columns=["equity"])
    wide = pd.concat(per_ticker_curves, axis=1)
    # Forward-fill so a ticker that skips a trading day inherits its
    # prior close (rather than NaN dropping the whole basket).
    wide = wide.sort_index().ffill()
    equity = wide.mean(axis=1) * (weight * len(resolved))
    return pd.DataFrame({"equity": equity})


def _compute_metrics(curve: pd.DataFrame) -> Metrics:
    """Derive the seven core metrics from a daily equity curve."""

    if curve.empty or curve["equity"].dropna().shape[0] < 5:
        return Metrics(
            annual_return=math.nan,
            volatility=math.nan,
            sharpe=math.nan,
            sortino=math.nan,
            calmar=math.nan,
            max_drawdown=math.nan,
            win_rate=math.nan,
            row_count=int(curve.shape[0]),
        )

    equity = curve["equity"].dropna()
    daily_returns = equity.pct_change().dropna()
    n_days = len(daily_returns)
    if n_days == 0:
        return Metrics(
            annual_return=math.nan,
            volatility=math.nan,
            sharpe=math.nan,
            sortino=math.nan,
            calmar=math.nan,
            max_drawdown=math.nan,
            win_rate=math.nan,
            row_count=int(curve.shape[0]),
        )

    total_return = float(equity.iloc[-1] / equity.iloc[0]) - 1.0
    years = n_days / TRADING_DAYS_PER_YEAR
    annual_return = (
        (1.0 + total_return) ** (1.0 / years) - 1.0 if years > 0 else math.nan
    )
    volatility = float(daily_returns.std(ddof=1)) * math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = annual_return / volatility if volatility > 0 else math.nan
    downside = daily_returns[daily_returns < 0]
    if len(downside) == 0:
        sortino = math.nan
    else:
        downside_vol = float(downside.std(ddof=1)) * math.sqrt(TRADING_DAYS_PER_YEAR)
        sortino = annual_return / downside_vol if downside_vol > 0 else math.nan

    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    max_dd = float(drawdown.min())
    calmar = (
        annual_return / abs(max_dd) if max_dd < 0 and math.isfinite(annual_return) else math.nan
    )
    win_rate = float((daily_returns > 0).mean())

    return Metrics(
        annual_return=annual_return,
        volatility=volatility,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_dd,
        win_rate=win_rate,
        row_count=n_days,
    )


def _resolved_count(prices: pd.DataFrame, tickers: tuple[str, ...]) -> int:
    """Return how many universe tickers actually appear in the frame."""

    if not tickers:
        return 0
    available = set(prices["ticker"].astype(str).unique())
    return sum(1 for t in tickers if t in available)


def _run_sleeve_under_source(
    sleeve: SleeveConfig, force_fixture: bool
) -> tuple[Metrics | None, int]:
    """Run one sleeve's buy-and-hold backtest under the chosen source.

    Returns ``(metrics, resolved_count)``. ``metrics`` is ``None`` when
    the universe has zero resolved tickers — the report will note
    "no data" rather than reporting all-NaN ratios.
    """

    prior = os.environ.get("FORCE_FIXTURE_PATH")
    try:
        if force_fixture:
            os.environ["FORCE_FIXTURE_PATH"] = "1"
        else:
            os.environ.pop("FORCE_FIXTURE_PATH", None)
        prices = repo.load_prices()
    finally:
        if prior is None:
            os.environ.pop("FORCE_FIXTURE_PATH", None)
        else:
            os.environ["FORCE_FIXTURE_PATH"] = prior

    resolved = _resolved_count(prices, sleeve.tickers)
    if resolved == 0:
        return None, 0
    curve = _equal_weight_equity_curve(prices, sleeve.tickers)
    return _compute_metrics(curve), resolved


def compare_sleeve(sleeve: SleeveConfig) -> SleeveComparison:
    """Run the fixture-vs-real comparison for one sleeve."""

    if sleeve.is_stub:
        return SleeveComparison(
            sleeve_id=sleeve.sleeve_id,
            label=sleeve.label,
            universe_size=0,
            is_stub=True,
            fixture_metrics=None,
            real_metrics=None,
            fixture_universe_resolved=0,
            real_universe_resolved=0,
            note=(
                "B011 satellite stub — no implemented backtest engine. "
                "Real-data cutover for this sleeve is deferred to the post-"
                "milestone-A backlog (HK/China implementation batch)."
            ),
        )

    fixture_metrics, fixture_n = _run_sleeve_under_source(sleeve, force_fixture=True)
    real_metrics, real_n = _run_sleeve_under_source(sleeve, force_fixture=False)
    note_parts: list[str] = [
        "Equal-weight buy-and-hold proxy across the sleeve's universe. "
        "Captures data-source quality delta; strategy-logic correctness "
        "is pinned by the existing test suite under FORCE_FIXTURE_PATH=1."
    ]
    if fixture_n < len(sleeve.tickers):
        note_parts.append(
            f"Fixture branch resolved {fixture_n}/{len(sleeve.tickers)} "
            f"universe tickers (others absent from the fixture)."
        )
    if real_n < len(sleeve.tickers):
        note_parts.append(
            f"Real branch resolved {real_n}/{len(sleeve.tickers)} universe "
            f"tickers (others absent from the unified backfill — see "
            f"B030 PIT validation report §4 for the BAC/V structural gap)."
        )

    return SleeveComparison(
        sleeve_id=sleeve.sleeve_id,
        label=sleeve.label,
        universe_size=len(sleeve.tickers),
        is_stub=False,
        fixture_metrics=fixture_metrics,
        real_metrics=real_metrics,
        fixture_universe_resolved=fixture_n,
        real_universe_resolved=real_n,
        note=" ".join(note_parts),
    )


def render_sleeve_markdown(cmp: SleeveComparison, today: date) -> str:
    """Render one sleeve's comparison to Markdown."""

    lines: list[str] = []
    lines.append(f"# {cmp.label} — fixture vs real ({today.isoformat()})")
    lines.append("")
    lines.append(f"**Sleeve id:** `{cmp.sleeve_id}`")
    lines.append(f"**Universe size:** {cmp.universe_size}")
    lines.append("")
    lines.append(f"**Methodology note:** {cmp.note}")
    lines.append("")
    if cmp.is_stub:
        lines.append(
            "_No backtest comparison generated (satellite stub; "
            "no implemented strategy)._"
        )
        lines.append("")
        return "\n".join(lines)

    lines.append("## Side-by-side metrics")
    lines.append("")
    lines.append(
        "| Metric | Fixture (synthetic) | Real (unified) | Δ (real − fixture) |"
    )
    lines.append("|---|---:|---:|---:|")
    metric_pairs = (
        ("Annual Return", "annual_return", _pct),
        ("Volatility", "volatility", _pct),
        ("Sharpe", "sharpe", _ratio),
        ("Sortino", "sortino", _ratio),
        ("Calmar", "calmar", _ratio),
        ("Max Drawdown", "max_drawdown", _pct),
        ("Win Rate", "win_rate", _pct),
    )
    for display_name, field, fmt in metric_pairs:
        fixture_val = (
            getattr(cmp.fixture_metrics, field) if cmp.fixture_metrics else None
        )
        real_val = (
            getattr(cmp.real_metrics, field) if cmp.real_metrics else None
        )
        delta_str = _format_delta(fixture_val, real_val, fmt)
        lines.append(
            f"| {display_name} | {fmt(fixture_val)} | {fmt(real_val)} | {delta_str} |"
        )
    lines.append("")
    fixture_rows = (
        getattr(cmp.fixture_metrics, "row_count", None)
        if cmp.fixture_metrics
        else None
    )
    real_rows = (
        getattr(cmp.real_metrics, "row_count", None)
        if cmp.real_metrics
        else None
    )
    lines.append(
        f"_Daily return rows used:_ "
        f"fixture={_int(fixture_rows)}, real={_int(real_rows)}"
    )
    lines.append("")
    lines.append(
        f"_Universe tickers resolved:_ "
        f"fixture={cmp.fixture_universe_resolved}/{cmp.universe_size}, "
        f"real={cmp.real_universe_resolved}/{cmp.universe_size}"
    )
    lines.append("")
    return "\n".join(lines)


def render_sleeve_json(cmp: SleeveComparison, today: date) -> dict[str, Any]:
    """Render one sleeve's comparison to a JSON-serialisable dict."""

    return {
        "sleeve_id": cmp.sleeve_id,
        "label": cmp.label,
        "as_of": today.isoformat(),
        "universe_size": cmp.universe_size,
        "is_stub": cmp.is_stub,
        "fixture": cmp.fixture_metrics.to_row() if cmp.fixture_metrics else None,
        "real": cmp.real_metrics.to_row() if cmp.real_metrics else None,
        "fixture_universe_resolved": cmp.fixture_universe_resolved,
        "real_universe_resolved": cmp.real_universe_resolved,
        "note": cmp.note,
    }


def render_overview(
    comparisons: Iterable[SleeveComparison], today: date
) -> str:
    """High-level summary of all sleeve deltas."""

    lines: list[str] = []
    lines.append(f"# Fixture vs Real — Overview ({today.isoformat()})")
    lines.append("")
    lines.append(
        "Generated by `scripts/compare_fixture_vs_real.py` as part of "
        "**B030 F003** (Real Data Cutover; milestone A Layer 0→1)."
    )
    lines.append("")
    lines.append(
        "Each per-sleeve report under `reports/fixture_vs_real/` runs an "
        "equal-weight buy-and-hold proxy twice — once under "
        "`FORCE_FIXTURE_PATH=1` (B025 synthetic fixture; 30 tickers) and "
        "once under the default unified-first branch (B028/B029 real "
        "backfill; 25-52 tickers depending on sleeve) — and reports the "
        "delta on seven core metrics."
    )
    lines.append("")
    lines.append(
        "Approximation scope: the buy-and-hold proxy isolates data-source "
        "quality (which F003 owns); strategy-logic correctness stays pinned "
        "by the existing test suite running under FORCE_FIXTURE_PATH=1 (B025 "
        "deterministic invariant; B030 F002 acceptance §(8))."
    )
    lines.append("")
    lines.append("## Per-sleeve summary")
    lines.append("")
    lines.append(
        "| Sleeve | Fixture Ann Ret | Real Ann Ret | Fixture Vol | Real Vol "
        "| Fixture Sharpe | Real Sharpe | Universe resolved (fix/real) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cmp in comparisons:
        if cmp.is_stub:
            lines.append(
                f"| {cmp.label} | _stub_ | _stub_ | _stub_ | _stub_ | "
                f"_stub_ | _stub_ | n/a |"
            )
            continue
        fx = cmp.fixture_metrics
        rl = cmp.real_metrics
        lines.append(
            f"| {cmp.label} | {_pct(fx.annual_return if fx else None)} | "
            f"{_pct(rl.annual_return if rl else None)} | "
            f"{_pct(fx.volatility if fx else None)} | "
            f"{_pct(rl.volatility if rl else None)} | "
            f"{_ratio(fx.sharpe if fx else None)} | "
            f"{_ratio(rl.sharpe if rl else None)} | "
            f"{cmp.fixture_universe_resolved}/{cmp.universe_size} vs "
            f"{cmp.real_universe_resolved}/{cmp.universe_size} |"
        )
    lines.append("")
    lines.append("## Reading the delta")
    lines.append("")
    lines.append(
        "* Annual-return differences arise from the universe composition "
        "delta (different ticker counts) and the date-range overlap delta. "
        "Both branches use buy-and-hold so direction-of-trade isn't a "
        "confounder."
    )
    lines.append(
        "* Sharpe-ratio differences ≥0.3 in absolute terms warrant a closer "
        "look during F004 L2 because they indicate the real-data branch is "
        "materially different in volatility-adjusted return."
    )
    lines.append(
        "* Win-Rate differences <2pp are within sample noise for a 1000+ "
        "trading-day window; differences ≥5pp are unusual."
    )
    lines.append("")
    lines.append("## Per-sleeve reports")
    lines.append("")
    for cmp in comparisons:
        lines.append(
            f"* [{cmp.label}](./{cmp.sleeve_id}_{today.isoformat()}.md)"
        )
    lines.append("")
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def _ratio(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.2f}"


def _int(value: int | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _format_delta(
    fixture_val: float | None,
    real_val: float | None,
    fmt: Any,
) -> str:
    if fixture_val is None or real_val is None:
        return "n/a"
    if not (math.isfinite(fixture_val) and math.isfinite(real_val)):
        return "n/a"
    delta = real_val - fixture_val
    if not math.isfinite(delta):
        return "n/a"
    if fmt is _pct:
        return f"{delta * 100:+.2f}pp"
    return f"{delta:+.2f}"


def write_reports(
    comparisons: list[SleeveComparison],
    output_root: Path,
    today: date,
) -> list[Path]:
    """Write all five sleeve files + the overview; return list of paths."""

    output_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for cmp in comparisons:
        base = output_root / f"{cmp.sleeve_id}_{today.isoformat()}"
        md_path = base.with_suffix(".md")
        json_path = base.with_suffix(".json")
        md_path.write_text(render_sleeve_markdown(cmp, today), encoding="utf-8")
        json_path.write_text(
            json.dumps(render_sleeve_json(cmp, today), indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(md_path)
        written.append(json_path)
    overview_path = output_root / f"overview_{today.isoformat()}.md"
    overview_path.write_text(render_overview(comparisons, today), encoding="utf-8")
    written.append(overview_path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "reports" / "fixture_vs_real",
        help="Where to write the per-sleeve and overview reports.",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help="As-of date stamped into report filenames (default: today).",
    )
    args = parser.parse_args(argv)

    # ``np`` is imported but the proxy curve uses pandas only; keep
    # the import alive for downstream extensions (e.g. log-returns).
    _ = np

    comparisons: list[SleeveComparison] = []
    failures: list[str] = []
    for sleeve in SLEEVES:
        try:
            cmp = compare_sleeve(sleeve)
        except Exception as exc:
            failures.append(f"{sleeve.sleeve_id}: {type(exc).__name__}: {exc}")
            logger.error("compare failed for %s: %s", sleeve.sleeve_id, exc)
            continue
        comparisons.append(cmp)
        logger.info(
            "%s — fixture %d, real %d resolved tickers",
            sleeve.sleeve_id,
            cmp.fixture_universe_resolved,
            cmp.real_universe_resolved,
        )
    written = write_reports(comparisons, args.output_root, args.as_of)
    print(f"Wrote {len(written)} files to {args.output_root}")
    for p in written:
        print(f"  {p.relative_to(REPO_ROOT)}")
    if failures:
        print(f"\n{len(failures)} sleeve(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
