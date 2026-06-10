"""B054 F002 — backend dynamic strings localize per request locale.

The strategy notes / gate details / execution reason / risk defense rationale /
home position summary were hardcoded English rendered verbatim by the frontend.
They now resolve through the B024 ``t()`` machinery against the per-request
locale (default zh-CN), so the user reads Chinese. These tests pin both locales
and the parameterised templates.
"""

from __future__ import annotations

import pytest

from workbench_api.i18n import _LOCALE_VAR, t
from workbench_api.services.strategies import _REGISTRY, get_strategy


@pytest.fixture(autouse=True)
def _zh_locale() -> None:
    # Each test starts in the default zh-CN locale; restore it on teardown so a
    # test that switches to en cannot leak into the next.
    _LOCALE_VAR.set("zh-CN")


def test_strategy_note_localizes_and_drops_note_key() -> None:
    detail_zh = get_strategy("master_portfolio")
    assert detail_zh is not None
    assert "note_key" not in detail_zh.config  # resolved away, never leaked
    assert "完整组合" in detail_zh.config["note"]  # zh-CN default

    _LOCALE_VAR.set("en")
    detail_en = get_strategy("master_portfolio")
    assert detail_en is not None
    assert "combined portfolio" in detail_en.config["note"]


def test_all_registry_notes_resolve_nonempty() -> None:
    for strategy_id in _REGISTRY:
        detail = get_strategy(strategy_id)
        assert detail is not None
        note = detail.config["note"]
        assert isinstance(note, str) and note
        assert "note_key" not in detail.config


def test_regime_inactive_notes_share_one_key() -> None:
    # B014 + B015 carry the same note_key → identical localized text.
    a = get_strategy("B014-regime-stress")
    b = get_strategy("B015-regime-active")
    assert a is not None and b is not None
    assert a.config["note"] == b.config["note"]
    assert "研究态" in a.config["note"]


def test_gate_detail_localizes_and_interpolates() -> None:
    zh = t("gate.kill_switch_detail", master_dd="0.0197", comparator="≤", threshold="0.15")
    assert zh == "主组合回撤 0.0197 ≤ 阈值 0.15。"
    assert t("gate.min_equity_detail", equity="50000.00") == "账户权益 = 50000.00"
    _LOCALE_VAR.set("en")
    en = t("gate.kill_switch_detail", master_dd="0.0197", comparator="<=", threshold="0.15")
    assert en == "Master drawdown 0.0197 <= threshold 0.15."


def test_execution_reason_and_home_summary_localize() -> None:
    assert t("diff.reason.sell_to_zero") == "已持有但已不在目标内——清仓至零"
    assert t("home.positions_one") == "1 个持仓"
    assert t("home.positions_many", count=4) == "4 个持仓"
    _LOCALE_VAR.set("en")
    assert t("home.positions_many", count=4) == "4 positions"


def test_risk_defense_rationales_localize_and_interpolate() -> None:
    panel = t("risk.defense_panel_rationale", dd_pct="19.7", threshold_pct="15.0", symbol="SGOV")
    assert "19.7%" in panel and "15.0%" in panel and "SGOV" in panel and "防御代理" in panel
    assert "熔断已触发" in t("risk.defense_target_rationale")
    assert "防御代理" in t("risk.defense_diff_rationale")
