"""B112 F001 — cn_attack 指数趋势防御闸（MA200，spec §1 冻结口径）。

月末信号日评估：若基准指数（CSI300）收盘 < 其 200 日简单移动平均
（数据 ≤ 评估日，严格无前视），**次月目标 = 100% 现金**；否则正常发布动量目标。
月频评估，与策略调仓节奏对齐；月内不翻转。

冻结纪律（spec §1/H5）：
- MA200 是文献最标准默认值（Faber 2007 族），禁扫参、禁按观测值调整。
- **fail-open**：指数序列缺失或评估日可用观测不足 ``ma_window`` 时，闸**不触发**
  （保持进攻），并以 ``reason`` 可见留痕（H6 不静默）。
- 闸只产生「全现金/正常」两态目标，不改变信号本身的任何计算。

本模块纯函数、不联网；被引擎按日调用时每个自然月只评估一次（月初首个交易日
确定该月状态）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

DEFAULT_GATE_MA_WINDOW = 200


@dataclass(frozen=True, slots=True)
class DefenseGateConfig:
    """防御闸配置（冻结：MA200；无其他可调项）。"""

    ma_window: int = DEFAULT_GATE_MA_WINDOW


@dataclass(frozen=True, slots=True)
class GateState:
    """一个自然月的闸状态（留痕用）。"""

    month: str  # "YYYY-MM"（被评估的持仓月份）
    active: bool  # True = 该月防守（100% 现金）
    eval_date: date | None  # 评估日（上一自然月最后一个交易日）
    index_close: float | None
    ma_value: float | None
    reason: str  # "on" / "off" / "fail_open_insufficient_history" / "fail_open_no_series"


class DefenseGate:
    """MA200 指数趋势闸：按自然月评估，月度状态机（无前视）。

    ``trading_dates`` 为完整交易日历（引擎价格框的索引，含窗口前的历史）。
    ``index_close`` 为日期索引的指数收盘序列（评估只用 ≤ 评估日的值）。
    """

    def __init__(
        self,
        config: DefenseGateConfig,
        trading_dates: list[date],
        index_close: pd.Series,
    ) -> None:
        self._config = config
        self._trading_dates = trading_dates
        # 规整为 date → close 的升序序列（剔除非法值，与 cn_benchmark loader 同纪律）。
        series = index_close.copy()
        series.index = pd.to_datetime(series.index)
        series = series.sort_index()
        self._index = series[series > 0]
        self._month_cache: dict[str, GateState] = {}

    def _last_trading_day_of_previous_month(self, day: date) -> date | None:
        """``day`` 所在自然月的上一自然月的最后一个交易日（用完整日历）。"""
        first_of_month = day.replace(day=1)
        prior = [d for d in self._trading_dates if d < first_of_month]
        return prior[-1] if prior else None

    def state_for(self, day: date) -> GateState:
        """``day`` 所在自然月的闸状态（每月评估一次并缓存）。

        ★B112-F001-3（evaluator 对抗用例）：指数在评估日必须有**当日的**有效
        观测；评估日缺失/NaN/非正一律可见 fail-open（reason 留痕），
        绝不回退到更早的收盘冒充当日值（spec §1/H6）。
        """
        key = f"{day.year:04d}-{day.month:02d}"
        cached = self._month_cache.get(key)
        if cached is not None:
            return cached
        eval_date = self._last_trading_day_of_previous_month(day)
        if eval_date is None or self._index.empty:
            state = GateState(key, False, eval_date, None, None, "fail_open_no_series")
            self._month_cache[key] = state
            return state
        upto = self._index[self._index.index <= pd.Timestamp(eval_date)]
        if len(upto) < self._config.ma_window:
            state = GateState(
                key, False, eval_date, None, None, "fail_open_insufficient_history"
            )
            self._month_cache[key] = state
            return state
        # 评估日精确观测检查（缺当日/NaN/非正都已被 __init__ 的 >0 过滤剔除 →
        # 最新可用日 < 评估日即视为评估日缺失）。
        latest_date = upto.index[-1].date()
        if latest_date != eval_date:
            state = GateState(
                key, False, eval_date, None, None, "fail_open_missing_eval_date"
            )
            self._month_cache[key] = state
            return state
        window = upto.iloc[-self._config.ma_window :]
        ma_value = float(window.mean())
        close = float(upto.iloc[-1])
        active = close < ma_value
        state = GateState(key, active, eval_date, close, ma_value, "on" if active else "off")
        self._month_cache[key] = state
        return state


__all__ = [
    "DEFAULT_GATE_MA_WINDOW",
    "DefenseGate",
    "DefenseGateConfig",
    "GateState",
]
