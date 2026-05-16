/**
 * Pure NextAuth configuration object + helpers, kept free of the
 * `NextAuth(...)` factory call so Vitest (which runs in plain Node and
 * cannot resolve the Next.js server runtime) can exercise the callbacks
 * directly. `lib/auth.ts` re-exports this config wrapped through the
 * factory for actual use in the Next.js app.
 *
 * Two non-default choices anchor the workbench's single-user model and the
 * backend interop:
 *
 *  1. `signIn` callback enforces the single-email allowlist
 *     (`ALLOWED_USER_EMAIL`). Anyone else returning from Google OAuth gets
 *     `false`, which Auth.js surfaces as the documented "AccessDenied"
 *     error on the `/login` page (`pages.error`).
 *
 *  2. `jwt.encode` / `jwt.decode` are overridden to use HS256 JWS instead
 *     of Auth.js's default JWE. That lets the FastAPI backend (which
 *     verifies the same cookie via python-jose using `NEXTAUTH_SECRET`)
 *     read the token directly without porting Auth.js's HKDF + JWE key
 *     derivation to Python.
 */
import type { NextAuthConfig } from "next-auth";
import type { JWT } from "next-auth/jwt";
import Google from "next-auth/providers/google";
import { SignJWT, jwtVerify } from "jose";

export const DEFAULT_SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30 days

/**
 * Production NextAuth requires the callback URL to live under the
 * `trade.guangai.ai` apex; otherwise a misconfigured deploy would happily
 * accept Google's OAuth redirect to an attacker-controlled host. Run this
 * at boot so the failure surfaces before any user request is served.
 */
export function assertProductionCallbackUrl(env: NodeJS.ProcessEnv = process.env): void {
  if (env.NODE_ENV !== "production") return;
  const url = env.NEXTAUTH_URL ?? env.AUTH_URL ?? "";
  if (!url.includes("trade.guangai.ai")) {
    throw new Error(
      "NEXTAUTH_URL / AUTH_URL must contain 'trade.guangai.ai' in production builds; " +
        "OAuth callbacks would otherwise resolve to an unauthorized host. " +
        `Got: '${url || "<unset>"}'`,
    );
  }
}

function _normalize(email: string | null | undefined): string {
  return (email ?? "").trim().toLowerCase();
}

function _resolveSecret(secret: string | Buffer | (string | Buffer)[] | undefined): Uint8Array {
  const raw = Array.isArray(secret) ? secret[0] : secret;
  if (!raw) {
    throw new Error("NEXTAUTH_SECRET is required; refusing to mint anonymous tokens.");
  }
  return typeof raw === "string" ? new TextEncoder().encode(raw) : new Uint8Array(raw);
}

/**
 * Bracket-access read of `process.env` to defeat webpack DefinePlugin.
 *
 * Next.js 14's webpack inlines every static `process.env.X` access —
 * even inside server-only code, even inside function bodies — when X
 * is unset in the `next build` env, replacing the access site with a
 * literal `undefined`. That swallowed `GOOGLE_OAUTH_CLIENT_ID` /
 * `GOOGLE_OAUTH_CLIENT_SECRET` from the build (the deploy workflow
 * only exports `NEXTAUTH_URL` to the build step), baking Google
 * provider config as `{ clientId: undefined, clientSecret: undefined }`
 * into the standalone bundle and producing `?error=Configuration` on
 * every sign-in attempt in production.
 *
 * Bracket access (`env[name]` with `name` as a variable) is not a
 * pattern DefinePlugin matches, so the runtime read survives the build.
 * The verification is `grep -roE "process.env.[A-Z_]+" .next/server/`
 * — that pattern should not list GOOGLE_OAUTH_CLIENT_ID at all once
 * this function is the only access site, and the runtime read of
 * `env["GOOGLE_OAUTH_CLIENT_ID"]` succeeds with the systemd-injected
 * value.
 */
function readEnv(env: NodeJS.ProcessEnv, name: string): string | undefined {
  return env[name];
}

/**
 * Build the NextAuthConfig from the supplied process env. Wrapped in a
 * function (rather than a top-level const) so `NextAuth(() => buildAuthConfig())`
 * defers the read until request time. See `readEnv` above for why
 * bracket access is required.
 */
export function buildAuthConfig(env: NodeJS.ProcessEnv = process.env): NextAuthConfig {
  return {
    // Auth.js v5 switched the canonical env var prefix from `NEXTAUTH_*`
    // to `AUTH_*` and no longer auto-falls-back to NEXTAUTH_SECRET inside
    // `next-auth@5.0.0-beta`. Without this explicit pass, every endpoint
    // that touches the JWT (csrf, session, providers) returns 500
    // "There was a problem with the server configuration" because the
    // resolved secret is undefined. Keep `NEXTAUTH_SECRET` as the
    // primary key (it's what /etc/workbench/workbench.env ships and what
    // the FastAPI backend reads via python-jose), with `AUTH_SECRET` as
    // an alternate spelling if someone re-bootstraps the env file.
    secret: readEnv(env, "NEXTAUTH_SECRET") ?? readEnv(env, "AUTH_SECRET"),
    // Auth.js v5 refuses to trust the X-Forwarded-Host header behind a
    // reverse proxy unless the deployer says so explicitly. nginx on the
    // production VM sets that header from the public hostname
    // (trade.guangai.ai); without `trustHost: true`, every /api/auth/*
    // endpoint that needs the URL returns the same opaque
    // "server configuration" 500 as a missing secret.
    trustHost: true,
    providers: [
      Google({
        clientId: readEnv(env, "GOOGLE_OAUTH_CLIENT_ID"),
        clientSecret: readEnv(env, "GOOGLE_OAUTH_CLIENT_SECRET"),
      }),
    ],
    session: { strategy: "jwt", maxAge: DEFAULT_SESSION_MAX_AGE_SECONDS },
    pages: {
      signIn: "/login",
      error: "/login",
    },
    callbacks: {
      async signIn({ profile }) {
        // Re-check the production callback URL guard at OAuth completion.
        // Doing it here (instead of at module load) keeps `next build` from
        // tripping the assertion while still failing loud the first time a
        // misconfigured production server actually handles a login.
        assertProductionCallbackUrl();
        const allowed = readEnv(process.env, "ALLOWED_USER_EMAIL");
        if (!allowed) {
          return false;
        }
        return _normalize(profile?.email) === _normalize(allowed);
      },
      async jwt({ token, profile }) {
        if (profile?.email && !token.email) {
          token.email = profile.email;
        }
        return token;
      },
    },
    jwt: {
      async encode({ token, secret, maxAge }) {
        const key = _resolveSecret(secret);
        const now = Math.floor(Date.now() / 1000);
        const exp = now + (maxAge ?? DEFAULT_SESSION_MAX_AGE_SECONDS);
        return await new SignJWT(token ?? {})
          .setProtectedHeader({ alg: "HS256", typ: "JWT" })
          .setIssuedAt(now)
          .setExpirationTime(exp)
          .sign(key);
      },
      async decode({ token, secret }) {
        if (!token) return null;
        const key = _resolveSecret(secret);
        try {
          const { payload } = await jwtVerify(token, key, { algorithms: ["HS256"] });
          return payload as JWT;
        } catch {
          return null;
        }
      },
    },
  };
}

/**
 * Eager evaluation for unit tests. Vitest runs in a plain Node context
 * where most production env vars are unset; tests only exercise the
 * callbacks + jwt encode/decode + pages, none of which depend on the
 * Google provider config. Production code MUST use `buildAuthConfig`
 * inside the NextAuth() factory call (see `lib/auth.ts`).
 */
export const authConfig: NextAuthConfig = buildAuthConfig();
