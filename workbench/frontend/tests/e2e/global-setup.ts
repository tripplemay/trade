/**
 * B025 F006 fix-round 2: pre-warm Next.js dev-mode route compilation.
 *
 * Codex F006 reverify saw many protected-route tests fail with repeated
 * console ``Failed to load resource: 404 (Not Found)`` errors. The root
 * cause was Next.js dev-mode lazy compilation: the first visit to each
 * route compiles its server bundle + RSC chunks; in a resource-constrained
 * sandbox the compile lag overlaps with the test's network capture window
 * and the ``_next/static/*`` chunks 404 before they finish writing.
 *
 * This global setup runs *once* before any test starts. It mints a session
 * cookie (so authed routes don't redirect to /login) and hits every
 * NAV_ITEMS route via Playwright's request fixture. The first hit triggers
 * compile; subsequent hits return cached output. By the time the test
 * projects boot up, every route is warm.
 *
 * No-op when frontend already returns 200 on the first probe, so this
 * is cheap on a fast machine.
 */
import type { FullConfig } from "@playwright/test";
import { chromium } from "@playwright/test";
import { SignJWT } from "jose";

import { NAV_ITEMS } from "../../src/components/shell/nav-items";

const COOKIE_NAME = "authjs.session-token";
const COOKIE_DOMAIN = process.env.PLAYWRIGHT_COOKIE_DOMAIN ?? "127.0.0.1";

function resolveBaseUrl(config: FullConfig): string {
  const project = config.projects[0];
  return (
    project?.use?.baseURL ??
    process.env.PLAYWRIGHT_BASE_URL ??
    `http://127.0.0.1:${process.env.PORT ?? 3000}`
  );
}

async function mintSessionCookie(): Promise<{
  name: string;
  value: string;
  domain: string;
  path: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "Lax";
  expires: number;
}> {
  const secret = process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET;
  const email = process.env.ALLOWED_USER_EMAIL;
  if (!secret || !email) {
    throw new Error(
      "global-setup: NEXTAUTH_SECRET + ALLOWED_USER_EMAIL must be set before pre-warming authed routes.",
    );
  }
  const now = Math.floor(Date.now() / 1000);
  const exp = now + 60 * 60;
  const value = await new SignJWT({ email, sub: email, name: email })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(exp)
    .sign(new TextEncoder().encode(secret));
  return {
    name: COOKIE_NAME,
    value,
    domain: COOKIE_DOMAIN,
    path: "/",
    httpOnly: true,
    secure: false,
    sameSite: "Lax",
    expires: exp,
  };
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = resolveBaseUrl(config);
  // Lazy import for environments missing playwright browsers (CI install
  // is a separate step). If chromium is unavailable, skip warm-up; the
  // tests still have their own setup project so worst case is a dev-mode
  // compile race that the test retries cover.
  let browser;
  try {
    browser = await chromium.launch();
  } catch {
    return;
  }
  try {
    const cookie = await mintSessionCookie();
    const context = await browser.newContext({ baseURL });
    await context.addCookies([cookie]);
    const page = await context.newPage();
    // Warm-up: visit every protected route once + /login + /risk +
    // /reports/[slug] sample so dev mode compiles each bundle.
    const paths = new Set<string>([
      "/login",
      ...NAV_ITEMS.map((item) => item.href),
      "/reports/master_portfolio-2026-06-01",
    ]);
    for (const href of paths) {
      try {
        await page.goto(href, { waitUntil: "load", timeout: 90_000 });
      } catch {
        // Best-effort: ignore individual warm-up failures so the test
        // projects can still execute (and the diagnostics in
        // protected-routes.spec.ts will catch real regressions).
      }
    }
    await context.close();
  } finally {
    await browser.close();
  }
}
