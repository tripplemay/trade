"""B084 F001 — ETF Sina-symbol derivation (sh/sz prefix)."""

from __future__ import annotations

from scripts.research.b084_etf_fetch import _sina_symbol


def test_sina_symbol_exchange_prefix() -> None:
    assert _sina_symbol("510300") == "sh510300"  # 沪深300, Shanghai (5)
    assert _sina_symbol("512890") == "sh512890"  # 红利低波, Shanghai (5)
    assert _sina_symbol("588000") == "sh588000"  # 科创50, Shanghai (5)
    assert _sina_symbol("159915") == "sz159915"  # 创业板, Shenzhen (1)
