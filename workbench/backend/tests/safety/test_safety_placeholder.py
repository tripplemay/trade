"""Placeholder so the CI ``pytest tests/safety`` step succeeds in B020 F002.

B020 F003 replaces this module with the real boundary-violation guards
(``test_no_broker_sdk_imports.py``, ``test_no_paper_or_live_urls.py``,
``test_settings_env_allowlist.py``). Leaving the placeholder in place lets the
dedicated safety step run from F002 onwards so CI exercise of the new test
directory begins before the real assertions land.
"""

from __future__ import annotations

from pathlib import Path

SAFETY_DIR = Path(__file__).resolve().parent


def test_safety_directory_present() -> None:
    """Asserts the directory layout B020 F003 will populate."""

    assert SAFETY_DIR.is_dir()
    assert SAFETY_DIR.name == "safety"
