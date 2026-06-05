# B035 Market Context Blocker 2026-06-05

## Scope

- F004 Codex L1 + L2 verification for B035 Market Context.
- L1 local gates: backend tests, safety guards, lint, mypy, alembic reversibility, frontend lint/typecheck/vitest.
- L2 production VM gates: deployed SHA / HEAD equivalence, new env secrets present, alembic head, `/api/market-context` availability, systemd timer installed and enabled.

## Result

**FAIL / blocker.**

L1 passed, but L2 cannot pass because production has not been updated to B035 and the new production preconditions are not in place:

- production `/api/health.version` is still B034 SHA `ec02894...`, not current B035 `main` HEAD `e62aeb5...`
- production `/api/market-context` returns `404`
- production `workbench-market-context.timer` does not exist
- production VM env currently exposes `WORKBENCH_DB_URL`, but not `FRED_API_KEY` / `ALPHAVANTAGE_API_KEY`

This blocks B035 signoff.

## Evidence

### L1 Passed

```text
git pull --ff-only origin main
Already up to date.

Backend:
python -m pytest tests -q
701 passed, 2 skipped

python -m pytest tests/safety/test_market_scheduler_scope.py \
  tests/safety/test_news_no_scheduler.py \
  tests/safety/test_market_context_env_wiring.py -q
18 passed

python -m ruff check .
All checks passed!

python -m mypy workbench_api tests
Success: no issues found in 215 source files

Alembic:
0007_b035_market_context (head)
-> downgrade to 0006_b034_news_embedding
-> upgrade to 0007_b035_market_context (head)

Frontend:
npm run lint
No ESLint warnings or errors

npm run typecheck
pass

npm test
180 passed
```

### L2 Failed

Production health and HEAD:

```text
curl -fsS https://trade.guangai.ai/api/health
{"status":"ok","version":"ec0289495eaf10255c20064982ed33d554c5905b","db_connectivity":"ok",...}

git rev-parse HEAD
e62aeb5a99010a6192e2e1d723bbe553d35ca01d
```

Diff from deployed SHA to current HEAD contains B035 product files, not just metadata:

```text
git log --oneline ec02894..e62aeb5
e62aeb5 chore(B035): generator F001-F003 done + CI green → status verifying (Codex F004)
d0ce6ac fix(B035-F003): add market-context to Next dev rewrite allowlist (CI 404)
5019490 feat(B035-F003): GET /market-context + Home MarketContextCard
5ef0414 feat(B035-F002): market-context scheduler (systemd timer 只读拉取)
8d0922e feat(B035-F001): market context 基建 — schema + alembic 0007 + FRED/Alpha Vantage 双 adapter + 2 secret 四处接线
...
```

Representative file drift:

```text
workbench/backend/workbench_api/routes/market_context.py
workbench/backend/workbench_api/services/market_context.py
workbench/backend/workbench_api/db/migrations/versions/0007_b035_market_context.py
workbench/deploy/systemd/workbench-market-context.service
workbench/deploy/systemd/workbench-market-context.timer
workbench/frontend/src/components/market/MarketContextCard.tsx
```

Route and timer absence on production:

```text
curl -I https://trade.guangai.ai/api/market-context
HTTP/2 404

systemctl status workbench-market-context.timer
Unit workbench-market-context.timer could not be found.
```

Production VM env presence probe:

```text
WORKBENCH_DB_URL=<present>
```

Missing from the same probe:

```text
FRED_API_KEY
ALPHAVANTAGE_API_KEY
```

## Root Cause

This is an environment/deploy readiness gap, not an L1 code failure:

1. B035 product code has not yet been deployed to production.
2. The two new production secrets required by B035 (`FRED_API_KEY`, `ALPHAVANTAGE_API_KEY`) are not yet available in `/etc/workbench/workbench.env`.
3. Because deploy has not advanced, the new route, migration head, and systemd timer are absent from the VM.

## Required Action

Before Codex can complete B035 L2 and signoff, the following must happen:

- Deploy B035 production code so `/api/health.version` reaches a B035 SHA.
- Inject both new secrets into production VM env through the documented §12.9 path:
  - GitHub Secrets: `FRED_API_KEY`, `ALPHAVANTAGE_API_KEY`
  - bootstrap-env workflow -> `/etc/workbench/workbench.env`
- Run the B035 deploy flow so:
  - alembic head becomes `0007_b035_market_context`
  - `workbench-market-context.service` / `.timer` are installed
  - timer is enabled and active

After that, return the batch to `reverifying` and Codex can run the remaining authenticated L2 checks.

## Conclusion

Do not sign off B035 yet. The batch cannot pass L2 until production deploy + secrets setup is complete.
