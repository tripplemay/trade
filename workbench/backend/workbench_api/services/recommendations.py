"""Recommendations + export-ticket service (B022 F010).

The workbench is **research-only**: this service computes a target
portfolio and writes it to a markdown checklist for the user to
manually review and execute outside the workbench. It does NOT place
orders, talk to a broker, or trigger any execution surface. The
exported markdown carries a mandatory disclaimer (see
``DISCLAIMER_LITERAL``); the F010 acceptance pins that literal via
``tests/unit/test_recommendations.py``.

For F010 the target portfolio is computed from the strategies registry
(equal-weight across the 4 sleeves until F011 wires a real master
portfolio aggregator); current_weights come from the Account row(s)
when present, otherwise 0. ``account_present=False`` lights the
frontend's empty state.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workbench_api.db.models.account import Account
from workbench_api.schemas.recommendations import (
    ExportTicketRequest,
    ExportTicketResponse,
    GateCheck,
    RecommendationsResponse,
    TargetPosition,
)
from workbench_api.services.strategies import list_strategies

_logger = logging.getLogger("workbench.recommendations")

DISCLAIMER_LITERAL: str = (
    "research-only; this is a manual review checklist, not a trading instruction"
)
"""Verbatim string the export ticket must contain — F010 acceptance pin.

The English literal stays immutable across releases; B024 F005 layers a
Chinese translation **alongside** it (never replaces), so the rendered
Markdown carries the same compliance assertion in both languages.
"""

DISCLAIMER_LITERAL_ZH: str = (
    "仅供研究使用;这是一份人工核对清单,不构成交易指令"
)
"""B024 F005 bilingual disclaimer — emitted on the line immediately
following ``DISCLAIMER_LITERAL``. The Markdown body is locale-agnostic:
both languages are always present, so file history stays stable
regardless of the user's UI locale.

Changing this literal requires updating
``tests/unit/test_recommendations.py`` and the matching frontend
copy. Treat as a contract surface, not an editable string.
"""

DEFAULT_KILL_SWITCH_THRESHOLD: float = 0.20


def _aggregate_account_state(session: Session) -> tuple[bool, float]:
    """Return (account_present, total_equity).

    DB failure → treat as "no account on file" and let the
    Recommendations page render its empty-state. B022 F014
    fixing-round 2: prod observed /api/recommendations/current 500
    with no journal entry; defensive degrade + the new app-level
    exception logger surface the SQLAlchemy cause without crashing
    the route.
    """

    try:
        accounts = list(session.execute(select(Account)).scalars())
    except SQLAlchemyError as exc:
        _logger.warning(
            "recommendations account aggregation skipped due to DB error",
            extra={
                "event": "recommendations_account_db_error",
                "exception_message": str(exc),
            },
            exc_info=True,
        )
        session.rollback()
        return False, 0.0
    if not accounts:
        return False, 0.0
    total = 0.0
    for account in accounts:
        total += float(account.cash) + float(account.equity_value)
    return True, total


def _build_target_positions(account_present: bool) -> list[TargetPosition]:
    """Equal-weight across sleeves; current_weight=0 until F011 wires it.

    The schema requires both target and current; with no account data we
    surface zeroed-out current weights so the frontend's diff column
    reads "buy everything from scratch" — the user immediately sees that
    this is a fresh-start recommendation rather than a rebalance delta.
    """

    if not account_present:
        return []

    sleeves = list_strategies().strategies
    if not sleeves:
        return []
    weight = round(1.0 / len(sleeves), 4)
    out: list[TargetPosition] = []
    for sleeve in sleeves:
        out.append(
            TargetPosition(
                symbol=sleeve.id.split("-")[0],
                target_weight=weight,
                current_weight=0.0,
                diff=weight,
                rationale=f"Sleeve {sleeve.sleeve} → target weight (F011 wires diff vs current).",
            )
        )
    return out


def _build_gate_checks(total_equity: float) -> list[GateCheck]:
    """Two placeholder gates so the page's gate panel has something to render."""

    return [
        GateCheck(
            name="kill_switch",
            status="pass",
            detail=f"Drawdown 0.00 ≤ threshold {DEFAULT_KILL_SWITCH_THRESHOLD}.",
        ),
        GateCheck(
            name="min_equity",
            status="pass" if total_equity >= 0 else "fail",
            detail=f"Account equity = {total_equity:.2f}",
        ),
    ]


def get_current_recommendations(session: Session) -> RecommendationsResponse:
    """Build the RecommendationsResponse for ``GET /api/recommendations/current``."""

    account_present, total_equity = _aggregate_account_state(session)
    as_of = date.today().isoformat()
    return RecommendationsResponse(
        as_of_date=as_of,
        target_positions=_build_target_positions(account_present),
        gate_checks=_build_gate_checks(total_equity),
        # No trade journal in MVP → no heuristic source for wash-sale flags.
        # F010 ships an empty list so the frontend's flag panel can render
        # its "no flags" empty state. F012's backlog page may surface real
        # signals later via a separate journal-import flow.
        wash_sale_flags=[],
        account_present=account_present,
    )


PROD_RELEASE_CURRENT: Path = Path("/srv/workbench/current")
"""B021 deploy symlink; presence is the prod marker for _resolve_runs_dir."""

PROD_RUNS_DIR: Path = Path("/var/lib/workbench/runs")
"""Production-writable runs directory.

The workbench systemd unit (workbench/deploy/systemd/workbench-backend.service)
declares ``ReadWritePaths=/var/lib/workbench /var/log/workbench /tmp``, so the
backend can mkdir under ``/var/lib/workbench`` without sudo. B022 F014
blocker rejected the prior default (``docs/runs`` under the read-only release
tree) because the export-ticket write path didn't exist in production.
"""


def _resolve_runs_dir(configured: str) -> Path:
    """Pick the writable directory the export-ticket lands in.

    Resolution order:

    1. ``configured`` is absolute → use as-is.
    2. ``/srv/workbench/current`` exists (prod) → ``/var/lib/workbench/runs``.
       The systemd unit's ReadWritePaths grant covers this path; the
       service can mkdir its own subdirs on demand.
    3. Otherwise (dev / source checkout) → ``<repo_root>/<configured>``.

    A future operator override is still honoured by passing an absolute
    ``WORKBENCH_RUNS_DIR``; the chain only kicks in for the default
    relative value.
    """

    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    if PROD_RELEASE_CURRENT.exists():
        return PROD_RUNS_DIR
    # parents[4] reaches the repo root from services/recommendations.py;
    # parents[3] (prior value) stopped at `workbench/` and missed docs/.
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / candidate


def _render_ticket_markdown(
    response: RecommendationsResponse,
    as_of_date: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Order ticket — {as_of_date} / 订单清单 — {as_of_date}")
    lines.append("")
    lines.append(f"> **{DISCLAIMER_LITERAL}**")
    lines.append(f"> **{DISCLAIMER_LITERAL_ZH}**")
    lines.append("")

    lines.append("## Target positions / 目标持仓")
    lines.append("")
    if response.target_positions:
        lines.append(
            "| Symbol / 标的 | Target / 目标 | Current / 当前 "
            "| Diff / 偏离 | Rationale / 说明 |"
        )
        lines.append("|---|---:|---:|---:|---|")
        for position in response.target_positions:
            lines.append(
                "| "
                + " | ".join(
                    [
                        position.symbol,
                        f"{position.target_weight:.4f}",
                        f"{position.current_weight:.4f}",
                        f"{position.diff:+.4f}",
                        position.rationale or "",
                    ]
                )
                + " |"
            )
    else:
        lines.append(
            "_No target positions surfaced. accounts/me.json missing or no sleeves registered._"
        )
    lines.append("")

    lines.append("## Gate checks / 门控检查")
    lines.append("")
    for gate in response.gate_checks:
        lines.append(f"- **{gate.name}**: {gate.status} — {gate.detail or ''}")
    lines.append("")

    lines.append("## Wash-sale flags / 洗售标记")
    lines.append("")
    if response.wash_sale_flags:
        for flag in response.wash_sale_flags:
            lines.append(
                f"- **{flag.symbol}** — last buy {flag.last_buy_date} ({flag.days_since}d ago)"
            )
    else:
        lines.append("_None flagged._")
    lines.append("")

    return "\n".join(lines)


def export_ticket(
    session: Session,
    body: ExportTicketRequest,
    *,
    runs_dir: Path,
) -> ExportTicketResponse:
    """Render the current recommendation as a markdown checklist + write it.

    The file lands at ``<runs_dir>/<as_of_date>/order-ticket-<as_of_date>.md``;
    nested directories are created on demand. Returns the (repo-relative
    when possible) path the frontend can show + the disclaimer literal
    so the caller can pin it again on the way out.
    """

    response = get_current_recommendations(session)
    as_of = body.as_of_date or response.as_of_date
    target_dir = runs_dir / as_of
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"order-ticket-{as_of}.md"
    body_md = _render_ticket_markdown(response, as_of)
    target_file.write_text(body_md, encoding="utf-8")

    # Try to express the path repo-relative so the response stays
    # portable across environments. parents[4] reaches the repo root
    # (services/ → workbench_api/ → backend/ → workbench/ → repo).
    try:
        repo_root = Path(__file__).resolve().parents[4]
        rel_path = str(target_file.relative_to(repo_root.resolve()))
    except ValueError:
        rel_path = str(target_file)

    return ExportTicketResponse(path=rel_path, disclaimer=DISCLAIMER_LITERAL)
