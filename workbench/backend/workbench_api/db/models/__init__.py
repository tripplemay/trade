"""Declarative ORM models for the workbench.

The B021 baseline ships three tables — Account, BacklogEntry, SnapshotMeta —
mirroring the repo-root bootstrap files (`accounts/me.json`, `backlog.json`)
and the snapshot registry that B009/B017 produced. B023 F001 adds three
execution-workflow tables (OrderTicket, FillJournalEntry, AccountSnapshot)
that record the manual rebalance loop. Re-exports keep the import surface
flat for Alembic auto-generate and the bootstrap CLI.
"""

from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.advisor_recommendation import AdvisorRecommendation
from workbench_api.db.models.backlog_entry import BacklogEntry
from workbench_api.db.models.backtest_data_window import BacktestDataWindow
from workbench_api.db.models.backtest_run import BacktestRun
from workbench_api.db.models.base import Base
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.investment_report import InvestmentReport
from workbench_api.db.models.llm_budget_log import LLMBudgetLog
from workbench_api.db.models.market_context import MarketContextObservation
from workbench_api.db.models.news import News
from workbench_api.db.models.news_embedding import NewsEmbedding
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.models.paper_account import (
    PaperAccount,
    PaperPosition,
    PaperRebalance,
)
from workbench_api.db.models.paper_nav_history import PaperNavHistory
from workbench_api.db.models.price_history import PriceHistory
from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.db.models.recommendation_snapshot import RecommendationSnapshot
from workbench_api.db.models.risk_explanation_snapshot import RiskExplanationSnapshot
from workbench_api.db.models.snapshot_meta import SnapshotMeta
from workbench_api.db.models.symbol_fundamentals_cache import SymbolFundamentalsCache
from workbench_api.db.models.symbol_name import SymbolName
from workbench_api.db.models.symbol_price_cache import SymbolPriceCache
from workbench_api.db.models.target_refresh_job import TargetRefreshJob
from workbench_api.db.models.tiingo_budget_log import TiingoBudgetLog

__all__ = [
    "Account",
    "AccountSnapshot",
    "AdvisorRecommendation",
    "BacklogEntry",
    "BacktestDataWindow",
    "BacktestRun",
    "Base",
    "FillJournalEntry",
    "InvestmentReport",
    "LLMBudgetLog",
    "MarketContextObservation",
    "News",
    "NewsEmbedding",
    "OrderTicket",
    "PaperAccount",
    "PaperNavHistory",
    "PaperPosition",
    "PaperRebalance",
    "PriceHistory",
    "PriceSnapshot",
    "RecommendationSnapshot",
    "RiskExplanationSnapshot",
    "SnapshotMeta",
    "SymbolFundamentalsCache",
    "SymbolName",
    "SymbolPriceCache",
    "TargetRefreshJob",
    "TiingoBudgetLog",
]
