# B031 LLM Gateway Blocker Report

- Date: 2026-05-27
- Batch: B031-llm-gateway
- Sprint: F003
- Evaluator: Codex
- Verdict: L1 PASS / L2 FAIL

## Summary

B031 first-round verification cannot sign off. Local L1 gates all pass, but the production smoke required by F003 fails: `LLMGateway().health_check()` cannot reach the gateway and raises `httpx.ConnectError`. This is a real production wiring/runtime issue, not a local-only artifact.

## L1 Result

- backend `pytest`: `466 passed, 2 skipped`
- backend `ruff`: pass
- backend `mypy`: pass
- alembic: `upgrade head -> downgrade 0003_b027_tiingo_budget_log -> upgrade head` pass
- trade `pytest`: `778 passed`
- trade `mypy`: pass
- frontend tests: `172 passed`
- frontend build: pass
- Playwright: `38 passed`
- safety checks:
  - `AIGC_GATEWAY_API_KEY` wiring present in `.env.example`, `settings.py`, `deploy.sh`, `bootstrap-env.yml`
  - hardcoded model-name guard still green
  - frontend build artifact contains no gateway secret / model-name leakage

## L2 Result

Pass:

- production `/api/health.version` equals local `main` HEAD:
  - `b002ef59eef58e9ed40c1f22512037c7f3650c50`
- VM `/etc/workbench/workbench.env` contains `AIGC_GATEWAY_API_KEY`
- production SQLite contains table `llm_budget_log`
- authenticated `/api/debug/recent-errors` returns `{"count":0,"records":[]}`
- `llm_budget_log` aggregate remained unchanged at `0` after the failed smoke attempt

Fail:

- VM smoke command:
  - `LLMGateway().health_check()`
  - expected: returns `True`
  - actual: raises `httpx.ConnectError: [Errno -2] Name or service not known`

## Evidence

### Production smoke failure

Observed on production VM under the deployed backend working directory:

```text
BEFORE=0
aigc_gateway_network_retry
aigc_gateway_network_retry
aigc_gateway_network_retry
httpx.ConnectError: [Errno -2] Name or service not known
AFTER=0
```

This also proves the failed health check did not increment the budget log.

### Code-level pointer

The deployed backend still defaults `LLMGateway` to the placeholder base URL in [gateway.py](/Users/yixingzhou/project/trade/workbench/backend/workbench_api/llm/gateway.py:43):

```python
AIGC_GATEWAY_BASE_URL = "https://aigc-gateway.example.com"
```

and the constructor default is still wired from that constant in [gateway.py](/Users/yixingzhou/project/trade/workbench/backend/workbench_api/llm/gateway.py:141).

## Blocker

F003 L2 acceptance explicitly requires:

- production `LLMGateway().health_check()` succeeds
- gateway `/balance` smoke is reachable
- health check does not increment `llm_budget_log`

Only the last sub-condition is currently true. The production gateway base URL / service wiring is not valid at runtime, so signoff must be blocked.

## Required Fix

Generator needs to make production `LLMGateway().health_check()` resolve a real reachable gateway endpoint instead of the placeholder host, then return the batch in `reverifying`.
