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

export const authConfig = {
  providers: [
    Google({
      clientId: process.env.GOOGLE_OAUTH_CLIENT_ID,
      clientSecret: process.env.GOOGLE_OAUTH_CLIENT_SECRET,
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
      const allowed = process.env.ALLOWED_USER_EMAIL;
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
} satisfies NextAuthConfig;
