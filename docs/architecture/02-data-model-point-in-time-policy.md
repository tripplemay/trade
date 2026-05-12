# 数据模型与 Point-in-Time 政策

## 1. 目标

定义首期量化系统的数据实体、时间字段、复权和公司行为处理、成分股历史、基本面可得时间、数据版本和反未来函数政策。

该文档是后续回测、因子研究、Paper Trading 和实盘信号生成的基础约束。

## 2. 核心原则

- 所有信号必须只使用当时可获得的数据。
- 所有数据必须记录来源和抓取时间。
- 价格、基本面、新闻和公司行为都必须有时间语义。
- 回测不得使用未来成分、未来财报、未来复权信息或修订后数据冒充历史可得数据。
- 数据异常时不得生成实盘订单。

## 3. 核心实体

### 3.1 instruments

证券主数据。

字段：

- instrument_id。
- symbol。
- broker_symbols。
- asset_type：stock/etf/index/bond/cash_proxy。
- exchange。
- currency。
- country。
- sector。
- industry。
- active。
- list_date。
- delist_date。
- data_source。
- created_at。
- updated_at。

### 3.2 daily_bars

原始日线行情。

字段：

- instrument_id。
- trade_date。
- open。
- high。
- low。
- close。
- volume。
- currency。
- source。
- as_of_time。
- ingested_at。

### 3.3 adjusted_daily_bars

复权日线。

字段：

- instrument_id。
- trade_date。
- adjusted_open。
- adjusted_high。
- adjusted_low。
- adjusted_close。
- adjusted_volume。
- adjustment_factor。
- source。
- as_of_time。
- ingested_at。

### 3.4 corporate_actions

公司行为。

字段：

- instrument_id。
- action_type：split/dividend/symbol_change/delist/merger/spinoff。
- ex_date。
- record_date。
- pay_date。
- announcement_date。
- value。
- currency。
- source。
- ingested_at。

### 3.5 index_constituents

指数或股票池历史成分。

字段：

- index_id。
- instrument_id。
- effective_from。
- effective_to。
- announced_at。
- source。
- ingested_at。

若无历史成分，只能使用当前成分做研究假设，报告必须标注幸存者偏差风险。

### 3.6 fundamentals

基本面数据。

字段：

- instrument_id。
- fiscal_period。
- fiscal_year。
- statement_type。
- metric。
- value。
- currency。
- filing_date。
- accepted_at。
- available_at。
- source。
- source_document_url。
- ingested_at。

关键字段是 `available_at`，表示该数据可被策略使用的最早时间。

### 3.7 news_items

新闻和公告。

字段：

- news_id。
- source。
- source_url。
- published_at。
- ingested_at。
- title。
- body。
- language。
- related_instruments。
- dedupe_key。

### 3.8 ai_features

AI 文本特征。

字段：

- feature_id。
- source_news_id 或 source_document_id。
- instrument_id。
- event_type。
- sentiment。
- risk_tags。
- confidence。
- summary。
- evidence。
- model。
- prompt_version。
- generated_at。
- audit_status。

## 4. 时间字段定义

必须区分：

- `trade_date`：市场交易日期。
- `published_at`：新闻或公告发布时间。
- `accepted_at`：SEC 或交易所接收时间。
- `available_at`：系统允许策略使用该数据的时间。
- `ingested_at`：系统抓取入库时间。
- `as_of_time`：数据供应商声明的数据截至时间。
- `created_at/updated_at`：系统记录时间。

策略回测只能使用 `available_at <= signal_time` 的数据。

## 5. Point-in-Time 政策

### 5.1 行情数据

日频策略：

```text
T 日收盘后生成信号。
T+1 日执行。
```

不得使用 T+1 的价格、成交量或复权信息生成 T 日信号。

### 5.2 基本面数据

基本面数据必须按 `available_at` 进入因子计算。

SEC 数据建议：

```text
available_at = accepted_at + safety_lag
```

首期 safety_lag 可设为 1 个交易日，避免披露时间、时区和处理延迟造成未来函数。

如果只有 fiscal period 而没有 filing/accepted time，则不得用于严肃回测。

### 5.3 指数成分

指数成分必须使用历史成分。

若只使用当前成分：

- 必须在报告中标注幸存者偏差。
- 不得作为实盘收益预期。
- 只能用于原型研究。

### 5.4 新闻和公告

新闻必须使用 `published_at` 和 `ingested_at` 中较晚者作为策略可用时间基础。

```text
available_at = max(published_at, ingested_at)
```

AI 特征可用时间：

```text
ai_available_at = generated_at
```

## 6. 复权与公司行为

必须同时保留：

- 原始价格。
- 复权价格。
- 调整因子。
- 公司行为记录。

回测收益计算默认使用复权价格。

实盘订单价格和成交价必须使用原始市场价格。

公司行为异常时必须暂停相关标的交易。

## 7. 数据版本管理

每次数据导入必须记录：

- source。
- source_version，若可得。
- ingested_at。
- checksum，若为文件。
- row_count。
- date_range。

回测必须记录数据快照版本，保证可复现。

## 8. 反未来函数规则

禁止：

- 使用当前指数成分回测历史选股并不标注。
- 使用财报期末日期作为可用时间。
- 使用修订后基本面数据但不记录版本。
- 使用未来分红拆股信息生成历史信号。
- 使用 T 日收盘信号并假设 T 日收盘成交。
- 使用 AI 对未来新闻的摘要作为历史特征。

必须：

- 所有特征记录 `feature_time`。
- 所有信号记录 `signal_time`。
- 所有回测记录 `data_snapshot_id`。
- 所有报告说明数据限制。

## 9. 数据质量门禁

信号生成前必须检查：

- 目标标的是否 active。
- 当前交易日是否有效。
- 最新数据是否缺失。
- 价格是否异常。
- 复权因子是否异常。
- 公司行为是否未处理。
- 基本面 available_at 是否有效。
- 新闻/AI 特征是否可追溯。

任一关键检查失败，不得生成实盘订单。

## 10. 后续实现要求

B003 回测 MVP 至少实现：

- instruments。
- daily_bars。
- adjusted_daily_bars。
- corporate_actions。
- data quality checks。
- data snapshot metadata。

美股多因子批次前必须实现：

- fundamentals。
- index_constituents。
- available_at policy。

AI 风控批次前必须实现：

- news_items。
- ai_features。
- prompt/model audit fields。
