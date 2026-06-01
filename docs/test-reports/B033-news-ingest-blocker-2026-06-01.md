# B033 News Ingest Blocker 2026-06-01

## Scope

- F004 Codex L1 + L2 verification for B033 News Ingest.
- L1 local gates: backend tests, lint, mypy, alembic reversibility, frontend lint/typecheck/vitest/Playwright, static boundary grep.
- L2 production VM gates: health SHA, recent errors, alembic head, news scheduler/cron/systemd absence, B026 banner absence, and production snapshot directory state.

## Result

**FAIL / blocker.**

L1 passed and most L2 checks passed, but production does not satisfy the required snapshot-directory invariant:

- Expected: production VM `data/snapshots/news/` exists and is empty.
- Actual: both checked candidate locations are missing:
  - `/srv/workbench/current/data/snapshots/news` -> missing
  - `/var/lib/workbench/data/snapshots/news` -> missing

This violates F004 L2 acceptance and prevents signoff.

## Evidence

### L1 Passed

```text
git pull --ff-only origin main
Already up to date.

Backend:
python -m pytest tests -q
570 passed, 2 skipped

python -m ruff check .
All checks passed!

python -m mypy
Success: no issues found in 179 source files

Alembic:
0005_b033_news (head) -> downgrade to 0004_b031_llm_budget_log -> upgrade to 0005_b033_news (head)

Frontend:
npm run lint
No ESLint warnings or errors

npm run typecheck
pass

npm test
172 passed

Playwright:
38 passed
```

Note: the first Playwright attempt failed because the local dev server was started without `NEXTAUTH_SECRET`, producing Auth.js `MissingSecret` and redirecting protected pages to `/login`. Re-running with the same test env shape used by CI passed.

### L2 Passed

```text
curl -fsS https://trade.guangai.ai/api/health
{"status":"ok","version":"843fbef3696dfec078103fb7f3993fedb5dd0a5a","db_connectivity":"ok",...}

git rev-parse HEAD
843fbef3696dfec078103fb7f3993fedb5dd0a5a
```

Production service and scheduler boundary checks:

```text
current=/srv/workbench/releases/843fbef3696dfec078103fb7f3993fedb5dd0a5a
release_sha=843fbef3696dfec078103fb7f3993fedb5dd0a5a
service_backend=active
service_frontend=active
scheduler_py=absent
news_scheduler_imports=absent
workbench_news_systemd_refs=absent
all_user_crontab_news=absent
```

Production DB as deploy user:

```text
deploy_user=deploy
alembic_current=0005_b033_news (head)
alembic_version_db=0005_b033_news
news_table_present=True
```

Authenticated production recent errors and protected auth:

```text
recent_errors_secure_cookie={"count":0,"records":[]}
protected_test_secure_cookie={"status":"ok","email":"tripplezhou@gmail.com"}
```

B026 banner remains decommissioned:

```text
/strategies_banner_hits=0
/reports_banner_hits=0
/recommendations_banner_hits=0
/risk_banner_hits=0
```

### L2 Failed

Production snapshot directory check:

```text
snapshots_news_dir=release_missing
var_snapshots_news_dir=var_missing
repo_snapshots_news_listing=
var_snapshots_news_listing=
```

## Required Action

Generator should make the production deploy create the canonical writable B033 news snapshot directory without running ingest:

- Create the agreed production path for `data/snapshots/news/`.
- Ensure it is present after deploy and empty before any manual CLI fetch.
- Keep news ingest production-disabled: no scheduler, cron, APScheduler, aiocron, or systemd news fetch unit.
- Re-run deploy so the VM state matches the acceptance.

The fix should not run `python -m workbench_api.news.cli fetch` in production as part of this batch.

## Conclusion

Do not sign off B033 yet. Status should return to `fixing` for the missing production snapshot directory.
