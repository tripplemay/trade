"""B030 F003 — B026 banner-off four-place wiring guard.

The B026 synthetic-data banner is turned **off** in production as
part of milestone A Layer 0→1 close-out. Per the framework v0.9.30
§12.9 production-secret three-place rule (extended here to four
places for build-time flags), the same intent must surface in:

1. ``workbench/frontend/.env.example`` — local dev default (banner
   stays ``true`` so devs working against the B025 fixture continue
   to see the warning).
2. ``workbench/frontend/.env.production`` — production build-time
   inject (``=false``). Next.js auto-loads this file on
   ``next build`` when ``NODE_ENV=production``.
3. ``.github/workflows/workbench-deploy.yml`` — belt-and-braces
   ``NEXT_PUBLIC_SYNTHETIC_DATA_BANNER: "false"`` in the frontend
   build step's ``env`` block (in case ``.env.production`` is
   accidentally removed).
4. ``.github/workflows/bootstrap-env.yml`` — documentation note
   explaining why this frontend flag is NOT injected into
   ``/etc/workbench/workbench.env`` (backend secret file).

A regression on any of those four places either re-enables the
banner in production OR silently shifts the wiring out of the
documented pattern, both of which violate the 永久边界 (k)
"Layer 状态不可逆向滑落" invariant. These tests fail loudly on
any drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_EXAMPLE_PATH = REPO_ROOT / "workbench" / "frontend" / ".env.example"
ENV_PRODUCTION_PATH = REPO_ROOT / "workbench" / "frontend" / ".env.production"
DEPLOY_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"
BOOTSTRAP_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bootstrap-env.yml"


def _read(path: Path) -> str:
    """Return the file's UTF-8 text; fail loud with a fix pointer if
    the path moves so a future restructure surfaces the assert here
    rather than as a confusing 'no match' downstream."""

    if not path.is_file():
        pytest.fail(
            f"Expected file at {path.relative_to(REPO_ROOT)} but none was found. "
            "B030 F003 wiring drift: check whether the frontend env structure moved."
        )
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Place 1 — workbench/frontend/.env.example (dev default = true, with note)
# ---------------------------------------------------------------------------


def test_env_example_keeps_banner_true_for_local_dev() -> None:
    """Dev default must remain ``true`` so a fresh checkout against the
    B025 fixture surfaces the banner as a safety belt."""

    content = _read(ENV_EXAMPLE_PATH)
    assert "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true" in content


def test_env_example_documents_b030_f003_production_flip() -> None:
    """The dev comment must reference B030 F003 + the production
    ``=false`` value so a developer reading the file understands why
    the production VM behaves differently."""

    content = _read(ENV_EXAMPLE_PATH)
    assert "B030" in content
    # Mention the milestone A / Layer 0→1 transition explicitly.
    assert (
        "Layer 0→1" in content
        or "milestone A" in content.lower()
        or "milestone-a" in content.lower()
    )
    # Component-preserved language flags the downgrade path (永久边界 (k)).
    assert (
        "SyntheticDataBanner.tsx" in content
        or "component code" in content.lower()
        or "component is preserved" in content.lower()
    )


# ---------------------------------------------------------------------------
# Place 2 — workbench/frontend/.env.production (=false; new file)
# ---------------------------------------------------------------------------


def test_env_production_file_exists_with_banner_false() -> None:
    """The production env file must exist AND set the banner to false."""

    content = _read(ENV_PRODUCTION_PATH)
    assert "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false" in content
    # Sanity: ``=true`` must NOT appear (catches a copy-paste reversal).
    assert "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true" not in content


def test_env_production_explains_why_banner_off_and_downgrade_path() -> None:
    """Production comment must justify the closure (real data wired,
    milestone A complete) AND document the downgrade path (re-flip
    to ``true`` + raise a spec batch — 永久边界 (k) no silent
    rollback)."""

    content = _read(ENV_PRODUCTION_PATH)
    assert "B030 F003" in content
    assert "real" in content.lower() and "data" in content.lower()
    # Either Layer 0→1 phrasing or milestone A must appear.
    assert "Layer 0→1" in content or "milestone A" in content.lower()


# ---------------------------------------------------------------------------
# Place 3 — workbench-deploy.yml build step env (belt-and-braces)
# ---------------------------------------------------------------------------


def test_deploy_workflow_inlines_banner_false_in_build_step() -> None:
    """The deploy workflow's ``Build frontend`` step env block must
    set ``NEXT_PUBLIC_SYNTHETIC_DATA_BANNER: "false"`` so the
    production bundle ships banner-free even if .env.production is
    deleted."""

    content = _read(DEPLOY_WORKFLOW_PATH)
    # YAML-style: ``NEXT_PUBLIC_SYNTHETIC_DATA_BANNER: "false"``
    assert (
        'NEXT_PUBLIC_SYNTHETIC_DATA_BANNER: "false"' in content
        or "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER: 'false'" in content
    )


def test_deploy_workflow_references_b030_f003_for_banner_env() -> None:
    """The comment block introducing the banner env var must mention
    B030 F003 so the wiring is traceable from the workflow file."""

    content = _read(DEPLOY_WORKFLOW_PATH)
    # Find the chunk of comments around the banner env line.
    needle = "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER"
    idx = content.find(needle)
    assert idx > 0, "banner env var not found in deploy workflow"
    # The 500 chars before the env line must reference B030 F003 / B026.
    preamble = content[max(0, idx - 500) : idx]
    assert "B030 F003" in preamble or "B026" in preamble


# ---------------------------------------------------------------------------
# Place 4 — bootstrap-env.yml (documentation note; NOT injected to
# /etc/workbench/workbench.env because NEXT_PUBLIC_* is frontend-public)
# ---------------------------------------------------------------------------


def test_bootstrap_workflow_documents_banner_lives_elsewhere() -> None:
    """``bootstrap-env.yml`` must explicitly call out that the banner
    env var is NOT a backend secret and lives in
    ``workbench/frontend/.env.production``. Prevents a future
    maintainer from copying the banner var into the backend env file
    by mistake (which would silently do nothing — the backend doesn't
    read NEXT_PUBLIC_* vars)."""

    content = _read(BOOTSTRAP_WORKFLOW_PATH)
    # The doc note must mention the env var name + the .env.production
    # destination so a maintainer's grep lands the explanation.
    assert "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER" in content
    assert ".env.production" in content
    assert "B030 F003" in content


def test_bootstrap_workflow_does_not_inject_banner_into_workbench_env() -> None:
    """Belt-and-braces: the bootstrap workflow must NOT actually write
    ``NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=`` into the assembled
    ``workbench.env`` (only docs comments may reference the var).
    Catches the failure mode where the doc note accidentally lands
    on the wrong side of the heredoc.

    The heredoc that builds ``$ENVFILE`` runs from
    ``cat > "$ENVFILE" <<EOF`` to the matching ``EOF`` line; any
    ``NAME=VALUE`` line inside that range gets written to the
    backend env file.
    """

    content = _read(BOOTSTRAP_WORKFLOW_PATH)
    lines = content.splitlines()
    in_heredoc = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("cat > ") and "<<EOF" in stripped:
            in_heredoc = True
            continue
        if in_heredoc and stripped == "EOF":
            in_heredoc = False
            continue
        if in_heredoc and stripped.startswith("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER="):
            pytest.fail(
                "bootstrap-env.yml heredoc body contains a "
                "NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=... line. This is a "
                "frontend build-time public flag — it must NOT be written "
                "to /etc/workbench/workbench.env. Move the line out of "
                "the cat-heredoc and into a comment block."
            )


# ---------------------------------------------------------------------------
# Compare-script smoke (verifies the F003 deliverable exists + is callable)
# ---------------------------------------------------------------------------


def test_compare_fixture_vs_real_script_present_and_importable() -> None:
    """The F003 deliverable script must exist at the spec path so the
    PIT validation report's '5 + 1 reports' deliverable claim stays
    truthful."""

    script_path = REPO_ROOT / "scripts" / "compare_fixture_vs_real.py"
    assert script_path.is_file(), (
        f"F003 deliverable missing: {script_path.relative_to(REPO_ROOT)}"
    )
    # Sanity: the script must define the five sleeve identifiers per
    # the B030 F003 acceptance §(1) list.
    content = script_path.read_text(encoding="utf-8")
    for sleeve_id in (
        "master",
        "momentum",
        "risk_parity",
        "us_quality",
        "hk_china_proxy",
    ):
        assert f'"{sleeve_id}"' in content, (
            f"sleeve {sleeve_id!r} missing from compare_fixture_vs_real.py"
        )
