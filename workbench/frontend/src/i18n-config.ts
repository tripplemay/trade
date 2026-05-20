/**
 * B024 F001 — pure i18n constants + helpers.
 *
 * Split from `src/i18n.ts` so client components (LocaleSwitcher) and
 * middleware can share the locale allowlist + Accept-Language
 * negotiator without dragging the server-only `next/headers` / next-
 * intl loader into the client bundle.
 *
 * `src/i18n.ts` re-exports everything here and adds the server-side
 * pieces consumed by next-intl's plugin.
 */
export const LOCALES = ["zh-CN", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "zh-CN";
export const LOCALE_COOKIE = "NEXT_LOCALE";
export const LOCALE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year, seconds

export function isLocale(value: string | undefined | null): value is Locale {
  return value !== null && value !== undefined && (LOCALES as readonly string[]).includes(value);
}

/**
 * Pick a locale from a raw `Accept-Language` header. Only exact matches
 * against {@link LOCALES} count — we don't expand `zh` → `zh-CN`
 * silently. Common browser regional tags (`en-US`, `zh-TW`) collapse
 * to their base when that base is a supported locale.
 */
export function negotiateFromAcceptLanguage(header: string | null | undefined): Locale | null {
  if (!header) return null;
  // Accept-Language is comma-separated, each entry may have a q-weight
  // ("zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"). We just need the first
  // entry whose normalized form matches an allowed locale.
  for (const part of header.split(",")) {
    const tag = part.split(";")[0]?.trim();
    if (!tag) continue;
    if (isLocale(tag)) return tag;
    const base = tag.split("-")[0];
    if (base === "en") return "en";
    if (base === "zh") return "zh-CN";
  }
  return null;
}
