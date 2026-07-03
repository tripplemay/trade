"use client";

/**
 * B041 F001 — simplified Robinhood-style target-positions view.
 *
 * One card per target position: symbol + big-number target / current weight +
 * a colour-coded delta (rebalance direction) + the existing rationale text
 * (placeholder, surfaced as-is — the rich "why" explanation is B043). Field
 * labels carry a bilingual radix tooltip. Reuses the B040 colour palette
 * (lib/metric-color) and the shared Card/Tooltip primitives.
 *
 * These are TARGET vs CURRENT configuration weights (facts), never a return
 * prediction (positioning §1.1). There is NO order/execute affordance here —
 * the workbench is research-only; rebalancing happens via the existing
 * export-to-ticket workflow, untouched by this view.
 */

import { useTranslations } from "next-intl";

import { SymbolLink } from "@/components/symbol/SymbolLink";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { colorForDelta } from "@/lib/metric-color";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type TargetPosition = components["schemas"]["TargetPosition"];

type FieldKey = "target" | "current" | "delta";

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function signedPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

export function PositionCards({ positions }: { positions: TargetPosition[] }) {
  const t = useTranslations("recommendations.cards");

  if (positions.length === 0) {
    return (
      <p data-testid="position-cards-empty" className="text-sm text-muted-foreground">
        {t("empty")}
      </p>
    );
  }

  const Stat = ({
    field,
    value,
    colorClass,
    valueTestId,
  }: {
    field: FieldKey;
    value: string;
    colorClass?: string;
    valueTestId?: string;
  }) => (
    <div>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            data-testid={`position-label-${field}`}
            className="inline-block cursor-help text-[10px] uppercase tracking-wide text-muted-foreground underline decoration-dotted underline-offset-2"
          >
            {t(`${field}Label`)}
          </div>
        </TooltipTrigger>
        <TooltipContent
          data-testid={`position-tooltip-${field}`}
          className="max-w-[220px] text-xs leading-snug"
        >
          {t(`tooltips.${field}`)}
        </TooltipContent>
      </Tooltip>
      <div
        data-testid={valueTestId}
        className={cn("numeric text-lg font-semibold", colorClass ?? "text-foreground")}
      >
        {value}
      </div>
    </div>
  );

  return (
    <TooltipProvider delayDuration={150}>
      <div data-testid="position-cards" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {positions.map((p) => (
          <Card key={p.symbol} data-testid={`position-card-${p.symbol}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                <SymbolLink symbol={p.symbol} name={p.name} />
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <Stat field="target" value={pct(p.target_weight)} />
                {/* B053 F003 — a held-but-unpriced position reads current_weight=0;
                    show a distinct "held, no price" label instead of a misleading 0%. */}
                <Stat
                  field="current"
                  value={p.has_mark ? pct(p.current_weight) : t("noMark")}
                  colorClass={p.has_mark ? undefined : "text-amber-500"}
                  valueTestId={`position-current-${p.symbol}`}
                />
                <Stat
                  field="delta"
                  value={signedPct(p.diff)}
                  colorClass={colorForDelta(p.diff)}
                  valueTestId={`position-delta-${p.symbol}`}
                />
              </div>
              {p.rationale ? (
                <p data-testid="position-rationale" className="text-xs text-muted-foreground">
                  {p.rationale}
                </p>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </TooltipProvider>
  );
}
