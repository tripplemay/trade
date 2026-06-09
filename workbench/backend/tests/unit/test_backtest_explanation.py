"""B043 F002 — grounded backtest explanation (worker injection + degrade).

Pins that the worker generates a grounded "why these results" explanation from
the real metrics, attaches it to the mapped result, and degrades to ``None``
(full result still stored) when the LLM refuses / errors / is absent.
"""

from __future__ import annotations

from types import SimpleNamespace

from workbench_api.backtests import worker as worker_mod
from workbench_api.backtests.explanation import (
    _build_grounding,
    generate_backtest_explanation,
)
from workbench_api.services.explanation import STATUS_OK, ExplanationResult

_METRICS: dict[str, float] = {
    "cagr": 0.085,
    "sharpe": 1.42,
    "max_drawdown": -0.063,
    "turnover": 0.42,
}
_MAPPED: dict[str, object] = {
    "metrics": _METRICS,
    "equity": [{"date": "2024-01-01", "nav": 100.0}, {"date": "2024-06-30", "nav": 104.5}],
    "allocations": [],
    "trades": [{"date": "2024-01-02", "symbol": "SPY", "side": "buy"}],
    "report_markdown": "# report",
}


class _StubExplainer:
    def __init__(self, result: ExplanationResult | None = None, *, boom: bool = False) -> None:
        self._result = result
        self._boom = boom
        self.last_kwargs: dict[str, object] = {}

    def explain(self, **kwargs: object) -> ExplanationResult:
        self.last_kwargs = kwargs
        if self._boom:
            raise RuntimeError("budget cap")
        assert self._result is not None
        return self._result


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        run_id="bt-1",
        strategy_id="B016-risk-parity-hrp",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )


def _ok(
    explanation: str = "Sharpe 1.42 reflects steady risk-parity returns over the window.",
) -> ExplanationResult:
    return ExplanationResult(status=STATUS_OK, explanation=explanation, raw_output="{}", model="m")


def test_grounding_contains_real_metrics_as_citable() -> None:
    text, citable = _build_grounding(
        strategy_id="B016-risk-parity-hrp",
        metrics=_METRICS,
        trades_count=1,
        equity_points=2,
        start_date="2024-01-01",
        end_date="2024-06-30",
    )
    assert "SHARPE: 1.42" in text
    assert "B016-risk-parity-hrp" in citable
    assert "1.42" in citable  # the real metric is restate-able / citable


def test_generate_explanation_none_without_explainer() -> None:
    assert generate_backtest_explanation(None, _run(), _MAPPED) is None


def test_generate_explanation_ok() -> None:
    explainer = _StubExplainer(_ok())
    out = generate_backtest_explanation(explainer, _run(), _MAPPED)  # type: ignore[arg-type]
    assert out is not None and "Sharpe" in out
    assert explainer.last_kwargs["task"] == "backtest_explanation"


def test_generate_explanation_degrades_on_refusal() -> None:
    refused = ExplanationResult(
        status="insufficient_grounding", explanation=None, raw_output="x", model="m"
    )
    assert generate_backtest_explanation(_StubExplainer(refused), _run(), _MAPPED) is None  # type: ignore[arg-type]


def test_generate_explanation_degrades_on_exception() -> None:
    assert generate_backtest_explanation(_StubExplainer(boom=True), _run(), _MAPPED) is None  # type: ignore[arg-type]


def test_run_backtest_job_attaches_explanation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", lambda: SimpleNamespace())
    monkeypatch.setitem(
        worker_mod._DISPATCH, "B016-risk-parity-hrp", lambda _s, _r: dict(_MAPPED)
    )
    mapped = worker_mod.run_backtest_job(_run(), _StubExplainer(_ok()))  # type: ignore[arg-type]
    assert mapped["explanation"] is not None and "Sharpe" in mapped["explanation"]


def test_run_backtest_job_explanation_none_without_explainer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", lambda: SimpleNamespace())
    monkeypatch.setitem(
        worker_mod._DISPATCH, "B016-risk-parity-hrp", lambda _s, _r: dict(_MAPPED)
    )
    mapped = worker_mod.run_backtest_job(_run())  # default explainer=None
    assert mapped["explanation"] is None
