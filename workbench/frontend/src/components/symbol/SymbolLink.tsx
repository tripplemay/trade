"use client";

/**
 * B060 F001 — shared clickable security-symbol link.
 *
 * Wraps any displayed ticker so a click deep-links to the B059 symbol detail
 * page (``/symbols?symbol=XXX``, uppercase-normalised). Reused site-wide
 * (recommendations / holdings / position-diff / ticket / paper / risk /
 * backtest / news) via a single component so the deep-link convention lives in
 * one place. No new backend — it reuses the B059 ``/symbols`` query param.
 *
 * research-only (spec §2.3): this is **read-only navigation** to a price/quote
 * view, NOT a buy / sell / execute affordance. It carries no order action and
 * is covered by the no-execution-buttons safety guard.
 *
 * A-share note: A-share codes (e.g. 600519.SH) have no price data yet; clicking
 * deep-links all the same and the detail page shows its empty/degraded state
 * until the A-share data source lands (a separate batch).
 */

import Link from "next/link";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

export interface SymbolLinkProps {
  /** The ticker to display + deep-link to (case-insensitive). */
  symbol: string;
  /**
   * B079 — optional display name. When present it renders name-primary with the
   * code as a muted, smaller suffix (`贵州茅台 600519.SH`); when absent/null the
   * link shows the raw code exactly as before (graceful fallback — 缺失纯 code).
   */
  name?: string | null;
  /** Extra classes merged onto the link (e.g. to preserve bold / mono context). */
  className?: string;
}

export function SymbolLink({ symbol, name, className }: SymbolLinkProps) {
  const t = useTranslations("symbolLink");
  // Normalise for the deep link only; the visible text stays verbatim so the
  // surrounding table/card appearance is unchanged.
  const normalized = (symbol ?? "").trim().toUpperCase();

  if (!normalized) {
    // Defensive: never render a broken empty link — fall back to raw text.
    return <>{symbol}</>;
  }

  const label = t("viewQuote", { symbol: normalized });
  const displayName = name?.trim();

  return (
    <Link
      href={`/symbols?symbol=${encodeURIComponent(normalized)}`}
      title={label}
      aria-label={label}
      data-testid="symbol-link"
      data-symbol={normalized}
      className={cn(
        "text-sky-400 underline-offset-2 transition-colors hover:text-sky-300 hover:underline",
        className,
      )}
    >
      {displayName ? (
        <>
          {displayName}
          <span className="ml-1 text-xs text-muted-foreground">{symbol}</span>
        </>
      ) : (
        symbol
      )}
    </Link>
  );
}

export default SymbolLink;
