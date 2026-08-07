"""Independently verify the B112 A/B artifact without project-code imports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

WINDOW_START = pd.Timestamp("2019-04-01")
WINDOW_END = pd.Timestamp("2026-07-31")
IS_FRACTION = 0.70
MA_WINDOW = 200


def _close(left: float | None, right: float | None, tolerance: float = 1e-10) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def _independent_deltas(cell: dict[str, Any], segment: str) -> dict[str, float]:
    v0 = cell["v0"]["segments"][segment]
    v1 = cell["v1"]["segments"][segment]
    return {
        "delta_max_drawdown_pp": (v1["max_drawdown"] - v0["max_drawdown"]) * 100,
        "delta_cagr_pp": (v1["annualized_return"] - v0["annualized_return"]) * 100,
        "delta_sharpe": v1["sharpe_ratio"] - v0["sharpe_ratio"],
    }


def _mechanical_verdict(cell: dict[str, Any], thresholds: dict[str, float]) -> str:
    full = _independent_deltas(cell, "full")
    oos = _independent_deltas(cell, "oos")
    passed = (
        full["delta_max_drawdown_pp"]
        >= thresholds["main_full_maxdd_improve_min_pp"]
        and oos["delta_max_drawdown_pp"]
        >= thresholds["main_oos_maxdd_improve_min_pp"]
        and full["delta_cagr_pp"] >= thresholds["secondary_delta_cagr_min_pp"]
        and full["delta_sharpe"] >= thresholds["secondary_delta_sharpe_min"]
    )
    return "GO" if passed else "NO-GO"


def _expected_gate_states(
    recorded: list[dict[str, Any]], trading_dates: pd.DatetimeIndex, index: pd.Series
) -> list[dict[str, Any]]:
    expected: list[dict[str, Any]] = []
    for state in recorded:
        month_start = pd.Timestamp(f"{state['month']}-01")
        prior = trading_dates[trading_dates < month_start]
        eval_date = prior[-1] if len(prior) else None
        item: dict[str, Any] = {
            "month": state["month"],
            "eval_date": None if eval_date is None else eval_date.date().isoformat(),
            "active": False,
            "index_close": None,
            "ma_value": None,
            "reason": "fail_open_no_series",
        }
        if eval_date is not None and eval_date in index.index:
            upto = index.loc[:eval_date]
            if len(upto) < MA_WINDOW:
                item["reason"] = "fail_open_insufficient_history"
            else:
                window = upto.iloc[-MA_WINDOW:]
                close = float(upto.iloc[-1])
                ma_value = float(window.mean())
                item.update(
                    active=close < ma_value,
                    index_close=close,
                    ma_value=ma_value,
                    reason="on" if close < ma_value else "off",
                )
        expected.append(item)
    return expected


def verify(args: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(args.artifact.read_text(encoding="utf-8"))
    price_frames = [pd.read_pickle(path) for path in args.prices]
    price_segment_observations = []
    for path, frame in zip(args.prices, price_frames, strict=True):
        dates = pd.to_datetime(frame["date"])
        price_segment_observations.append(
            {
                "path": str(path),
                "rows": int(len(frame)),
                "span": f"{dates.min().date()} → {dates.max().date()}",
            }
        )
    prices = pd.concat(price_frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.drop_duplicates(["date", "ticker"], keep="first")
    all_dates = pd.DatetimeIndex(pd.to_datetime(prices["date"]).drop_duplicates()).sort_values()
    window_dates = all_dates[(all_dates >= WINDOW_START) & (all_dates <= WINDOW_END)]
    expected_split = window_dates[int(len(window_dates) * IS_FRACTION)].date().isoformat()

    index_frame = pd.read_pickle(args.index)
    index = pd.Series(
        pd.to_numeric(index_frame["close"]).to_numpy(),
        index=pd.to_datetime(index_frame["date"]),
    ).sort_index()
    index = index[index > 0]

    metric_mismatches: list[dict[str, Any]] = []
    split_mismatches: list[dict[str, Any]] = []
    gate_mismatches: list[dict[str, Any]] = []
    verdicts: dict[str, str] = {}
    for key, cell in payload["comparisons"].items():
        verdicts[key] = _mechanical_verdict(cell, payload["criterion_thresholds"])
        for segment in ("full", "oos"):
            expected = _independent_deltas(cell, segment)
            recorded = cell["deltas"][segment]
            for metric, value in expected.items():
                if not _close(value, recorded[metric]):
                    metric_mismatches.append(
                        {"cell": key, "segment": segment, "metric": metric,
                         "expected": value, "recorded": recorded[metric]}
                    )
        for arm in ("v0", "v1"):
            if cell[arm]["split_date"] != expected_split:
                split_mismatches.append(
                    {"cell": key, "arm": arm, "expected": expected_split,
                     "recorded": cell[arm]["split_date"]}
                )

        recorded_states = cell["v1"]["gate_states"]
        expected_states = _expected_gate_states(recorded_states, all_dates, index)
        for recorded, expected in zip(recorded_states, expected_states, strict=True):
            scalar_match = all(
                recorded[field] == expected[field]
                for field in ("month", "eval_date", "active", "reason")
            )
            numeric_match = _close(recorded["index_close"], expected["index_close"]) and _close(
                recorded["ma_value"], expected["ma_value"]
            )
            if not scalar_match or not numeric_match:
                gate_mismatches.append(
                    {"cell": key, "month": recorded["month"],
                     "expected": expected, "recorded": recorded}
                )

    if args.universe is not None:
        universe = pd.read_csv(args.universe)
        universe_sizes = universe.groupby("as_of_date").size()
        universe_observation = {
            "universe_blocks": int(universe_sizes.size),
            "universe_size_min": int(universe_sizes.min()),
            "universe_size_max": int(universe_sizes.max()),
        }
    else:
        base_universe = pd.read_csv(args.universe_base)
        extended_universe = pd.read_pickle(args.universe_extended)
        base_sizes = base_universe.groupby("as_of_date").size()
        extended_sizes = extended_universe.groupby("as_of_date").size()
        universe_observation = {
            "base_universe_blocks": int(base_sizes.size),
            "base_universe_size_min": int(base_sizes.min()),
            "base_universe_size_max": int(base_sizes.max()),
            "extended_universe_blocks": int(extended_sizes.size),
            "extended_universe_size_min": int(extended_sizes.min()),
            "extended_universe_size_max": int(extended_sizes.max()),
        }
    coverage_key = next(
        (key for key in ("input_coverage", "coverage") if key in payload), None
    )
    coverage = payload.get(coverage_key, {}) if coverage_key is not None else {}
    price_coverage = coverage.get("prices", {})
    universe_coverage = coverage.get("universe", {})
    index_coverage = coverage.get("index", {})
    recorded_price_segments = price_coverage.get("segments", [])
    price_segments_match = len(recorded_price_segments) == len(price_segment_observations)
    if price_segments_match:
        for recorded, observed in zip(
            recorded_price_segments, price_segment_observations, strict=True
        ):
            if (
                Path(observed["path"]).stem not in recorded.get("name", "")
                or recorded.get("rows") != observed["rows"]
                or recorded.get("span") != observed["span"]
            ):
                price_segments_match = False
                break
    index_window_covered = int(window_dates.isin(index.index).sum())
    annual_turnover_present = all(
        any(
            key in cell[arm]
            for key in ("annual_turnover", "annualized_turnover")
        )
        for cell in payload["comparisons"].values()
        for arm in ("v0", "v1")
    )
    checks = {
        "metric_deltas_match": not metric_mismatches,
        "mechanical_split_matches": not split_mismatches,
        "gate_states_match_independent_ma200": not gate_mismatches,
        "h6_coverage_declared_in_artifact": coverage_key is not None,
        "h6_price_counts_match_inputs": (
            price_coverage.get("rows") == len(prices)
            and price_coverage.get("tickers") == prices["ticker"].nunique()
            and price_coverage.get("date_min") == prices["date"].min().date().isoformat()
            and price_coverage.get("date_max") == prices["date"].max().date().isoformat()
        ),
        "h6_price_splice_discloses_new_names": "prices_newnames" in price_coverage.get(
            "splice", ""
        ),
        "h6_price_segments_match_inputs": price_segments_match,
        "h6_universe_counts_match_inputs": (
            universe_coverage.get("n_blocks") == universe_observation["universe_blocks"]
            and universe_coverage.get("size_min") == universe_observation["universe_size_min"]
            and universe_coverage.get("size_max") == universe_observation["universe_size_max"]
        ),
        "h6_index_coverage_matches_trading_calendar": (
            index_coverage.get("window_trading_days_covered") == index_window_covered
            and index_coverage.get("window_trading_days_total") == len(window_dates)
        ),
        "annual_turnover_declared": annual_turnover_present,
    }
    return {
        "method": {
            "independence": "no imports from scripts.research or trade",
            "artifact": str(args.artifact),
        },
        "input_observations": {
            "window_trading_days": len(window_dates),
            "window_first_date": window_dates[0].date().isoformat(),
            "window_last_date": window_dates[-1].date().isoformat(),
            "mechanical_split_date": expected_split,
            "index_window_coverage": index_window_covered,
            "price_segments": price_segment_observations,
            **universe_observation,
        },
        "checks": checks,
        "mechanical_verdicts_from_delivered_numbers": verdicts,
        "metric_mismatches": metric_mismatches,
        "split_mismatches": split_mismatches,
        "gate_mismatches": gate_mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact", type=Path,
        default=Path("docs/research/B112-F001-defense-gate-ab.json"),
    )
    parser.add_argument(
        "--prices", type=Path, nargs="+",
        default=[Path("data/research/b070/b081_prices_cache.pkl"),
                 Path("data/research/b112/b112_prices_ext.pkl"),
                 Path("data/research/b112/prices_newnames.pkl")],
    )
    parser.add_argument(
        "--index", type=Path, default=Path("data/research/b112/b112_csi300.pkl")
    )
    parser.add_argument(
        "--universe", type=Path,
        default=Path("data/research/b112/cn_pit_universe_1500.csv"),
        help="single PIT universe CSV; use the legacy base/extended flags only for old artifacts",
    )
    parser.add_argument("--universe-base", type=Path, default=None)
    parser.add_argument(
        "--universe-extended", type=Path,
        default=None,
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if (args.universe_base is None) != (args.universe_extended is None):
        parser.error("--universe-base and --universe-extended must be supplied together")
    if args.universe_base is not None:
        args.universe = None
    result = verify(args)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
