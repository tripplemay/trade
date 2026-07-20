"""B109 F002 — 分页与静默截断防护的单测（离线，用假 API 替身）。

★这是一条**回归测试**，对应 2026-07-20 在真实 Tushare 上实测到的缺陷：
单次 `income_vip` 调用在 2022 年报期返回**恰好 9000 行**，分页拉全为 10,093 行，
漏掉 10.8%，且 ``update_flag=0`` 行漏掉 18.7%（截断非均匀，富集于 vintage 记录）。

替身按「满页即还有下一页」复现该行为——修复前的单次实现会在第一页就停下。
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.research.ashare_pit import fetch as fetch_module
from scripts.research.ashare_pit.fetch import (
    KNOWN_ROW_CAPS,
    fetch_paged,
    fetch_single_checked,
    looks_truncated,
)


@pytest.fixture(autouse=True)
def _no_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """失败路径的用例否则要空等 9 秒。"""
    monkeypatch.setattr(fetch_module, "RETRY_BACKOFF_SECONDS", 0.0)


class _FakeEndpoint:
    """按 offset/limit 分页返回的假接口，行数可配。

    ``server_cap`` 模拟**不带 limit 调用时服务端自己的上限**——这正是真实
    Tushare 静默截断的形态（`income_vip` 9000 / `namechange` 10000）。
    """

    def __init__(
        self,
        total: int,
        *,
        fail_at_offset: int | None = None,
        server_cap: int | None = None,
    ) -> None:
        self.total = total
        self.fail_at_offset = fail_at_offset
        self.server_cap = server_cap
        self.calls: list[tuple[int, int | None]] = []

    def __call__(self, *, offset: int = 0, limit: int | None = None, **_: object) -> pd.DataFrame:
        self.calls.append((offset, limit))
        if self.fail_at_offset is not None and offset == self.fail_at_offset:
            raise RuntimeError("上游超时")
        take = limit if limit is not None else (self.server_cap or self.total)
        rows = range(offset, min(offset + take, self.total))
        return pd.DataFrame({"ts_code": [f"{i:06d}.SZ" for i in rows], "v": list(rows)})


# --- 触顶识别 ---


def test_exact_cap_row_counts_are_flagged() -> None:
    """★真实数据几乎不会恰好停在 9000/10000——这正是实测踩到的信号。"""
    assert looks_truncated(9000) is True
    assert looks_truncated(10000) is True
    assert looks_truncated(10093) is False  # 分页拉全后的真实行数
    assert looks_truncated(5673) is False


def test_known_caps_include_the_two_observed_in_the_wild() -> None:
    assert 9000 in KNOWN_ROW_CAPS  # income_vip 实测
    assert 10000 in KNOWN_ROW_CAPS  # namechange 实测


# --- 分页 ---


def test_pagination_keeps_going_past_a_full_page() -> None:
    """★核心回归：满页不是终点。修复前的单次实现在这里只会拿到 9000 行。"""
    api = _FakeEndpoint(total=10093)
    frame, report = fetch_paged(api, endpoint="income_vip", page_size=9000, throttle=0)

    assert len(frame) == 10093
    assert report.pages == 2
    assert report.rows == 10093
    assert not report.failures
    assert api.calls == [(0, 9000), (9000, 9000)]


def test_short_first_page_stops_immediately() -> None:
    api = _FakeEndpoint(total=1200)
    frame, report = fetch_paged(api, endpoint="daily_basic", page_size=5000, throttle=0)
    assert len(frame) == 1200
    assert report.pages == 1
    assert len(api.calls) == 1


def test_exact_multiple_of_page_size_still_probes_one_more_page() -> None:
    """总数恰为页长整数倍时，必须再探一页才能确认到底——否则又是「满页当全量」。"""
    api = _FakeEndpoint(total=9000)
    frame, report = fetch_paged(api, endpoint="income_vip", page_size=9000, throttle=0)
    assert len(frame) == 9000
    assert report.pages == 1
    assert api.calls == [(0, 9000), (9000, 9000)]  # 第二次探到空页才收手


def test_empty_result_is_not_an_error() -> None:
    api = _FakeEndpoint(total=0)
    frame, report = fetch_paged(api, endpoint="income_vip", page_size=5000, throttle=0)
    assert frame.empty
    assert report.rows == 0
    assert not report.failures


def test_mid_pagination_failure_is_recorded_not_passed_off_as_complete() -> None:
    """★半截数据不得冒充全量——缺口必须落在 failures 里（H4）。"""
    api = _FakeEndpoint(total=20000, fail_at_offset=5000)
    frame, report = fetch_paged(api, endpoint="income_vip", page_size=5000, throttle=0)

    assert len(frame) == 5000
    assert report.failures == ["income_vip:offset=5000"]


def test_duplicate_rows_across_page_boundaries_are_deduped() -> None:
    class _Overlapping(_FakeEndpoint):
        def __call__(self, *, offset: int = 0, limit: int = 5000, **kw: object) -> pd.DataFrame:
            # 供应商在分页边界重复返回上一页最后一行
            return super().__call__(offset=max(offset - 1, 0), limit=limit, **kw)

    api = _Overlapping(total=100)
    frame, report = fetch_paged(api, endpoint="x", page_size=60, throttle=0)
    assert len(frame) == frame.drop_duplicates().shape[0]
    assert report.rows == len(frame)


# --- 单次 checked ---


def test_single_fetch_flags_a_capped_looking_result() -> None:
    """★复现 `namechange` 实测形态：真实 11,414 条，单次调用被服务端砍到 10,000。

    调用方**看不到任何错误**——只看到一个很像全量的整数。守卫必须置位。
    """
    api = _FakeEndpoint(total=11414, server_cap=10000)
    frame, report = fetch_single_checked(api, endpoint="namechange")
    assert len(frame) == 10000
    assert report.truncation_suspected is True


def test_paging_recovers_what_the_single_call_lost() -> None:
    """同一个被截断的接口，改走分页即拿回全部 11,414 条（实测差 1,414 条）。"""
    api = _FakeEndpoint(total=11414, server_cap=10000)
    frame, report = fetch_paged(api, endpoint="namechange", page_size=5000, throttle=0)
    assert len(frame) == 11414
    assert report.pages == 3


def test_single_fetch_on_normal_size_is_clean() -> None:
    api = _FakeEndpoint(total=5528)  # 实测 stock_basic list_status=L
    frame, report = fetch_single_checked(api, endpoint="stock_basic:L")
    assert len(frame) == 5528
    assert report.truncation_suspected is False
    assert report.pages == 1


def test_single_fetch_failure_yields_empty_frame_and_a_recorded_failure() -> None:
    api = _FakeEndpoint(total=100, fail_at_offset=0)
    frame, report = fetch_single_checked(api, endpoint="stock_basic:L")
    assert frame.empty
    assert report.failures == ["stock_basic:L"]


def test_report_is_serializable_for_audit_trail() -> None:
    api = _FakeEndpoint(total=10)
    _, report = fetch_paged(
        api, endpoint="income_vip", page_size=5000, throttle=0, period="20221231"
    )
    payload = report.as_dict()
    assert payload["endpoint"] == "income_vip"
    assert payload["params"] == {"period": "20221231"}
    assert payload["rows"] == 10
