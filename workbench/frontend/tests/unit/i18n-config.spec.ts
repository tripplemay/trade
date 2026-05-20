/**
 * B024 F001 — i18n config primitives.
 *
 * Validates the Accept-Language negotiator + locale guard that both the
 * middleware (cookie writer) and src/i18n.ts (next-intl loader) share.
 * These are pure functions so node env is fine — no DOM needed.
 */
import { describe, expect, it } from "vitest";

import {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_COOKIE,
  LOCALE_COOKIE_MAX_AGE,
  isLocale,
  negotiateFromAcceptLanguage,
} from "@/i18n-config";

describe("i18n constants", () => {
  it("ships the supported locale set in the documented order", () => {
    expect([...LOCALES]).toEqual(["zh-CN", "en"]);
  });

  it("defaults to zh-CN (spec §2)", () => {
    expect(DEFAULT_LOCALE).toBe("zh-CN");
  });

  it("uses NEXT_LOCALE as the cookie name and 365 days max-age", () => {
    expect(LOCALE_COOKIE).toBe("NEXT_LOCALE");
    expect(LOCALE_COOKIE_MAX_AGE).toBe(365 * 24 * 60 * 60);
  });
});

describe("isLocale type guard", () => {
  it("accepts the supported locale tags exactly", () => {
    expect(isLocale("zh-CN")).toBe(true);
    expect(isLocale("en")).toBe(true);
  });

  it("rejects unknown tags and falsy values", () => {
    expect(isLocale("zh")).toBe(false);
    expect(isLocale("en-US")).toBe(false);
    expect(isLocale("ja")).toBe(false);
    expect(isLocale("")).toBe(false);
    expect(isLocale(null)).toBe(false);
    expect(isLocale(undefined)).toBe(false);
  });
});

describe("negotiateFromAcceptLanguage", () => {
  it("returns null when the header is missing or empty", () => {
    expect(negotiateFromAcceptLanguage(null)).toBeNull();
    expect(negotiateFromAcceptLanguage(undefined)).toBeNull();
    expect(negotiateFromAcceptLanguage("")).toBeNull();
  });

  it("matches an exact supported tag on the first preference", () => {
    expect(negotiateFromAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")).toBe("zh-CN");
    expect(negotiateFromAcceptLanguage("en,en-US;q=0.9")).toBe("en");
  });

  it("normalises browser regional tags into the supported set", () => {
    // Browsers commonly send `en-US` / `zh-TW` — we collapse the base.
    expect(negotiateFromAcceptLanguage("en-US,en;q=0.9")).toBe("en");
    expect(negotiateFromAcceptLanguage("zh-TW,zh;q=0.8")).toBe("zh-CN");
  });

  it("returns null when no preference matches the supported locales", () => {
    expect(negotiateFromAcceptLanguage("ja-JP,ko;q=0.7")).toBeNull();
  });
});
