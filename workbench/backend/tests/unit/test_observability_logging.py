"""Unit tests for the JSON log formatter + setup helper."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from workbench_api.observability.logging import (
    REQUEST_ID_VAR,
    USER_ID_VAR,
    JSONLogFormatter,
    setup_logging,
)
from workbench_api.settings import Settings


def _format(record: logging.LogRecord) -> dict[str, object]:
    rendered = JSONLogFormatter().format(record)
    return json.loads(rendered)  # type: ignore[no-any-return]


def _make_record(message: str = "hello", level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="workbench.test",
        level=level,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=None,
        exc_info=None,
    )


def test_formatter_emits_reserved_fields_in_order() -> None:
    payload = _format(_make_record())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "workbench.test"
    assert payload["event"] == "hello"
    assert isinstance(payload["timestamp"], str)
    assert payload["timestamp"].endswith("Z")


def test_formatter_emits_request_id_and_user_id_from_contextvars() -> None:
    request_token = REQUEST_ID_VAR.set("req-abc")
    user_token = USER_ID_VAR.set("owner@example.com")
    try:
        payload = _format(_make_record("after auth"))
    finally:
        REQUEST_ID_VAR.reset(request_token)
        USER_ID_VAR.reset(user_token)
    assert payload["request_id"] == "req-abc"
    assert payload["user_id"] == "owner@example.com"


def test_formatter_omits_request_id_when_unset() -> None:
    payload = _format(_make_record())
    assert "request_id" not in payload
    assert "user_id" not in payload


def test_formatter_merges_extra_fields() -> None:
    record = _make_record("with extras")
    record.__dict__["custom_key"] = "custom_value"
    payload = _format(record)
    assert payload["custom_key"] == "custom_value"


def test_setup_logging_replaces_root_handlers(tmp_path: Path) -> None:
    settings = Settings(WORKBENCH_LOG_DIR=str(tmp_path))
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        setup_logging(settings)
        # At least one handler is the JSON-formatted stdout stream + a
        # RotatingFileHandler pointing at the log dir.
        formatter_types = {type(handler.formatter).__name__ for handler in root.handlers}
        assert "JSONLogFormatter" in formatter_types
        file_handlers = [
            h
            for h in root.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename.endswith("app.log")
        ]
        assert file_handlers, "expected a file handler pointing at app.log"
    finally:
        # Restore so subsequent tests do not log JSON to stdout.
        for handler in root.handlers:
            handler.close()
        root.handlers = original_handlers


def test_setup_logging_tolerates_missing_log_dir(tmp_path: Path) -> None:
    # Pointing at a non-existent dir must not raise; the helper degrades
    # to stdout-only.
    settings = Settings(WORKBENCH_LOG_DIR=str(tmp_path / "does-not-exist"))
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        setup_logging(settings)
        assert root.handlers, "stdout handler should still be attached"
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = original_handlers


def test_formatter_handles_non_jsonable_extra() -> None:
    record = _make_record("with object")

    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    record.__dict__["weird"] = Opaque()
    payload = _format(record)
    assert payload["weird"] == "<opaque>"


# Silence pytest's "monkeypatch is unused" warning if we ever want it.
@pytest.fixture(autouse=False)
def _placeholder() -> None:
    return None
