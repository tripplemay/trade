"""B013 Regime-Adaptive Multi-Asset research strategy.

This package implements an independent research-only strategy that stacks three defensive
shields on top of B010 inverse-volatility weighting: L1 per-asset 200-day SMA trend gating,
L2 inverse-vol weighting with an 8% portfolio target, and L3 portfolio-level regime
detection (NORMAL / BEAR / CRISIS) with crisis exposure halving. All artifacts produced
here are research-only and never authorize any paper or live trading action.
"""
