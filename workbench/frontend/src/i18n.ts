import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  type Locale,
  isLocale,
  negotiateFromAcceptLanguage,
} from "@/i18n-config";

/**
 * B024 F001 — server-side i18n entry point.
 *
 * Wires next-intl's request-config loader (via the plugin in
 * next.config.mjs) to the cookie + Accept-Language resolution chain.
 * The pure constants and the negotiator live in `src/i18n-config.ts`
 * so client code (LocaleSwitcher) and middleware can import them
 * without dragging `next/headers` into the client bundle.
 *
 * Re-exports from `i18n-config` are intentional: legacy import sites
 * pointing at `@/i18n` keep working, and there is one canonical
 * location to import locale primitives from.
 */
export {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_COOKIE,
  LOCALE_COOKIE_MAX_AGE,
  isLocale,
  negotiateFromAcceptLanguage,
  type Locale,
} from "@/i18n-config";

export async function resolveLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(LOCALE_COOKIE)?.value;
  if (isLocale(cookieValue)) return cookieValue;

  const headerStore = await headers();
  const negotiated = negotiateFromAcceptLanguage(headerStore.get("accept-language"));
  if (negotiated) return negotiated;

  return DEFAULT_LOCALE;
}

export default getRequestConfig(async () => {
  const locale = await resolveLocale();
  const messages = (await import(`../messages/${locale}.json`)).default;
  return { locale, messages };
});
