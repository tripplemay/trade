"""Tests for the active-user registry."""

from __future__ import annotations

from workbench_api.observability.active_users import ActiveUserRegistry


def test_touch_and_count_within_window() -> None:
    registry = ActiveUserRegistry(window_seconds=10)
    registry.touch("a@example.com", now=100.0)
    registry.touch("b@example.com", now=105.0)
    assert registry.count(now=108.0) == 2


def test_count_prunes_stale_entries() -> None:
    registry = ActiveUserRegistry(window_seconds=10)
    registry.touch("old@example.com", now=100.0)
    registry.touch("new@example.com", now=200.0)
    assert registry.count(now=205.0) == 1


def test_repeated_touch_keeps_user_active() -> None:
    registry = ActiveUserRegistry(window_seconds=10)
    registry.touch("a@example.com", now=100.0)
    registry.touch("a@example.com", now=200.0)
    assert registry.count(now=205.0) == 1


def test_clear_drops_everything() -> None:
    registry = ActiveUserRegistry(window_seconds=10)
    registry.touch("a@example.com", now=100.0)
    registry.clear()
    assert registry.count(now=101.0) == 0


def test_singleton_is_independent_per_process() -> None:
    from workbench_api.observability.active_users import active_users

    active_users.clear()
    active_users.touch("singleton@example.com")
    assert active_users.count() >= 1
    active_users.clear()
