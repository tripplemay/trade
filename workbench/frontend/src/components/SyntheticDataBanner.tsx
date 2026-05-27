"use client";

/**
 * B026 F001 — Synthetic data banner (decommissioned in B030 F004
 * fix-round 1, 2026-05-27).
 *
 * **Status**: the component is **NOT** imported by any active route as
 * of B030 milestone A Layer 0→1. The file is preserved as a ready-to-
 * restore artefact per 永久边界 (k) — re-enabling Layer 0 mode (e.g.
 * the unified real-data backfill becomes unreliable) requires a new
 * spec batch that re-imports this component from
 * `src/app/(protected)/layout.tsx` and flips
 * `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER` to anything other than "false".
 *
 * Why the headline + close-button text are hardcoded (rather than
 * pulled from `syntheticBanner.*` via `useTranslations`): the
 * decommissioning removed the matching keys from
 * `messages/{zh-CN,en}.json` so the banner copy no longer ships in
 * the i18n payload of every authenticated page (Codex F004 fix-round
 * 1 hard blocker — production HTML must NOT contain the banner
 * literal, even in unrendered translation maps). Keeping the strings
 * inside this component means restoration is single-file: re-add the
 * import + JSX in the protected layout; no message-bundle edits.
 *
 * Behaviour pinned by docs/specs/B026-synthetic-data-banner-spec.md §2:
 *   - Visible at the very top of the protected shell when imported.
 *   - Bilingual headline — falls back to zh-CN when the locale is
 *     unknown so the banner never silently shows the dev key.
 *   - Dismiss is *session-scoped* — React state only; a reload or
 *     fresh navigation re-renders the banner.
 *   - `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` (build-time inlined)
 *     makes the component return `null`. Any other value (or unset)
 *     renders the banner — that's how the layer-toggle works after
 *     the component is re-imported.
 */
import { useEffect, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { Info, X } from "lucide-react";

// Headline + aria-label live in the component file rather than the
// i18n bundle (see component docstring for the why). zh-CN is the
// fallback locale because next-intl defaults to that elsewhere too.
const BANNER_HEADLINE = {
  "zh-CN": "研究原型 · 仅含合成数据 · 不构成投资决策依据",
  en: "Research prototype · Synthetic data only · Not for investment decisions",
} as const satisfies Record<"zh-CN" | "en", string>;
const BANNER_ARIA_CLOSE = {
  "zh-CN": "关闭此提示",
  en: "Dismiss this notice",
} as const satisfies Record<"zh-CN" | "en", string>;

function _pickLocaleString(table: Record<"zh-CN" | "en", string>, locale: string): string {
  if (locale === "en") return table.en;
  return table["zh-CN"];
}

export function SyntheticDataBanner() {
  const locale = useLocale();
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
      <span data-testid="synthetic-data-banner-headline" className="flex-1 leading-5">
        {_pickLocaleString(BANNER_HEADLINE, locale)}
      </span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label={_pickLocaleString(BANNER_ARIA_CLOSE, locale)}
        data-testid="synthetic-data-banner-close"
        className="rounded p-1 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 dark:hover:bg-amber-900"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
