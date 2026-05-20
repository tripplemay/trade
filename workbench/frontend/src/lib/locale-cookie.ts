import type { NextRequest, NextResponse } from "next/server";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  LOCALE_COOKIE_MAX_AGE,
  isLocale,
  negotiateFromAcceptLanguage,
} from "@/i18n-config";

/**
 * B024 F001 — locale-cookie writer for the auth middleware.
 *
 * If the request lacks a valid `NEXT_LOCALE` cookie, write one onto
 * the outgoing response. Negotiated from `Accept-Language` when
 * possible, otherwise the default (zh-CN).
 *
 * Lives in its own module so unit tests can exercise the logic
 * without dragging `next-auth` (which `src/middleware.ts` imports) into
 * the test bundle.
 */
export function ensureLocaleCookie(req: NextRequest, res: NextResponse): NextResponse {
  const existing = req.cookies.get(LOCALE_COOKIE)?.value;
  if (isLocale(existing)) return res;

  const negotiated =
    negotiateFromAcceptLanguage(req.headers.get("accept-language")) ?? DEFAULT_LOCALE;
  res.cookies.set({
    name: LOCALE_COOKIE,
    value: negotiated,
    path: "/",
    maxAge: LOCALE_COOKIE_MAX_AGE,
    sameSite: "lax",
  });
  return res;
}
