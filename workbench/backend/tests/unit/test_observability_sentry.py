"""Tests for the optional Sentry init helper."""

from __future__ import annotations

from typing import Any

import pytest

from workbench_api.observability import sentry as sentry_module
from workbench_api.settings import Settings


def test_init_sentry_returns_false_when_dsn_unset() -> None:
    sentry_module._reset_for_tests()
    settings = Settings(SENTRY_DSN=None)
    assert sentry_module.init_sentry(settings) is False


def test_init_sentry_returns_false_for_blank_dsn() -> None:
    sentry_module._reset_for_tests()
    settings = Settings(SENTRY_DSN="   ")
    assert sentry_module.init_sentry(settings) is False


def test_init_sentry_warns_when_dsn_set_but_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sentry-sdk is not in the dev dependency set; the import fails and
    the helper must degrade to a logged warning instead of raising. We
    monkeypatch the module logger directly so the test does not depend on
    pytest's caplog interacting with ``setup_logging`` side-effects from
    sibling tests.
    """

    sentry_module._reset_for_tests()

    captured: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _capture(*args: Any, **kwargs: Any) -> None:
        captured.append((args, kwargs))

    monkeypatch.setattr(sentry_module._logger, "warning", _capture)

    settings = Settings(SENTRY_DSN="https://public@sentry.example/1")
    result = sentry_module.init_sentry(settings)
    assert result is False
    assert captured, "expected a warning call when sentry-sdk is missing"
    rendered = captured[0][0][0] % captured[0][0][1:] if captured[0][0][1:] else captured[0][0][0]
    assert "sentry-sdk not installed" in rendered
