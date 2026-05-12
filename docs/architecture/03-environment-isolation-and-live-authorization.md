# 环境隔离与真实资金测试授权规则

## 1. 目标

定义 research、paper、live 三类环境的隔离规则，防止研究代码、模拟交易和真实资金交易混淆。

本项目默认只允许 research 和 paper 环境。任何真实券商 live API 或真实资金测试都必须获得用户明确授权。

## 2. 环境定义

### 2.1 Research

用途：

- 数据研究。
- 策略回测。
- 参数测试。
- 报告生成。

限制：

- 不连接真实交易账户。
- 不发送订单。
- 不读取 live broker secrets。
- 可使用历史数据和 mock broker。

### 2.2 Paper

用途：

- 模拟交易。
- Paper broker API。
- OMS 和风控流程演练。
- 调仓报告和订单流程验证。

限制：

- 必须使用 paper endpoint 或 MockBroker。
- 不允许真实资金。
- 所有订单标记为 paper。

### 2.3 Live

用途：

- 真实券商账户。
- 真实资金交易。

默认状态：禁用。

启用条件：

- 用户在当前会话明确授权。
- 环境变量显式启用。
- 风控引擎开启。
- 一键停机可用。
- 人工确认可用。
- 审计日志开启。

## 3. 环境变量规则

建议变量：

```text
APP_ENV=research|paper|live
BROKER_ENV=paper|live
ENABLE_LIVE_TRADING=false
REQUIRE_MANUAL_ORDER_CONFIRMATION=true
MAX_LIVE_ORDER_VALUE_USD=...
```

默认值必须安全：

```text
APP_ENV=research
BROKER_ENV=paper
ENABLE_LIVE_TRADING=false
REQUIRE_MANUAL_ORDER_CONFIRMATION=true
```

如果 `ENABLE_LIVE_TRADING != true`，任何 live order API 都必须拒绝执行。

## 4. 密钥管理

禁止：

- 把 API key 提交到 Git。
- 把 `.env` 提交到 Git。
- 把 broker token 写入文档。
- 把真实账号截图或敏感信息入库。

必须：

- 使用环境变量或云密钥管理。
- Paper 和 Live key 分开。
- 不同 broker 独立配置。
- 定期轮换密钥。
- 日志脱敏。

## 5. 真实资金授权规则

任何真实资金操作都必须满足：

- 用户明确说出授权真实资金或 live trading。
- 明确授权 broker。
- 明确授权账户。
- 明确授权策略。
- 明确授权最大金额。
- 明确授权时间窗口。

没有以上授权，不得执行：

- live 下单。
- live 撤单。
- live 改单。
- live 持仓调整。
- live 账户敏感查询，除非用户明确同意。

## 6. 实盘前强制检查

live order 前必须检查：

- `APP_ENV == live`。
- `BROKER_ENV == live`。
- `ENABLE_LIVE_TRADING == true`。
- 用户授权记录存在。
- 订单已通过风控。
- 订单已人工确认。
- 当前持仓已对账。
- 市场处于可交易时段。
- 行情未延迟或异常。
- 订单金额低于上限。

任一失败即拒绝订单。

## 7. 数据文件禁入 Git

禁止提交：

- CSV 行情文件。
- Parquet 文件。
- SQLite / DuckDB / database dump。
- API 原始响应大文件。
- broker statement。
- account export。
- logs 中的敏感信息。

允许提交：

- 小型测试 fixture，且不含真实账号或授权数据。
- schema 文件。
- 数据字典。
- 文档。

## 8. 审计日志

必须记录：

- 用户授权。
- 环境变量快照，敏感值脱敏。
- 风控检查结果。
- 订单请求。
- broker response。
- 错误和重试。
- 人工确认人和时间。
- 一键停机事件。

审计日志不得被策略代码修改或删除。

## 9. 一键停机

live 环境必须支持：

- 停止所有策略。
- 阻止新订单。
- 可选撤销 open orders。
- 保留当前持仓。
- 生成停机报告。

停机功能必须优先于策略和调度器。

## 10. L1 / L2 测试边界

L1：本地测试。

- Mock broker。
- 无真实 API key。
- 无真实券商连接。
- 无真实资金。

L2：外部服务测试。

- Paper broker API。
- 真实数据供应商 API。
- 不涉及真实资金。

Live validation：真实资金或 live broker。

- 必须单独授权。
- 必须小金额。
- 必须人工确认。
- 必须可随时停机。

## 11. 后续实现要求

实现阶段必须先完成：

- Mock environment。
- Paper environment。
- Secrets loading with validation。
- Environment guard middleware。
- Order guard。
- Audit logger。
- Kill switch。

在这些能力完成前，不允许实现真实下单路径。
