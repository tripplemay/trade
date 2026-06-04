# B034 News Ticker Embedding Blocker 2026-06-04

## Scope

- F004 Codex L1 + L2 verification for B034 News↔ticker/sleeve association + Embedding.
- L1 local gates: backend tests, safety guards, lint, mypy, alembic reversibility, frontend lint/typecheck/vitest/Playwright.
- L2 production VM gates: health SHA / HEAD equivalence, authenticated route behavior, alembic head, no scheduler/cron/systemd, structured Recommendations NewsPanel behavior.

## Result

**FAIL / blocker.**

L1 passed, and most L2 infra checks passed, but production fails the core user-facing B034 route:

- Expected: authenticated `GET /api/recommendations/news?sleeve=satellite_us_quality` returns `200` with pure structured payload.
- Actual: production returns `500 Internal Server Error`.

This violates F004 L2 acceptance and prevents signoff.

## Evidence

### L1 Passed

```text
git pull --ff-only origin main
Already up to date.

Backend:
python -m pytest tests -q
643 passed, 2 skipped

python -m pytest tests/safety/test_b034_no_generative_ai.py \
  tests/safety/test_news_schema_metadata_only.py \
  tests/safety/test_news_no_scheduler.py -q
12 passed

python -m ruff check .
All checks passed!

python -m mypy workbench_api tests
Success: no issues found in 196 source files

Alembic:
0006_b034_news_embedding (head)
-> downgrade to 0005_b033_news
-> upgrade to 0006_b034_news_embedding (head)

Frontend:
npm run lint
No ESLint warnings or errors

npm run typecheck
pass

npm test
176 passed

Playwright:
39 passed
```

### L2 Passed

Production health and HEAD equivalence:

```text
curl -fsS https://trade.guangai.ai/api/health
{"status":"ok","version":"d1c2b30a1a09dbbfd5991e897e881703fd8fc092","db_connectivity":"ok",...}

git rev-parse HEAD
133d60950379f2c835234e6cff50483accbd0cce

git diff --name-only d1c2b30..133d609
.auto-memory/project-status.md
framework/proposed-learnings.md
progress.json
```

结论：production 与 `main` 不同 SHA，但仅有元数据差异，产品代码无漂移。

Authenticated production checks:

```text
/api/debug/recent-errors -> 200 {"count":0,"records":[]}
/api/protected-test -> 200 {"status":"ok","email":"tripplezhou@gmail.com"}
```

Production DB / schema:

```text
WORKBENCH_DB_URL -> sqlite:///var/lib/workbench/db/workbench.db
alembic_version -> 0006_b034_news_embedding
tables -> news, news_embedding
```

Production scheduler boundary and snapshot directory:

```text
scheduler_py_absent
cron_absent
systemd_units_absent

readlink -f /srv/workbench/current/data/snapshots/news
/var/lib/workbench/data/snapshots/news

snapshot_dir_empty
```

### L2 Failed

Authenticated production route:

```text
GET /api/recommendations/news?sleeve=satellite_us_quality
-> 500 {"detail":"Internal Server Error"}
```

Recent errors after triggering the route:

```text
{"count":2,"records":[
  {
    "path":"/api/recommendations/news",
    "exception_type":"FileNotFoundError",
    "exception_message":"[Errno 2] No such file or directory: '/srv/workbench/releases/data/fixtures/us_quality_momentum/universe.csv'"
  }
]}
```

Backend journal / traceback:

```text
File "/srv/workbench/releases/d1c2b30.../backend/workbench_api/news/ticker_match.py", line 97, in _load_universe_names
  with UNIVERSE_CSV.open(encoding="utf-8") as fh:
FileNotFoundError: [Errno 2] No such file or directory:
'/srv/workbench/releases/data/fixtures/us_quality_momentum/universe.csv'
```

## Root Cause

Production runtime path for B034 sleeve ticker loading depends on a fixture file under `data/fixtures/us_quality_momentum/universe.csv`, but the deploy artifact on VM does not include that fixture path under `/srv/workbench/releases/...`.

Local and CI passed because the repo checkout contains the fixture file. Production fails because the deployed release tree does not.

## Required Action

Generator should remove the production runtime dependency on the repo fixture path, or ensure the deploy artifact carries the required universe data in a production-safe location.

Acceptable fix directions:

- Move the required universe data into a deployed runtime asset path that is shipped to VM, or
- Replace runtime file loading with an already-deployed in-repo/runtime-safe source, or
- Materialize the 27+4 ticker universe in code/config already present in deploy artifact.

Constraints that must remain true:

- `GET /api/recommendations/news` stays pure structured, auth-gated, same-origin.
- No scheduler / cron / systemd ingest.
- No generative AI text.
- No new secret introduction.

## Conclusion

Do not sign off B034 yet. Status should return to `fixing` for the production `GET /api/recommendations/news` 500 blocker.
