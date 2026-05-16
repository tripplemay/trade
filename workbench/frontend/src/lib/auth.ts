/**
 * Auth.js v5 entry point wired into the Next.js runtime.
 *
 * Behaviour (allowlist, HS256 JWS) lives in `auth-config.ts` so the same
 * configuration is unit-testable in plain Node (Vitest cannot resolve
 * Next.js's server runtime). This file simply invokes the factory and
 * re-exports the public surface used by route handlers and middleware.
 *
 * Critical: we pass a callback `() => buildAuthConfig()` instead of a
 * pre-built config object. Reading `process.env.GOOGLE_OAUTH_CLIENT_ID`
 * (and friends) inside that callback defers evaluation until request
 * time on the deployed server. With a top-level config object, Next.js's
 * server build evaluates the OAuth provider config at `next build` time
 * — where GOOGLE_OAUTH_CLIENT_ID is unset — and bakes `undefined` into
 * the bundle, surfacing as `?error=Configuration` on every sign-in.
 * The systemd EnvironmentFile=/etc/workbench/workbench.env provides the
 * real values at runtime, which the callback then sees on each request.
 */
import NextAuth from "next-auth";

import { buildAuthConfig } from "@/lib/auth-config";

export const { auth, handlers, signIn, signOut } = NextAuth(() => buildAuthConfig());
