"use client";

/**
 * B026 F001 — Synthetic data banner shown on every (protected) page while
 * the workbench runs on Layer 0 fixture data.
 *
 * Behaviour pinned by docs/specs/B026-synthetic-data-banner-spec.md §2:
 *   - Visible at the very top of the protected shell.
 *   - Bilingual headline pulled from `syntheticBanner.*` (B024 i18n).
 *   - Dismiss is *session-scoped* — React state only; a reload or fresh
 *     navigation re-renders the banner. This is by design: the goal is
 *     to keep "this is synthetic data" in the user's field of view, so
 *     persistent dismissal (cookie / localStorage) would defeat the
 *     point. See spec §6 "Not doing".
 *   - `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` hides the banner entirely
 *     so the deployment can turn it off once real-data Phase 1 lands.
 *     Default (unset or anything other than the literal "false") shows it.
 */
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Info, X } from "lucide-react";

export function SyntheticDataBanner() {
  const t = useTranslations("syntheticBanner");
  const [dismissed, setDismissed] = useState(false);

  const enabled = process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER !== "false";
  if (!enabled || dismissed) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="synthetic-data-banner"
      className="flex items-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
    >
      <Info className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span
        data-testid="synthetic-data-banner-headline"
        className="flex-1 leading-5"
      >
        {t("headline")}
      </span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label={t("ariaClose")}
        data-testid="synthetic-data-banner-close"
        className="rounded p-1 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 dark:hover:bg-amber-900"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
