"use client";

import { useTranslations } from "next-intl";
import { Fragment, useEffect, useState } from "react";

import { SymbolLink } from "@/components/symbol/SymbolLink";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { colorForDrawdown, colorForRiskState } from "@/lib/metric-color";
import { sleeveLabel } from "@/lib/sleeve-label";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

export type RiskPanelResponse = components["schemas"]["RiskPanelResponse"];

const RISK_URL = "/api/execution/risk-panel";

/** Shared dotted-underline "has a tooltip" affordance (matches MetricsDisplay). */
const TERM_CLASS = "cursor-help underline decoration-dotted underline-offset-2";

export interface RiskBannerProps {
  /** Override the fetched payload (used by tests + the optional pre-fetched flow). */
  data?: RiskPanelResponse | null;
  /** Hide the embedded fetch so a parent can drive the data prop. */
  noFetch?: boolean;
  className?: string;
}

export function useRiskPanel(noFetch = false): {
  data: RiskPanelResponse | null;
  error: string | null;
} {
  const [data, setData] = useState<RiskPanelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (noFetch) return;
    let cancelled = false;
    fetch(RISK_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as RiskPanelResponse;
        if (!cancelled) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [noFetch]);

  return { data, error };
}

export function RiskBanner({ data, noFetch, className }: RiskBannerProps) {
  const t = useTranslations("risk");
  const { data: fetched, error } = useRiskPanel(noFetch || data != null);
  const payload = data ?? fetched;
  if (error && payload == null) {
    return (
      <Card
        data-testid="risk-banner-error"
        className={cn("border-zinc-700/60 bg-zinc-900/40", className)}
      >
        <CardContent className="py-3 text-xs text-muted-foreground">
          {t("unreachablePrefix")} {error}
        </CardContent>
      </Card>
    );
  }
  if (payload == null) {
    return (
      <Card
        data-testid="risk-banner-loading"
        className={cn("border-border/60 bg-background", className)}
      >
        <CardContent className="py-3 text-xs text-muted-foreground">{t("loading")}</CardContent>
      </Card>
    );
  }
  const degradedSymbols = payload.degraded_symbols ?? [];
  return (
    <TooltipProvider delayDuration={150}>
      <Card
        data-testid="risk-banner"
        data-state={payload.state}
        className={cn(colorForRiskState(payload.state), className)}
      >
        <CardContent className="space-y-1.5 py-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <strong className="font-semibold">{t(`headlines.${payload.state}`)}</strong>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  data-testid="risk-term-masterDrawdown"
                  className={cn("font-mono text-xs", TERM_CLASS)}
                >
                  {t("masterDd", { value: (payload.master_dd * 100).toFixed(2) })}
                </span>
              </TooltipTrigger>
              <TooltipContent
                data-testid="risk-tooltip-masterDrawdown"
                className="max-w-[240px] text-xs leading-snug"
              >
                {t("tooltips.masterDrawdown")}
              </TooltipContent>
            </Tooltip>
          </div>
          <p className="text-xs text-muted-foreground">
            <Tooltip>
              <TooltipTrigger asChild>
                <span data-testid="risk-term-killSwitch" className={TERM_CLASS}>
                  {t("killSwitchThreshold", {
                    value: (payload.kill_switch_threshold * 100).toFixed(0),
                  })}
                </span>
              </TooltipTrigger>
              <TooltipContent
                data-testid="risk-tooltip-killSwitch"
                className="max-w-[240px] text-xs leading-snug"
              >
                {t("tooltips.killSwitch")}
              </TooltipContent>
            </Tooltip>
            {" · "}
            {t("perSleeveThreshold", {
              value: (payload.per_sleeve_threshold * 100).toFixed(0),
            })}
            {payload.slippage_trend_3m_bps != null
              ? ` · ${t("slippageTrend", { value: payload.slippage_trend_3m_bps.toFixed(1) })}`
              : ""}
          </p>
          {payload.valuation_basis === "cost_degraded" ? (
            <p data-testid="risk-banner-valuation-degraded" className="text-xs text-amber-200/90">
              {t("valuationBasis.costDegraded")}
              {degradedSymbols.length > 0 ? (
                <>
                  {" ("}
                  {degradedSymbols.map((sym, index) => (
                    <Fragment key={sym}>
                      {index > 0 ? ", " : ""}
                      <SymbolLink symbol={sym} />
                    </Fragment>
                  ))}
                  {")"}
                </>
              ) : null}
            </p>
          ) : null}
          {payload.alternative_defensive_ticket ? (
            <p data-testid="risk-banner-defensive-rationale" className="text-xs">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    data-testid="risk-term-defensiveTicket"
                    className={cn("font-semibold", TERM_CLASS)}
                  >
                    {t("defensiveLabel")}
                  </span>
                </TooltipTrigger>
                <TooltipContent
                  data-testid="risk-tooltip-defensiveTicket"
                  className="max-w-[240px] text-xs leading-snug"
                >
                  {t("tooltips.defensiveTicket")}
                </TooltipContent>
              </Tooltip>{" "}
              {payload.alternative_defensive_ticket.rationale}
            </p>
          ) : null}
          {payload.per_sleeve_dd && payload.per_sleeve_dd.length > 0 ? (
            <div className="mt-2 space-y-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    data-testid="risk-term-perSleeveDrawdown"
                    className={cn(
                      "text-[10px] uppercase tracking-wide text-muted-foreground",
                      TERM_CLASS,
                    )}
                  >
                    {t("perSleeveLabel")}
                  </span>
                </TooltipTrigger>
                <TooltipContent
                  data-testid="risk-tooltip-perSleeveDrawdown"
                  className="max-w-[240px] text-xs leading-snug"
                >
                  {t("tooltips.perSleeveDrawdown")}
                </TooltipContent>
              </Tooltip>
              <ul
                data-testid="risk-banner-per-sleeve-list"
                className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-3"
              >
                {payload.per_sleeve_dd.map((sleeve) => (
                  <li
                    key={sleeve.sleeve}
                    data-testid={`risk-sleeve-${sleeve.sleeve}`}
                    className="font-mono"
                  >
                    <span className="text-muted-foreground">{sleeveLabel(sleeve.sleeve)}</span>
                    {": "}
                    <span
                      className={colorForDrawdown(sleeve.drawdown, payload.per_sleeve_threshold)}
                    >
                      {(sleeve.drawdown * 100).toFixed(2)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {payload.explanation ? (
            <p
              data-testid="risk-banner-explanation"
              className="mt-2 border-t border-border/40 pt-2 text-xs text-muted-foreground"
            >
              <span className="font-semibold text-foreground">{t("explanationLabel")}</span>{" "}
              {payload.explanation}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}
