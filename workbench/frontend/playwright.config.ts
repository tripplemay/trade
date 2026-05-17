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
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
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
      testMatch: [
        "e2e/home-loads.spec.ts",
        "safety/disclaimer-present.spec.ts",
      ],
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
      testMatch: ["e2e/protected-routes.spec.ts"],
    },
  ],
});
