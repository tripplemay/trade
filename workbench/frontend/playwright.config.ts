import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 3000);
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`;

// Relative to the project root (Playwright's CWD); auth-setup.ts writes
// to the same path. Keeping it relative avoids depending on __dirname
// (config files run before Playwright fixes the runtime module mode).
const SESSION_STATE_FILE = path.join("tests", "e2e", ".auth", "session.json");

export default defineConfig({
  testDir: "./tests",
  globalSetup: require.resolve("./tests/e2e/global-setup.ts"),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // Retries help tolerate the dev-mode lazy-compile race in resource-
  // constrained sandboxes; B025 F006 reverify spent a fix-round on
  // repeated `_next/static/* 404` console errors that only appeared on
  // the very first compile pass. Setting retries=2 even outside CI keeps
  // ad-hoc local runs robust without slowing the happy path.
  retries: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    // Dev-mode `next dev` compiles routes on first hit; the strategies
    // page in particular pulls in AG Grid + 3 chart wrappers and easily
    // pushes first-paint past Playwright's default 30s. The production
    // build doesn't have this lag but we run E2E against the dev server
    // (so the rewrite proxy + HMR are intact). Bumping the per-test
    // navigation timeout absorbs the cold compile without slowing the
    // happy path; warm hits stay sub-second.
    navigationTimeout: 90_000,
    actionTimeout: 15_000,
  },
  timeout: 120_000,
  // `expect(...)` matchers default to 5s; the click-navigation test
  // hops across 7 routes where some need a cold compile, so bump the
  // matcher timeout to match `actionTimeout`.
  expect: { timeout: 15_000 },
  projects: [
    // 1. Mint the session storageState used by the authed project below.
    //    Lives in its own project so the storage file is regenerated
    //    once per test run and the dependent projects can run in parallel.
    {
      name: "setup",
      testDir: "./tests/e2e",
      testMatch: /auth-setup\.ts/,
    },

    // 2. Anonymous coverage — login page + middleware redirect smoke +
    //    the disclaimer regression for the only unauthenticated surface.
    {
      name: "anon",
      use: { ...devices["Desktop Chrome"] },
      testMatch: ["e2e/home-loads.spec.ts", "safety/disclaimer-present.spec.ts"],
    },

    // 3. Authed coverage — the 7 protected routes. Depends on `setup` so
    //    the storageState file is in place before any test runs.
    {
      name: "authed",
      use: {
        ...devices["Desktop Chrome"],
        storageState: SESSION_STATE_FILE,
      },
      dependencies: ["setup"],
      testMatch: [
        "e2e/protected-routes.spec.ts",
        "e2e/b025-us-quality-bilingual.spec.ts",
        "e2e/b026-synthetic-banner.spec.ts",
        "e2e/b034-sleeve-news.spec.ts",
        "e2e/b035-market-context.spec.ts",
        "e2e/b036-advisor.spec.ts",
        "e2e/b037-home.spec.ts",
        "e2e/b040-metrics.spec.ts",
        "e2e/b041-recommendations.spec.ts",
        "e2e/b042-risk-tooltips.spec.ts",
      ],
    },
  ],
});
