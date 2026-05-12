# 券商适配层规格

## 1. 目标

定义统一 Broker Adapter，使策略、组合、风控和订单管理系统不直接依赖某个券商 API。

系统必须支持多券商扩展，但首期重点是 IBKR，Alpaca 可用于美股 paper trading，Futu/Tiger 可作为港股备用适配方向。

## 2. 架构原则

交易链路：

```text
策略信号 -> 目标仓位 -> 组合构建 -> 风控检查 -> OMS -> Broker Adapter -> Broker API
```

规则：

- 策略不得直接调用券商 API。
- 实盘订单必须经过 OMS 和风控。
- Paper 和 Live 必须显式隔离。
- 所有券商错误码必须标准化。
- 所有订单和成交必须可审计。

## 3. 券商优先级

| 优先级 | 券商 | 用途 |
|---|---|---|
| P0 | IBKR | 主券商，美股、港股、全球 ETF |
| P0/P1 | Alpaca | 美股和 ETF paper trading，快速开发 |
| P1 | Futu | 港股和美股备用 |
| P1 | Tiger | 港股、美股、新加坡备用 |
| P2 | Schwab | 美股个人账户，后续考虑 |
| P2 | Saxo | 全球多资产，后续考虑 |

首期不得因为兼容所有券商而牺牲 IBKR 的主流程设计。

## 4. Adapter 接口

### 4.1 Account

必须支持：

```text
get_account()
get_cash_balances()
get_buying_power()
get_margin_status()
```

返回字段：

- account_id。
- broker。
- environment：paper/live。
- base_currency。
- net_liquidation。
- cash。
- buying_power。
- margin_used。
- updated_at。

### 4.2 Positions

必须支持：

```text
get_positions()
get_position(symbol)
```

字段：

- broker_symbol。
- internal_instrument_id。
- quantity。
- average_cost。
- market_value。
- unrealized_pnl。
- currency。
- updated_at。

### 4.3 Orders

必须支持：

```text
place_order(order_request)
cancel_order(broker_order_id)
replace_order(broker_order_id, replace_request)
get_order(broker_order_id)
list_open_orders()
```

首期订单类型：

- Market，谨慎使用。
- Limit，默认优先。
- Stop，后续。
- Stop Limit，后续。

首期禁止：

- 期权复杂组合单。
- 杠杆产品自动下单。
- 盘前盘后默认下单。
- 未经人工确认的大额市价单。

### 4.4 Fills

必须支持：

```text
list_fills(start, end)
get_fill(fill_id)
```

字段：

- broker_order_id。
- fill_id。
- symbol。
- side。
- quantity。
- price。
- commission。
- fees。
- currency。
- executed_at。

### 4.5 Quotes

必须支持：

```text
get_latest_quote(symbol)
get_latest_trade(symbol)
```

实盘下单前需要：

- last price。
- bid。
- ask。
- spread。
- timestamp。
- data_delay 标记。

若行情延迟或价差异常，不得自动下单。

## 5. 标准化订单模型

订单请求：

```json
{
  "instrument_id": "internal-id",
  "broker_symbol": "SPY",
  "side": "buy",
  "quantity": 10,
  "order_type": "limit",
  "limit_price": 500.0,
  "time_in_force": "day",
  "strategy_id": "global_etf_momentum",
  "environment": "paper",
  "client_order_id": "uuid"
}
```

要求：

- `client_order_id` 必须幂等。
- 所有订单必须记录策略来源。
- 所有订单必须记录 paper/live 环境。
- 所有订单必须记录风控检查结果。

## 6. 错误码标准化

统一错误类型：

- AUTH_FAILED。
- RATE_LIMITED。
- MARKET_CLOSED。
- INSUFFICIENT_FUNDS。
- INSUFFICIENT_POSITION。
- INVALID_SYMBOL。
- ORDER_REJECTED。
- PRICE_OUT_OF_RANGE。
- DATA_DELAYED。
- NETWORK_ERROR。
- BROKER_MAINTENANCE。
- UNKNOWN。

每个 broker adapter 必须把原始错误保存到 `raw_error`，同时映射到标准错误。

## 7. 限速与重试

必须实现：

- 每个券商独立 rate limiter。
- 指数退避重试。
- 幂等订单保护。
- 订单状态轮询上限。
- API 维护窗口处理。

IBKR 特别注意：

- 会话机制复杂。
- API 速率限制和 market data line 限制需要独立处理。
- 单 username 可能存在 competing session。

Alpaca 特别注意：

- Paper 和 Live endpoint 必须隔离。
- 美股以外市场覆盖不足。

Futu/Tiger 特别注意：

- 港股权限、行情授权、地区限制和交易时段需单独确认。

## 8. Paper / Live 隔离

必须强制区分：

- `BROKER_ENV=paper`。
- `BROKER_ENV=live`。

系统默认必须是 paper。

Live 环境启用必须满足：

- 用户明确授权。
- 环境变量显式配置。
- 风控引擎开启。
- 一键停机可用。
- 订单人工确认可用。
- 审计日志开启。

## 9. 账户和持仓对账

每个交易日必须对账：

- 系统持仓 vs 券商持仓。
- 系统现金 vs 券商现金。
- 系统订单 vs 券商订单。
- 系统成交 vs 券商成交。

若差异超过阈值：

- 暂停自动下单。
- 生成异常报告。
- 需要人工确认后恢复。

## 10. 审计要求

所有 broker 操作必须记录：

- 请求时间。
- broker。
- environment。
- account_id。
- request payload。
- response payload。
- 标准错误码。
- raw error。
- 操作来源。
- 关联策略和风控检查。

真实账户审计日志不得删除。

## 11. 后续实现要求

首期实现顺序：

1. MockBrokerAdapter。
2. PaperBrokerAdapter 接口。
3. Alpaca paper trading，可选。
4. IBKR paper trading。
5. IBKR live 只在用户授权后研究。

实盘前必须完成：

- OMS。
- 风控引擎。
- 账户对账。
- 一键停机。
- 人工确认。
- Evaluator 验收。
