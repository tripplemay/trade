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
 *
 * Fix-round 2 (2026-05-26): dismiss now has two redundant paths after Codex
 * F002 L2 reverify saw the React onClick → setState path fail to visually
 * hide the banner on the live production VM (works locally in both
 * `next dev` and `next start`, both unit + Playwright). To make the
 * dismiss interaction robust to whichever production-only edge case is
 * preventing the React state path from propagating to the DOM, the close
 * button now also (a) attaches a vanilla DOM click listener via
 * `useEffect`, and (b) sets `display: none` on the container directly.
 * `setDismissed(true)` is still the canonical state path — the DOM hide
 * is belt-and-braces so the user-visible "hide now" half of the spec
 * holds even if React event delegation is broken. A reload still
 * re-renders SSR HTML, so the "reappear after reload" half holds too.
 */
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Info, X } from "lucide-react";

export function SyntheticDataBanner() {
  const t = useTranslations("syntheticBanner");
  const [dismissed, setDismissed] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const enabled = process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER !== "false";

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const btn = container.querySelector<HTMLButtonElement>(
      '[data-testid="synthetic-data-banner-close"]',
    );
    if (!btn) return;
    const handler = () => {
      // setDismissed is the canonical source of truth — once React
      // re-renders, the component returns null and the node unmounts.
      setDismissed(true);
      // Defensive: if React's setState path is interrupted in
      // production (event delegation, hydration partial, etc.), hide
      // the container directly so the user-visible dismiss still
      // happens. The reload behaviour stays the same: a full reload
      // re-runs the server render and the banner reappears.
      container.style.display = "none";
    };
    btn.addEventListener("click", handler);
    return () => {
      btn.removeEventListener("click", handler);
    };
  }, []);

  if (!enabled || dismissed) return null;

  return (
    <div
      ref={containerRef}
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
