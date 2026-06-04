"""Settings env-var allowlist contract for the workbench backend.

``ALLOWED_ENV_VARS`` and ``Settings`` model fields must stay in sync. Either
side drifting silently widens the boundary and is rejected here.

Expected contents are also pinned by name: B021 F001 introduces exactly two
entries — NextAuth's shared signing secret and the single-user allowlist
email. New env vars in subsequent features must update this set together
with the ``Settings`` model.
"""

from __future__ import annotations

from workbench_api.settings import ALLOWED_ENV_VARS, Settings

EXPECTED_ALLOWLIST: frozenset[str] = frozenset(
    {
        "NEXTAUTH_SECRET",
        "ALLOWED_USER_EMAIL",
        "WORKBENCH_DB_URL",
        "SENTRY_DSN",
        "WORKBENCH_BACKUP_LOG",
        "WORKBENCH_LOG_DIR",
        "WORKBENCH_REPORTS_DIR",
        "WORKBENCH_RUNS_DIR",
        # B027 F001 — Tiingo Starter API key for real-market-data ingest.
        "TIINGO_API_KEY",
        # B029 F001 — SEC EDGAR contact email for required User-Agent
        # header (永久边界 (h); ban IP without it).
        "SEC_EDGAR_CONTACT_EMAIL",
        # B031 F001 — aigc-gateway API key for the unified LLM gateway
        # (Stream 3.A / Phase 2 starting infra; v0.9.30 §12.9 four-
        # place wiring + permanent boundaries (l) routing and
        # (m) ¥1500 cap enforced inside gateway/cost-guard code).
        "AIGC_GATEWAY_API_KEY",
        # B035 F001 — FRED + Alpha Vantage API keys for the market-context
        # series (Stream 2.C; v0.9.30 §12.9 four-place wiring).
        "FRED_API_KEY",
        "ALPHAVANTAGE_API_KEY",
    }
)


def test_allowlist_matches_expected_set() -> None:
    assert ALLOWED_ENV_VARS == EXPECTED_ALLOWLIST, (
        "Allowlist drifted from the documented contract. Update this test "
        f"intentionally when a feature widens the surface. Expected: "
        f"{sorted(EXPECTED_ALLOWLIST)}; got: {sorted(ALLOWED_ENV_VARS)}."
    )


def test_settings_fields_are_subset_of_allowlist() -> None:
    declared_fields = set(Settings.model_fields.keys())
    extras = declared_fields - set(ALLOWED_ENV_VARS)
    assert extras == set(), (
        "Settings declares fields outside ALLOWED_ENV_VARS — add them to the "
        f"allowlist and re-check the boundary justification. Extras: {extras}"
    )


def test_settings_fields_cover_full_allowlist() -> None:
    """Every allowlisted env var must have a typed field; otherwise the var
    is read by ``os.environ`` outside the typed surface and bypasses validation.
    """

    declared_fields = set(Settings.model_fields.keys())
    missing = set(ALLOWED_ENV_VARS) - declared_fields
    assert missing == set(), (
        "Allowlist entries lack matching Settings fields — add typed fields "
        f"so consumers go through the validated surface. Missing: {missing}"
    )
