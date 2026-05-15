"""Settings env-var allowlist contract for the workbench backend.

B020 keeps the allowlist empty; every future env var added to ``Settings``
must also be appended to ``ALLOWED_ENV_VARS``. The two assertions below
detect drift in either direction.
"""

from __future__ import annotations

from workbench_api.settings import ALLOWED_ENV_VARS, Settings


def test_allowlist_is_empty_in_b020() -> None:
    assert len(ALLOWED_ENV_VARS) == 0, (
        "B020 contract: workbench backend reads no environment variables. "
        f"Add a deliberate ADR entry before relaxing this. Current: {ALLOWED_ENV_VARS}"
    )


def test_settings_fields_are_subset_of_allowlist() -> None:
    declared_fields = set(Settings.model_fields.keys())
    extras = declared_fields - set(ALLOWED_ENV_VARS)
    assert extras == set(), (
        "Settings declares fields outside ALLOWED_ENV_VARS — add them to the "
        f"allowlist and re-check the boundary justification. Extras: {extras}"
    )
