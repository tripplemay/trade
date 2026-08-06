"""B112 F001 — cn_attack 指数趋势防御闸（MA200）的单测。

覆盖：DefenseGate 纯函数行为（月末评估/无前视/fail-open）、引擎集成
（防守月目标=空、逐月留痕）、以及 gate=None 的零回归保证（A/B 的 V0 基准）。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.defense_gate import (
    DefenseGate,
    DefenseGateConfig,
)
from trade.backtest.cn_attack_momentum_quality.engine import (
    CnAttackBacktestConfig,
    run_cn_attack_backtest,
)
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    CnAttackParameters,
)

# --- DefenseGate 纯函数 ---


def _trading_dates() -> list[date]:
    return [d.date() for d in pd.bdate_range("2024-01-01", "2025-12-31")]


def _index_series(drop_from: pd.Timestamp | None = None) -> pd.Series:
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    values: list[float] = []
    for day in days:
        if drop_from is not None and day >= drop_from:
            values.append(60.0)
        else:
            values.append(100.0)
    return pd.Series(values, index=days)


def test_gate_inactive_when_index_above_ma() -> None:
    gate = DefenseGate(DefenseGateConfig(), _trading_dates(), _index_series())
    state = gate.state_for(date(2025, 10, 15))
    assert state.active is False
    assert state.reason == "off"
    assert state.eval_date == date(2025, 9, 30)  # 上月最后一个交易日
    assert state.index_close == 100.0
    assert state.ma_value == 100.0


def test_gate_active_when_index_below_ma() -> None:
    # 2025-09-01 起指数跌到 60：9 月末评估时 MA200 仍≈99 → close 60 < MA → 10 月防守。
    gate = DefenseGate(
        DefenseGateConfig(), _trading_dates(), _index_series(pd.Timestamp("2025-09-01"))
    )
    state = gate.state_for(date(2025, 10, 8))
    assert state.active is True
    assert state.reason == "on"
    assert state.eval_date == date(2025, 9, 30)
    assert state.index_close == 60.0
    assert state.ma_value is not None and state.ma_value > 90.0


def test_gate_fail_open_on_insufficient_history() -> None:
    # 窗口最早的月份：评估日之前不足 200 个观测 → 不触发 + 留痕。
    gate = DefenseGate(DefenseGateConfig(), _trading_dates(), _index_series())
    state = gate.state_for(date(2024, 3, 15))
    assert state.active is False
    assert state.reason == "fail_open_insufficient_history"


def test_gate_fail_open_on_empty_series() -> None:
    gate = DefenseGate(
        DefenseGateConfig(), _trading_dates(), pd.Series(dtype=float)
    )
    state = gate.state_for(date(2025, 10, 8))
    assert state.active is False
    assert state.reason == "fail_open_no_series"


def test_gate_fail_open_when_evaluation_date_is_missing() -> None:
    series = _index_series().drop(pd.Timestamp("2025-09-30"))
    gate = DefenseGate(DefenseGateConfig(), _trading_dates(), series)

    state = gate.state_for(date(2025, 10, 8))

    assert state.active is False
    assert state.reason.startswith("fail_open")
    assert state.eval_date == date(2025, 9, 30)
    assert state.index_close is None
    assert state.ma_value is None


def test_gate_state_is_stable_within_a_month() -> None:
    gate = DefenseGate(
        DefenseGateConfig(), _trading_dates(), _index_series(pd.Timestamp("2025-09-01"))
    )
    early = gate.state_for(date(2025, 10, 1))
    late = gate.state_for(date(2025, 10, 31))
    assert early is late  # 月内同一状态（缓存实例）


def test_gate_uses_no_lookahead() -> None:
    # 指数在 10 月 15 日才跌穿；10 月的状态只能在 9 月 30 日的评估日定——不得用 10 月数据。
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    values = [100.0] * len(days)
    for i, day in enumerate(days):
        if day >= pd.Timestamp("2025-10-15"):
            values[i] = 60.0
    series = pd.Series(values, index=days)
    gate = DefenseGate(DefenseGateConfig(), _trading_dates(), series)
    october = gate.state_for(date(2025, 10, 8))
    assert october.active is False  # 9 月末评估时指数仍在 100
    november = gate.state_for(date(2025, 11, 5))
    assert november.active is True  # 10 月末评估时已跌穿


# --- 引擎集成 + 零回归 ---


def _growth() -> dict[str, float]:
    return {
        "600519.SH": 0.0024,
        "000858.SZ": 0.0022,
        "600036.SH": 0.0020,
        "300750.SZ": 0.0018,
        "002594.SZ": 0.0016,
        "000333.SZ": 0.0014,
    }


def _synth_prices() -> pd.DataFrame:
    dip_center = pd.Timestamp("2025-10-15")

    def envelope(day: pd.Timestamp) -> float:
        delta = (day - dip_center).days
        if -20 <= delta <= 0:
            return 1.0 - 0.28 * (delta + 20) / 20
        if 0 < delta <= 25:
            return 0.72 + 0.28 * delta / 25
        return 1.0

    days = pd.bdate_range("2024-01-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for ticker, growth in _growth().items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i * envelope(day)
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.005,
                    "low": price * 0.995,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _params() -> CnAttackParameters:
    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=4, max_position_weight=0.4
    )


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2024, 1, 1): tuple(_growth())}


_WINDOW = (date(2025, 8, 1), date(2025, 12, 31))


def test_gate_none_is_byte_identical_to_default() -> None:
    """A/B 的 V0 零回归基准（B112-F001-5）：pre-B112 默认路径（不构造闸）与
    显式 defense_gate=None 两条路径的输出必须逐字段一致（确定性证明）。"""
    prices = _synth_prices()
    baseline = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(),
        *_WINDOW,
        prices=prices,
        universe_history=_universe_history(),
    )
    explicit_none = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(defense_gate=None),
        *_WINDOW,
        prices=prices,
        universe_history=_universe_history(),
    )
    assert baseline.gate_states == ()
    assert explicit_none.gate_states == ()
    assert baseline.ending_value == explicit_none.ending_value
    assert baseline.total_cost == explicit_none.total_cost
    assert baseline.total_turnover == explicit_none.total_turnover
    assert baseline.rebalance_count == explicit_none.rebalance_count
    assert baseline.exit_count == explicit_none.exit_count
    assert baseline.equity_curve.equals(explicit_none.equity_curve)
    assert baseline.daily_records == explicit_none.daily_records


def _load_pre_b112_engine():
    """从 git 历史加载 pre-B112 引擎（commit 2e81836，B112 闸门落地前）。

    该历史模块 import 的同级模块（costs/universe/signal/metrics/parameters）在
    B112 中均未改动，故其行为等价于 pre-B112 真实基线。
    """
    import importlib.util
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    src = subprocess.run(
        ["git", "show", "2e81836:trade/backtest/cn_attack_momentum_quality/engine.py"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    path = Path(tempfile.mkdtemp()) / "pre_b112_engine.py"
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("pre_b112_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # 标准 importlib 咒语：先注册进 sys.modules（dataclasses/typing 内部会查
    # 模块字典），再执行。
    sys.modules["pre_b112_engine"] = module
    spec.loader.exec_module(module)
    return module


def test_v0_matches_pre_b112_baseline() -> None:
    """B112-F001-5a：defense_gate=None 的输出必须与 pre-B112 git 基线逐字段一致
    （不是与同一实现的其他配置比）。覆盖权益曲线、逐日记录、终值、成本、换手、
    调仓数和退出数。"""
    import dataclasses

    old = _load_pre_b112_engine()
    prices = _synth_prices()
    old_result = old.run_cn_attack_backtest(
        _params(),
        old.CnAttackBacktestConfig(),
        *_WINDOW,
        prices=prices,
        universe_history=_universe_history(),
    )
    new_result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(defense_gate=None),
        *_WINDOW,
        prices=prices,
        universe_history=_universe_history(),
    )
    assert old_result.ending_value == new_result.ending_value
    assert old_result.total_cost == new_result.total_cost
    assert old_result.total_turnover == new_result.total_turnover
    assert old_result.rebalance_count == new_result.rebalance_count
    assert old_result.exit_count == new_result.exit_count
    assert old_result.equity_curve.equals(new_result.equity_curve)
    # 跨模块类的 slots-dataclass 不能用 == 直接比（类身份不同）→ astuple 逐字段。
    assert [dataclasses.astuple(r) for r in old_result.daily_records] == [
        dataclasses.astuple(r) for r in new_result.daily_records
    ]


def test_defensive_month_liquidates_and_stays_cash() -> None:
    """指数 9 月起跌穿 MA200 → 10 月起目标恒空：持仓清零、权益在 10 月崩段走平。"""
    prices = _synth_prices()
    index = _index_series(pd.Timestamp("2025-09-01"))
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(defense_gate=DefenseGateConfig()),
        *_WINDOW,
        prices=prices,
        universe_history=_universe_history(),
        index_close=index,
    )
    states = {state.month: state for state in result.gate_states}
    assert states["2025-10"].active is True
    assert states["2025-08"].active is False  # 8 月评估时指数还没跌
    # 防守月内每日目标为空（全部记录 target_tickers=()）。
    october_records = [
        record
        for record in result.daily_records
        if record.date.month == 10 and record.target_tickers
    ]
    assert october_records == []
    # 10 月崩段（价格 −28% 深 V）期间权益曲线应近似走平（持币）。
    curve = result.equity_curve.set_index("date")["equity"]
    october = curve.loc["2025-10-01":"2025-10-31"]
    assert october.max() / october.min() < 1.02  # 防守月内波动 < 2%
    # 11 月指数仍低于 MA（60 < ~90）→ 继续防守到年末。
    assert states["2025-12"].active is True


def test_gate_requires_index_series() -> None:
    with pytest.raises(Exception, match="index_close"):
        run_cn_attack_backtest(
            _params(),
            CnAttackBacktestConfig(defense_gate=DefenseGateConfig()),
            *_WINDOW,
            prices=_synth_prices(),
            universe_history=_universe_history(),
        )
