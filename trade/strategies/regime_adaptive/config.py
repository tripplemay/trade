"""Regime-Adaptive strategy configuration boundary.

Defines the 9-asset universe (Risk Core / Stabilizer / Defensive), default parameters for
the L1 / L2 / L3 defensive pipeline, and the validator that enforces no-leverage, complete
categorisation, and parameter-range invariants. The configuration is research-only and
never authorizes any paper or live trading action.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field

ASSET_CATEGORY_RISK_CORE = "risk_core"
ASSET_CATEGORY_STABILIZER = "stabilizer"
ASSET_CATEGORY_DEFENSIVE = "defensive"
VALID_ASSET_CATEGORIES: frozenset[str] = frozenset(
    {ASSET_CATEGORY_RISK_CORE, ASSET_CATEGORY_STABILIZER, ASSET_CATEGORY_DEFENSIVE}
)

STRATEGY_ID = "regime_adaptive_multi_asset"


@dataclass(frozen=True, slots=True)
class AssetEntry:
    """Single asset record in the regime-adaptive universe."""

    symbol: str
    category: str
    role_label: str = ""


_DEFAULT_UNIVERSE: tuple[AssetEntry, ...] = (
    AssetEntry(symbol="SPY", category=ASSET_CATEGORY_RISK_CORE, role_label="us_large_cap"),
    AssetEntry(symbol="QQQ", category=ASSET_CATEGORY_RISK_CORE, role_label="us_growth"),
    AssetEntry(symbol="VEA", category=ASSET_CATEGORY_RISK_CORE, role_label="developed_ex_us"),
    AssetEntry(symbol="VWO", category=ASSET_CATEGORY_RISK_CORE, role_label="emerging_markets"),
    AssetEntry(symbol="IEF", category=ASSET_CATEGORY_STABILIZER, role_label="us_treasury_7_10"),
    AssetEntry(symbol="TLT", category=ASSET_CATEGORY_STABILIZER, role_label="us_treasury_20_plus"),
    AssetEntry(symbol="GLD", category=ASSET_CATEGORY_STABILIZER, role_label="gold"),
    AssetEntry(symbol="DBC", category=ASSET_CATEGORY_STABILIZER, role_label="broad_commodities"),
    AssetEntry(symbol="SGOV", category=ASSET_CATEGORY_DEFENSIVE, role_label="ultra_short_treasury"),
)


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveConfig:
    """Research-only configuration for the Regime-Adaptive Multi-Asset strategy."""

    strategy_id: str = STRATEGY_ID
    universe: Sequence[AssetEntry] = field(default_factory=lambda: _DEFAULT_UNIVERSE)
    trend_window_days: int = 200
    vol_lookback_days: int = 120
    target_volatility: float = 0.08
    regime_fast_vol_window_days: int = 20
    regime_slow_vol_window_days: int = 120
    regime_crisis_ratio: float = 1.5
    regime_spy_symbol: str = "SPY"
    regime_crisis_exposure_scale: float = 0.5
    tolerance_band: float = 0.03
    account_drawdown_threshold: float = 0.15
    max_exposure: float = 1.0
    defensive_symbol: str = "SGOV"

    def parameter_hash(self) -> str:
        payload = {
            "account_drawdown_threshold": self.account_drawdown_threshold,
            "defensive_symbol": self.defensive_symbol,
            "max_exposure": self.max_exposure,
            "regime_crisis_exposure_scale": self.regime_crisis_exposure_scale,
            "regime_crisis_ratio": self.regime_crisis_ratio,
            "regime_fast_vol_window_days": self.regime_fast_vol_window_days,
            "regime_slow_vol_window_days": self.regime_slow_vol_window_days,
            "regime_spy_symbol": self.regime_spy_symbol,
            "strategy_id": self.strategy_id,
            "target_volatility": self.target_volatility,
            "tolerance_band": self.tolerance_band,
            "trend_window_days": self.trend_window_days,
            "universe": [
                {
                    "category": entry.category,
                    "role_label": entry.role_label,
                    "symbol": entry.symbol,
                }
                for entry in self.universe
            ],
            "vol_lookback_days": self.vol_lookback_days,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class RegimeAdaptiveConfigError(ValueError):
    """Raised when a RegimeAdaptiveConfig violates the B013 research boundary."""


def validate_regime_adaptive_config(config: RegimeAdaptiveConfig) -> None:
    if config.max_exposure > 1.0:
        raise RegimeAdaptiveConfigError(
            "leverage is not allowed; max_exposure must be <= 1.0"
        )
    if config.max_exposure <= 0:
        raise RegimeAdaptiveConfigError("max_exposure must be positive")
    if config.target_volatility <= 0:
        raise RegimeAdaptiveConfigError("target_volatility must be positive")
    if config.trend_window_days <= 0:
        raise RegimeAdaptiveConfigError("trend_window_days must be positive")
    if config.vol_lookback_days <= 0:
        raise RegimeAdaptiveConfigError("vol_lookback_days must be positive")
    if config.regime_fast_vol_window_days <= 0:
        raise RegimeAdaptiveConfigError("regime_fast_vol_window_days must be positive")
    if config.regime_slow_vol_window_days <= 0:
        raise RegimeAdaptiveConfigError("regime_slow_vol_window_days must be positive")
    if config.regime_crisis_ratio <= 1.0:
        raise RegimeAdaptiveConfigError(
            "regime_crisis_ratio must be greater than 1.0 to indicate fast-vs-slow vol breach"
        )
    if not 0.0 <= config.tolerance_band <= 1.0:
        raise RegimeAdaptiveConfigError("tolerance_band must be within [0, 1]")
    if not 0.0 <= config.regime_crisis_exposure_scale <= 1.0:
        raise RegimeAdaptiveConfigError(
            "regime_crisis_exposure_scale must be within [0, 1]"
        )
    if not 0.0 < config.account_drawdown_threshold < 1.0:
        raise RegimeAdaptiveConfigError(
            "account_drawdown_threshold must be within (0, 1)"
        )

    if not config.universe:
        raise RegimeAdaptiveConfigError("universe must not be empty")
    seen: set[str] = set()
    for entry in config.universe:
        if entry.category not in VALID_ASSET_CATEGORIES:
            raise RegimeAdaptiveConfigError(
                f"unknown asset category {entry.category!r} for {entry.symbol}"
            )
        if entry.symbol in seen:
            raise RegimeAdaptiveConfigError(f"duplicate symbol in universe: {entry.symbol}")
        seen.add(entry.symbol)

    categories_present = {entry.category for entry in config.universe}
    if ASSET_CATEGORY_RISK_CORE not in categories_present:
        raise RegimeAdaptiveConfigError("universe must contain at least one risk_core asset")
    if ASSET_CATEGORY_DEFENSIVE not in categories_present:
        raise RegimeAdaptiveConfigError("universe must contain at least one defensive asset")

    by_symbol = {entry.symbol: entry for entry in config.universe}
    if config.defensive_symbol not in by_symbol:
        raise RegimeAdaptiveConfigError(
            f"defensive_symbol {config.defensive_symbol!r} must be present in universe"
        )
    if by_symbol[config.defensive_symbol].category != ASSET_CATEGORY_DEFENSIVE:
        raise RegimeAdaptiveConfigError(
            f"defensive_symbol {config.defensive_symbol!r} must be categorised as defensive"
        )
    if config.regime_spy_symbol not in by_symbol:
        raise RegimeAdaptiveConfigError(
            f"regime_spy_symbol {config.regime_spy_symbol!r} must be present in universe"
        )


def default_regime_adaptive_config() -> RegimeAdaptiveConfig:
    config = RegimeAdaptiveConfig()
    validate_regime_adaptive_config(config)
    return config
