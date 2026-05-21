/**
 * B024 F003 — workbench fetch wrapper that auto-injects
 * `Accept-Language` from the active `NEXT_LOCALE` cookie.
 *
 * F004 wires the backend to read this header and return locale-specific
 * `HTTPException.detail` text; the wrapper exists now so every execution-
 * page fetch will pick up the contract once F004 ships (no further
 * client edits needed).
 *
 * Browser-only — no-ops on the server (Next.js RSC routes don't go
 * through this helper). Keep `init` semantics identical to native
 * `fetch`; we only enrich the `Accept-Language` header.
 *
 * Reading the cookie via `document.cookie` is intentional: the
 * LocaleSwitcher writes the cookie as a side-effect, and reading it on
 * every fetch keeps the request aligned with the latest user choice
 * without prop-drilling locale through every call site.
 */
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n-config";

function readLocaleCookie(): string {
  if (typeof document === "undefined") return DEFAULT_LOCALE;
  const target = `${LOCALE_COOKIE}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(target)) {
      const value = decodeURIComponent(trimmed.slice(target.length));
      if (isLocale(value)) return value;
    }
  }
  return DEFAULT_LOCALE;
}

export function workbenchFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? undefined);
  if (!headers.has("accept-language")) {
    headers.set("accept-language", readLocaleCookie());
  }
  return fetch(input, { ...init, headers });
}
