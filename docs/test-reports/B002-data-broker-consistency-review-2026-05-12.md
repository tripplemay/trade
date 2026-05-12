# B002 数据源与券商适配规格一致性审查报告

## 审查范围

本报告覆盖 B002 产出的四份规格文档：

- `docs/research/01-data-source-selection.md`
- `docs/architecture/01-broker-adapter-spec.md`
- `docs/architecture/02-data-model-point-in-time-policy.md`
- `docs/architecture/03-environment-isolation-and-live-authorization.md`

审查目标是确认数据源、券商适配层、数据模型、point-in-time 政策、环境隔离和真实资金授权规则之间没有冲突。

## 总体结论

结论：PASS。

B002 文档体系完整覆盖了 B003 回测 MVP 之前必须明确的基础设施规格。文档一致强调首期只做 research/paper，不做未经授权的 live broker 或真实资金测试；数据侧明确禁止 API key 和行情数据入 Git；回测侧明确 point-in-time、available_at、T 日信号 T+1 执行和反未来函数政策；券商侧明确策略不得直连 broker，必须通过 OMS、风控和 Broker Adapter。

## 一致性检查

| 检查项 | 结果 | 说明 |
|---|---|---|
| 首期数据源口径 | PASS | 数据源文档推荐 Polygon/Massive 或 EODHD + SEC + FRED，符合 B001 低频策略需求。 |
| 机构数据升级路径 | PASS | 明确 FactSet/Refinitiv/Bloomberg 作为稳定后升级，不作为 MVP 前置依赖。 |
| 券商优先级 | PASS | IBKR 为主，Alpaca/Futu/Tiger 为辅助或备用，和项目目标一致。 |
| Broker Adapter 边界 | PASS | 策略不得直接调用 broker API，必须经 OMS 和风控。 |
| Paper / Live 隔离 | PASS | Broker Adapter 和环境隔离文档均要求默认 paper/research，live 默认禁用。 |
| 真实资金授权 | PASS | 明确真实资金操作必须由用户授权 broker、账户、策略、金额和时间窗口。 |
| Point-in-time 政策 | PASS | 基本面、新闻、AI 特征和指数成分均定义可用时间规则。 |
| 反未来函数 | PASS | 明确禁止当前成分回测历史、财报期末日期冒充可得时间、T 日信号 T 日成交等。 |
| 数据禁入 Git | PASS | 数据源和环境隔离文档均禁止提交 key、行情数据、数据库和账户导出。 |
| B003 交接 | PASS | 明确 B003 可基于 ETF 日线复权数据、交易日历、公司行为和数据质量检查实现。 |

## 非阻断建议

- B003 实现前应优先创建 Mock 数据接口，避免回测逻辑直接绑定某个供应商 SDK。
- B003 可先只实现 `instruments`、`daily_bars`、`adjusted_daily_bars`、`corporate_actions` 和 `data_snapshot`，不要提前实现完整基本面模型。
- 后续美股多因子批次启动前，需要单独验证供应商是否提供 point-in-time 基本面和历史成分。
- live broker adapter 实现前，应先完成 kill switch、人工确认、账户对账和审计日志。

## 验收结论

F005 验收通过。

B002 文档没有发现阻断性冲突，也没有任何文档允许未经授权的真实资金测试。建议签收 B002，并进入 B003 全球 ETF 回测 MVP。
