"""B109 F002 — 分母：PIT 总市值（`CN_SECURITY_TOTAL_MV`）。

上游报告 §2.2 把分母冻结为**证券级 A 股 `total_mv`**，且必须与
``raw_close * PIT_total_share`` 同 basis 复算。

**本模块替换 `scripts/research/b076_fetch_pit_marketcap.py`**——那份用
``close * volume * 100 / turn`` 反推的是**流通市值**，语义上不能作全公司归母利润的分母
（上游禁令 #6）。三问探针实测 `daily_basic.total_mv` 与 ``close × total_share``
在 2015/2020/2023 三日均 **100.000%** 落在 0.5% 内、中位误差 **0.00000%**。

★单位陷阱：`daily_basic` 的 `total_mv` / `circ_mv` 文档单位为**万元**、
`total_share` 为**万股**。两者同单位，故身份复算可直接比较；
但对外输出必须在 schema 层显式转 CNY，不得让万元流进下游（上游报告 §4.5）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from scripts.research.ashare_pit.codes import MarketCapStatus
from scripts.research.ashare_pit.resolver import to_decimal

# 万元 → 元。`daily_basic` 的 total_mv/circ_mv 以万元计价。
WAN_TO_CNY = Decimal(10_000)

# 身份校验容差。上游 G4 要求「至少 99% 误差 <=0.5%」，>5% 标严重异常。
IDENTITY_TOLERANCE = Decimal("0.005")
IDENTITY_SEVERE = Decimal("0.05")


@dataclass(frozen=True)
class MarketCapPoint:
    """一个证券-交易日的分母观测。``total_mv_cny`` 已转为元。"""

    ts_code: str
    trade_date: str
    close: Decimal
    total_share_wan: Decimal
    total_mv_wan: Decimal
    total_mv_cny: Decimal
    identity_error: Decimal
    status: MarketCapStatus

    @property
    def is_usable(self) -> bool:
        return self.status is MarketCapStatus.RESOLVED

    @property
    def is_severe_outlier(self) -> bool:
        return self.identity_error > IDENTITY_SEVERE


def identity_error(close: Decimal, total_share_wan: Decimal, total_mv_wan: Decimal) -> Decimal:
    """``close × total_share`` 与 `total_mv` 的相对误差（同为万元口径）。

    这是上游 G4 的身份校验：分母必须能用同 basis 的价格×股本独立复算出来，
    否则无法排除供应商用了别的股本口径（流通股本、某一股份类别等）。
    """
    implied = close * total_share_wan
    denominator = max(abs(total_mv_wan), Decimal(1))
    return abs(implied - total_mv_wan) / denominator


def build_point(row: dict[str, object]) -> MarketCapPoint | None:
    """把 `daily_basic` 的一行规范化并做身份校验。字段缺失返回 None（由调用方计数）。"""
    close = to_decimal(row.get("close"))
    total_share = to_decimal(row.get("total_share"))
    total_mv = to_decimal(row.get("total_mv"))
    ts_code = str(row.get("ts_code") or "")
    trade_date = str(row.get("trade_date") or "")

    if close is None or total_share is None or total_mv is None:
        return None

    if total_mv <= 0:
        # 上游报告 §6：零市值或非正总市值一律拒绝，不得进入分母
        return MarketCapPoint(
            ts_code=ts_code,
            trade_date=trade_date,
            close=close,
            total_share_wan=total_share,
            total_mv_wan=total_mv,
            total_mv_cny=Decimal(0),
            identity_error=Decimal(0),
            status=MarketCapStatus.NON_POSITIVE_MARKET_CAP,
        )

    error = identity_error(close, total_share, total_mv)
    status = (
        MarketCapStatus.RESOLVED
        if error <= IDENTITY_TOLERANCE
        else MarketCapStatus.MARKET_CAP_IDENTITY_FAILED
    )
    return MarketCapPoint(
        ts_code=ts_code,
        trade_date=trade_date,
        close=close,
        total_share_wan=total_share,
        total_mv_wan=total_mv,
        # ★万元 → 元在此一次性完成。下游只见 CNY，不得再遇到万元。
        total_mv_cny=total_mv * WAN_TO_CNY,
        identity_error=error,
        status=status,
    )


def summarize(points: Iterable[MarketCapPoint]) -> dict[str, object]:
    """身份校验的覆盖报告。**隔离行必须显式计数**，不得静默丢弃（H4）。"""
    items = list(points)
    total = len(items)
    if not total:
        return {
            "n": 0,
            "identity_pass_fraction": 0.0,
            "isolated": 0,
            "severe_outliers": 0,
            "non_positive": 0,
        }
    resolved = [item for item in items if item.status is MarketCapStatus.RESOLVED]
    return {
        "n": total,
        "identity_pass_fraction": len(resolved) / total,
        "isolated": total - len(resolved),
        "severe_outliers": sum(item.is_severe_outlier for item in items),
        "non_positive": sum(
            item.status is MarketCapStatus.NON_POSITIVE_MARKET_CAP for item in items
        ),
        "median_identity_error": (
            sorted(item.identity_error for item in items)[total // 2] if total else Decimal(0)
        ),
    }
