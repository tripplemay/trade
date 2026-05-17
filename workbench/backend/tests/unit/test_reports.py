"""B022 F009 — /api/reports list + detail with markdown table extraction.

Three contracts pinned:

1. Auth gate (anon → 401).
2. List shape — top-N reports under ``WORKBENCH_REPORTS_DIR``, summary
   fields populated. Empty dir → empty list (no 500).
3. Detail extraction — markdown body returned verbatim, GFM tables
   pulled into ``tables[]`` with header + body rows, repo-relative
   links into ``cross_links``.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.observability.active_users import active_users
from workbench_api.services.reports import _extract_tables, get_report
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()


def _authed_client(reports_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(reports_dir),
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "reports-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


SAMPLE_REPORT_MD = """# B019 retune sign-off

See [B015 spec](docs/specs/B015-regime-adaptive-activation-policy-spec.md)
and prior sweep at [B017 base](docs/test-reports/B017-baseline-2026-05-01.md).

## Headline matrix

| strategy | cadence | threshold | changed |
|---|---|---:|:---:|
| B013 | quarterly | 0.11 | True |
| B014 | monthly | 0.13 | False |
| B015 | quarterly | 0.13 | False |
"""


def test_reports_list_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    client = TestClient(app)
    assert client.get("/api/reports").status_code == 401


def test_reports_list_lifts_summaries_from_disk(initialised_db: str, tmp_path: Path) -> None:
    (tmp_path / "B019-retune-signoff-2026-05-15.md").write_text(SAMPLE_REPORT_MD, encoding="utf-8")
    (tmp_path / "B018-stress-review-2026-05-01.md").write_text("# B018", encoding="utf-8")
    client = _authed_client(tmp_path)
    payload = client.get("/api/reports").json()
    slugs = [r["slug"] for r in payload["reports"]]
    assert "B019-retune-signoff" in slugs[0]
    assert payload["reports"][0]["batch"] == "B019"
    assert payload["reports"][0]["kind"] == "signoff"


def test_reports_list_empty_dir_returns_empty_list(
    initialised_db: str, tmp_path: Path
) -> None:
    client = _authed_client(tmp_path / "missing")
    assert client.get("/api/reports").json()["reports"] == []


def test_reports_detail_extracts_tables_and_cross_links(
    initialised_db: str, tmp_path: Path
) -> None:
    (tmp_path / "B019-retune-signoff-2026-05-15.md").write_text(SAMPLE_REPORT_MD, encoding="utf-8")
    client = _authed_client(tmp_path)
    payload = client.get("/api/reports/B019-retune-signoff").json()
    assert payload["slug"] == "B019-retune-signoff"
    assert payload["batch"] == "B019"
    assert payload["body_markdown"] == SAMPLE_REPORT_MD
    # One table with header + 3 body rows.
    assert len(payload["tables"]) == 1
    table = payload["tables"][0]
    assert table["columns"] == ["strategy", "cadence", "threshold", "changed"]
    assert len(table["rows"]) == 3
    # Cross-links pulled out (de-duped, order preserved).
    assert "docs/specs/B015-regime-adaptive-activation-policy-spec.md" in payload["cross_links"]
    assert "docs/test-reports/B017-baseline-2026-05-01.md" in payload["cross_links"]


def test_reports_detail_404_for_unknown_slug(initialised_db: str, tmp_path: Path) -> None:
    (tmp_path / "B019-retune-signoff-2026-05-15.md").write_text("body", encoding="utf-8")
    client = _authed_client(tmp_path)
    assert client.get("/api/reports/this-slug-does-not-exist").status_code == 404


def test_extract_tables_unit_handles_no_tables(tmp_path: Path) -> None:
    """Pure-Python unit test on the parser — empty markdown → []."""

    del tmp_path
    assert _extract_tables("Just prose with no pipes here.") == []


def test_get_report_substring_match(initialised_db: str, tmp_path: Path) -> None:
    """Slug = filename substring also resolves (handy for short links)."""

    (tmp_path / "B019-retune-signoff-2026-05-15.md").write_text("# B019\n", encoding="utf-8")
    detail = get_report("retune-signoff", tmp_path)
    assert detail.slug == "B019-retune-signoff"
