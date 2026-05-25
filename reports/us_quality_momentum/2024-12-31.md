# US Quality Momentum Backtest / 美股质量动量回测

> research-only; not a trading instruction / 仅供研究使用；不构成交易指令

## Strategy / 策略
- strategy_id: `us_quality_momentum`
- parameters_hash: `a50868440a077f9b65ea85efe46c8fefffabd80b98ba80a8ff120d77c98e1c60`
- factor weights / 因子权重: {'momentum': 0.35, 'quality': 0.3, 'low_vol': 0.15, 'value': 0.1, 'trend': 0.1}
- top_n / 持仓数量: 15
- max_position_weight / 单股上限: 7.00%
- max_sector_weight / 行业上限: 30.00%
- earnings_window_days / 财报规避窗口: 5 天

## Window / 回测窗口
- start: 2017-01-31
- end: 2025-12-31
- rebalances / 调仓次数: 96

## Performance Metrics / 业绩指标

| Metric / 指标 | Value / 数值 |
|---|---|
| Annualized Return / 年化收益 | 8.64% |
| Annualized Volatility / 年化波动 | 7.67% |
| Sharpe Ratio / Sharpe | 1.0834 |
| Sortino Ratio / Sortino | 1.0890 |
| Calmar Ratio / Calmar | 0.5037 |
| Max Drawdown / MDD | -17.15% |
| Win Rate / 胜率 | 54.47% |
| Profit/Loss Ratio / 盈亏比 | 1.0328 |
| Cumulative Return / 累计收益 | 109.30% |
| Total Turnover / 累计换手率 | 21.9333 |

## Annual Returns / 年度收益

| Year / 年份 | Return / 收益 |
|---|---|
| 2018 | 18.79% |
| 2019 | 17.49% |
| 2020 | 11.53% |
| 2021 | -1.71% |
| 2022 | 5.89% |
| 2023 | -6.58% |
| 2024 | 11.50% |
| 2025 | 32.17% |

## Average Sector Exposure / 平均行业暴露

| Sector / 行业 | Weight / 权重 |
|---|---|
| Consumer Staples | 14.51% |
| Health Care | 13.61% |
| Information Technology | 12.92% |
| Materials | 12.92% |
| Industrials | 11.11% |
| Financials | 9.38% |
| Communication Services | 9.31% |
| Consumer Discretionary | 5.56% |
| Real Estate | 4.51% |
| Energy | 3.47% |
| Utilities | 2.50% |

## Average Ticker Contribution / 平均个股仓位

| Ticker / 代码 | Avg Weight / 平均权重 |
|---|---|
| KO | 6.60% |
| JNJ | 6.39% |
| PG | 5.97% |
| UNH | 5.49% |
| APD | 5.42% |
| META | 5.35% |
| NVDA | 5.21% |
| V | 4.86% |
| HD | 4.58% |
| MSFT | 4.58% |
| LIN | 4.58% |
| GOOGL | 3.96% |
| UPS | 3.96% |
| HON | 3.68% |
| AAPL | 3.12% |
| CAT | 2.99% |
| ECL | 2.92% |
| JPM | 2.78% |
| AMT | 2.50% |
| PLD | 2.01% |

## Benchmarks / 基准对比

| Benchmark / 基准 | Cumulative / 累计收益 | Excess (bps total) / 累计超额 |
|---|---|---|
| spy_proxy | 250.68% | -5104.4 |
| qqq_proxy | 863.08% | -16482.3 |
| rsp_proxy | 250.68% | -5104.4 |
| static_top_n | 97.07% | 671.4 |

## Data Source / 数据来源
- fixture:us_quality_momentum (synthetic, not actual filings)
