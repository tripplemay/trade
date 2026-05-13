# B012 Paper Trading Prep MVP Spec

## Background

B006-B011 delivered the core strategy backtest path (Global ETF Momentum, Risk Parity) and the Master Portfolio Allocation MVP combining both with quarterly rebalance, 15% drawdown kill-switch, and a calculated baseline. MVP PRD §10 success criteria are now substantively met. The next milestone in MVP PRD §12 is "Paper Trading / Mock Broker", which per MVP PRD §4.5 is explicitly **preparation only**:

> MVP 不实现真实 paper broker API。MVP 只为后续 Paper Trading 做准备：目标仓位输出格式、策略配置格式、回测报告格式、Broker Adapter 接口文档引用。Paper Trading 作为后续批次实现。

B012 establishes the interface boundary between research backtests and any future paper / live trading adapter. It defines a Target Positions output format, an abstract Broker Adapter interface (without real broker SDKs), a Mock Broker journal that records intent only (no simulated fills, no virtual P&L), and a Backtest-to-Paper bridge that can convert a B011 Master Portfolio backtest result (or per-strategy backtest result) into target positions at any signal date. All artifacts remain research-only, fixture/mock-first, offline by default, with explicit "this is not a trading instruction" labeling.

## Goal

Implement the minimal, testable Paper Trading prep MVP that:

- Defines a Target Positions output schema exposing both percentage weights and dollar exposures, including strategy/portfolio identifiers, signal date, snapshot reference, account-state reference, research limitations, and explicit research-only labeling.
- Defines an abstract `BrokerAdapter` interface (`submit_target_positions`, `get_account_state`, `get_open_orders`) with no real broker SDK dependency. Live or paper broker adapters are explicitly out of scope for B012.
- Implements a Mock Broker that reads a fixed research account state, journals submitted target positions to an append-only JSON Lines file, returns the configured account state, and never performs any network call, fill simulation, or P&L tracking.
- Implements a Backtest-to-Paper bridge that converts a Master Portfolio (B011) or single-strategy backtest result into a Target Positions object at any manually supplied signal date (defaulting to the latest period) and can submit it through the Mock Broker.
- Adds safety guard regression proving B012 introduces no real broker SDK import, no paper-trading API call, no environment / secret access, and no claim of live or paper-executed trades.
- Closes with independent Codex L1 verification.

This batch creates the research-to-paper interface boundary, not an OMS, real paper broker adapter, live execution path, multi-broker integration, or trading recommendation product.

## Hard Decisions

- No real broker SDK imports in B012 code: `ib_insync`, `alpaca`, `alpaca_trade_api`, `futu`, `futu-api`, `tiger`, `tiger_api`, `tradier`, `polygon`, or equivalent must not be imported anywhere in the new modules. A regression test enforces this list.
- No paper-trading API URLs or endpoints. Even Alpaca-paper / IBKR-paper URLs are out of scope; that is B013.
- No simulated fills, no virtual portfolio P&L tracking, no order lifecycle (pending / filled / settled). Mock Broker journals intent only.
- Mock Broker returns a fixed research account state defined in config (default: USD 250000 cash-equivalent research balance, zero open positions). It never claims a real balance.
- Journal format: JSON Lines, append-only. Each `submit_target_positions` call appends exactly one line. The journal file path is configurable; default lives under a designated research output directory and is gitignored. Each journal entry is immutable; rewriting or truncating the file is not part of the supported API.
- Target Positions output emits both percentage weights and dollar exposures. Dollar exposure is computed from the supplied account state: `dollar_exposure_i = weight_i * (account.cash + account.equity_value)`. Cash placeholder weight maps to a defensive sleeve symbol or to `CASH` per the existing master portfolio configuration.
- Manual any-time trigger: the bridge accepts an optional `signal_date` argument; if omitted it picks the latest period in the backtest result. The Mock Broker accepts target positions regardless of date; it does not enforce cadence.
- All artifacts are explicitly research-only. Reports, journals, and any docstring must contain "research-only, not a trading instruction" or equivalent. Tests verify the absence of `paper-execution`, `live-execution`, `executed-order`, and similar phrasings.
- Default CI and L1 tests remain fixture/mock-first and offline. No new environment variables, no secrets, no network.
- The Mock Broker journal must not contain any real account credential, API key, or environment-derived data.
- Master Portfolio path may continue to reuse B009 local snapshots only through explicit configuration. The bridge does not introduce any new snapshot semantics.
- No frontend dashboard, browser E2E, React/Next.js, Playwright, or Cypress.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/specs/B011-portfolio-allocation-risk-mvp-spec.md`
- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B009-public-data-snapshot-mvp-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`

## Proposed Implementation Shape

### Target Positions Output Schema

A `TargetPositions` dataclass (and equivalent JSON schema) with required fields:

- `schema_version` (string, e.g. `"target-positions/v1"`)
- `target_positions_id` (deterministic hash of inputs)
- `strategy_id` or `portfolio_id` (one of them, identifying the source)
- `signal_date` (ISO date)
- `generation_timestamp` (UTC ISO datetime, deterministic in tests)
- `snapshot_id` and optional `snapshot_manifest_path`
- `account_state_reference` (id of the account state used for dollar conversion)
- `entries[]`: list of `{ symbol, target_weight, target_dollar_exposure }`
- `defensive_allocation`: residual weight + dollar exposure mapped to defensive sleeve
- `research_limitations[]` (non-empty)
- `disclaimer`: literal "research-only; not a trading instruction" (or equivalent fixed string)

Validation:

- Weights non-negative, sum of `weights + defensive_allocation.weight` rounds to `1.0`.
- No leverage: total target dollar exposure `<=` `account.cash + account.equity_value`.
- No duplicate symbols.
- `signal_date` must be a valid trading day in the backtest result if generated through the bridge.

### Broker Adapter Interface

An `BrokerAdapter` abstract base class with method signatures only:

```python
class BrokerAdapter(ABC):
    @abstractmethod
    def submit_target_positions(self, positions: TargetPositions) -> JournalEntry: ...

    @abstractmethod
    def get_account_state(self) -> AccountState: ...

    @abstractmethod
    def get_open_orders(self) -> Sequence[OpenOrder]: ...
```

Module-level docstring states explicitly: "B012 only defines this abstract interface and a Mock implementation. Real paper / live broker adapters are out of scope and will be addressed in a later batch."

### Mock Broker

`MockBroker(account_state: AccountState, journal_path: Path)`:

- Reads `account_state` from config / constructor (no environment access).
- `submit_target_positions(positions)`:
  - Validates schema (weights, no leverage, no duplicates).
  - Computes deterministic `journal_entry_id`.
  - Appends one JSON line to `journal_path` containing `{ journal_entry_id, recorded_at, target_positions }`.
  - Returns the journal entry.
- `get_account_state()` returns the constructor-provided account state unchanged.
- `get_open_orders()` returns `()`.
- Never opens sockets, never reads `os.environ`, never imports any broker SDK.
- Journal file created if missing; truncation/rewrites are not exposed.

### Backtest-To-Paper Bridge

`generate_target_positions_from_master(result: MasterPortfolioBacktestResult, *, signal_date: date | None = None, account_state: AccountState) -> TargetPositions`:

- If `signal_date` is None, uses the latest `MasterRebalancePeriodResult`.
- If `signal_date` is provided, locates the matching period; fails closed if not present.
- Computes percentage weights from the period's effective weights and dollar exposures from the supplied account state.
- Maps residual / defensive allocation to the master portfolio's defensive sleeve symbol.
- Records snapshot and portfolio identifiers, includes research limitations from the backtest result, attaches the fixed disclaimer.

A parallel `generate_target_positions_from_strategy(result, *, signal_date, account_state)` accepts B006 momentum or B010 risk parity single-strategy backtest results for any-time triggering at the per-strategy level.

### Configuration

Add minimal configuration:

- Default research account state: `cash=USD 250000`, `equity_value=0.0`, `open_positions=()`.
- Default journal path: `data/paper-prep/mock-broker-journal.jsonl` (gitignored).
- All defaults override-able through explicit constructor / config arguments. No environment variable reads.

### Safety And Regression

All existing safety boundaries remain mandatory and B012-specific tests must prove:

- Forbidden import list (`ib_insync`, `alpaca`, `alpaca_trade_api`, `futu`, `futu-api`, `tiger`, `tiger_api`, `tradier`, `polygon`) is absent across new modules.
- No paper-trading API URLs or endpoints in source.
- No `os.environ` reads inside paper-prep modules.
- No socket I/O during target-positions generation or journal writes.
- Journal entries never contain credentials.
- Journals / reports / docstrings include the research-only disclaimer and never claim `paper-execution`, `live-execution`, `executed-order`, `filled`, or similar.
- Default constructors never reach out to networks.
- Backtest-to-paper bridge fails closed on missing `signal_date` (when explicitly requested but not present) and rejects leverage.

Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 Target Positions Output Format

Executor: generator.

Add a `TargetPositions` dataclass and equivalent JSON schema with both percentage weights and dollar exposures, strategy/portfolio identifiers, signal date, snapshot reference, account-state reference, research limitations, and a fixed research-only disclaimer. Validation must enforce non-negative weights, sum ≈ 1.0 including defensive allocation, no leverage against the account state, and no duplicate symbols. Tests cover schema serialization, validation success and failure paths.

### F002 Broker Adapter Abstract Interface

Executor: generator.

Add a `BrokerAdapter` ABC with `submit_target_positions`, `get_account_state`, and `get_open_orders` method signatures only. Module must explicitly document that real paper / live broker adapters are out of scope for B012. Regression test enforces forbidden broker SDK import list across new modules. Tests cover ABC instantiation failure and subclass contract.

### F003 Mock Broker Implementation

Executor: generator.

Implement `MockBroker(account_state, journal_path)` that reads a fixed research account state, journals submitted target positions to an append-only JSON Lines file (one line per call, immutable), returns the fixed account state, returns empty open orders, performs no network I/O, no env reads, and no broker SDK imports. Tests cover happy path append, schema validation failure rejection, deterministic journal entry id, account state pass-through, and empty open orders.

### F004 Backtest-To-Paper Bridge

Executor: generator.

Implement `generate_target_positions_from_master` and `generate_target_positions_from_strategy` bridge functions. Each accepts an optional `signal_date` (defaulting to the latest period) and a required `account_state`. Outputs include both percentage weights and dollar exposures. Manual any-time trigger is supported through direct function calls; fails closed if a requested `signal_date` is not present in the backtest result. Tests cover happy path conversion from B011 master and B006/B010 strategy results, default-latest-period selection, explicit signal date selection, missing signal date failure, and account-state-driven dollar exposure computation.

### F005 Safety Guard And Workflow Regression

Executor: generator.

Add regression coverage proving B012 introduces no forbidden broker SDK imports, no paper-trading API URLs, no environment / secret access, no socket I/O, no claim of live or paper-executed trades, and that journals carry the research-only disclaimer. Required local checks must pass: pytest, ruff, compileall, mypy.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. It must confirm B012 implements the minimal Paper Trading prep MVP, that target positions output is schema-validated and exposes both percentage weights and dollar exposures, that the Mock Broker journals intent only without simulated fills or network I/O, that the Backtest-to-Paper bridge supports any-time manual trigger and fails closed on invalid signal dates, that the forbidden-import safety guard regression is comprehensive, and that all no-live / no-secret / no-network-by-default / no-broker / no-paper / no-AI safety guards remain intact. Produce review and signoff under `docs/test-reports/`.

## Acceptance Summary

B012 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- `TargetPositions` schema exists, validates inputs, and emits both percentage weights and dollar exposures.
- `BrokerAdapter` ABC exists and is documented as B012-scope abstract only.
- Mock Broker journals submitted target positions to an append-only JSON Lines file, returns a fixed research account state, returns no open orders, and performs no network or env I/O.
- Backtest-to-Paper bridge accepts B011 master and B006/B010 strategy backtest results, supports any-time manual `signal_date`, defaults to latest period, fails closed on missing date.
- No forbidden broker SDK import or paper-trading API endpoint is introduced anywhere in B012 modules.
- All journals / reports / docstrings carry the research-only disclaimer; tests assert absence of live/paper-execution language.
- Default CI remains fixture/mock-first and offline.
- Evaluator signs off F006 with reports under `docs/test-reports/`.
