/**
 * Canonical research-only disclaimer reused on every workbench route.
 *
 * Stability of this constant is asserted by both the Vitest unit test and the
 * Playwright safety test `disclaimer-present.spec.ts` (delivered in B020 F003).
 * Wording is sourced from PRD §Disclaimer and must remain in sync there.
 */
export const DISCLAIMER_TEXT =
  "Research-only. This workbench surfaces backtests and recommendations for study; " +
  "it never authorizes paper or live trading.";
