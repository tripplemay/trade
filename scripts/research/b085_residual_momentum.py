#!/usr/bin/env python
"""B085 F001 (core) — residual (idiosyncratic) momentum computation.

★先验口径（禁扫参）：单因子残差动量（Lin 2020 EFM / IRFA 2021 中国证据的简化）——
每名日收益对**等权市场收益**滚动回归取残差（rolling β = cov/var, 窗 lookback_beta），
残差动量 = 过去 [t-skip-lookback_mom, t-skip] 的累计残差（skip 近月避短反转）。

这是 F001 的**机械可测**核心（β/残差/累计, 单测锁）。零回归：纯研究脚本, 不触 cn_attack 产品码。
A/B（残差动量 rank 喂引擎 vs pure_momentum）+ 分子窗损耗 + turnover + GO/INCONCLUSIVE 裁定
= **判断重**的部分, 留 fresh context 严做（B084 sub-window 过度乐观教训：判断在 fresh 做）。
"""

from __future__ import annotations

from typing import Any

# 先验参数（禁扫参）：文献口径 12M β 窗 / 6M 动量 / skip 1M。
LOOKBACK_BETA = 252
LOOKBACK_MOM = 126
SKIP = 21


def residual_returns(prices: Any) -> Any:
    """每名日收益减去 (rolling β × 等权市场收益) 的残差。

    prices: wide (date × ticker) close. Returns a same-shaped residual-return frame.
    Rolling β_t = cov_win(r_i, r_mkt) / var_win(r_mkt); residual = r_i − β_t·r_mkt.
    (α 略去：横截面动量看相对残差累计, 常数项不影响排序。)
    """

    rets = prices.pct_change()
    mkt = rets.mean(axis=1)  # 等权市场收益（宇宙横截面均值）
    var_mkt = mkt.rolling(LOOKBACK_BETA, min_periods=LOOKBACK_BETA // 2).var()
    resid = rets.copy()
    for col in rets.columns:
        cov = rets[col].rolling(LOOKBACK_BETA, min_periods=LOOKBACK_BETA // 2).cov(mkt)
        beta = cov / var_mkt
        resid[col] = rets[col] - beta * mkt
    return resid


def residual_momentum(prices: Any) -> Any:
    """残差动量 = 过去 [t-SKIP-LOOKBACK_MOM, t-SKIP] 的累计残差收益（skip 近月避短反转）。

    Returns a wide (date × ticker) frame of the residual-momentum signal at each date
    (higher = stronger idiosyncratic up-trend). NaN in the warmup window."""

    resid = residual_returns(prices)
    # cumulative residual over the momentum window, ending SKIP days ago.
    cum = resid.rolling(LOOKBACK_MOM, min_periods=LOOKBACK_MOM // 2).sum()
    return cum.shift(SKIP)


if __name__ == "__main__":
    print(
        "residual_momentum: call residual_momentum(prices_wide). "
        f"先验 β 窗 {LOOKBACK_BETA} / 动量 {LOOKBACK_MOM} / skip {SKIP}."
    )
