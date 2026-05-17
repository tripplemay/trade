/**
 * Playwright "setup" project: mint an HS256 JWS session cookie and save
 * it as a storageState file the authed project depends on.
 *
 * Background: `workbench/frontend/src/lib/auth-config.ts` overrides
 * NextAuth's JWT encode/decode to use plain HS256 JWS (instead of the
 * default JWE) so the FastAPI backend can verify the same cookie via
 * `python-jose`. That same trick lets Playwright bypass Google OAuth in
 * CI — minting a token against `NEXTAUTH_SECRET` produces a cookie the
 * frontend middleware and backend dependency both accept as a
 * legitimate session for `ALLOWED_USER_EMAIL`.
 *
 * The fixture is gated on the same env vars production reads: missing
 * either one is a setup error, not a fall-back to anonymous, so a
 * test-config drift can never silently produce a "logged-out" run that
 * still looks green because the protected pages happen to render their
 * skeletons.
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { test as setup } from "@playwright/test";
import { SignJWT } from "jose";

// Playwright runs tests with CWD = project root (workbench/frontend/),
// so a CWD-relative path lands the storageState file under
// tests/e2e/.auth/. Avoiding `import.meta.url` keeps the file
// compatible with Playwright's CommonJS transpile (workbench/frontend
// has no "type": "module" in package.json).
export const SESSION_STATE_FILE = path.join("tests", "e2e", ".auth", "session.json");

// Cookie domain must match Playwright's baseURL host. CI binds the dev
// server to 127.0.0.1; the local convenience matches.
const COOKIE_DOMAIN = process.env.PLAYWRIGHT_COOKIE_DOMAIN ?? "127.0.0.1";
const COOKIE_NAME = "authjs.session-token";
const ONE_HOUR = 60 * 60;

setup("authenticate", async () => {
  const secret = process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET;
  const email = process.env.ALLOWED_USER_EMAIL;
  if (!secret || !email) {
    throw new Error(
      "auth-setup: NEXTAUTH_SECRET + ALLOWED_USER_EMAIL must be set so the minted " +
        "cookie matches what middleware/auth-config decode at request time.",
    );
  }

  const now = Math.floor(Date.now() / 1000);
  const exp = now + ONE_HOUR;
  const token = await new SignJWT({ email, sub: "playwright-auth-setup" })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuedAt(now)
    .setExpirationTime(exp)
    .sign(new TextEncoder().encode(secret));

  await mkdir(path.dirname(SESSION_STATE_FILE), { recursive: true });
  await writeFile(
    SESSION_STATE_FILE,
    JSON.stringify({
      cookies: [
        {
          name: COOKIE_NAME,
          value: token,
          domain: COOKIE_DOMAIN,
          path: "/",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
          expires: exp,
        },
      ],
      origins: [],
    }),
    "utf-8",
  );
});
