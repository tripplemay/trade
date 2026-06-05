# B037 Home Restructure Blocker 2026-06-05

## Scope

- F004 evaluator acceptance for B037 `verifying`
- L1: backend / frontend / Playwright gates, local `/api/home`, local `recent-errors`
- L2: production `trade.guangai.ai` health, route reachability, deployed SHA equivalence, VM systemd + alembic checks

## Result

- L1: PASS
- L2: FAIL
- Conclusion: do not sign off; return to `fixing`

## Evidence

### L1 passed

- Backend targeted B037 tests:
  - `./.venv/bin/python -m pytest workbench/backend/tests/unit/test_price_snapshot_repo.py workbench/backend/tests/unit/test_prices_provider.py workbench/backend/tests/unit/test_prices_cli.py workbench/backend/tests/unit/test_home_route.py workbench/backend/tests/safety/test_market_scheduler_scope.py -q`
  - Result: `29 passed in 0.81s`
- Backend full suite:
  - `cd workbench/backend && ../../.venv/bin/python -m pytest -q`
  - Result: `757 passed, 17 skipped in 8.88s`
- Backend static gates:
  - `./.venv/bin/python -m ruff check workbench/backend/workbench_api workbench/backend/tests`
  - Result: `All checks passed!`
  - `cd workbench/backend && ../../.venv/bin/python -m mypy workbench_api tests`
  - Result: `Success: no issues found in 247 source files`
- Frontend static + unit gates:
  - `cd workbench/frontend && npm run lint` → `No ESLint warnings or errors`
  - `cd workbench/frontend && npm run typecheck` → pass
  - `cd workbench/frontend && npm run test` → `40 passed (40), 198 passed (198)`
- Frontend Playwright:
  - `cd workbench/frontend && NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test`
  - Result: `44 passed (36.2s)`
- Local authed `/api/home` payload shape:
  - `curl -H "Cookie: authjs.session-token=<minted-local-test-cookie>" http://127.0.0.1:8723/api/home | jq`
  - Result:
    - `nav: 0.0`
    - `day_pnl: null`
    - `sleeves: [regime, risk_parity, satellite_us_quality]`
  - This matches the spec's allowed empty-account path (`nav=0`, `day_pnl=null`).
- Local authed recent-errors:
  - `curl -H "Cookie: authjs.session-token=<minted-local-test-cookie>" http://127.0.0.1:8723/api/debug/recent-errors | jq`
  - Result: `{"count":0,"records":[]}`

### L2 partial passes

- Public production health:
  - `curl -sS https://trade.guangai.ai/api/health | jq`
  - Result:
    - `status: "ok"`
    - `version: "77c50faa1b4ea7dc046312ac8c39f47d24ff9fe2"`
    - `db_connectivity: "ok"`
- Production root/login reachability:
  - `curl -i -sS https://trade.guangai.ai/`
  - Result: `307` redirect to `/login`
  - `curl -i -sS https://trade.guangai.ai/login`
  - Result: `200`, login page HTML renders
- Production `/api/home` exists and is auth-gated:
  - `curl -i -sS https://trade.guangai.ai/api/home`
  - Result: `401 Unauthorized`
- Production SHA equivalence:
  - `git log --oneline 77c50fa..HEAD`
  - Result: only `aa7e140 chore(B037): generator F001-F003 done + CI green → status=verifying`
  - By framework rule §10, this is acceptable non-product drift, not a blocker.
- Production DB migration:
  - `ssh tripplezhou@34.180.93.185 'sudo -n sqlite3 /var/lib/workbench/db/workbench.db "select version_num from alembic_version;"'`
  - Result: `0009_b037_price_snapshot`

### L2 blocker

- Required timer/service missing on production VM:
  - `ssh tripplezhou@34.180.93.185 'systemctl status workbench-prices.timer --no-pager || true; systemctl status workbench-prices.service --no-pager || true; systemctl list-unit-files | grep workbench-prices || true; ls /etc/systemd/system/workbench-prices.* 2>/dev/null || true'`
  - Result:
    - `Unit workbench-prices.timer could not be found.`
    - `Unit workbench-prices.service could not be found.`
    - no unit files listed
- This violates F004 L2 acceptance item `(8) price_snapshot/timer L2: workbench-prices.timer admin 安装 enabled`.

## Required Action

- Generator must treat the missing production `workbench-prices.{service,timer}` install as a real deployment gap and fix it in-product or in deploy flow, not as a testing artifact.
- After the fix, Codex should reverify:
  - `systemctl` sees both units
  - timer is installed and enabled
  - a manual run or timer evidence shows `price_snapshot` ingestion is wired on VM
  - production authenticated `/api/home` and browser Home UI checks can be completed

## Conclusion

B037 cannot be signed off in this round. L1 is clean, but L2 fails because the production `workbench-prices` timer/service required by B037 F001/F004 is not installed on the VM.

---

## Resolution (Generator — 2026-06-06)

**Root cause:** code + deploy flow were already complete and correct — the unit files ship in the release (`workbench-deploy.yml:176` rsyncs `systemd/`), reach the VM at `/srv/workbench/current/systemd/workbench-prices.{service,timer}`, and `deploy.sh:300-313` attempts install + `enable --now`. The install **silently warned** because the `deploy` user's sudoers (`/etc/sudoers.d/deploy-workbench`) only whitelists `systemctl restart/status` + `daemon-reload` for backend/frontend — not `/usr/bin/install` into `/etc/systemd/system/` nor `enable --now`. This is the identical one-time-admin-install pattern used for `workbench-market-context.timer` (B035) and `workbench-advisor.timer` (B036). The prices instance simply hadn't been run yet. **No product/deploy code change was required.**

**Fix:** user authorized direct VM admin access; Generator installed + enabled the timer one-time as `tripplezhou` (mirroring `deploy.sh` exactly):

```bash
sudo /usr/bin/install -m 644 /srv/workbench/current/systemd/workbench-prices.service /etc/systemd/system/workbench-prices.service
sudo /usr/bin/install -m 644 /srv/workbench/current/systemd/workbench-prices.timer   /etc/systemd/system/workbench-prices.timer
sudo /bin/systemctl daemon-reload
sudo /bin/systemctl enable --now workbench-prices.timer
sudo /bin/systemctl start workbench-prices.service   # manual one-shot to validate the read-only path
```

**Post-fix evidence (VM, 2026-06-06):**

- `ls -la /etc/systemd/system/workbench-prices.*` → both units installed (root:root, mode 644).
- `systemctl is-enabled workbench-prices.timer` → `enabled`; `is-active` → `active`.
- `systemctl list-timers workbench-prices.timer` → NEXT `Sat 2026-06-06 00:30:00 UTC` (00:30 between market-context 00:00 and advisor 01:00, as designed).
- `systemctl is-enabled workbench-market-context.timer workbench-advisor.timer workbench-prices.timer` → `enabled / enabled / enabled` (all three read-only timers now parity).
- Manual one-shot `workbench-prices.service` → `Result=success ExecMainStatus=0 ActiveState=inactive`.
- Journal: `price_cli_no_holdings` → `price-snapshot ingest done — symbols=0 saved=0 errors=0`.
  - **Recorded per F004 L2 item (8) "记录哪种":** the empty result is the **no-holdings** case (the production research account currently has no positions), **not** a TIINGO-missing case. `price_snapshot` table has 0 rows by design — there are no held symbols to fetch. This is consistent with the spec-allowed empty path (authed `/api/home` → `nav=0, day_pnl=null`, which Codex already confirmed in L1). The boundary-(r) read-only CLI path itself executed successfully end-to-end on prod.
- `sqlite3 .../workbench.db "select count(*) from price_snapshot;"` → `0` (expected, no holdings).
- `alembic_version` → `0009_b037_price_snapshot` (unchanged).
- Public `/api/health` → `200`, `version 77c50fa…`, `db_connectivity: ok`.

**Status:** `fixing → reverifying` (fix_rounds 1). Codex F004 L2 item (8) should now pass; remaining L2 items (authed `/api/home` 200, browser Home UI / mockup / no-execution / bilingual, old-dashboard-absent, HEAD≡main) are unaffected by this fix and were either already green or pending the browser pass.

**Durable-fix candidate (not done this round, surfaced to Planner):** the recurring "admin must hand-install each new timer" friction has now bitten three batches (B035/B036/B037). A durable fix would expand the `deploy` user's sudoers to whitelist `/usr/bin/install -m 644 * /etc/systemd/system/workbench-*.{service,timer}` + `systemctl enable --now workbench-*.timer`, so `deploy.sh`'s best-effort blocks succeed automatically. Deferred because it needs a one-time admin sudoers `apply` and is out of B037's feature scope; logged as a framework-learning candidate.
