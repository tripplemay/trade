# B022 npm audit deferral — Next 14 ecosystem advisories

**Date:** 2026-05-18 (B022 F014 fixing-round 1)
**Author:** Generator
**Status:** Deferred to B023 (Next 16 migration backlog).

## Context

Codex F014 verification (blocker `B022-F001-SEC`) flagged that
`npm audit --omit=dev` reported high-severity advisories against
`next@14.2.33` and `playwright@1.48`. As part of the fixing round we:

1. Upgraded `next` from `14.2.33` → `14.2.35` (latest 14.x patch).
2. Upgraded `eslint-config-next` to match: `14.2.33` → `14.2.35`.
3. Upgraded `@playwright/test` from `1.48.2` → `1.55.1`
   (clears the `<1.55.1` playwright advisory).
4. Upgraded `vitest` from `2.1.3` → `2.1.9` (clears the dev-tree
   advisory).

After the upgrades, `npm audit` reports **10 vulnerabilities (6
moderate / 4 high / 0 critical)** — down from 12 (1 critical) before
the fixing round. The critical class is cleared.

## Remaining advisories — why not patched

Every remaining `next` advisory affects a range like `9.3.4-canary.0
- 16.3.0-canary.5`. The only `npm audit fix` path is the
`--force` upgrade to `next@16.2.6`, which is a major-version
breaking change (App Router behaviour, React 19, middleware API,
`output: "standalone"` semantics). That is out of scope for a
fixing-round commit on a fresh production deploy.

The headline classes are:

- DoS in image optimizer / RSC handler / middleware proxy.
- HTTP request smuggling in rewrites.
- Cache poisoning in RSC responses + middleware redirects.
- XSS in App Router CSP nonces / `beforeInteractive` scripts.
- SSRF in WebSocket upgrades.

Workbench-specific exposure analysis:

| Class | Workbench surface | Effective risk |
|---|---|---|
| Image optimizer DoS | `/api/image` not used; no `<Image />` consumer in B022. | Low. |
| RSC handler DoS | App Router + RSC are used, but the surface is gated by Google OAuth + single-email allowlist. Unauthenticated probes redirect to `/login`. | Low. |
| Rewrite smuggling | `next.config.mjs` rewrites are dev-only and target `127.0.0.1:8723`. Production routing is nginx. | Negligible (production). |
| Cache poisoning (RSC) | Auth-gated; single-user. | Low. |
| CSP nonce XSS | App does not set CSP nonces today. | N/A. |
| WebSocket SSRF | App does not use upgrades. | N/A. |
| Pages Router i18n bypass | App is App-Router only; no `pages/` dir; no i18n. | N/A. |

The remaining advisories are residual risk on a single-user, auth-
gated surface and do not justify a B022-mid major upgrade. The
backlog tracks the migration (next entry below); B023 is the natural
window.

## Backlog hand-off

A new backlog entry should be added by the next planner run:

```json
{
  "id": "BL-WB-NEXT-16",
  "title": "Migrate workbench frontend to Next 16 + React 19",
  "description": "B022 F014 deferred all 13 Next 14.2.x advisories because the only patched line is 16.x. Plan the App-Router-compat upgrade (RSC behaviour, middleware API, output:standalone changes) as a dedicated batch, ideally before the satellite strategies (BL-B011-S2) land so the frontend stays one major behind production.",
  "decisions": [
    "Plan as its own batch (no mid-flight upgrade).",
    "Validate auth + Playwright authed project against the new App Router behaviour.",
    "Re-run npm audit and re-record this deferral file."
  ],
  "priority": "medium",
  "source": "B022 F014 fixing-round 1 deferral",
  "confirmed_at": "2026-05-18"
}
```

## Re-verification plan

The blocker entry asks Codex to verify the deferral is documented
when re-running F014. The L2 production browser checks remain the
same; the L1 / npm audit step should be re-run against this commit
and the remaining ≤10 advisories cross-checked against this file.
