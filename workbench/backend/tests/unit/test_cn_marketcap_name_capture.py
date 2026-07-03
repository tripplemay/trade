"""B079 F001 — zero-fetch A-share display-name capture in cn_marketcap.

The daily akshare spot frame is fetched for ST filtering + liquidity ranking and
its 名称 column is discarded. B079 harvests ``{canonical: 名称}`` from that same
frame (zero extra fetch) into an optional ``capture_names`` out-dict, while the
ranking output — the existing ``(symbols, provenance)`` contract every current
caller depends on — stays byte-identical.

Faked akshare (no network), mirroring ``test_cn_universe`` fixtures.
"""

from __future__ import annotations

import pandas as pd  # type: ignore[import-untyped]

from workbench_api.data_refresh.cn_marketcap import (
    _discover_from_eastmoney,
    _discover_from_sina,
    discover_ashare_superset,
)
from workbench_api.data_refresh.cn_universe import CN_UNIVERSE_SEED


class _FakeAkshare:
    def __init__(
        self,
        spot_frame: pd.DataFrame | None = None,
        sina_frame: pd.DataFrame | None = None,
    ) -> None:
        self._spot = spot_frame
        self._sina = sina_frame

    def stock_zh_a_spot_em(self) -> pd.DataFrame:
        if self._spot is None:
            raise RuntimeError("unreachable")
        return self._spot

    def stock_zh_a_spot(self) -> pd.DataFrame:
        if self._sina is None:
            raise RuntimeError("unreachable")
        return self._sina


def test_eastmoney_captures_names_including_st_ranking_unchanged() -> None:
    spot = pd.DataFrame(
        {
            "代码": ["600519", "000858", "002999"],
            "名称": ["贵州茅台", "五粮液", "*ST退市"],
            "总市值": [3.0e12, 1.0e12, 5.0e12],  # ST biggest on purpose
        }
    )
    fake = _FakeAkshare(spot_frame=spot)
    names: dict[str, str] = {}
    ranked = _discover_from_eastmoney(fake, 10, names_out=names)
    # Ranking excludes ST despite its larger market cap (byte-identical to pre-B079).
    assert ranked == ["600519.SH", "000858.SZ"]
    # Names captured for every mappable record — INCLUDING the ST name.
    assert names == {
        "600519.SH": "贵州茅台",
        "000858.SZ": "五粮液",
        "002999.SZ": "*ST退市",
    }


def test_sina_captures_names_including_st_and_ranking_unchanged() -> None:
    sina = pd.DataFrame(
        {
            "代码": ["sh600519", "sz300750", "sz000999", "bj920000"],
            "名称": ["贵州茅台", "宁德时代", "*ST示例", "北交所示例"],
            "成交额": [9.0e9, 8.0e9, 9.9e9, 9.9e9],  # ST + bj biggest on purpose
        }
    )
    fake = _FakeAkshare(sina_frame=sina)
    names: dict[str, str] = {}
    ranked = _discover_from_sina(fake, 3, names_out=names)
    # Ranking excludes ST + 北交所 (byte-identical to pre-B079).
    assert ranked == ["600519.SH", "300750.SZ"]
    # Names captured for every mappable record — INCLUDING the ST name (a held
    # risk-warning ticker still deserves its display name). 北交所 has no canonical.
    assert names == {
        "600519.SH": "贵州茅台",
        "300750.SZ": "宁德时代",
        "000999.SZ": "*ST示例",
    }


def test_discover_threads_capture_names_from_answering_branch() -> None:
    # eastmoney down (sina answers + research opt-in): names come from the sina
    # branch that actually produced the symbols.
    sina = pd.DataFrame(
        {
            "代码": ["sh600519", "sz300750"],
            "名称": ["贵州茅台", "宁德时代"],
            "成交额": [9.0e9, 8.0e9],
        }
    )
    fake = _FakeAkshare(spot_frame=None, sina_frame=sina)
    captured: dict[str, str] = {}
    symbols, provenance = discover_ashare_superset(
        akshare_module=fake,
        top_n=10,
        allow_sina_fallback=True,
        capture_names=captured,
    )
    assert provenance == "sina_spot"
    assert captured == {"600519.SH": "贵州茅台", "300750.SZ": "宁德时代"}
    assert set(CN_UNIVERSE_SEED).issubset(set(symbols))


def test_discover_without_capture_names_is_byte_identical_contract() -> None:
    # Zero-regression: the 2-tuple (symbols, provenance) contract is unchanged
    # when capture_names is omitted (every existing caller's path).
    spot = pd.DataFrame(
        {
            "代码": ["600519", "000858", "300750"],
            "总市值": [3.0e12, 1.0e12, 2.0e12],
        }
    )
    fake = _FakeAkshare(spot_frame=spot)
    symbols, provenance = discover_ashare_superset(akshare_module=fake, top_n=2)
    assert provenance == "bulk_spot"
    assert symbols[:2] == ("600519.SH", "300750.SZ")


def test_capture_names_stays_empty_when_discovery_degrades_to_seed() -> None:
    # Both endpoints down → seed fallback → nothing captured (the curated static
    # CN/HK names the bootstrap already seeded cover this case).
    fake = _FakeAkshare(spot_frame=None, sina_frame=None)
    captured: dict[str, str] = {}
    symbols, provenance = discover_ashare_superset(
        akshare_module=fake, allow_sina_fallback=True, capture_names=captured
    )
    assert provenance == "seed"
    assert captured == {}
    assert symbols == CN_UNIVERSE_SEED
