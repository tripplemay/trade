/**
 * Auth.js v5 entry point wired into the Next.js runtime.
 *
 * Behaviour (allowlist, HS256 JWS) lives in `auth-config.ts` so the same
 * configuration is unit-testable in plain Node (Vitest cannot resolve
 * Next.js's server runtime). This file simply invokes the factory and
 * re-exports the public surface used by route handlers and middleware.
 */
import NextAuth from "next-auth";

import { authConfig } from "@/lib/auth-config";

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig);
