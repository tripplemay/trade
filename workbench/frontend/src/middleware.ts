/**
 * Workbench auth middleware.
 *
 * Everything is private by default. Anonymous visitors get redirected to
 * `/login` unless they're already on `/login` or hitting NextAuth's own
 * route handlers / the public health probe. The matcher below excludes
 * static assets so Next.js can still serve `/favicon.ico`, `/_next/*`, etc.
 *
 * In production nginx routes `/api/*` directly to FastAPI, so the
 * `/api/health` and `/api/protected-test` allowlist entries below are
 * defensive — they cover the local dev rewrite path where Next.js does see
 * the request.
 */
import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";

// Every `/api/*` path is either:
//   - owned by NextAuth (the `/api/auth/*` handlers under app/api/auth/)
//     and handles its own session establishment, or
//   - proxied to the FastAPI backend (production via nginx, dev via the
//     next.config.mjs rewrites) where `require_authenticated_user`
//     re-checks the session cookie and emits 401 on missing auth.
//
// Either way, the Next.js middleware does not need to second-guess auth
// for `/api/*` — its redirect-to-`/login` is for browser navigation
// only. B022 F014 fix: the prior `/api/health` + `/api/auth` allowlist
// dropped every B022 backend route into the redirect path, which
// short-circuited next.config.mjs rewrites and produced `/api/strategies
// → 404` in Playwright once the dev-rewrite list grew (the rewrite
// never got a chance to fire because middleware returned a 307 first).
const PUBLIC_PATH_PREFIXES = ["/login", "/api/"] as const;

function isPublic(pathname: string): boolean {
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export default auth((req) => {
  const { nextUrl } = req;
  if (isPublic(nextUrl.pathname)) {
    return NextResponse.next();
  }
  if (!req.auth) {
    const loginUrl = new URL("/login", nextUrl);
    if (nextUrl.pathname !== "/") {
      loginUrl.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
    }
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
