"use client";

/**
 * B057 F005 — strategy-mode selector.
 *
 * Renders one pill per platform mode (Master flagship + regime research mode +
 * future modes, from ``GET /api/strategy-modes``) and drives the shared
 * ``useStrategyMode`` selection. Research-state modes (not funded) carry a
 * "研究态" badge and the surface shows a "前向验证中" notice, so building the
 * execution capability never implies the mode is funded (B057 §1 honesty).
 *
 * It is a mode SWITCH, not an execution affordance — it never places an order
 * (the workbench is research-only).
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { workbenchFetch } from "@/lib/api-fetch";
import { useStrategyMode } from "@/lib/strategy-mode";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type StrategyModeInfo = components["schemas"]["StrategyModeInfo"];

const MODES_URL = "/api/strategy-modes";

export function ModeSelector() {
  const t = useTranslations("modeSelector");
  const { strategyId, setStrategyId } = useStrategyMode();
  const [modes, setModes] = useState<StrategyModeInfo[]>([]);

  useEffect(() => {
    let active = true;
    workbenchFetch(MODES_URL)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { modes?: StrategyModeInfo[] } | null) => {
        if (active && data?.modes) setModes(data.modes);
      })
      .catch(() => {
        /* selector stays hidden on error — surfaces default to Master */
      });
    return () => {
      active = false;
    };
  }, []);

  // Nothing to switch (only the flagship, or the fetch failed) → render nothing,
  // so the Master-only experience is byte-identical.
  if (modes.length <= 1) return null;

  const current = modes.find((m) => m.strategy_id === strategyId);

  return (
    <div data-testid="mode-selector" className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">{t("label")}</span>
        {modes.map((mode) => {
          const selected = mode.strategy_id === strategyId;
          return (
            <button
              key={mode.strategy_id}
              type="button"
              aria-pressed={selected}
              onClick={() => setStrategyId(mode.strategy_id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors",
                selected
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-foreground hover:bg-accent",
              )}
            >
              <span>{mode.display_name}</span>
              {mode.is_research_state && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                    selected
                      ? "bg-primary-foreground/20 text-primary-foreground"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
                  )}
                >
                  {t("researchBadge")}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {current?.is_research_state && (
        <p
          className="text-xs text-amber-700 dark:text-amber-400"
          data-testid="mode-research-notice"
        >
          {t("researchNotice")}
        </p>
      )}
    </div>
  );
}
