"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useTransition } from "react";

import { LOCALE_COOKIE, LOCALE_COOKIE_MAX_AGE, LOCALES, isLocale } from "@/i18n-config";
import { cn } from "@/lib/utils";

/**
 * B024 F001 — Header locale switcher.
 *
 * Writes the explicit user choice to the `NEXT_LOCALE` cookie (365d
 * max-age) and triggers a router refresh so the next RSC render reads
 * the new locale via the cookie + i18n.ts pipeline. We deliberately
 * use a native <select> rather than Radix to keep the SSR contract
 * trivial and avoid any portal/hydration mismatch in the TopBar.
 *
 * The cookie is also written by middleware on first request when
 * absent — this component only fires when the user manually swaps.
 */
export default function LocaleSwitcher() {
  const router = useRouter();
  const currentLocale = useLocale();
  const t = useTranslations("common");
  const [isPending, startTransition] = useTransition();

  const handleChange = (nextLocale: string) => {
    if (!isLocale(nextLocale) || nextLocale === currentLocale) return;

    // Document cookie write — middleware will respect it on the next
    // request. SameSite=Lax + 365d matches the value the middleware
    // would write for first-time visitors.
    document.cookie = `${LOCALE_COOKIE}=${nextLocale}; path=/; max-age=${LOCALE_COOKIE_MAX_AGE}; SameSite=Lax`;

    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <label
      data-testid="locale-switcher"
      className={cn(
        "inline-flex items-center gap-1 text-xs text-muted-foreground",
        isPending && "opacity-60",
      )}
    >
      <span className="sr-only">{t("switchLanguage")}</span>
      <select
        data-testid="locale-switcher-select"
        aria-label={t("switchLanguage")}
        value={currentLocale}
        disabled={isPending}
        onChange={(event) => handleChange(event.target.value)}
        className="rounded-md border border-border bg-card/60 px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        {LOCALES.map((locale) => (
          <option key={locale} value={locale}>
            {locale === "zh-CN" ? t("languageChinese") : t("languageEnglish")}
          </option>
        ))}
      </select>
    </label>
  );
}
