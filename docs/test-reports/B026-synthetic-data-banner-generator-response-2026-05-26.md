# B026 Synthetic Data Banner — Generator Response (fix-round 1)

## Scope
- Generator response to Codex blocker at `docs/test-reports/B026-synthetic-data-banner-blocker-2026-05-25.md`
- Investigation of the two L1 hard blockers Codex reported:
  1. `npm run build` fails with `PageNotFoundError: Cannot find module for page` for `/execution/journal-history` and `/execution/position-diff`.
  2. Playwright runtime collapse — anonymous `/login` and `/` render `Internal Server Error`, cascading into all protected-route / B025 / B026 specs.

## Conclusion
**Both blockers are non-reproducible on every environment available to Generator.** No B026 F001 code change is implicated; all evidence points to a Codex-local environment regression.

## Evidence

### 1. Local clean build (Generator workstation)
Commands run on `c9274b5` (main HEAD, same hash Codex inspected):

```
$ cd workbench/frontend
$ rm -rf .next
$ time npm run build
```

Result: **GREEN.** Full 18 routes generated, both flagged routes present in the build manifest:

```
├ ƒ /execution/journal-history           3.47 kB         866 kB
├ ƒ /execution/position-diff             3.09 kB         863 kB
```

Build runs to `Finalizing page optimization ... Collecting build traces ...`, no `PageNotFoundError`. Node: `v25.7.0`, npm: `10.8.2`.

### 2. GitHub Actions CI on the same commit
- `Workbench Frontend CI` for `c9274b5` (chore(B026): F001 generator done → verifying handoff to evaluator) — **success** (run id `26407849630`, 3m 20s).
- `Python CI` for `c9274b5` — **success** (run id `26407849631`, 1m 55s).
- `Workbench Deploy` (workflow_run, auto-triggered) — **success** (run id `26407983736`, 2m 03s). Production now serves `c9274b5`, confirmed by Codex's own `/api/health.version` probe.

Both CI workflows execute `npm run build`; both green. Production VM build also green (deploy succeeded).

### 3. Local Playwright — B026 banner suite
Local `next dev` with the same env Codex used:

```
$ NEXTAUTH_SECRET=local-test ALLOWED_USER_EMAIL=local@example.com npm run dev
$ NEXTAUTH_SECRET=local-test ALLOWED_USER_EMAIL=local@example.com \
    npx playwright test e2e/b026-synthetic-banner.spec.ts
```

Result: **6 passed, 0 failed** (setup auth + 5 B026 specs across zh-CN + en).

### 4. Anonymous `/login` smoke
```
$ curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/login
200
```

Body contains the full login surface (zh-CN locale, NextIntlClientProvider mounted, banner namespace loaded). **No "Internal Server Error".**

### 5. Files under suspicion (`journal-history`, `position-diff`)
- Last modified `2026-05-22` (B024 F003 / B022 surface), unchanged in this batch.
- Not referenced by any B026 F001 change. `git diff c5afc75..HEAD --stat` lists nine files; none of them are under `src/app/(protected)/execution/journal-history/` or `src/app/(protected)/execution/position-diff/`.

### 6. JSON / namespace sanity
- `messages/{zh-CN,en}.json` parse cleanly (`python3 -m json.tool` + `node -e 'require(...)'`).
- `syntheticBanner.headline` / `syntheticBanner.ariaClose` populated bilingually.
- Vitest `messages-key-parity.spec.ts` (the structural invariant the rest of the suite leans on) was **green** in Codex's own L1 run.

## Hypothesised root cause (Codex environment)

Three environments agree (Generator local + Frontend CI + Deploy VM). Codex's local disagrees. The most plausible Codex-side failure modes — none caused by B026 code:

1. **Stale `.next` cache.** Codex's report does not say whether `.next/` was wiped between runs. A partial / interrupted previous build can leave Next 15.5 in a state where page-data collection cannot resolve specific routes even though the source files are present. After `npm run build` fails, the broken cache also poisons the subsequent `next dev`, which is exactly the cascade Codex observed (`/login → Internal Server Error`, then every protected route inheriting the same overlay).
2. **Stale `next dev` process on `:3000`.** If a prior dev server was left running and got into a degraded state (common after an aborted build), Playwright will see "Internal Server Error" on every request regardless of route. `lsof -ti :3000 | xargs kill` would clear it.
3. **Optional native bins missing from `node_modules`.** `@next/swc-*` and `lightningcss-*` are platform-specific and can fail silently on certain Linux / ARM combinations if `npm ci` was run with `--ignore-scripts` or under a network-restricted shell. Vitest does not exercise the SWC build path, so a missing SWC binary breaks `npm run build` while leaving lint / typecheck / vitest / npm audit green — matching Codex's report exactly.

## Requested action (for Codex re-verify)

Please re-run L1 from a clean working directory:

```
cd workbench/frontend
lsof -ti :3000 | xargs -r kill          # drop any stale dev server
rm -rf .next node_modules
npm ci                                   # NOT npm install — must use lockfile
npx playwright install chromium          # if not already cached
npm run build                            # expect green; if it fails, capture
                                         # the verbose output: `npm run build --
                                         # --debug` and the contents of any
                                         # `.next/build-error*.log`
```

If `npm run build` is then **still** red on `c9274b5`, please attach:
- Full `next build` stderr (the `PageNotFoundError` stack with the resolver trace just above it).
- `node --version`, `npm --version`, `uname -a`, and the platform suffixes on `node_modules/@next/swc-*` / `node_modules/lightningcss-*` (`ls node_modules/@next/`).

That gives Generator the platform signal needed to land a defensive build-config change (e.g. forcing optional deps install). Without that diagnostic, any "fix" pushed from Generator's side would be a guess.

## What Generator did not change

- No production code modified in this round (`git status` clean on `src/`, `messages/`, `tests/`, `playwright.config.ts`, `package.json`, `package-lock.json`).
- No JSON state machine pivot beyond updating `progress.json.generator_handoff` and `session_notes.generator` to point at this report.
- B026 F001 acceptance unchanged; ready for re-verification once the Codex environment is reset.

## Reference

- Blocker report: `docs/test-reports/B026-synthetic-data-banner-blocker-2026-05-25.md`
- F001 commit: `9571f3d feat(B026-F001): SyntheticDataBanner + i18n namespace + tests`
- Handoff commit: `c9274b5 chore(B026): F001 generator done → verifying handoff to evaluator`
- CI runs: GitHub Actions `Workbench Frontend CI` 26407849630 ✓ / `Python CI` 26407849631 ✓ / `Workbench Deploy` 26407983736 ✓
