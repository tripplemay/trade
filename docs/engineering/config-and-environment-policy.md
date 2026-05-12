# Config and Environment Policy

## Purpose

This policy defines safe configuration and environment behavior for the MVP. It is intended to prevent accidental live trading, hidden secret dependency, and non-reproducible tests.

## Environment Tiers

| Tier | Purpose | Default Allowed | External Calls | Secrets |
|---|---|---:|---:|---:|
| `local` | Developer runs and local backtests | Yes | No by default | No |
| `ci` | Required automated tests | Yes | No | No |
| `research` | Manual exploratory runs | Later optional | Optional, explicit | Optional, local only |
| `paper` | Broker paper trading | No in MVP | Requires explicit later authorization | Required later |
| `live` | Real-money trading | No | Requires separate user authorization | Required later |

## Configuration Sources

MVP defaults should be committed safe defaults. A required test run must not require:

- `.env`
- API keys
- Broker credentials
- Paid market data files
- Real account exports
- Network availability

Runtime configuration should support explicit file or CLI parameter loading in later implementation, but default values must remain local/CI-safe.

## Required Technical Decisions

- Python package with explicit module boundaries.
- `pytest` for tests.
- `ruff` for linting/formatting policy.
- `compileall` for basic import/syntax validation.
- `mypy` should be part of the intended engineering baseline, but B005 may stage adoption if early data models are still changing. If deferred, the reason must be documented in the B005 spec.

## Optional Public Data Download Scripts

B005 may include an optional script for public historical data if Planner explicitly scopes it. Such a script must be:

- Manual, not required by CI.
- Disabled by default.
- Clearly separated from fixture tests.
- Safe without credentials.
- Documented as best-effort and not a point-in-time production data source.

## Disallowed Behavior

- Auto-detecting credentials and switching into paper/live mode.
- Treating presence of `.env` as authorization.
- Running broker/data-vendor network calls in required CI.
- Failing required tests because an external service is unavailable.
- Writing real account data into the repository.
