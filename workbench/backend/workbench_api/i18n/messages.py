"""B024 F004 — message catalog for backend HTTPException details.

Keys map to a single user-facing string per locale. Placeholders use
`str.format()` named substitution (``{ticket_id}``, ``{status}``,
``{since}``, ``{detail}`` etc.). The schema is keyed by canonical
namespace (`auth.*`, `ticket.*`, `csv.*`, `report.*`, `backlog.*`,
`backtest.*`, `strategy.*`, `reconcile.*`, `health.*`, `validation.*`).

Note: F006 fixing round adds `validation.cash_negative` for the
`PUT /api/execution/account` `cash < 0` 422. The Pydantic default
422 detail is not user-translatable, so the route handler validates
`cash` manually and raises `HTTPException(422, detail=t(...))` so the
chosen locale's copy flows out via the standard `{"detail": "..."}`
shape.

The two bundles MUST share an identical key set — `test_i18n.py`
enforces parity so a future drop-in addition can't silently miss a
translation.
"""

from __future__ import annotations

from typing import Final

MESSAGES: Final[dict[str, dict[str, str]]] = {
    "zh-CN": {
        # Auth (500 / 401 / 403)
        "auth.misconfigured": "工作台未正确配置鉴权(NEXTAUTH_SECRET 或 ALLOWED_USER_EMAIL 缺失)。",
        "auth.unauthorized": "{detail}",
        "auth.forbidden": "{detail}",
        # Ticket lifecycle
        "ticket.not_found": "未找到订单清单:{ticket_id}",
        "ticket.cannot_void": "订单清单 {ticket_id} 无法作废(不存在或已处理/已作废)。",
        "ticket.is_voided": "订单清单 {ticket_id} 已作废,无法对账。",
        "ticket.no_fills_to_reconcile": "订单清单 {ticket_id} 暂无可对账的成交。",
        "ticket.status_blocks_fills": "订单清单 {ticket_id} 当前状态为 {status},无法追加成交。",
        "ticket.no_snapshot": "尚未配置账户快照;请先通过 /api/execution/account 录入。",
        # CSV upload
        "csv.adapter_unknown": "无法识别 CSV 格式(generic / schwab / ibkr)。表头:{headers}",
        "csv.missing_header_row": "CSV 缺少表头行。",
        "csv.empty_rows": "CSV 有表头但没有成交行。",
        # Reports / docs
        "report.not_found": "{detail}",
        "docs.invalid_path": "{detail}",
        "docs.not_found": "{detail}",
        # Backlog
        "backlog.not_found": "未找到 backlog 条目:{id}",
        "backlog.git_commit_failed": "Backlog git commit 失败:{detail}",
        # Backtests / strategies
        "backtest.unknown_strategy": "未知策略 id:{id}",
        "backtest.run_not_found": "未找到 run_id={run_id} 的回测结果。",
        "strategy.unknown": "未知策略 id:{strategy_id}",
        # Reconcile / analytics
        "reconcile.invalid_since": "无效的 'since' 日期:{since}",
        "reconcile.invalid_window": "window 必须为 3m/6m/1y 其一;实际收到 {window}",
        "reconcile.oversell": (
            "对账被拒绝:第 {line} 行卖出 {symbol} {sell_shares} 股,"
            "但账户仅持有 {held_shares} 股(本系统不支持卖空/做空)。"
            "请核对该笔成交录入的股数是否有误。"
        ),
        "reconcile.cash_would_go_negative": (
            "对账被拒绝:这些成交执行后现金将变为负数"
            "(缺口 ${shortfall};对账前现金 ${prior_cash},净现金变动 ${cash_delta})。"
            "常见原因:成交价格、股数或费用录入有误。"
        ),
        # Health
        "health.db_unreachable": "db_unreachable",
        # Generic
        "validation.detail_passthrough": "{detail}",
        "validation.cash_negative": "现金不能为负数。",
    },
    "en": {
        "auth.misconfigured": (
            "Workbench auth not configured "
            "(NEXTAUTH_SECRET or ALLOWED_USER_EMAIL missing)."
        ),
        "auth.unauthorized": "{detail}",
        "auth.forbidden": "{detail}",
        "ticket.not_found": "ticket not found: {ticket_id}",
        "ticket.cannot_void": (
            "ticket {ticket_id} cannot be voided "
            "(not found or already executed/voided)"
        ),
        "ticket.is_voided": "ticket {ticket_id} is voided; cannot reconcile.",
        "ticket.no_fills_to_reconcile": "ticket {ticket_id} has no fills to reconcile.",
        "ticket.status_blocks_fills": (
            "ticket {ticket_id} is {status}; fills cannot be appended."
        ),
        "ticket.no_snapshot": (
            "No account snapshot on file; seed one via "
            "/api/execution/account first."
        ),
        "csv.adapter_unknown": (
            "Could not identify CSV adapter (generic / schwab / ibkr). "
            "Headers seen: {headers}"
        ),
        "csv.missing_header_row": "CSV missing header row.",
        "csv.empty_rows": "CSV had headers but no fill rows.",
        "report.not_found": "{detail}",
        "docs.invalid_path": "{detail}",
        "docs.not_found": "{detail}",
        "backlog.not_found": "Unknown backlog id: {id}",
        "backlog.git_commit_failed": "Backlog git commit failed: {detail}",
        "backtest.unknown_strategy": "Unknown strategy id: {id}",
        "backtest.run_not_found": "No cached backtest with run_id={run_id}",
        "strategy.unknown": "Unknown strategy id: {strategy_id}",
        "reconcile.invalid_since": "invalid 'since' date: {since}",
        "reconcile.invalid_window": (
            "window must be one of 3m/6m/1y; got {window!r}"
        ),
        "reconcile.oversell": (
            "Reconcile rejected: line {line} sells {sell_shares} shares of "
            "{symbol} but the account only holds {held_shares} (short selling "
            "is out of scope). Check the fill's share count for a typo."
        ),
        "reconcile.cash_would_go_negative": (
            "Reconcile rejected: cash would go negative after these fills "
            "(shortfall ${shortfall}; prior cash ${prior_cash}, net cash "
            "change ${cash_delta}). Common cause: a wrong fill price, share "
            "count, or fee."
        ),
        "health.db_unreachable": "db_unreachable",
        "validation.detail_passthrough": "{detail}",
        "validation.cash_negative": "cash cannot be negative.",
    },
}

__all__ = ["MESSAGES"]
