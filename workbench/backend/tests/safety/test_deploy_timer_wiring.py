"""B037-OPS1 — durable timer auto-wiring guards.

Root cause this batch fixes: ``deploy.sh`` has shipped per-timer
install/enable logic since B035, but the VM ``/etc/sudoers.d/deploy-workbench``
only granted 5 service-control lines — not the ``install`` / ``enable --now``
needed for the timer units. So every batch that added a read-only timer
(B035 market-context, B036 advisor, B037 prices) needed a one-time admin
hand-install (see evaluator.md §24).

The durable fix has three parts, each pinned here:

1. A versioned sudoers artifact ``workbench/deploy/sudoers/deploy-workbench``
   (source of truth for the VM drop-in) that keeps the 5 B021 grants and adds
   3 wildcard grants scoped to ``workbench-*`` units in ``/etc/systemd/system/``.
2. ``deploy.sh`` collapses the 3 hardcoded per-timer blocks into ONE loop over
   ``${SYSTEMD_SRC}/workbench-*.timer`` so a new timer needs zero deploy.sh
   changes.
3. Every shipped ``*.timer`` has a sibling ``*.service`` (the loop installs the
   pair).

We grep the artifacts instead of executing them — ``deploy.sh`` expects a
release-dir arg and runs on the VM, and applying sudoers needs root.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SYSTEMD_DIR = REPO_ROOT / "workbench" / "deploy" / "systemd"
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"
SUDOERS_DIR = REPO_ROOT / "workbench" / "deploy" / "sudoers"
SUDOERS_ARTIFACT = SUDOERS_DIR / "deploy-workbench"
# Root-owned install wrapper (security-reviewer tightening, B037-OPS1 §5.1):
# removes the sudoers fnmatch `*`-matches-`/` path-traversal class by taking the
# unit as a bare name and rejecting any '/'.
INSTALL_WRAPPER = SUDOERS_DIR / "workbench-install-unit"
WRAPPER_DEST = "/usr/local/bin/workbench-install-unit"

# The per-timer enable literals that the DRY refactor must have REMOVED — if any
# reappears it means someone re-added a hardcoded block instead of relying on
# the loop (defeating the durable fix).
_PER_TIMER_ENABLE_LITERALS = (
    "enable --now workbench-market-context.timer",
    "enable --now workbench-advisor.timer",
    "enable --now workbench-prices.timer",
)

# The 5 B021 grants that must survive untouched (narrow-sudoers principle).
_LEGACY_GRANTS = (
    "/bin/systemctl restart workbench-backend.service",
    "/bin/systemctl restart workbench-frontend.service",
    "/bin/systemctl status workbench-backend.service",
    "/bin/systemctl status workbench-frontend.service",
    "/bin/systemctl daemon-reload",
)


def _shipped_timers() -> list[str]:
    return sorted(p.name for p in SYSTEMD_DIR.glob("workbench-*.timer"))


def _sudoers_command_lines() -> list[str]:
    """The command portion (after ``NOPASSWD:``) of each grant line."""
    lines: list[str] = []
    for raw in SUDOERS_ARTIFACT.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "NOPASSWD:" not in stripped:
            continue
        lines.append(stripped.split("NOPASSWD:", 1)[1].strip())
    return lines


# --- deploy.sh DRY loop ---------------------------------------------------


def test_deploy_sh_exists() -> None:
    assert DEPLOY_SH.exists(), f"missing {DEPLOY_SH}"


def test_deploy_uses_dry_timer_loop() -> None:
    """deploy.sh installs timers via a single glob loop, not per-timer blocks."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert 'SYSTEMD_SRC="${RELEASE_DIR}/systemd"' in text, (
        "deploy.sh must resolve units at the release layout ${RELEASE_DIR}/systemd"
    )
    assert 'for timer_path in "${SYSTEMD_SRC}"/workbench-*.timer' in text, (
        "deploy.sh must loop over ${SYSTEMD_SRC}/workbench-*.timer (DRY auto-wiring)"
    )
    # The enable call must use the loop variable, applied exactly once.
    assert text.count('enable --now "${timer_unit}"') == 1, (
        "the DRY loop must enable timers via the loop variable exactly once"
    )


def test_deploy_primes_price_snapshot_best_effort() -> None:
    """B058 F002 — deploy.sh primes price_snapshot with the current target
    universe (so the paper mark source is fresh immediately, not after the next
    daily prices timer). Must be best-effort + non-fatal: guarded on
    WORKBENCH_DB_URL and never `set -e`-aborts the deploy on a Tiingo failure."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "workbench_api.prices.cli fetch" in text, (
        "deploy.sh must prime price_snapshot via the prices.cli fetch step"
    )
    # Must resolve workbench_api from the release source (cd into the backend dir,
    # like the alembic step) AND run inside an `if (...)` so a failure warns
    # instead of aborting the `set -euo pipefail` deploy (best-effort, non-fatal).
    assert (
        'if ( cd "${RELEASE_DIR}/backend" && "${VENV_PYTHON}" '
        "-m workbench_api.prices.cli fetch ); then" in text
    ), "the prices prime must cd to the release backend dir and be non-fatal"
    assert "price_snapshot prime failed" in text, (
        "deploy.sh must warn (not hard-fail) when the price_snapshot prime fails"
    )


def test_deploy_installs_via_root_owned_wrapper_not_raw_install() -> None:
    """Security tightening (B037-OPS1 §5.1): the loop must call the root-owned
    wrapper, never `sudo /usr/bin/install` directly (a raw install wildcard in
    sudoers would allow `*`-matches-`/` path traversal)."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert f'INSTALL_UNIT={WRAPPER_DEST}' in text, (
        f"deploy.sh must resolve the install wrapper to {WRAPPER_DEST}"
    )
    assert 'sudo "${INSTALL_UNIT}"' in text, (
        "deploy.sh must install units via the wrapper, not raw `sudo install`"
    )
    assert "sudo /usr/bin/install" not in text, (
        "deploy.sh must NOT call `sudo /usr/bin/install` for unit files — go "
        "through the path-traversal-safe wrapper"
    )


def test_deploy_has_no_residual_per_timer_enable_literals() -> None:
    """No hardcoded per-timer enable block may remain — the loop covers them.
    Guards against a future batch pasting another B035-style block."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    offenders = [lit for lit in _PER_TIMER_ENABLE_LITERALS if lit in text]
    assert not offenders, (
        f"deploy.sh still hardcodes per-timer enable literal(s) {offenders} — "
        "remove them; the workbench-*.timer loop installs every timer (B037-OPS1)."
    )


# --- timer/service pairing (loop precondition) ----------------------------


def test_every_shipped_timer_has_service_sibling() -> None:
    """The loop installs a timer's ``.service`` sibling alongside it; a timer
    with no oneshot service would be a broken unit."""
    missing: list[str] = []
    for timer in _shipped_timers():
        sibling = timer[: -len(".timer")] + ".service"
        if not (SYSTEMD_DIR / sibling).is_file():
            missing.append(f"{timer} -> {sibling}")
    assert not missing, f"timer(s) missing a .service sibling: {missing}"


def test_there_is_at_least_one_shipped_timer() -> None:
    # Sanity: the guard above is vacuous if the glob matches nothing.
    assert _shipped_timers(), "no workbench-*.timer units found under deploy/systemd/"


# --- versioned sudoers artifact ------------------------------------------


def test_sudoers_artifact_exists() -> None:
    assert SUDOERS_ARTIFACT.exists(), (
        f"missing versioned sudoers artifact {SUDOERS_ARTIFACT}"
    )


def test_sudoers_preserves_legacy_five_grants() -> None:
    cmds = _sudoers_command_lines()
    for grant in _LEGACY_GRANTS:
        assert any(grant == c for c in cmds), (
            f"versioned sudoers dropped a B021 grant: {grant!r}"
        )


def test_sudoers_grants_timer_autowiring() -> None:
    cmds = _sudoers_command_lines()
    required = (
        f"{WRAPPER_DEST} * workbench-*.service",
        f"{WRAPPER_DEST} * workbench-*.timer",
        "/bin/systemctl enable --now workbench-*.timer",
    )
    for grant in required:
        assert any(grant == c for c in cmds), (
            f"versioned sudoers missing timer-autowiring grant: {grant!r}"
        )


def test_sudoers_does_not_grant_raw_install() -> None:
    """Installs must go through the wrapper — a raw `/usr/bin/install` wildcard
    grant is exactly the path-traversal hole the wrapper closes."""
    for cmd in _sudoers_command_lines():
        assert not cmd.startswith("/usr/bin/install"), (
            f"sudoers must not grant raw /usr/bin/install (use the wrapper): {cmd!r}"
        )


def test_sudoers_wildcards_cover_every_shipped_timer() -> None:
    """Each shipped timer (and its service sibling) must be matched by the
    sudoers wildcard grants — else deploy.sh's loop would still warn for it."""
    cmds = _sudoers_command_lines()
    enable_grant = "/bin/systemctl enable --now workbench-*.timer"
    install_timer = f"{WRAPPER_DEST} * workbench-*.timer"
    install_service = f"{WRAPPER_DEST} * workbench-*.service"
    assert enable_grant in cmds and install_timer in cmds and install_service in cmds

    # Wrapper grants take the unit as a BARE NAME (last token); the enable grant
    # likewise. fnmatch mirrors sudo's glob (no FNM_PATHNAME: * matches /).
    enable_pat = enable_grant.rsplit(" ", 1)[1]  # workbench-*.timer
    install_timer_pat = install_timer.rsplit(" ", 1)[1]
    install_service_pat = install_service.rsplit(" ", 1)[1]
    for timer in _shipped_timers():
        service = timer[: -len(".timer")] + ".service"
        assert fnmatch.fnmatch(timer, enable_pat), (
            f"sudoers enable wildcard {enable_pat!r} does not cover {timer!r}"
        )
        assert fnmatch.fnmatch(timer, install_timer_pat)
        assert fnmatch.fnmatch(service, install_service_pat)


def test_sudoers_scope_locked_to_workbench_prefix() -> None:
    """Every timer-autowiring grant must stay locked to the workbench- prefix
    and route installs through the wrapper — never an open install or an
    arbitrary systemctl. Guards against future over-broadening."""
    for cmd in _sudoers_command_lines():
        if cmd.startswith(WRAPPER_DEST):
            # last token is the bare unit-name pattern, must be workbench-locked
            unit_pat = cmd.rsplit(" ", 1)[1]
            assert unit_pat.startswith("workbench-"), (
                f"wrapper grant unit pattern not locked to workbench-: {cmd!r}"
            )
        if cmd.startswith("/bin/systemctl enable"):
            unit = cmd.rsplit(" ", 1)[1]
            assert unit.startswith("workbench-"), (
                f"enable grant unit not locked to workbench- prefix: {cmd!r}"
            )


# --- root-owned install wrapper (path-traversal tightening) ---------------


def test_install_wrapper_exists() -> None:
    assert INSTALL_WRAPPER.exists(), f"missing install wrapper {INSTALL_WRAPPER}"


def test_deploy_workflow_ships_sudoers_dir() -> None:
    """The one-time admin sudoers update sources the artifacts from the release
    tree (/srv/workbench/current/sudoers/); the deploy workflow must rsync them
    so that runbook step stays accurate."""
    workflow = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "rsync -a workbench/deploy/sudoers" in text


def test_install_wrapper_rejects_path_separator_and_locks_prefix() -> None:
    """The wrapper is the enforcement point: it must reject any '/' in the unit
    name and lock the name to workbench-*.{service,timer}. We assert the guard
    source is present (the wrapper runs as root on the VM, not in CI)."""
    src = INSTALL_WRAPPER.read_text(encoding="utf-8")
    # rejects a path separator in the unit name
    assert "*/*)" in src, "wrapper must reject a '/' in the unit name"
    # locks the unit-name shape
    assert r"^workbench-[A-Za-z0-9._-]+\.(service|timer)$" in src
    # pins the destination dir + mode and never accepts an arbitrary dest path
    assert "DEST_DIR=/etc/systemd/system" in src
    assert '/usr/bin/install -m 644 "${src}" "${DEST_DIR}/${unit}"' in src
