/**
 * Auth.js v5 entry point wired into the Next.js runtime.
 *
 * Behaviour (allowlist, HS256 JWS) lives in `auth-config.ts` so the same
 * configuration is unit-testable in plain Node (Vitest cannot resolve
 * Next.js's server runtime). This file simply invokes the factory and
 * re-exports the public surface used by route handlers and middleware.
 *
 * The factory takes the SYNC config object form (not a callback). The
 * callback form `NextAuth(() => buildAuthConfig())` breaks
 * `export default auth(...)` in `middleware.ts` — Next.js's middleware
 * compiler refuses with "must export a `middleware` or a `default`
 * function" because under the callback form `auth` lazy-initialises
 * and the default export resolves to something the static analyser
 * does not see as a function.
 *
 * The `process.env.GOOGLE_OAUTH_CLIENT_ID` build-time inlining fix
 * therefore lives entirely in `auth-config.ts`: `buildAuthConfig(env)`
 * reads env via bracket access on a function parameter, which webpack
 * DefinePlugin cannot statically replace. The top-level `authConfig =
 * buildAuthConfig()` evaluates at module load (which is service-start
 * time on the deployed VM with the systemd-injected env present), not
 * at `next build` time — server modules under app/ are not run by the
 * build, only bundled.
 */
import NextAuth from "next-auth";

import { authConfig } from "@/lib/auth-config";

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig);
