#!/usr/bin/env python
"""B077 F001 §23 — A-share *smart-money* data-availability feasibility probe.

NOT product code. A spike tool answering the single hard prerequisite for the
whole B077 batch (spec §0 / §2 F001): **what can free akshare actually give us,
TODAY, for the three "smart-money" sources — and can each one support a backtest
of a follow-the-institutions strategy?**

    Source 1 — 北向持股 (Northbound holdings via Stock/HK Connect)
               per-stock: ``stock_hsgt_individual_em``  (持股数量占A股百分比 / 今日增持资金)
               aggregate: ``stock_hsgt_hist_em``        (当日成交净买额 daily net buy)
    Source 2 — 龙虎榜机构席位 (Dragon-Tiger institutional seats)
               inst stats: ``stock_lhb_jgmmtj_em``      (机构买入净额 / 买方机构数)
               broad LHB : ``stock_lhb_detail_em``      (龙虎榜净买额 + 上榜后N日 fwd-returns)
    Source 3 — 主力资金流超大单 (Main / super-large-order fund flow)
               per-stock: ``stock_individual_fund_flow``      (超大单净流入-净额)
               x-section: ``stock_individual_fund_flow_rank``  (whole-market coverage)

It measures, per source, the §23 *data reality* — **never assumed, only measured**:
fields (is there a usable 机构净买入 / 超大单净流入 / 北向持股变化 column?), timeliness
(daily? lagged?), **history depth** (how many years back = can we backtest?),
coverage / sparsity (full market? only 异动? Connect-only?), and stability (success
rate over a sample). It then emits a mechanical per-source verdict on whether the
source can support a backtest.

★ The 北向 2024.8 disclosure change is MEASURED, not assumed: the exchanges stopped
publishing per-stock Connect holdings in Aug-2024, so the per-stock series'
**latest date** (a freeze far behind today) and the aggregate net-buy column's
**latest non-null date** (when daily net-buy stopped being disclosed) both fall
out of real measurement — see ``judge_source``.

★ §23 host lesson (B062): eastmoney's *push* host (``push2his.eastmoney.com``, which
``stock_individual_fund_flow*`` routes through) SSL-/JSON-fails off the prod VM and
is unreliable ON it. So fund-flow reachability is an open question this probe
resolves by RUNNING — off-box it records the error; the real depth/coverage is
measured on the VM.

HARD BOUNDARY (spec §0 invariants): read-only public-disclosure databases only
(akshare). NEVER a broker SDK. research-only / no real money / no auto-order / no
production change. This module imports neither ``trade`` nor ``workbench_api`` — it
inlines the few akshare-frame helpers (mirroring
``workbench_api.symbols.akshare_frames``) so the spike is a single file that is
both root-importable (root pytest locks the pure parse + judge logic offline) and
trivially copy-portable to the VM ``/tmp`` for the §23 live run.

Usage::

    # local (北向 + 龙虎榜 reach the finance host; fund-flow push host SSL-fails)
    .venv/bin/python scripts/research/b077_smart_money_feasibility_probe.py \
        --out data/research/b077/f001_data_reality_local.json --label local

    # VM §23 live run (resolves fund-flow reachability on prod infra)
    scp scripts/research/b077_smart_money_feasibility_probe.py tripplezhou@<vm>:/tmp/
    /opt/workbench/.venv/bin/python /tmp/b077_smart_money_feasibility_probe.py \
        --out /tmp/b077_data_reality_vm.json --label vm
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
import traceback
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- #
# Real akshare column aliases (§23: discovered by live measurement 2026-06-25,
# not guessed). Resolution is exact-then-substring so an akshare header rename
# that keeps the keyword (e.g. "超大单净流入-净额" -> "超大单净流入") still matches.
# --------------------------------------------------------------------------- #
_DATE_ALIASES: tuple[str, ...] = (
    "持股日期",
    "上榜日期",
    "上榜日",
    "日期",
    "交易日",
    "trade_date",
    "date",
)
_CODE_ALIASES: tuple[str, ...] = ("代码", "code", "ticker")

# Source 1 — northbound per-stock (stock_hsgt_individual_em)
NB_NET_BUY_ALIASES: tuple[str, ...] = ("今日增持资金",)
NB_HOLD_PCT_ALIASES: tuple[str, ...] = ("持股数量占A股百分比",)
# Source 1 — northbound aggregate (stock_hsgt_hist_em): the 2024.8-cut net-buy col
NB_AGG_NET_BUY_ALIASES: tuple[str, ...] = ("当日成交净买额",)

# Source 2 — dragon-tiger institutional seats (stock_lhb_jgmmtj_em)
LHB_INST_NET_BUY_ALIASES: tuple[str, ...] = ("机构买入净额",)
LHB_INST_BUYERS_ALIASES: tuple[str, ...] = ("买方机构数",)
# Broad LHB (stock_lhb_detail_em) — built-in forward-return columns (F002 convenience)
LHB_FWD_RETURN_ALIASES: tuple[str, ...] = ("上榜后1日", "上榜后5日", "上榜后10日", "上榜后")

# Source 3 — main fund flow per-stock (stock_individual_fund_flow)
FF_SUPER_LARGE_ALIASES: tuple[str, ...] = ("超大单净流入-净额", "超大单净流入")
FF_MAIN_ALIASES: tuple[str, ...] = ("主力净流入-净额", "主力净流入")

# A "freeze" = the latest observation is this many days (or more) behind the run
# date. The 北向 per-stock feed froze 2024-08-16, so on any 2025+ run this trips.
FREEZE_LAG_DAYS = 120
# A backtest needs at least this much history to be worth building on.
MIN_BACKTEST_YEARS = 2.0

# A small known-liquid fallback sample (used when no B070 universe is supplied).
_FALLBACK_SAMPLE: tuple[str, ...] = (
    "600519.SH",
    "601318.SH",
    "600036.SH",
    "000858.SZ",
    "000333.SZ",
    "300750.SZ",
    "002594.SZ",
    "601012.SH",
    "600276.SH",
    "000001.SZ",
)


# --------------------------------------------------------------------------- #
# Inlined akshare-frame helpers (mirror workbench_api.symbols.akshare_frames;
# duplicated here only so this spike stays a single root-importable / VM-portable
# file with no workbench_api on the path). Best-effort: never raise on bad data.
# --------------------------------------------------------------------------- #
def coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def coerce_float(value: object) -> float | None:
    """Float or None — None for blanks AND pandas NaN (the post-2024.8 net-buy
    cells come back as ``float('nan')``; treating them as None is what lets
    :func:`latest_non_null_date` find the real disclosure cutoff)."""
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


def frame_records(
    module: Any, fn_name: str, **kwargs: Any
) -> tuple[list[dict[str, Any]], list[str]]:
    """``module.<fn_name>(**kwargs)`` -> ``(records, columns)``; ``([], [])`` on ANY
    failure (missing fn / network / unparseable frame) so the caller degrades
    honestly instead of raising. ``module`` is the lazily-imported akshare."""
    fn = getattr(module, fn_name, None)
    if fn is None:
        return [], []
    try:
        frame = fn(**kwargs)
    except Exception:  # noqa: BLE001 — best-effort reachability probe
        return [], []
    if frame is None:
        return [], []
    try:
        columns = [str(c) for c in frame.columns]
        records: list[dict[str, Any]] = frame.to_dict("records")
    except Exception:  # noqa: BLE001
        return [], []
    return records, columns


def resolve_column(columns: Sequence[str], aliases: Sequence[str]) -> str | None:
    """The actual column header matching one of ``aliases`` (exact first, then a
    substring containment), or None when no alias is present."""
    cols = [str(c) for c in columns]
    for alias in aliases:
        if alias in cols:
            return alias
    for alias in aliases:
        for col in cols:
            if alias in col:
                return col
    return None


def canonical_to_code_market(canonical: str) -> tuple[str, str]:
    """``"600519.SH"`` -> ``("600519", "sh")``; ``"000858.SZ"`` -> ``("000858", "sz")``.
    The bare 6-digit code + lowercase exchange is what the akshare smart-money
    endpoints expect (``stock_hsgt_individual_em`` wants the code; the fund-flow
    endpoint wants ``stock`` + ``market``)."""
    raw = canonical.strip().upper()
    if "." in raw:
        code, suffix = raw.split(".", 1)
    else:
        code, suffix = raw, ""
    market = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "")
    if not market:
        market = "sh" if code[:1] in {"6", "9"} else "sz"
    return code, market


# --------------------------------------------------------------------------- #
# Pure parse helpers (the unit-tested core — no network).
# --------------------------------------------------------------------------- #
def extract_dated_series(
    records: Sequence[dict[str, Any]],
    columns: Sequence[str],
    value_aliases: Sequence[str],
    date_aliases: Sequence[str] = _DATE_ALIASES,
) -> list[tuple[date, float]]:
    """Schema-discovering ``[(date, value)]`` extraction, best-effort + sorted.

    Resolves the date and value columns by alias, then yields one pair per row
    whose date AND value both parse (rows with a NaN/blank value are skipped, so
    the result is the *non-null* observations only). Returns ``[]`` if either
    column is absent."""
    date_col = resolve_column(columns, date_aliases)
    value_col = resolve_column(columns, value_aliases)
    if date_col is None or value_col is None:
        return []
    out: list[tuple[date, float]] = []
    for record in records:
        bar_date = coerce_date(record.get(date_col))
        value = coerce_float(record.get(value_col))
        if bar_date is not None and value is not None:
            out.append((bar_date, value))
    out.sort(key=lambda item: item[0])
    return out


def observed_dates(
    records: Sequence[dict[str, Any]],
    columns: Sequence[str],
    date_aliases: Sequence[str] = _DATE_ALIASES,
) -> list[date]:
    """Every parseable date in a frame's resolved date column (measured, not
    assumed — used to read the real event dates a sparse LHB window contains
    instead of stamping ``today``)."""
    date_col = resolve_column(columns, date_aliases)
    if date_col is None:
        return []
    return [d for record in records if (d := coerce_date(record.get(date_col))) is not None]


def series_span(series: Sequence[tuple[date, float]]) -> dict[str, Any]:
    """``{"earliest","latest","n_obs","years"}`` for a (date,value) series."""
    if not series:
        return {"earliest": None, "latest": None, "n_obs": 0, "years": 0.0}
    earliest = series[0][0]
    latest = series[-1][0]
    years = round((latest - earliest).days / 365.25, 2)
    return {
        "earliest": earliest.isoformat(),
        "latest": latest.isoformat(),
        "n_obs": len(series),
        "years": years,
    }


def latest_non_null_date(
    records: Sequence[dict[str, Any]],
    columns: Sequence[str],
    value_aliases: Sequence[str],
    date_aliases: Sequence[str] = _DATE_ALIASES,
) -> date | None:
    """Latest date at which ``value_aliases`` is non-null — the §23 disclosure
    cutoff detector. ``stock_hsgt_hist_em`` keeps emitting rows dated to *today*
    but with a NaN ``当日成交净买额`` after the 2024.8 cut, so this returns the last
    day daily northbound net-buy was actually disclosed (≠ the row index's max)."""
    series = extract_dated_series(records, columns, value_aliases, date_aliases)
    return series[-1][0] if series else None


def _lag_days(latest_iso: str | None, today: date) -> int | None:
    if latest_iso is None:
        return None
    latest = coerce_date(latest_iso)
    return None if latest is None else (today - latest).days


# --------------------------------------------------------------------------- #
# Probe primitives.
# --------------------------------------------------------------------------- #
def _err(stage: str, exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "stage": stage,
        "error_class": type(exc).__name__,
        "error": str(exc)[:300],
        "traceback_tail": traceback.format_exc().splitlines()[-2:],
    }


def _timed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.monotonic()
    out = fn(*args, **kwargs)
    return out, round(time.monotonic() - start, 2)


class _AkshareProbe:
    """Lazy-akshare base (mirrors the cn_*.py loader injection pattern)."""

    def __init__(self, akshare_module: Any | None = None) -> None:
        self._akshare = akshare_module

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:  # noqa: BLE001
            return None


class NorthboundHoldingProbe(_AkshareProbe):
    """北向持股 availability — per-stock holdings + aggregate net buy.

    The §23 2024.8 disclosure change is measured: the per-stock series' latest
    date (freeze) and the aggregate net-buy column's latest non-null date."""

    source = "northbound_hold"

    def fetch_individual(self, canonical: str) -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        # stock_hsgt_individual_em wants the BARE 6-digit code ("600519"), not the
        # canonical "600519.SH" — convert or akshare returns an empty frame.
        code, _market = canonical_to_code_market(canonical)
        return frame_records(akshare, "stock_hsgt_individual_em", symbol=code)

    def fetch_aggregate(self) -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        return frame_records(akshare, "stock_hsgt_hist_em", symbol="北向资金")

    def probe(self, sample: Sequence[str], today: date) -> dict[str, Any]:
        out: dict[str, Any] = {"source": self.source, "per_stock": [], "aggregate": {}}
        reachable = 0
        empty = 0
        errors = 0
        columns_seen: list[str] = []
        signal_found = False
        spans: list[dict[str, Any]] = []
        for canonical in sample:
            try:
                (records, columns), elapsed = _timed(self.fetch_individual, canonical)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                out["per_stock"].append({"ticker": canonical, **_err("individual", exc)})
                continue
            if not records:
                empty += 1
                out["per_stock"].append(
                    {"ticker": canonical, "ok": False, "rows": 0, "elapsed_s": elapsed}
                )
                continue
            reachable += 1
            columns_seen = columns
            if resolve_column(columns, NB_NET_BUY_ALIASES):
                signal_found = True
            series = extract_dated_series(records, columns, NB_HOLD_PCT_ALIASES)
            span = series_span(series)
            spans.append(span)
            out["per_stock"].append(
                {
                    "ticker": canonical,
                    "ok": True,
                    "rows": len(records),
                    "elapsed_s": elapsed,
                    "span": span,
                }
            )

        latest = max((s["latest"] for s in spans if s["latest"]), default=None)
        earliest = min((s["earliest"] for s in spans if s["earliest"]), default=None)
        # aggregate net-buy disclosure cutoff (the headline 2024.8 reality)
        agg = self._probe_aggregate(today)
        out["aggregate"] = agg
        attempted = len(sample)
        out["summary"] = {
            "reachable": reachable > 0,
            "signal_column_found": signal_found,
            "signal_columns": [a for a in NB_NET_BUY_ALIASES if resolve_column(columns_seen, [a])],
            "columns_seen": columns_seen,
            "coverage": "per_stock_connect",  # Connect-eligible names only (大盘 bias)
            "earliest_date": earliest,
            "latest_date": latest,
            "lag_days": _lag_days(latest, today),
            "success_rate": round(reachable / attempted, 3) if attempted else 0.0,
            "attempted": attempted,
            "empty": empty,
            "errors": errors,
            "agg_net_buy_last_disclosed": agg.get("net_buy_last_disclosed"),
        }
        return out

    def _probe_aggregate(self, today: date) -> dict[str, Any]:
        try:
            (records, columns), elapsed = _timed(self.fetch_aggregate)
        except Exception as exc:  # noqa: BLE001
            return _err("aggregate", exc)
        if not records:
            return {"ok": False, "rows": 0, "elapsed_s": elapsed}
        cutoff = latest_non_null_date(records, columns, NB_AGG_NET_BUY_ALIASES)
        index_dates = [
            d
            for d in (coerce_date(r.get(resolve_column(columns, _DATE_ALIASES))) for r in records)
            if d
        ]
        index_latest = max(index_dates, default=None)
        return {
            "ok": True,
            "rows": len(records),
            "elapsed_s": elapsed,
            "net_buy_column": resolve_column(columns, NB_AGG_NET_BUY_ALIASES),
            "row_index_latest": index_latest.isoformat() if index_latest else None,
            "net_buy_last_disclosed": cutoff.isoformat() if cutoff else None,
            "net_buy_disclosure_lag_days": _lag_days(cutoff.isoformat() if cutoff else None, today),
        }


class DragonTigerInstitutionalProbe(_AkshareProbe):
    """龙虎榜机构席位 — institutional seat net buy (``stock_lhb_jgmmtj_em``) + broad
    LHB events (``stock_lhb_detail_em``). Sparse (异动 only): each window is counted
    across the whole market to quantify sparsity, walking windows back to measure
    history depth."""

    source = "dragon_tiger_inst"

    def fetch_inst_stats(self, start: str, end: str) -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        return frame_records(akshare, "stock_lhb_jgmmtj_em", start_date=start, end_date=end)

    def fetch_detail(self, start: str, end: str) -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        return frame_records(akshare, "stock_lhb_detail_em", start_date=start, end_date=end)

    def probe(self, windows: Sequence[tuple[str, str]], today: date) -> dict[str, Any]:
        out: dict[str, Any] = {"source": self.source, "windows": []}
        reachable = 0
        signal_found = False
        columns_seen: list[str] = []
        event_dates: list[date] = []  # real 上榜日期 observed across all windows
        for start, end in windows:
            try:
                (records, columns), elapsed = _timed(self.fetch_inst_stats, start, end)
            except Exception as exc:  # noqa: BLE001
                out["windows"].append({"window": f"{start}..{end}", **_err("inst_stats", exc)})
                continue
            n_events = len(records)
            codes = (
                {str(r.get(resolve_column(columns, _CODE_ALIASES))) for r in records}
                if records
                else set()
            )
            has_signal = bool(resolve_column(columns, LHB_INST_NET_BUY_ALIASES))
            if n_events:
                reachable += 1
                columns_seen = columns
                event_dates.extend(observed_dates(records, columns))
                if has_signal:
                    signal_found = True
            out["windows"].append(
                {
                    "window": f"{start}..{end}",
                    "ok": n_events > 0,
                    "inst_events": n_events,
                    "distinct_codes": len(codes),
                    "inst_net_buy_col": resolve_column(columns, LHB_INST_NET_BUY_ALIASES),
                    "elapsed_s": elapsed,
                }
            )
        # Depth / recency from the REAL observed 上榜日期 (not a stamped today/0).
        earliest = min(event_dates).isoformat() if event_dates else None
        latest = max(event_dates).isoformat() if event_dates else None
        recent = out["windows"][-1] if out["windows"] else {}
        out["detail_reachability"] = self._probe_detail(windows)
        out["summary"] = {
            "reachable": reachable > 0,
            "signal_column_found": signal_found,
            "signal_columns": [
                c
                for c in (
                    resolve_column(columns_seen, LHB_INST_NET_BUY_ALIASES),
                    resolve_column(columns_seen, LHB_INST_BUYERS_ALIASES),
                )
                if c
            ],
            "columns_seen": columns_seen,
            "coverage": "sparse_event",  # only 异动 (limit-hit / big-move) names appear
            "earliest_date": earliest,
            "latest_date": latest,
            "lag_days": _lag_days(latest, today),
            "recent_events": recent.get("inst_events"),
            "broad_lhb_reachable": out["detail_reachability"].get("ok"),
            "broad_lhb_has_fwd_returns": out["detail_reachability"].get("has_fwd_returns"),
            "windows_reachable": reachable,
            "windows_tried": len(windows),
        }
        return out

    def _probe_detail(self, windows: Sequence[tuple[str, str]]) -> dict[str, Any]:
        """Reachability of the broad-LHB feed (``stock_lhb_detail_em``) on the most
        recent window — confirms the 龙虎榜净买额 + 上榜后N日 forward-return columns the
        docstring advertises actually exist (an F002 convenience, measured here)."""
        if not windows:
            return {"ok": False, "reason": "no windows"}
        start, end = windows[-1]
        try:
            (records, columns), elapsed = _timed(self.fetch_detail, start, end)
        except Exception as exc:  # noqa: BLE001
            return _err("detail", exc)
        return {
            "ok": bool(records),
            "window": f"{start}..{end}",
            "rows": len(records),
            "has_fwd_returns": bool(resolve_column(columns, LHB_FWD_RETURN_ALIASES)),
            "fwd_return_col": resolve_column(columns, LHB_FWD_RETURN_ALIASES),
            "elapsed_s": elapsed,
        }


class MainFundFlowProbe(_AkshareProbe):
    """主力资金流超大单 — per-stock daily history (``stock_individual_fund_flow``) +
    whole-market cross-section (``stock_individual_fund_flow_rank``). Routes through
    eastmoney's push host (§23 B062: SSL-fails off-box, unreliable on the VM), so
    off-box the probe records the error and reachability is resolved on the VM."""

    source = "main_fund_flow"

    def fetch_individual(self, code: str, market: str) -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        return frame_records(akshare, "stock_individual_fund_flow", stock=code, market=market)

    def fetch_rank(self, indicator: str = "今日") -> tuple[list[dict[str, Any]], list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return [], []
        return frame_records(akshare, "stock_individual_fund_flow_rank", indicator=indicator)

    def probe(self, sample: Sequence[str], today: date) -> dict[str, Any]:
        out: dict[str, Any] = {"source": self.source, "per_stock": []}
        reachable = 0
        empty = 0
        errors = 0
        columns_seen: list[str] = []
        signal_found = False
        spans: list[dict[str, Any]] = []
        for canonical in sample:
            code, market = canonical_to_code_market(canonical)
            try:
                (records, columns), elapsed = _timed(self.fetch_individual, code, market)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                out["per_stock"].append({"ticker": canonical, **_err("fund_flow", exc)})
                continue
            if not records:
                empty += 1
                out["per_stock"].append(
                    {"ticker": canonical, "ok": False, "rows": 0, "elapsed_s": elapsed}
                )
                continue
            reachable += 1
            columns_seen = columns
            if resolve_column(columns, FF_SUPER_LARGE_ALIASES):
                signal_found = True
            series = extract_dated_series(records, columns, FF_SUPER_LARGE_ALIASES)
            span = series_span(series)
            spans.append(span)
            out["per_stock"].append(
                {
                    "ticker": canonical,
                    "ok": True,
                    "rows": len(records),
                    "elapsed_s": elapsed,
                    "span": span,
                }
            )

        rank = self._probe_rank()
        out["cross_section"] = rank
        latest = max((s["latest"] for s in spans if s["latest"]), default=None)
        earliest = min((s["earliest"] for s in spans if s["earliest"]), default=None)
        attempted = len(sample)
        out["summary"] = {
            "reachable": reachable > 0,
            "signal_column_found": signal_found,
            "signal_columns": [
                a
                for a in (*FF_SUPER_LARGE_ALIASES, *FF_MAIN_ALIASES)
                if resolve_column(columns_seen, [a])
            ],
            "columns_seen": columns_seen,
            # per-stock ADDRESSABLE for every A-share (no Connect/异动 gate). The
            # whole-market bulk-snapshot endpoint (rank) is a separate, best-effort
            # corroboration — its breadth is reported below, measured not assumed.
            "coverage": "full_market",
            "cross_section_breadth": rank.get("rows"),
            "cross_section_snapshot_ok": bool(rank.get("ok")),
            "earliest_date": earliest,
            "latest_date": latest,
            "lag_days": _lag_days(latest, today),
            "success_rate": round(reachable / attempted, 3) if attempted else 0.0,
            "attempted": attempted,
            "empty": empty,
            "errors": errors,
        }
        return out

    def _probe_rank(self) -> dict[str, Any]:
        try:
            (records, columns), elapsed = _timed(self.fetch_rank, "今日")
        except Exception as exc:  # noqa: BLE001
            return _err("rank", exc)
        return {
            "ok": bool(records),
            "rows": len(records),
            "columns": columns[:12],
            "elapsed_s": elapsed,
        }


# --------------------------------------------------------------------------- #
# Mechanical per-source verdict (spec §0: "明确每源能不能支撑回测").
# --------------------------------------------------------------------------- #
def judge_source(summary: dict[str, Any], today: date) -> dict[str, Any]:
    """Map a source's measured reality to a backtest-supportability verdict.

    Verdicts (all §23-honest, none claim tradeable edge — that is F002+):
      * ``UNREACHABLE``          — source did not answer (off-host / dead endpoint).
      * ``NO_SIGNAL_COLUMN``     — reachable but no usable smart-money column.
      * ``BACKTEST_ONLY_FROZEN`` — rich history but the feed is frozen/stale
                                   (no live data) → can backtest the past era,
                                   cannot drive a *live* follow strategy on free data.
      * ``USABLE_SPARSE``        — live + signal, but sparse coverage (only a subset
                                   of names each day).
      * ``USABLE_FULL``          — live + signal + broad (per-stock addressable) coverage.
    ``can_support_backtest`` is the **measured-depth** gate: True only when the
    observed history reaches ``MIN_BACKTEST_YEARS`` (so a live-but-shallow source
    like the ~0.5y fund flow reads False — live yet too shallow to backtest), and
    True for ``BACKTEST_ONLY_FROZEN`` (deep history exists up to the freeze).
    ``live_tradeable`` is the independent gate (current data flowing) that
    ``BACKTEST_ONLY_FROZEN`` fails and the USABLE verdicts pass."""
    reachable = bool(summary.get("reachable"))
    has_signal = bool(summary.get("signal_column_found"))
    lag = summary.get("lag_days")
    coverage = summary.get("coverage", "")
    years = _years_from_summary(summary)

    if not reachable:
        agg_cut = summary.get("agg_net_buy_last_disclosed")
        agg_note = (
            f" (Aggregate net-buy still readable but last disclosed {agg_cut} — the "
            f"2024.8 northbound disclosure cut; the per-stock holdings feed returns "
            f"no rows here.)"
            if agg_cut
            else ""
        )
        return _verdict(
            "UNREACHABLE",
            False,
            False,
            "Per-stock endpoint returned no rows on this run (dead / empty endpoint, "
            "or an eastmoney push-host SSL/JSON failure)." + agg_note,
        )
    if not has_signal:
        return _verdict(
            "NO_SIGNAL_COLUMN",
            False,
            False,
            "Reachable but no usable smart-money column (机构净买入 / "
            "超大单净流入 / 北向持股变化) present.",
        )

    frozen = isinstance(lag, int) and lag >= FREEZE_LAG_DAYS
    enough_history = years is None or years >= MIN_BACKTEST_YEARS
    if frozen:
        return _verdict(
            "BACKTEST_ONLY_FROZEN",
            True,
            False,
            f"Signal present with history but the feed is frozen "
            f"(latest obs {summary.get('latest_date')}, {lag}d stale ≥ "
            f"{FREEZE_LAG_DAYS}d) — backtestable on the historical era, NOT live-"
            f"tradeable on free data. Matches the 北向 2024.8 disclosure cut.",
            extra={"history_years": years},
        )
    verdict = "USABLE_SPARSE" if coverage == "sparse_event" else "USABLE_FULL"
    # can_support_backtest is the DEPTH gate: a sub-MIN_BACKTEST_YEARS feed is live
    # but too shallow to backtest on, so the structured flag must say so (not only
    # the prose). Live-tradeable (current data flowing) is independently True here.
    shallow = (
        ""
        if enough_history
        else (
            f" (shallow history ~{years}y < {MIN_BACKTEST_YEARS}y — live but too shallow "
            f"for a backtest, so can_support_backtest=False)"
        )
    )
    # "broad" coverage means per-stock addressable for any A-share. Qualify it when
    # the whole-market bulk-snapshot probe (rank) did not answer this run.
    breadth_note = ""
    if coverage == "full_market" and summary.get("cross_section_snapshot_ok") is False:
        breadth_note = (
            " (per-stock addressable; bulk cross-section snapshot endpoint "
            "unreachable this run — breadth confirmed per-stock, not by snapshot)"
        )
    reason = (
        f"Live signal ({summary.get('latest_date') or 'recent'}, lag {lag}d) with "
        f"{'sparse 异动-only' if coverage == 'sparse_event' else 'broad'} coverage"
        + breadth_note
        + shallow
        + ". First-look only; tradeable edge is F002+, never claimed here."
    )
    return _verdict(verdict, enough_history, True, reason, extra={"history_years": years})


def _years_from_summary(summary: dict[str, Any]) -> float | None:
    earliest = coerce_date(summary.get("earliest_date"))
    latest = coerce_date(summary.get("latest_date"))
    if earliest is None or latest is None:
        return None
    return round((latest - earliest).days / 365.25, 2)


def _verdict(
    verdict: str,
    can_support_backtest: bool,
    live_tradeable: bool,
    reason: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "verdict": verdict,
        "can_support_backtest": can_support_backtest,
        "live_tradeable": live_tradeable,
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


# --------------------------------------------------------------------------- #
# Orchestrator.
# --------------------------------------------------------------------------- #
def _load_sample(universe_csv: str | None, sample_n: int) -> list[str]:
    """Draw the per-stock sample from a B070 universe CSV (deterministic head of
    distinct tickers) or fall back to the curated liquid list."""
    if not universe_csv:
        return list(_FALLBACK_SAMPLE[:sample_n])
    import csv
    from pathlib import Path

    path = Path(universe_csv)
    if not path.is_file():
        return list(_FALLBACK_SAMPLE[:sample_n])
    seen: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = (row.get("ticker") or "").strip()
            if ticker and ticker not in seen:
                seen.append(ticker)
            if len(seen) >= sample_n:
                break
    return seen or list(_FALLBACK_SAMPLE[:sample_n])


def _lhb_windows(today: date) -> list[tuple[str, str]]:
    """Month-long LHB windows walking back from ~6y ago to last month (oldest
    first) so depth + recency + sparsity are all measured."""
    anchors = (72, 36, 12, 1)  # months back: depth probe ladder
    windows: list[tuple[str, str]] = []
    for months in sorted(anchors, reverse=True):
        end = today - timedelta(days=30 * (months - 1) if months > 1 else 7)
        start = end - timedelta(days=29)
        windows.append((start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
    return windows


def run_probe(
    *,
    sample: Sequence[str],
    today: date,
    akshare_module: Any | None = None,
) -> dict[str, Any]:
    """Run all three source probes + judge each (injectable akshare for tests)."""
    nb = NorthboundHoldingProbe(akshare_module).probe(sample, today)
    dt = DragonTigerInstitutionalProbe(akshare_module).probe(_lhb_windows(today), today)
    ff = MainFundFlowProbe(akshare_module).probe(sample, today)
    sources = {"northbound_hold": nb, "dragon_tiger_inst": dt, "main_fund_flow": ff}
    verdicts = {name: judge_source(src["summary"], today) for name, src in sources.items()}
    return {"sources": sources, "verdicts": verdicts}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="B077 F001 §23 smart-money data-availability probe"
    )
    parser.add_argument("--out", type=str, default=None, help="also write JSON here")
    parser.add_argument("--label", type=str, default="local", help="run label (env)")
    parser.add_argument("--sample", type=int, default=8, help="per-stock sample size")
    parser.add_argument(
        "--universe", type=str, default=None, help="B070 universe CSV to sample from"
    )
    parser.add_argument("--today", type=str, default=None, help="override run date (YYYY-MM-DD)")
    cli = parser.parse_args(argv)

    today = coerce_date(cli.today) or date.today()
    sample = _load_sample(cli.universe, cli.sample)

    result = run_probe(sample=sample, today=today)
    doc = {
        "probe": "b077_smart_money_data_reality",
        "run_label": cli.label,
        "run_date": today.isoformat(),
        "sample": list(sample),
        **result,
        "honesty": (
            "§23 measured-not-assumed; first-look data-availability only — NO "
            "tradeable edge claimed (that is F002+). research-only / no-broker / "
            "no real money / read-only public disclosure."
        ),
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2, default=str)
    print(text)
    if cli.out:
        from pathlib import Path

        out_path = Path(cli.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
