"""B061 F001 — SymbolRef market-qualified identity + normalize backward-compat.

Covers the acceptance (spec §4 F001 / path-doc §9.3-9.4): US bare → US default,
CN canonical parse, the BRK.B disambiguation pitfall, board inference, illegal
ticker rejection, and that ``normalize_symbol`` stays byte-for-byte
backward-compatible for existing US symbols (zero migration 铁律).
"""

from __future__ import annotations

import pytest

from workbench_api.symbols.provider import InvalidSymbolError
from workbench_api.symbols.service import normalize_symbol
from workbench_api.symbols.symbol_ref import SymbolRef


class TestUsDefault:
    def test_bare_ticker_defaults_to_us(self) -> None:
        ref = SymbolRef.parse("AAPL")
        assert ref.canonical == "AAPL"
        assert ref.code == "AAPL"
        assert ref.market == "US"
        assert ref.currency == "USD"
        assert ref.board == "us"
        assert ref.exchange is None

    def test_lowercase_and_whitespace_are_normalised(self) -> None:
        ref = SymbolRef.parse("  aapl  ")
        assert ref.canonical == "AAPL"
        assert ref.market == "US"

    @pytest.mark.parametrize("symbol", ["SPY", "NVDA", "BRK-B", "^GSPC", "ES=F"])
    def test_existing_us_ticker_shapes_stay_us(self, symbol: str) -> None:
        # '-' (class share), '^' (index), '=' (future) must keep parsing as US
        # exactly as the pre-B061 lookup accepted them (zero regression).
        ref = SymbolRef.parse(symbol)
        assert ref.market == "US"
        assert ref.currency == "USD"
        assert ref.canonical == symbol


class TestDisambiguation:
    def test_brk_dot_b_is_us_not_market_qualified(self) -> None:
        # The pitfall: '.B' is a US class-share suffix, NOT a market code — we
        # must not split on every dot.
        ref = SymbolRef.parse("BRK.B")
        assert ref.market == "US"
        assert ref.canonical == "BRK.B"
        assert ref.code == "BRK.B"

    def test_two_letter_non_market_suffix_falls_through_to_us(self) -> None:
        # '.SS' (Yahoo Shanghai) is a 6-digit+2-letter shape but 'SS' is not a
        # known market code → US (canonical CN form uses .SH).
        ref = SymbolRef.parse("600519.SS")
        assert ref.market == "US"


class TestCnParse:
    def test_shanghai_main_board(self) -> None:
        ref = SymbolRef.parse("600519.SH")
        assert ref.canonical == "600519.SH"
        assert ref.code == "600519"
        assert ref.market == "CN"
        assert ref.currency == "CNY"
        assert ref.exchange == "XSHG"
        assert ref.board == "sh_main"

    def test_shenzhen_main_board(self) -> None:
        ref = SymbolRef.parse("000001.SZ")
        assert ref.market == "CN"
        assert ref.exchange == "XSHE"
        assert ref.board == "sz_main"
        assert ref.currency == "CNY"

    def test_lowercase_cn_suffix_is_accepted(self) -> None:
        ref = SymbolRef.parse("600519.sh")
        assert ref.canonical == "600519.SH"
        assert ref.market == "CN"

    @pytest.mark.parametrize(
        ("symbol", "board"),
        [
            ("600519.SH", "sh_main"),
            ("601318.SH", "sh_main"),
            ("603259.SH", "sh_main"),
            ("605499.SH", "sh_main"),
            ("688981.SH", "star"),
            ("000001.SZ", "sz_main"),
            ("002594.SZ", "sz_main"),
            ("300750.SZ", "chinext"),
            ("301236.SZ", "chinext"),
        ],
    )
    def test_board_inferred_from_code_prefix(self, symbol: str, board: str) -> None:
        assert SymbolRef.parse(symbol).board == board

    def test_unknown_cn_prefix_falls_back_to_cn_other(self) -> None:
        ref = SymbolRef.parse("999999.SZ")
        assert ref.market == "CN"
        assert ref.board == "cn_other"


class TestHkParse:
    def test_hong_kong_symbol(self) -> None:
        ref = SymbolRef.parse("0700.HK")
        assert ref.canonical == "0700.HK"
        assert ref.code == "0700"
        assert ref.market == "HK"
        assert ref.currency == "HKD"
        assert ref.exchange == "XHKG"
        assert ref.board == "hk_main"

    @pytest.mark.parametrize("symbol", ["0700.HK", "9988.HK", "3690.HK", "1810.HK", "700.hk"])
    def test_hk_codes_parse(self, symbol: str) -> None:
        ref = SymbolRef.parse(symbol)
        assert ref.market == "HK"
        assert ref.canonical == symbol.upper()

    def test_hk_code_too_long_rejected(self) -> None:
        # HK codes are 1-5 digits; a 6-digit .HK is not valid HK.
        with pytest.raises(InvalidSymbolError):
            SymbolRef.parse("123456.HK")

    def test_cn_suffix_still_requires_six_digits(self) -> None:
        # A 4-digit .SH is not a valid CN code (CN is exactly 6 digits) — the
        # unified parser must keep the per-market length rule.
        with pytest.raises(InvalidSymbolError):
            SymbolRef.parse("0700.SH")


class TestIllegal:
    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "!!!", "AA PL", "A" * 33, "茅台", "@#$"],
    )
    def test_illegal_tickers_raise(self, raw: str) -> None:
        with pytest.raises(InvalidSymbolError):
            SymbolRef.parse(raw)


class TestNormalizeBackwardCompat:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("aapl", "AAPL"),
            ("  spy  ", "SPY"),
            ("BRK.B", "BRK.B"),
            ("^GSPC", "^GSPC"),
            ("600519.sh", "600519.SH"),
            ("000001.SZ", "000001.SZ"),
            ("0700.hk", "0700.HK"),
        ],
    )
    def test_normalize_returns_canonical_string(self, raw: str, expected: str) -> None:
        # normalize_symbol must keep returning the canonical string so existing
        # US cache keys / paths are untouched while CN canonicalises.
        assert normalize_symbol(raw) == expected

    def test_normalize_rejects_illegal(self) -> None:
        with pytest.raises(InvalidSymbolError):
            normalize_symbol("")
