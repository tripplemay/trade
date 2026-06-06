"use client";

/**
 * B040 F002 — shared Robinhood-style metrics primitive.
 *
 * A big-number grid: each metric shows an English term label (kept English
 * per spec — Sharpe / Sortino / Calmar / CAGR / MDD) with a colour-coded
 * value and a bilingual explanatory tooltip (radix). Reused by /backtest
 * (BacktestMetrics) and /reports/[slug] (ReportMetrics).
 *
 * These are HISTORICAL backtest statistics, never a forward return
 * prediction (positioning §1.1). There are NO execution / order affordances
 * here — it is a read-only display.
 */

import { useTranslations } from "next-intl";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { colorForMetric, type MetricKey } from "@/lib/metric-color";
import { cn } from "@/lib/utils";

/** English term labels — intentionally identical in both locales (the
 * jargon stays English; the tooltip carries the localised explanation). */
const METRIC_LABELS: Record<MetricKey, string> = {
  sharpe: "Sharpe",
  sortino: "Sortino",
  calmar: "Calmar",
  cagr: "CAGR",
  maxDrawdown: "Max Drawdown",
  volatility: "Volatility",
  turnover: "Turnover",
};

export interface MetricStat {
  key: MetricKey;
  value: number | null | undefined;
  /** "percent" → value*100 + "%"; "ratio" → 2-dp number. */
  format: "percent" | "ratio";
}

function formatValue(stat: MetricStat): string {
  const v = stat.value;
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return stat.format === "percent" ? `${(v * 100).toFixed(2)}%` : v.toFixed(2);
}

export function MetricsDisplay({ stats }: { stats: MetricStat[] }) {
  const t = useTranslations("metrics.tooltips");
  return (
    <TooltipProvider delayDuration={150}>
      <div
        data-testid="metrics-display"
        className="grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-7"
      >
        {stats.map((stat) => (
          <div key={stat.key} data-testid={`metric-${stat.key}`}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="cursor-help text-[10px] uppercase tracking-wide text-muted-foreground underline decoration-dotted underline-offset-2">
                  {METRIC_LABELS[stat.key]}
                </div>
              </TooltipTrigger>
              <TooltipContent
                data-testid={`metric-tooltip-${stat.key}`}
                className="max-w-[220px] text-xs leading-snug"
              >
                {t(stat.key)}
              </TooltipContent>
            </Tooltip>
            <div
              data-testid={`metric-value-${stat.key}`}
              className={cn("numeric text-2xl font-semibold", colorForMetric(stat.key, stat.value))}
            >
              {formatValue(stat)}
            </div>
          </div>
        ))}
      </div>
    </TooltipProvider>
  );
}
