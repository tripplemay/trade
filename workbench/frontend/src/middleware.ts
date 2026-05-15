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

const PUBLIC_PATH_PREFIXES = ["/login", "/api/auth", "/api/health"] as const;

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
