#!/usr/bin/env python
"""B060 F002 — A-share data source P0 feasibility probe (spike tool, NOT product code).

Answers the single go/no-go question of the B060 spike: **can an overseas
production VM reliably fetch usable A-share EOD data?** AkShare (东财 history —
a large commercial site, most likely reachable from abroad) is tried first;
baostock is the cross-check / fallback.

This is a SPIKE PROBE, not product code:

* It lives under ``scripts/test/`` (a Codex-writable area), is excluded from
  CI collection (``testpaths = ["tests"]``) and is imported by no product
  module.
* It imports ``akshare`` / ``baostock`` / ``pandas`` **lazily** and degrades
  gracefully when a library is absent, so the repo never takes a hard
  dependency on them. They are installed ad-hoc in a temporary venv on the VM
  by Codex — deliberately **NOT** added to ``pyproject.toml`` (that would
  violate dependency hygiene §12.8 and is out of scope for a P0 spike).
* HARD BOUNDARY (spec §3 / path-doc §8): **databases only** (AkShare /
  baostock). It never imports a broker SDK (futu / tiger / ib / alpaca —
  safety 禁列). It additionally self-audits the installed distribution set and
  marks the dependency-hygiene metric FAIL if any forbidden broker SDK is
  present.

Metrics collected (path-doc §8.3): connectivity (repeat-pull success rate +
p50/p95 latency + timeout/geo-block classification), coverage (5 representative
symbols), depth (history years), quality (OHLCV completeness + weekday gaps +
front-adjust availability), cross-source agreement (AkShare vs baostock same-day
close), scale (per-symbol fetch time + extrapolated N≈300 daily-update),
dependency hygiene, and currency/units sanity.

Output: a single structured JSON document on stdout (and optionally ``--out``)
so Codex can fold the measured values straight into the feasibility report.
Multi-timeslot coverage (path-doc §8.5) is achieved by Codex running this probe
several times across a day with different ``--label`` values and aggregating;
each run stamps ``run_label`` + ``run_started_at``.

Usage::

    # full probe (5 representative symbols, connectivity N=50)
    python scripts/test/ashare_p0_probe.py --out ashare_p0_afternoon.json --label cn-afternoon

    # quick smoke (fewer pulls, one symbol) — local API-shape sanity
    python scripts/test/ashare_p0_probe.py --connectivity-pulls 3 --symbols 600519.SH

Exit codes:

* ``0`` — the probe ran to completion. **A NO-GO verdict is still exit 0**: a
  reachability spike that honestly reports "cannot reach" has succeeded.
* ``2`` — CLI / usage error only.

The probe NEVER raises on a provider error; every failure is captured as a
measured datapoint (that is the entire point of a reachability spike).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Representative universe (path-doc §8.2): main boards + ChiNext + STAR + index.
@dataclass(frozen=True)
class SymbolSpec:
    """How to address one symbol in each provider's API."""

    canonical: str  # e.g. "600519.SH"
    kind: str  # "stock" | "index"
    ak_code: str  # AkShare 6-digit code (no suffix)
    bs_code: str  # baostock "sh.600519" / "sz.000001"
    label: str  # human board label


_DEFAULT_SYMBOLS: tuple[SymbolSpec, ...] = (
    SymbolSpec("600519.SH", "stock", "600519", "sh.600519", "沪主板·茅台"),
    SymbolSpec("000001.SZ", "stock", "000001", "sz.000001", "深主板·平安银行"),
    SymbolSpec("300750.SZ", "stock", "300750", "sz.300750", "创业板·宁德时代"),
    SymbolSpec("688981.SH", "stock", "688981", "sh.688981", "科创板·中芯国际"),
    SymbolSpec("000300", "index", "000300", "sh.000300", "沪深300指数"),
)

# Broker SDK names forbidden by the safety boundary. Mirrors
# workbench/frontend/tests/safety/no-broker-sdk-imports.spec.ts, mapped to the
# Python packaging ecosystem. Two forms are checked separately:
#   * distribution-name fragments (substring match on installed pip packages)
#   * top-level import roots (EXACT match on the first dotted segment of a
#     loaded module — substring matching here would false-positive on stdlib
#     such as ``__future__`` which contains "futu").
_FORBIDDEN_DIST_FRAGMENTS: tuple[str, ...] = (
    "futu",  # futu-api
    "tiger",  # tigeropen / tiger-securities
    "ib-insync",
    "ib_insync",
    "ibapi",
    "alpaca",  # alpaca-trade-api / alpaca-py
)
_FORBIDDEN_IMPORT_ROOTS: frozenset[str] = frozenset(
    {"futu", "tigeropen", "ib_insync", "ibapi", "alpaca", "alpaca_trade_api"}
)

# Connectivity uses a short recent window so latency reflects the network, not
# payload size. AkShare wants YYYYMMDD strings.
_CONNECTIVITY_WINDOW_DAYS = 30


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolated percentile (pct in [0, 1]); None for empty input."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def _classify_error(exc: BaseException) -> str:
    """Bucket a provider failure for the connectivity verdict."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timed out" in msg or "timeout" in msg:
        return "timeout"
    geo_markers = ("connection", "refused", "ssl", "max retries", "403", "forbidden", "unreachable")
    if any(marker in name or marker in msg for marker in geo_markers):
        return "connection/geo-suspect"
    if "empty" in msg or "no data" in msg:
        return "empty-result"
    return "other"


def _import_optional(module_name: str) -> ModuleType | None:
    """Import a third-party module lazily, returning None when unavailable."""
    try:
        return importlib.import_module(module_name)
    except Exception:  # noqa: BLE001 — a probe must never crash on import
        return None


def _ymd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# OHLCV normalisation (AkShare Chinese cols + baostock English cols → standard)
# --------------------------------------------------------------------------- #

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("日期", "date", "trade_date"),
    "open": ("开盘", "open"),
    "high": ("最高", "high"),
    "low": ("最低", "low"),
    "close": ("收盘", "close"),
    "volume": ("成交量", "volume", "vol"),
}


def _normalize_columns(columns: list[str]) -> dict[str, str | None]:
    """Map a raw column list to the standard OHLCV field names."""
    lowered = {c.lower(): c for c in columns}
    resolved: dict[str, str | None] = {}
    for std, aliases in _COLUMN_ALIASES.items():
        match: str | None = None
        for alias in aliases:
            if alias in columns:
                match = alias
                break
            if alias.lower() in lowered:
                match = lowered[alias.lower()]
                break
        resolved[std] = match
    return resolved


# --------------------------------------------------------------------------- #
# AkShare access
# --------------------------------------------------------------------------- #


def _akshare_history(
    ak: ModuleType,
    spec: SymbolSpec,
    start: str,
    end: str,
    adjust: str,
) -> Any:
    """Fetch a daily-bar DataFrame for one symbol from AkShare. Raises on error."""
    if spec.kind == "index":
        # index_zh_a_hist is the modern eastmoney index endpoint; fall back to
        # the legacy stock_zh_index_daily if the build lacks it.
        if hasattr(ak, "index_zh_a_hist"):
            return ak.index_zh_a_hist(
                symbol=spec.ak_code, period="daily", start_date=start, end_date=end
            )
        return ak.stock_zh_index_daily(symbol=f"sh{spec.ak_code}")
    return ak.stock_zh_a_hist(
        symbol=spec.ak_code,
        period="daily",
        start_date=start,
        end_date=end,
        adjust=adjust,
    )


# --------------------------------------------------------------------------- #
# baostock access
# --------------------------------------------------------------------------- #


def _baostock_history(
    bs: ModuleType,
    spec: SymbolSpec,
    start: str,
    end: str,
    adjustflag: str,
) -> list[dict[str, str]]:
    """Fetch daily bars for one symbol from baostock as a list of row dicts."""
    fields = "date,open,high,low,close,volume"
    rs = bs.query_history_k_data_plus(
        spec.bs_code,
        fields,
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag=adjustflag,
    )
    if getattr(rs, "error_code", "0") != "0":
        raise RuntimeError(f"baostock error_code={rs.error_code} msg={rs.error_msg}")
    rows: list[dict[str, str]] = []
    columns = list(rs.fields)
    while rs.next():
        rows.append(dict(zip(columns, rs.get_row_data(), strict=False)))
    return rows


# --------------------------------------------------------------------------- #
# Metric: connectivity
# --------------------------------------------------------------------------- #


@dataclass
class ConnectivityResult:
    provider: str
    symbol: str
    pulls: int
    successes: int
    success_rate: float | None
    timeout_rate: float | None
    latency_p50_s: float | None
    latency_p95_s: float | None
    error_breakdown: dict[str, int] = field(default_factory=dict)
    sample_errors: list[str] = field(default_factory=list)


def _connectivity_akshare(
    ak: ModuleType, spec: SymbolSpec, pulls: int
) -> ConnectivityResult:
    end = _now_utc()
    start_ymd = _ymd(end - timedelta(days=_CONNECTIVITY_WINDOW_DAYS))
    end_ymd = _ymd(end)
    latencies: list[float] = []
    errors: dict[str, int] = {}
    samples: list[str] = []
    successes = 0
    for _ in range(pulls):
        began = time.perf_counter()
        try:
            df = _akshare_history(ak, spec, start_ymd, end_ymd, adjust="qfq")
            elapsed = time.perf_counter() - began
            if df is None or len(df) == 0:
                raise RuntimeError("empty result")
            successes += 1
            latencies.append(elapsed)
        except Exception as exc:  # noqa: BLE001 — capture, never crash
            bucket = _classify_error(exc)
            errors[bucket] = errors.get(bucket, 0) + 1
            if len(samples) < 5:
                samples.append(f"{type(exc).__name__}: {exc}"[:200])
    timeouts = errors.get("timeout", 0)
    return ConnectivityResult(
        provider="akshare",
        symbol=spec.canonical,
        pulls=pulls,
        successes=successes,
        success_rate=successes / pulls if pulls else None,
        timeout_rate=timeouts / pulls if pulls else None,
        latency_p50_s=_percentile(latencies, 0.50),
        latency_p95_s=_percentile(latencies, 0.95),
        error_breakdown=errors,
        sample_errors=samples,
    )


# --------------------------------------------------------------------------- #
# Metric: coverage + depth + quality (per symbol, full history)
# --------------------------------------------------------------------------- #


@dataclass
class SymbolQuality:
    canonical: str
    label: str
    provider: str
    fetched: bool
    rows: int
    first_date: str | None
    last_date: str | None
    history_years: float | None
    fetch_seconds: float | None
    missing_ohlcv_fields: list[str]
    weekday_gap_count: int | None
    max_gap_days: int | None
    adjust_available: bool | None
    sample_close: float | None
    sample_volume: float | None
    error: str | None


def _years_between(first: str | None, last: str | None) -> float | None:
    if not first or not last:
        return None
    fmt_candidates = ("%Y-%m-%d", "%Y%m%d")
    parsed: list[datetime] = []
    for value in (first, last):
        dt: datetime | None = None
        for fmt in fmt_candidates:
            try:
                dt = datetime.strptime(value[:10], fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
        parsed.append(dt)
    return round((parsed[1] - parsed[0]).days / 365.25, 2)


def _weekday_gaps(dates: list[str]) -> tuple[int | None, int | None]:
    """Count weekday-to-weekday gaps > 1 business day (noise incl CN holidays)."""
    parsed: list[datetime] = []
    for value in dates:
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                parsed.append(datetime.strptime(value[:10], fmt))
                break
            except ValueError:
                continue
    if len(parsed) < 2:
        return None, None
    parsed.sort()
    gap_count = 0
    max_gap = 0
    for prev, cur in zip(parsed, parsed[1:], strict=False):
        delta = (cur - prev).days
        max_gap = max(max_gap, delta)
        # A normal day-to-day step is 1 (or 3 across a weekend). Anything wider
        # is a suspected non-holiday gap to be eyeballed in the report.
        if delta > 4:
            gap_count += 1
    return gap_count, max_gap


def _quality_from_akshare(
    ak: ModuleType, spec: SymbolSpec, start: str, end: str
) -> SymbolQuality:
    began = time.perf_counter()
    try:
        df = _akshare_history(ak, spec, start, end, adjust="qfq")
        elapsed = time.perf_counter() - began
    except Exception as exc:  # noqa: BLE001
        return SymbolQuality(
            canonical=spec.canonical,
            label=spec.label,
            provider="akshare",
            fetched=False,
            rows=0,
            first_date=None,
            last_date=None,
            history_years=None,
            fetch_seconds=round(time.perf_counter() - began, 3),
            missing_ohlcv_fields=[],
            weekday_gap_count=None,
            max_gap_days=None,
            adjust_available=None,
            sample_close=None,
            sample_volume=None,
            error=f"{type(exc).__name__}: {exc}"[:200],
        )

    columns = [str(c) for c in df.columns]
    resolved = _normalize_columns(columns)
    missing = [std for std, col in resolved.items() if col is None]
    date_col = resolved["date"]
    close_col = resolved["close"]
    vol_col = resolved["volume"]
    dates = [str(v) for v in df[date_col].tolist()] if date_col else []
    first_date = dates[0] if dates else None
    last_date = dates[-1] if dates else None
    gap_count, max_gap = _weekday_gaps(dates) if dates else (None, None)

    sample_close: float | None = None
    sample_volume: float | None = None
    try:
        if close_col and len(df) > 0:
            sample_close = float(df[close_col].iloc[-1])
        if vol_col and len(df) > 0:
            sample_volume = float(df[vol_col].iloc[-1])
    except Exception:  # noqa: BLE001 — sampling is best-effort
        pass

    adjust_available = _adjust_available_akshare(ak, spec, start, end)

    return SymbolQuality(
        canonical=spec.canonical,
        label=spec.label,
        provider="akshare",
        fetched=True,
        rows=int(len(df)),
        first_date=first_date,
        last_date=last_date,
        history_years=_years_between(first_date, last_date),
        fetch_seconds=round(elapsed, 3),
        missing_ohlcv_fields=missing,
        weekday_gap_count=gap_count,
        max_gap_days=max_gap,
        adjust_available=adjust_available,
        sample_close=sample_close,
        sample_volume=sample_volume,
        error=None,
    )


def _adjust_available_akshare(
    ak: ModuleType, spec: SymbolSpec, start: str, end: str
) -> bool | None:
    """Front-adjust (前复权) availability: qfq series differs from raw series."""
    if spec.kind == "index":
        return None  # indices are not dividend-adjusted
    try:
        qfq = _akshare_history(ak, spec, start, end, adjust="qfq")
        raw = _akshare_history(ak, spec, start, end, adjust="")
    except Exception:  # noqa: BLE001
        return None
    q_cols = _normalize_columns([str(c) for c in qfq.columns])
    r_cols = _normalize_columns([str(c) for c in raw.columns])
    if not q_cols["close"] or not r_cols["close"]:
        return None
    try:
        q_first = float(qfq[q_cols["close"]].iloc[0])
        r_first = float(raw[r_cols["close"]].iloc[0])
    except Exception:  # noqa: BLE001
        return None
    # For a stock with any historical dividend/split, the earliest front-adjusted
    # close differs from the raw close. Equal across full history => no adjust.
    return abs(q_first - r_first) > 1e-6


# --------------------------------------------------------------------------- #
# Metric: cross-source agreement (AkShare vs baostock, same-day close)
# --------------------------------------------------------------------------- #


@dataclass
class CrossSourceResult:
    canonical: str
    overlapping_days: int
    max_abs_pct_dev: float | None
    mean_abs_pct_dev: float | None
    error: str | None


def _cross_source(
    ak: ModuleType,
    bs: ModuleType,
    spec: SymbolSpec,
    start: str,
    end: str,
) -> CrossSourceResult:
    try:
        df = _akshare_history(ak, spec, start, end, adjust="qfq")
        ak_cols = _normalize_columns([str(c) for c in df.columns])
        ak_dates = df[ak_cols["date"]].tolist()
        ak_closes = df[ak_cols["close"]].tolist()
        ak_close = {
            str(d)[:10].replace("-", ""): float(c)
            for d, c in zip(ak_dates, ak_closes, strict=False)
        }
        # baostock wants YYYY-MM-DD; adjustflag 2 = 前复权 (matches AkShare qfq).
        bs_start = f"{start[:4]}-{start[4:6]}-{start[6:]}"
        bs_end = f"{end[:4]}-{end[4:6]}-{end[6:]}"
        bs_rows = _baostock_history(bs, spec, bs_start, bs_end, "2")
        deviations: list[float] = []
        for row in bs_rows:
            key = row.get("date", "").replace("-", "")
            close_str = row.get("close", "")
            if not key or not close_str:
                continue
            try:
                bs_close = float(close_str)
            except ValueError:
                continue
            ak_value = ak_close.get(key)
            if ak_value is None or ak_value == 0:
                continue
            deviations.append(abs(bs_close - ak_value) / ak_value)
        if not deviations:
            return CrossSourceResult(spec.canonical, 0, None, None, "no overlapping days")
        return CrossSourceResult(
            canonical=spec.canonical,
            overlapping_days=len(deviations),
            max_abs_pct_dev=round(max(deviations) * 100, 4),
            mean_abs_pct_dev=round(sum(deviations) / len(deviations) * 100, 4),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        return CrossSourceResult(
            spec.canonical, 0, None, None, f"{type(exc).__name__}: {exc}"[:200]
        )


# --------------------------------------------------------------------------- #
# Metric: dependency hygiene
# --------------------------------------------------------------------------- #


def _dependency_hygiene() -> dict[str, Any]:
    """Scan installed distributions for forbidden broker SDKs (safety boundary)."""
    from importlib import metadata

    installed: list[str] = []
    try:
        installed = sorted(
            {(dist.metadata["Name"] or "").lower() for dist in metadata.distributions()}
        )
    except Exception:  # noqa: BLE001
        installed = []
    offenders = sorted(
        {name for name in installed for frag in _FORBIDDEN_DIST_FRAGMENTS if frag and frag in name}
    )
    # Exact top-level import-root match (substring would catch stdlib __future__).
    loaded_offenders = sorted(
        {mod for mod in list(sys.modules) if mod.split(".")[0] in _FORBIDDEN_IMPORT_ROOTS}
    )
    return {
        "forbidden_installed": offenders,
        "forbidden_loaded_modules": loaded_offenders,
        "pass": not offenders and not loaded_offenders,
        "installed_count": len(installed),
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def _parse_symbol_args(raw: str | None) -> tuple[SymbolSpec, ...]:
    if not raw:
        return _DEFAULT_SYMBOLS
    by_canonical = {s.canonical: s for s in _DEFAULT_SYMBOLS}
    chosen: list[SymbolSpec] = []
    for token in raw.split(","):
        token = token.strip()
        if token in by_canonical:
            chosen.append(by_canonical[token])
    return tuple(chosen) if chosen else _DEFAULT_SYMBOLS


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    started = _now_utc()
    symbols = _parse_symbol_args(args.symbols)
    start_ymd = args.history_start.replace("-", "")
    end_ymd = _ymd(started)

    ak = None if args.no_akshare else _import_optional("akshare")
    bs_module = None if args.no_baostock else _import_optional("baostock")
    pandas_present = _import_optional("pandas") is not None

    # baostock requires an explicit login session.
    bs: ModuleType | None = None
    bs_login_error: str | None = None
    if bs_module is not None:
        try:
            login = bs_module.login()
            if getattr(login, "error_code", "0") != "0":
                bs_login_error = f"login error_code={login.error_code} msg={login.error_msg}"
            else:
                bs = bs_module
        except Exception as exc:  # noqa: BLE001
            bs_login_error = f"{type(exc).__name__}: {exc}"[:200]

    result: dict[str, Any] = {
        "probe": "ashare_p0_probe",
        "feature": "B060-F002",
        "run_label": args.label,
        "run_started_at": started.isoformat(),
        "host": _host_fingerprint(),
        "config": {
            "symbols": [s.canonical for s in symbols],
            "connectivity_symbol": args.connectivity_symbol,
            "connectivity_pulls": args.connectivity_pulls,
            "history_start": args.history_start,
            "history_end": _iso(started),
        },
        "libraries": {
            "akshare": _lib_version(ak),
            "baostock": _lib_version(bs_module),
            "pandas_present": pandas_present,
            "baostock_login_error": bs_login_error,
        },
        "dependency_hygiene": _dependency_hygiene(),
    }

    if ak is None and bs is None:
        result["status"] = "no-providers-importable"
        result["note"] = (
            "Neither akshare nor baostock could be imported. On the VM, "
            "`pip install akshare baostock` in the temporary venv first. "
            "(This local run still validates CLI + dependency hygiene.)"
        )
        return result

    # Connectivity — repeat-pull on the designated symbol (AkShare primary).
    conn_spec = next(
        (s for s in _DEFAULT_SYMBOLS if s.canonical == args.connectivity_symbol),
        _DEFAULT_SYMBOLS[0],
    )
    result["connectivity"] = (
        _connectivity_akshare(ak, conn_spec, args.connectivity_pulls).__dict__
        if ak is not None
        else {"skipped": "akshare not importable"}
    )

    # Coverage + depth + quality per symbol (AkShare).
    if ak is not None:
        qualities = [_quality_from_akshare(ak, spec, start_ymd, end_ymd) for spec in symbols]
        result["coverage_quality"] = [q.__dict__ for q in qualities]
        fetched = sum(1 for q in qualities if q.fetched)
        result["coverage_summary"] = {"requested": len(symbols), "fetched": fetched}
        result["scale_estimate"] = _scale_estimate(qualities)
        result["currency_units"] = _currency_units(qualities)
    else:
        result["coverage_quality"] = {"skipped": "akshare not importable"}

    # Cross-source agreement (needs both providers).
    if ak is not None and bs is not None:
        # Use a recent 1y window to keep the cross-check cheap.
        recent_start = _ymd(started - timedelta(days=365))
        result["cross_source"] = [
            _cross_source(ak, bs, spec, recent_start, end_ymd).__dict__
            for spec in symbols
            if spec.kind == "stock"
        ]
    else:
        result["cross_source"] = {"skipped": "needs both akshare and baostock"}

    if bs is not None:
        with contextlib.suppress(Exception):
            bs.logout()

    result["verdict_hint"] = _verdict_hint(result)
    return result


def _lib_version(module: ModuleType | None) -> str | None:
    if module is None:
        return None
    return str(getattr(module, "__version__", "unknown"))


def _host_fingerprint() -> dict[str, str]:
    import platform

    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def _scale_estimate(qualities: list[SymbolQuality]) -> dict[str, Any]:
    times = [q.fetch_seconds for q in qualities if q.fetched and q.fetch_seconds is not None]
    if not times:
        return {"per_symbol_full_history_s_avg": None, "extrapolated_300_universe_min": None}
    avg = sum(times) / len(times)
    return {
        "per_symbol_full_history_s_avg": round(avg, 3),
        "per_symbol_full_history_s_max": round(max(times), 3),
        "extrapolated_300_universe_min": round(avg * 300 / 60, 2),
        "note": (
            "Extrapolation is full-history × 300; a real daily update fetches "
            "only the latest bar and is far cheaper. Watch for throttling."
        ),
    }


def _currency_units(qualities: list[SymbolQuality]) -> dict[str, Any]:
    sample = next((q for q in qualities if q.fetched and q.canonical == "600519.SH"), None)
    if sample is None:
        sample = next((q for q in qualities if q.fetched), None)
    return {
        "currency": "CNY (documented; A-share quotes are in RMB)",
        "sample_symbol": sample.canonical if sample else None,
        "sample_close": sample.sample_close if sample else None,
        "sample_volume": sample.sample_volume if sample else None,
        "note": (
            "Eyeball the sample: 600519.SH close should be ~hundreds–thousands "
            "CNY. AkShare 成交量 is in 手 (1 手 = 100 股) on some endpoints and "
            "股 on others — confirm the unit before any aggregation."
        ),
    }


def _verdict_hint(result: dict[str, Any]) -> dict[str, Any]:
    """A mechanical hint only. The authoritative go/no-go call is Codex's."""
    conn = result.get("connectivity", {})
    success_rate = conn.get("success_rate") if isinstance(conn, dict) else None
    p95 = conn.get("latency_p95_s") if isinstance(conn, dict) else None
    cov = result.get("coverage_summary", {})
    fetched = cov.get("fetched") if isinstance(cov, dict) else None
    requested = cov.get("requested") if isinstance(cov, dict) else None
    hygiene_ok = result.get("dependency_hygiene", {}).get("pass")

    reasons: list[str] = []
    hint = "inconclusive"
    if success_rate is not None and requested:
        full_coverage = fetched == requested
        if success_rate >= 0.95 and (p95 is None or p95 < 5.0) and full_coverage and hygiene_ok:
            hint = "go-leaning"
        elif success_rate >= 0.5:
            hint = "conditional-leaning"
            if success_rate < 0.95:
                reasons.append(f"connectivity success_rate={success_rate:.2f} < 0.95")
            if p95 is not None and p95 >= 5.0:
                reasons.append(f"p95 latency={p95:.2f}s >= 5s")
            if not full_coverage:
                reasons.append(f"coverage {fetched}/{requested}")
        else:
            hint = "no-go-leaning"
            reasons.append(f"connectivity success_rate={success_rate:.2f} too low (geo-block?)")
    if not hygiene_ok:
        hint = "blocked"
        reasons.append("dependency hygiene FAILED — forbidden broker SDK present")
    return {
        "mechanical_hint": hint,
        "reasons": reasons,
        "disclaimer": (
            "Mechanical hint from a single run only. The authoritative "
            "go/conditional/no-go verdict requires multi-timeslot runs across "
            "≥1 day and is Codex's call in the feasibility report."
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A-share data source P0 feasibility probe (B060 F002 spike tool)."
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma list of canonical symbols to probe (default: the 5 representatives).",
    )
    parser.add_argument(
        "--connectivity-symbol",
        default="600519.SH",
        help="Symbol used for the repeat-pull connectivity test (default: 600519.SH).",
    )
    parser.add_argument(
        "--connectivity-pulls",
        type=int,
        default=50,
        help="Number of repeat pulls for the connectivity test (default: 50).",
    )
    parser.add_argument(
        "--history-start",
        default="2010-01-01",
        help="Start date (YYYY-MM-DD) for the full-history depth/quality fetch.",
    )
    parser.add_argument(
        "--label",
        default="unlabeled",
        help="Timeslot label for this run (e.g. cn-open, cn-close, vm-night).",
    )
    parser.add_argument("--out", default=None, help="Optional path to write the JSON report.")
    parser.add_argument(
        "--no-akshare", action="store_true", help="Skip AkShare (debug/baostock-only)."
    )
    parser.add_argument(
        "--no-baostock", action="store_true", help="Skip baostock (debug/akshare-only)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.connectivity_pulls < 0:
        parser.error("--connectivity-pulls must be >= 0")

    report = run_probe(args)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
        except OSError as exc:
            print(f"warning: could not write --out file: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
