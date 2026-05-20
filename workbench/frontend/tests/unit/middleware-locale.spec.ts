/**
 * B024 F001 — middleware locale-cookie writer.
 *
 * Verifies the auth-independent half of the middleware: regardless of
 * whether NextAuth let the request through, an absent or invalid
 * NEXT_LOCALE cookie gets replaced with the negotiated value (zh-CN
 * fallback). A present, valid cookie is left untouched.
 *
 * The auth wrapper itself is exercised in production E2E (B021/B022
 * Playwright) so this spec focuses on the cookie-write behaviour in
 * isolation.
 */
import { describe, expect, it } from "vitest";
import { NextRequest, NextResponse } from "next/server";

import { ensureLocaleCookie } from "@/lib/locale-cookie";
import { DEFAULT_LOCALE, LOCALE_COOKIE, LOCALE_COOKIE_MAX_AGE } from "@/i18n-config";

function buildRequest(opts: {
  cookie?: string | null;
  acceptLanguage?: string | null;
}): NextRequest {
  const headers = new Headers();
  if (opts.cookie !== undefined && opts.cookie !== null) {
    headers.set("cookie", opts.cookie);
  }
  if (opts.acceptLanguage !== undefined && opts.acceptLanguage !== null) {
    headers.set("accept-language", opts.acceptLanguage);
  }
  return new NextRequest("http://localhost/", { headers });
}

function findSetCookie(res: NextResponse): { value: string; maxAge?: number } | null {
  // Parse the actual Set-Cookie response header — `res.cookies.get`
  // also surfaces request-cookies in a fresh NextResponse, so we go
  // directly to what the browser will see.
  const raw = res.headers.get("set-cookie");
  if (!raw) return null;
  const match = raw.match(new RegExp(`(?:^|, )${LOCALE_COOKIE}=([^;,]+)`));
  if (!match) return null;
  const value = match[1] ?? "";
  const maxAgeMatch = raw.match(/Max-Age=(\d+)/i);
  return {
    value,
    maxAge: maxAgeMatch?.[1] ? Number(maxAgeMatch[1]) : undefined,
  };
}

describe("ensureLocaleCookie", () => {
  it("writes the default locale when no cookie or header is present", () => {
    const req = buildRequest({});
    const out = ensureLocaleCookie(req, NextResponse.next());
    const setCookie = findSetCookie(out);
    expect(setCookie?.value).toBe(DEFAULT_LOCALE);
    expect(setCookie?.maxAge).toBe(LOCALE_COOKIE_MAX_AGE);
  });

  it("negotiates from Accept-Language when the cookie is absent", () => {
    const req = buildRequest({ acceptLanguage: "en-US,en;q=0.9" });
    const out = ensureLocaleCookie(req, NextResponse.next());
    const setCookie = findSetCookie(out);
    expect(setCookie?.value).toBe("en");
  });

  it("falls back to default when Accept-Language has no supported locale", () => {
    const req = buildRequest({ acceptLanguage: "ja-JP,ko;q=0.7" });
    const out = ensureLocaleCookie(req, NextResponse.next());
    const setCookie = findSetCookie(out);
    expect(setCookie?.value).toBe(DEFAULT_LOCALE);
  });

  it("does not touch the cookie when a valid one is already set", () => {
    const req = buildRequest({ cookie: `${LOCALE_COOKIE}=en` });
    const out = ensureLocaleCookie(req, NextResponse.next());
    expect(findSetCookie(out)).toBeNull();
  });

  it("overwrites an invalid cookie value with the negotiated locale", () => {
    const req = buildRequest({
      cookie: `${LOCALE_COOKIE}=ja-JP`,
      acceptLanguage: "zh-CN,en;q=0.9",
    });
    const out = ensureLocaleCookie(req, NextResponse.next());
    const setCookie = findSetCookie(out);
    expect(setCookie?.value).toBe("zh-CN");
  });
});
