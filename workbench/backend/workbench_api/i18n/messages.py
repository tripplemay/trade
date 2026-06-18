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
        "strategy_modes.unknown_mode": "未知策略模式 id:{id}",
        "strategy_modes.refresh_job_not_found": "未找到 job_id={job_id} 的刷新任务。",
        # Symbols (B059 — 标的查询，仅 EOD 收盘价，无实时/交易入口)
        "symbols.invalid_symbol": "标的代码无效:{symbol}。请输入有效代码,例如 AAPL、SPY、BRK.B。",
        "symbols.not_found": (
            "无法获取标的 {symbol} 的价格数据。可能是代码有误、已退市,或暂无 EOD 数据。"
            "请检查代码后重试,例如 AAPL、SPY。"
        ),
        "symbols.rate_limited": "标的查询过于频繁,已触发限流。请稍后再试。",
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
        # B054 F002 — 后端动态串本地化(策略说明 / 门控 / 执行 reason / 风险防御 / 首页汇总)
        "strategy.note.master_portfolio": (
            "覆盖全部四个活跃子策略的完整组合(季度再平衡,含熔断与回撤控制)。"
            "基于真实日线价格回测(Tiingo,B045 数据刷新)。仅供研究参考——不构成收益预测。"
        ),
        "strategy.note.momentum": (
            "Master 核心趋势引擎子策略(规划权重=0.40)。基于真实日线价格评分"
            "(Tiingo,B045 数据刷新)。仅供研究参考——不构成收益预测。"
        ),
        "strategy.note.risk_parity": (
            "Master 核心稳定器子策略(规划权重=0.30)。B016 以 HRP 升级了 "
            "risk_parity_vol_target 子策略。"
        ),
        "strategy.note.us_quality": (
            "B025 卫星-美股质量(规划权重=0.20)。基于真实价格(Tiingo)+真实 SEC EDGAR "
            "申报(B045 数据刷新)评分。仅供研究参考——不构成收益预测。"
        ),
        "strategy.note.hk_china": (
            "Master 卫星-港股中概子策略(规划权重=0.10),由 BL-B011-S2 实现。基于在美"
            "上市的港股/中概 ETF 集合(MCHI/FXI/KWEB/ASHR)的真实日线价格做趋势评分"
            "(Tiingo,B045 数据刷新)。仅供研究参考——不构成收益预测。"
        ),
        "strategy.note.regime_quarterly": (
            "研究态:Master 以 0.0 权重加载 regime_adaptive(未激活)。B019 调参将 "
            "activation_threshold 设为 0.11(原 0.13)。激活留待未来的 B013 批次。"
        ),
        "strategy.note.regime_inactive": "研究态:regime 叠加层以未激活状态发布(权重 0.0)。",
        "strategy.note.regime_adaptive": (
            "智能择时组合(B057):基于市场状态(正常/熊市/危机)自适应的多资产研究策略,"
            "月度调仓。基于真实日线价格回测(Tiingo,B045 数据刷新)。研究态、前向验证中"
            "——不构成收益预测,亦非交易指令。"
        ),
        "strategy.note.cn_attack": (
            "A股 进攻动量质量(B066,研究态):独立于 Master 的进攻型 A股 个股选股引擎,"
            "纯进攻满仓无防御闸。回测页跑 2 因子×3 退出=6 变体对比+样本外验证+沪深300 基准,"
            "据此判断是否值得进 P2 实盘 advisory。research-only:无实盘推荐/无执行/不构成"
            "收益预测/不碰 live。"
        ),
        "gate.kill_switch_detail": "主组合回撤 {master_dd} {comparator} 阈值 {threshold}。",
        "gate.min_equity_detail": "账户权益 = {equity}",
        "diff.reason.sell_to_zero": "已持有但已不在目标内——清仓至零",
        "diff.reason.profit_take": "已持有但已跌出 top-N——获利了结 / 调仓退出",
        "risk.defense_target_rationale": (
            "熔断已触发——全部轮动至防御子策略,直至主组合回撤回落至阈值以下。"
        ),
        "risk.defense_panel_rationale": (
            "主组合回撤 {dd_pct}% ≥ 熔断阈值({threshold_pct}%)。"
            "防御清单将 100% 配置至 {symbol},作为 B011 防御代理。"
        ),
        "risk.defense_diff_rationale": "防御清单模式——全部轮动至 B011 防御代理。",
        "home.positions_one": "1 个持仓",
        "home.positions_many": "{count} 个持仓",
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
        "strategy_modes.unknown_mode": "Unknown strategy mode id: {id}",
        "strategy_modes.refresh_job_not_found": "No target-refresh job with job_id={job_id}",
        # Symbols (B059 — symbol lookup; EOD close only, no live / no execution)
        "symbols.invalid_symbol": (
            "Invalid ticker: {symbol}. Enter a valid symbol, e.g. AAPL, SPY, BRK.B."
        ),
        "symbols.not_found": (
            "No price data for {symbol}. It may be an invalid or delisted ticker, "
            "or have no EOD data. Check the symbol and retry, e.g. AAPL, SPY."
        ),
        "symbols.rate_limited": "Too many symbol lookups right now; please retry shortly.",
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
        # B054 F002 — localized dynamic strings (mirror of the zh-CN copy)
        "strategy.note.master_portfolio": (
            "The full combined portfolio across all four active sleeves "
            "(quarterly rebalance, kill-switch + drawdown controls). Backtested "
            "on real daily prices (Tiingo, B045 data-refresh). Research-only "
            "advisory — not a return forecast."
        ),
        "strategy.note.momentum": (
            "Master core_trend_engine sleeve (planning_weight=0.40). Scored on "
            "real daily prices (Tiingo, B045 data-refresh). Research-only "
            "advisory — not a return forecast."
        ),
        "strategy.note.risk_parity": (
            "Master core_stabilizer sleeve (planning_weight=0.30). B016 HRP "
            "upgrades the risk_parity_vol_target sleeve."
        ),
        "strategy.note.us_quality": (
            "B025 satellite_us_quality (planning_weight=0.20). Scored on real "
            "prices (Tiingo) + real SEC EDGAR filings (B045 data-refresh). "
            "Research-only advisory — not a return forecast."
        ),
        "strategy.note.hk_china": (
            "Master satellite_hk_china sleeve (planning_weight=0.10), implemented "
            "in BL-B011-S2. Trend-scored on the US-listed HK/China ETF set "
            "(MCHI/FXI/KWEB/ASHR) using real daily prices (Tiingo, B045 "
            "data-refresh). Research-only advisory — not a return forecast."
        ),
        "strategy.note.regime_quarterly": (
            "Research-state: Master loads regime_adaptive at weight 0.0 "
            "(inactive). B019 retune set activation_threshold=0.11 (was 0.13). "
            "Activation is a future B013 batch."
        ),
        "strategy.note.regime_inactive": (
            "Research-state: regime overlay ships inactive (weight 0.0)."
        ),
        "strategy.note.regime_adaptive": (
            "Regime-Adaptive mode (B057): a multi-asset research strategy that "
            "adapts to the market regime (normal / bear / crisis), monthly "
            "rebalance. Backtested on real daily prices (Tiingo, B045 "
            "data-refresh). Research-state, forward-validation only — not a "
            "return forecast, not a trading instruction."
        ),
        "strategy.note.cn_attack": (
            "A-share Attack Momentum+Quality (B066, research-state): a pure-attack "
            "A-share single-stock engine independent of the Master (always fully "
            "invested, no defensive gate). The backtest page runs the 2 factor × 3 "
            "exit = 6-variant comparison + out-of-sample validation + CSI 300 "
            "benchmark to judge whether it merits a P2 live advisory. Research-only: "
            "no live recommendation / no execution / not a return forecast / not live."
        ),
        "gate.kill_switch_detail": (
            "Master drawdown {master_dd} {comparator} threshold {threshold}."
        ),
        "gate.min_equity_detail": "Account equity = {equity}",
        "diff.reason.sell_to_zero": "held but no longer in target — sell to zero",
        "diff.reason.profit_take": "held but dropped out of top-N — profit-take / rebalance exit",
        "risk.defense_target_rationale": (
            "Kill switch tripped — rotate fully into the defensive sleeve until "
            "master drawdown recovers below threshold."
        ),
        "risk.defense_panel_rationale": (
            "Master drawdown {dd_pct}% ≥ kill-switch threshold ({threshold_pct}%). "
            "The defensive ticket allocates 100% to {symbol} as the B011 "
            "defensive proxy."
        ),
        "risk.defense_diff_rationale": (
            "Defensive ticket mode — rotate fully to the B011 defensive proxy."
        ),
        "home.positions_one": "1 position",
        "home.positions_many": "{count} positions",
        "health.db_unreachable": "db_unreachable",
        "validation.detail_passthrough": "{detail}",
        "validation.cash_negative": "cash cannot be negative.",
    },
}

__all__ = ["MESSAGES"]
