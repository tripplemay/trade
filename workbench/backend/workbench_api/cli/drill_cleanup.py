"""``workbench-drill-cleanup`` — delete pre-cutoff drill rows from the
execution-domain tables (B052 F001).

Why this exists: L2 acceptance drills across past batches wrote snapshots,
tickets and fills into the **production** DB through the same UI/API paths a
real user uses (that is the point of a drill — and why no ``source`` marker
can distinguish them). The tables are append-only history, so "the drill PUT
the account back afterwards" still left every intermediate row behind —
including the BL-B023-S2 red-state drill's artificial ~$126k NAV peak.
``nav_history.reconstruct_nav_history`` rebuilds the NAV series over ALL
snapshots and ``master_drawdown`` is peak-to-latest, so a real user's $50k
account read as a fake 59.60% drawdown: kill-switch tripped, the ticket
defaulted to defensive, and the risk explanation cited the fake number. That
never self-heals (the fake peak stays the historical max). The mechanism is
correct — the data is wrong — so the fix is deletion, not an algorithm change.

Cutoff semantics (``--keep-from <snapshot_id | ISO date/datetime>``): rows
strictly BEFORE the cutoff are deleted; the cutoff row itself is kept. The
per-table axis differs deliberately:

* ``account_snapshot``  — ``snapshot_at``: the axis nav_history sorts by (the
  polluted series), and what a snapshot id resolves to.
* ``order_ticket`` / ``fill_journal_entry`` — ``created_at``: when the row was
  actually written. A real user fill entered AFTER the cutoff with a backdated
  ``filled_at`` (e.g. importing an old broker CSV) must never be swept; drill
  rows were all *written* during drills, before the user's real data starts.
* ``risk_explanation_snapshot`` — ALL existing rows: every explanation
  generated before the cleanup was computed from the polluted history. The
  daily 03:30 timer regenerates; run
  ``sudo systemctl start workbench-risk-explanation.service`` to do it now.

Safety posture:

* **Default is dry-run** — a complete preview of every row that would be
  deleted AND every row that would be kept; nothing is written.
* ``--apply`` performs the deletion in one transaction.
* §12.11.1 — this CLI writes the production DB, so ``main()`` calls
  :func:`require_production_db` before opening any session (missing env →
  loud non-zero exit, never the scratch DB).
* §12.10.2 — pure DB operations; imports no ``trade``-package code.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.models.risk_explanation_snapshot import RiskExplanationSnapshot
from workbench_api.db.require_production_db import (
    ScratchDatabaseError,
    require_production_db,
)

REGENERATE_HINT = (
    "risk explanations were deleted — regenerate now with "
    "`sudo systemctl start workbench-risk-explanation.service` "
    "(otherwise the daily 03:30 timer rebuilds them)."
)


class CutoffResolutionError(ValueError):
    """``--keep-from`` is neither an ISO date/datetime nor a known snapshot id."""


@dataclass(frozen=True, slots=True)
class CleanupPlan:
    """Everything the cutoff splits, resolved up-front so dry-run and apply
    print the exact same preview."""

    cutoff: datetime
    snapshots_delete: list[AccountSnapshot]
    snapshots_keep: list[AccountSnapshot]
    tickets_delete: list[OrderTicket]
    tickets_keep: list[OrderTicket]
    fills_delete: list[FillJournalEntry]
    fills_keep: list[FillJournalEntry]
    explanations_delete: list[RiskExplanationSnapshot]


def resolve_cutoff(session: Session, keep_from: str) -> datetime:
    """Resolve ``--keep-from`` to a cutoff datetime.

    An ISO date (``2026-06-10`` → midnight) or datetime is used as-is;
    anything else is treated as an ``account_snapshot`` id whose
    ``snapshot_at`` becomes the cutoff. Unknown id → loud failure.
    """

    try:
        return datetime.fromisoformat(keep_from)
    except ValueError:
        pass
    snapshot = session.get(AccountSnapshot, keep_from)
    if snapshot is None:
        raise CutoffResolutionError(
            f"--keep-from {keep_from!r} is neither an ISO date/datetime nor an "
            "existing account_snapshot id. Run a dry-run with an approximate "
            "date to list snapshot ids, then pick the first REAL one."
        )
    return snapshot.snapshot_at


def build_plan(session: Session, cutoff: datetime) -> CleanupPlan:
    """Pure reads — split each table into delete/keep by the cutoff."""

    snapshots = list(
        session.execute(
            select(AccountSnapshot).order_by(AccountSnapshot.snapshot_at)
        ).scalars()
    )
    tickets = list(
        session.execute(select(OrderTicket).order_by(OrderTicket.created_at)).scalars()
    )
    fills = list(
        session.execute(
            select(FillJournalEntry).order_by(FillJournalEntry.created_at)
        ).scalars()
    )
    explanations = list(
        session.execute(
            select(RiskExplanationSnapshot).order_by(RiskExplanationSnapshot.created_at)
        ).scalars()
    )
    return CleanupPlan(
        cutoff=cutoff,
        snapshots_delete=[s for s in snapshots if s.snapshot_at < cutoff],
        snapshots_keep=[s for s in snapshots if s.snapshot_at >= cutoff],
        tickets_delete=[t for t in tickets if t.created_at < cutoff],
        tickets_keep=[t for t in tickets if t.created_at >= cutoff],
        fills_delete=[f for f in fills if f.created_at < cutoff],
        fills_keep=[f for f in fills if f.created_at >= cutoff],
        explanations_delete=explanations,
    )


def _snapshot_line(s: AccountSnapshot) -> str:
    raw = s.positions if isinstance(s.positions, list) else []
    symbols = [
        f"{e.get('symbol')}×{e.get('shares')}"
        for e in raw
        if isinstance(e, dict) and e.get("symbol")
    ]
    positions = ", ".join(symbols) if symbols else "no positions (pure cash)"
    return (
        f"  snapshot {s.id}  snapshot_at={s.snapshot_at}  source={s.source}  "
        f"cash={float(s.cash):.2f}  [{positions}]"
    )


def _ticket_line(t: OrderTicket) -> str:
    return (
        f"  ticket {t.id}  ticket_date={t.ticket_date}  status={t.status}  "
        f"created_at={t.created_at}"
    )


def _fill_line(f: FillJournalEntry) -> str:
    return (
        f"  fill {f.id}  ticket={f.ticket_id}  {f.side} {f.symbol} "
        f"{float(f.shares):g} @ {float(f.fill_price):.4f}  "
        f"filled_at={f.filled_at}  created_at={f.created_at}"
    )


def _explanation_line(r: RiskExplanationSnapshot) -> str:
    return (
        f"  risk_explanation {r.id}  as_of={r.as_of_date}  state={r.state}  "
        f"master_dd={float(r.master_dd):.4f}"
    )


def render_plan(plan: CleanupPlan, *, apply: bool) -> str:
    """The full preview both modes print — delete section, keep section,
    per-table counts, and the mode footer."""

    lines: list[str] = []
    lines.append(f"cutoff = {plan.cutoff}  (rows strictly before this are deleted)")
    lines.append("")
    lines.append(
        f"DELETE — account_snapshot (snapshot_at < cutoff): {len(plan.snapshots_delete)}"
    )
    lines.extend(_snapshot_line(s) for s in plan.snapshots_delete)
    lines.append(f"DELETE — order_ticket (created_at < cutoff): {len(plan.tickets_delete)}")
    lines.extend(_ticket_line(t) for t in plan.tickets_delete)
    lines.append(
        f"DELETE — fill_journal_entry (created_at < cutoff): {len(plan.fills_delete)}"
    )
    lines.extend(_fill_line(f) for f in plan.fills_delete)
    lines.append(
        "DELETE — risk_explanation_snapshot (ALL — stale, computed from the "
        f"polluted history): {len(plan.explanations_delete)}"
    )
    lines.extend(_explanation_line(r) for r in plan.explanations_delete)
    lines.append("")
    lines.append(f"KEEP — account_snapshot: {len(plan.snapshots_keep)}")
    lines.extend(_snapshot_line(s) for s in plan.snapshots_keep)
    lines.append(f"KEEP — order_ticket: {len(plan.tickets_keep)}")
    lines.extend(_ticket_line(t) for t in plan.tickets_keep)
    lines.append(f"KEEP — fill_journal_entry: {len(plan.fills_keep)}")
    lines.extend(_fill_line(f) for f in plan.fills_keep)
    lines.append("")
    if apply:
        lines.append("mode: APPLY — deleting the rows listed above.")
    else:
        lines.append(
            "mode: DRY-RUN — nothing was deleted. Confirm the boundary above "
            "(the first KEEP snapshot must be the first REAL one), then re-run "
            "with --apply."
        )
    return "\n".join(lines)


def apply_plan(session: Session, plan: CleanupPlan) -> dict[str, int]:
    """Delete every planned row in the caller's transaction (no commit here)."""

    for row in (
        *plan.snapshots_delete,
        *plan.tickets_delete,
        *plan.fills_delete,
        *plan.explanations_delete,
    ):
        session.delete(row)
    session.flush()
    return {
        "account_snapshot": len(plan.snapshots_delete),
        "order_ticket": len(plan.tickets_delete),
        "fill_journal_entry": len(plan.fills_delete),
        "risk_explanation_snapshot": len(plan.explanations_delete),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workbench-drill-cleanup",
        description=(
            "Delete pre-cutoff drill rows from account_snapshot / order_ticket / "
            "fill_journal_entry (+ all stale risk_explanation_snapshot rows). "
            "Dry-run by default; --apply to delete."
        ),
    )
    parser.add_argument(
        "--keep-from",
        required=True,
        help=(
            "Boundary of REAL data: an account_snapshot id or an ISO "
            "date/datetime. Rows strictly before it are deleted; it is kept."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Without this flag the CLI only previews.",
    )
    args = parser.parse_args(argv)

    # §12.11.1 — this CLI writes the production DB: hard-fail before any
    # session when WORKBENCH_DB_URL would silently resolve to the dev scratch
    # fallback (B047 re-verify root cause family).
    try:
        require_production_db(entrypoint="workbench_api.cli.drill_cleanup")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        try:
            cutoff = resolve_cutoff(session, args.keep_from)
        except CutoffResolutionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        plan = build_plan(session, cutoff)
        print(render_plan(plan, apply=args.apply))
        if not args.apply:
            return 0
        counts = apply_plan(session, plan)
        session.commit()
        summary = ", ".join(f"{table}={n}" for table, n in counts.items())
        print(f"deleted: {summary}")
        if counts["risk_explanation_snapshot"]:
            print(REGENERATE_HINT)
        return 0
    except Exception as exc:  # noqa: BLE001 — surface the failure on the CLI
        session.rollback()
        print(f"drill cleanup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
