"""Ticket service (B023 F003).

A ticket is the user-readable manual-execution checklist generated from
the current position-diff. The workbench writes Markdown to
``<runs_dir>/<ticket_date>/order-ticket-<ticket_id>.md`` and inserts an
``order_ticket`` row; status transitions (generated → executed | voided)
happen via the F005 reconcile route or this module's ``void_ticket``.

The workbench is research-only. Nothing in this module talks to a
broker; the Markdown body carries the literal disclaimer
``DISCLAIMER_LITERAL`` (pinned to the same string the recommendations
service already exports — F010 acceptance pin).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.repositories.order_ticket import OrderTicketRepository
from workbench_api.i18n import t
from workbench_api.schemas.tickets import (
    GenerateTicketRequest,
    GenerateTicketResponse,
    TicketDetail,
    TicketListResponse,
    TicketSummary,
)
from workbench_api.services.execution import get_position_diff
from workbench_api.services.recommendations import (
    DISCLAIMER_LITERAL,
    DISCLAIMER_LITERAL_ZH,
    get_current_recommendations,
)

_logger = logging.getLogger("workbench.tickets")

# Re-export so route handlers + tests can reach the literal without
# pulling in the recommendations service directly.
__all__ = [
    "DISCLAIMER_LITERAL",
    "DISCLAIMER_LITERAL_ZH",
    "generate_ticket",
    "get_ticket_detail",
    "list_tickets",
    "render_ticket_markdown",
    "void_ticket",
]


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_shares(value: float) -> str:
    return f"{value:,.4f}".rstrip("0").rstrip(".") or "0"


def render_ticket_markdown(
    *,
    ticket_id: str,
    ticket_date: date,
    snapshot_date: date,
    cash_before: float,
    nav: float,
    diff_rows: list[dict[str, Any]],
    wash_sale_flags: list[dict[str, Any]],
    notes: str | None = None,
) -> str:
    """Render the F003 Markdown ticket template.

    All fields are passed in as plain dicts/primitives so this function
    is trivially testable without depending on the full Pydantic
    response shape. Acceptance test ``test_tickets.py`` asserts the
    disclaimer literal + the "Trades to place" + "After execution
    checklist" headings appear in the rendered body.
    """

    t_plus_one = ticket_date + timedelta(days=1)
    trades = [
        row for row in diff_rows if float(cast(Any, row.get("delta_shares") or 0.0)) != 0.0
    ]

    lines: list[str] = []
    lines.append(
        f"# Order Ticket — {ticket_date.isoformat()} "
        f"(T+1 execution day: {t_plus_one.isoformat()})"
    )
    lines.append("")
    lines.append(
        "> ⚠️ Manual review checklist. The system does NOT place orders. You are the executor."
    )
    lines.append(
        "> ⚠️ 人工核对清单。本系统不会下单,执行人是你。"
    )
    lines.append(
        f"> Reference prices = {snapshot_date.isoformat()} close; place LIMIT orders only."
    )
    lines.append(
        f"> 参考价 = {snapshot_date.isoformat()} 收盘价;仅使用限价委托。"
    )
    lines.append("")

    if notes:
        lines.append("## Notes / 备注")
        lines.append("")
        lines.append(notes.strip())
        lines.append("")

    lines.append("## Account snapshot / 账户快照")
    lines.append("")
    lines.append(
        f"- Cash before trades / 操作前现金: {_format_currency(cash_before)}"
    )
    lines.append(f"- Total NAV / 总权益: {_format_currency(nav)}")
    lines.append("")

    lines.append(
        f"## Trades to place / 待下达交易 ({len(trades)} lines, T+1)"
    )
    lines.append("")
    if trades:
        lines.append(
            "| # | Action / 方向 | Symbol / 标的 | Shares / 股数 "
            "| Reason / 说明 | Limit hint / 限价提示 | Reference close / 参考收盘 |"
        )
        lines.append("|---|---|---|---:|---|---:|---:|")
        for index, row in enumerate(trades, start=1):
            delta = float(cast(Any, row.get("delta_shares") or 0.0))
            action = "BUY" if delta > 0 else "SELL"
            symbol = str(row.get("symbol", ""))
            reason = str(row.get("reason") or "")
            reference_price = row.get("reference_price")
            ref_str = (
                _format_currency(float(cast(Any, reference_price)))
                if reference_price not in (None, "")
                else "—"
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(index),
                        action,
                        symbol,
                        _format_shares(abs(delta)),
                        reason,
                        ref_str,
                        ref_str,
                    ]
                )
                + " |"
            )
    else:
        lines.append("_No rebalance lines — the diff is flat._")
    lines.append("")

    lines.append("## Tax / wash-sale flags / 税务 / 洗售标记")
    lines.append("")
    if wash_sale_flags:
        for flag in wash_sale_flags:
            symbol = str(flag.get("symbol", ""))
            last_buy = str(flag.get("last_buy_date", ""))
            days = flag.get("days_since", 0)
            lines.append(f"- **{symbol}** — last buy {last_buy} ({days}d ago)")
    else:
        lines.append("- None flagged.")
    lines.append("")

    lines.append("## After execution checklist / 执行后核对清单")
    lines.append("")
    lines.append(
        "- [ ] Record actual fills in workbench's Fill Journal "
        "(`/execution/fills`) / 在工作台的 Fill Journal 中录入实际成交"
    )
    lines.append("- [ ] Or upload CSV from broker / 或上传券商导出的 CSV")
    lines.append(
        "- [ ] Reconcile in `/execution/journal-history` once fills land / "
        "成交记录完成后,在 `/execution/journal-history` 进行对账"
    )
    lines.append("")

    lines.append(f"_Ticket id: {ticket_id}._")
    lines.append("")
    lines.append(f"_Disclaimer: {DISCLAIMER_LITERAL}._")
    lines.append(f"_免责声明:{DISCLAIMER_LITERAL_ZH}。_")
    lines.append("")

    return "\n".join(lines)


def _defensive_diff_rows(
    total_equity: float,
    snapshot: Any,
) -> list[dict[str, Any]]:
    """B023 F006 — compute the diff rows for a 100%-defensive rotation.

    Every existing position sells to zero; the defensive symbol (SGOV)
    buys to consume the full equity. Reference prices fall back to
    each symbol's cost basis from the prior snapshot so the ticket's
    Markdown table can show the same `Limit hint` / `Reference close`
    columns as the normal flow.
    """

    from workbench_api.services.risk_panel import DEFENSIVE_SYMBOL

    rows: list[dict[str, Any]] = []
    for entry in snapshot.positions or []:
        symbol = entry.symbol if hasattr(entry, "symbol") else entry.get("symbol")
        shares = float(entry.shares if hasattr(entry, "shares") else entry.get("shares", 0))
        avg_cost = float(
            entry.avg_cost if hasattr(entry, "avg_cost") else entry.get("avg_cost", 0)
        )
        if shares <= 0:
            continue
        rows.append(
            {
                "symbol": symbol,
                "current_shares": shares,
                "target_shares": 0.0,
                "delta_shares": -shares,
                "current_weight": 0.0,
                "target_weight": 0.0,
                "delta_weight": 0.0,
                "delta_dollar": -shares * avg_cost,
                "reference_price": avg_cost or None,
                "reason": "Defensive rotation — sell to zero.",
            }
        )
    # The defensive symbol buy line. Without a real reference price we
    # leave reference_price None; the Markdown renderer surfaces "—".
    if total_equity > 0:
        rows.append(
            {
                "symbol": DEFENSIVE_SYMBOL,
                "current_shares": 0.0,
                "target_shares": total_equity,
                "delta_shares": total_equity,
                "current_weight": 0.0,
                "target_weight": 1.0,
                "delta_weight": 1.0,
                "delta_dollar": total_equity,
                "reference_price": None,
                "reason": (
                    "Defensive rotation — allocate full equity to the "
                    "defensive sleeve."
                ),
            }
        )
    return rows


def _repo_relative(path: Path) -> str:
    try:
        repo_root = Path(__file__).resolve().parents[4]
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _resolve_markdown_file(markdown_path: str) -> Path | None:
    """Resolve a stored ``markdown_path`` (repo-relative or absolute)
    back to a real file on disk. Returns ``None`` if the file is
    missing — callers degrade to re-rendering when that happens.
    """

    candidate = Path(markdown_path)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    repo_root = Path(__file__).resolve().parents[4]
    rooted = (repo_root / markdown_path).resolve()
    if rooted.exists():
        return rooted
    return None


def generate_ticket(
    session: Session,
    body: GenerateTicketRequest,
    *,
    runs_dir: Path,
    now: datetime | None = None,
) -> GenerateTicketResponse:
    """Compose the Markdown ticket + insert the order_ticket row.

    Fails with HTTP 409 when no AccountSnapshot is on file (the
    Recommendations page tells the user to seed via /execution/account
    first; the F002 acceptance reflects this).
    """

    now = now or datetime.now(UTC).replace(tzinfo=None)
    diff_response = get_position_diff(session, as_of=body.as_of_date)
    snapshot = diff_response.current
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail=t("ticket.no_snapshot"),
        )

    recommendations = get_current_recommendations(session)
    snapshot_date = (
        snapshot.snapshot_at.date()
        if snapshot.snapshot_at is not None
        else now.date()
    )
    ticket_date = (
        date.fromisoformat(body.as_of_date)
        if body.as_of_date
        else now.date()
    )
    ticket_id = f"tkt-{ticket_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    date_dir = runs_dir / ticket_date.isoformat()
    date_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = date_dir / f"order-ticket-{ticket_id}.md"

    if body.defensive:
        # B023 F006: defensive mode swaps the normal diff for a "rotate
        # to the defensive sleeve" target, computed against the current
        # cash + holdings. The diff rows then drive _render_ticket_markdown
        # the same way the normal flow does.
        diff_rows = _defensive_diff_rows(diff_response.total_equity, snapshot)
    else:
        diff_rows = [entry.model_dump() for entry in diff_response.diff]
    flags = [flag.model_dump() for flag in recommendations.wash_sale_flags]
    cash_before = float(snapshot.cash)
    body_md = render_ticket_markdown(
        ticket_id=ticket_id,
        ticket_date=ticket_date,
        snapshot_date=snapshot_date,
        cash_before=cash_before,
        nav=float(diff_response.total_equity),
        diff_rows=diff_rows,
        wash_sale_flags=flags,
        notes=body.notes,
    )
    markdown_path.write_text(body_md, encoding="utf-8")

    rel_path = _repo_relative(markdown_path)
    ticket_row = OrderTicket(
        id=ticket_id,
        ticket_date=ticket_date,
        snapshot_id=snapshot.id or "",
        target_positions_id=f"tp-{ticket_date.isoformat()}",
        markdown_path=rel_path,
        status="generated",
        created_at=now,
    )
    repo = OrderTicketRepository(session)
    repo.upsert(ticket_row)
    session.commit()
    return GenerateTicketResponse(
        id=ticket_id,
        ticket_date=ticket_date,
        snapshot_id=ticket_row.snapshot_id,
        target_positions_id=ticket_row.target_positions_id,
        markdown_path=rel_path,
        status="generated",
        created_at=now,
        executed_at=None,
        markdown_body=body_md,
        disclaimer=DISCLAIMER_LITERAL,
    )


def _ticket_to_summary(row: OrderTicket) -> TicketSummary:
    return TicketSummary(
        id=row.id,
        ticket_date=row.ticket_date,
        snapshot_id=row.snapshot_id,
        target_positions_id=row.target_positions_id,
        markdown_path=row.markdown_path,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        executed_at=row.executed_at,
    )


def list_tickets(session: Session, *, limit: int = 20, offset: int = 0) -> TicketListResponse:
    """Paginated newest-first list of tickets.

    ``limit`` is clamped to [1, 100] so a malicious query string cannot
    drain the DB; ``offset`` is clamped to [0, ∞).
    """

    limit = max(1, min(100, limit))
    offset = max(0, offset)
    stmt = (
        select(OrderTicket)
        .order_by(OrderTicket.created_at.desc(), OrderTicket.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(session.execute(stmt).scalars().all())
    total = OrderTicketRepository(session).count()
    return TicketListResponse(
        items=[_ticket_to_summary(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_ticket_detail(session: Session, ticket_id: str) -> TicketDetail | None:
    """Read a ticket row + its Markdown body. Returns ``None`` if the
    ticket id is unknown. If the on-disk Markdown file is missing the
    body field is a short note pointing to the stored path so the UI
    can still render the row metadata."""

    repo = OrderTicketRepository(session)
    row = repo.get_by_id(ticket_id)
    if row is None:
        return None
    file_path = _resolve_markdown_file(row.markdown_path)
    if file_path is not None:
        markdown_body = file_path.read_text(encoding="utf-8")
    else:
        markdown_body = (
            f"_Markdown artifact at `{row.markdown_path}` is missing on disk; "
            f"DB row preserved._"
        )
    return TicketDetail(
        id=row.id,
        ticket_date=row.ticket_date,
        snapshot_id=row.snapshot_id,
        target_positions_id=row.target_positions_id,
        markdown_path=row.markdown_path,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        executed_at=row.executed_at,
        markdown_body=markdown_body,
        disclaimer=DISCLAIMER_LITERAL,
    )


def void_ticket(session: Session, ticket_id: str) -> TicketSummary | None:
    """Flip a generated ticket to ``voided``. Returns ``None`` if the
    ticket is unknown OR is already in a terminal state (``executed``).
    Already-voided tickets round-trip as the same summary."""

    repo = OrderTicketRepository(session)
    row = repo.void(ticket_id)
    if row is None:
        return None
    session.commit()
    return _ticket_to_summary(row)
