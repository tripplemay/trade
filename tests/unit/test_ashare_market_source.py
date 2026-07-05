"""B086 F001 — multi-source ETF fetch fallback (mocked sources, no real network)."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.research import ashare_market_source as ams


def _df(code: str, source: str, adjust: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "ticker": code,
            "close": [1.0, 1.01],
            "source": source,
            "adjust": adjust,
        }
    )


def test_eastmoney_success_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ams, "_fetch_eastmoney", lambda c, s, e: _df(c, "eastmoney", "qfq"))
    monkeypatch.setattr(ams, "_fetch_sina", lambda c, s, e: pytest.fail("sina must not be called"))
    out = ams.fetch_etf_daily("510300")
    assert out["source"].iloc[0] == "eastmoney"
    assert out["adjust"].iloc[0] == "qfq"


def test_eastmoney_sslerror_falls_back_to_sina(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(c: str, s: str, e: str) -> pd.DataFrame:
        raise OSError("SSLError push2his.eastmoney.com")  # simulate the rate-limit

    monkeypatch.setattr(ams, "_fetch_eastmoney", _boom)
    monkeypatch.setattr(ams, "_fetch_sina", lambda c, s, e: _df(c, "sina", "raw"))
    out = ams.fetch_etf_daily("510300")
    assert out["source"].iloc[0] == "sina"  # fell back
    assert out["adjust"].iloc[0] == "raw"  # ★口径 differs — annotated, not silently mixed


def test_eastmoney_empty_falls_back_to_sina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ams, "_fetch_eastmoney", lambda c, s, e: None)  # empty
    monkeypatch.setattr(ams, "_fetch_sina", lambda c, s, e: _df(c, "sina", "raw"))
    assert ams.fetch_etf_daily("510300")["source"].iloc[0] == "sina"


def test_all_sources_fail_raises_not_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(c: str, s: str, e: str) -> pd.DataFrame:
        raise OSError("down")

    monkeypatch.setattr(ams, "_fetch_eastmoney", _boom)
    monkeypatch.setattr(ams, "_fetch_sina", _boom)
    with pytest.raises(ams.DataSourceError):  # never a silent empty frame
        ams.fetch_etf_daily("510300")


def test_sina_symbol_exchange_prefix() -> None:
    assert ams.sina_symbol("510300") == "sh510300"  # Shanghai (5)
    assert ams.sina_symbol("159915") == "sz159915"  # Shenzhen (1)
    with pytest.raises(ValueError):
        ams.sina_symbol("bad")


def test_return_carries_source_and_adjust_annotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ams, "_fetch_eastmoney", lambda c, s, e: _df(c, "eastmoney", "qfq"))
    out = ams.fetch_etf_daily("510300")
    assert {"date", "ticker", "close", "source", "adjust"} <= set(out.columns)
