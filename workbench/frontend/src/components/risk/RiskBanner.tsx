"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

export type RiskPanelResponse = components["schemas"]["RiskPanelResponse"];

const RISK_URL = "/api/execution/risk-panel";

const STATE_STYLES: Record<RiskPanelResponse["state"], string> = {
  green: "border-green-700/60 bg-green-950/30 text-green-200",
  yellow: "border-amber-700/60 bg-amber-950/40 text-amber-100",
  red: "border-destructive bg-destructive/20 text-destructive-foreground",
};

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
  return (
    <Card
      data-testid="risk-banner"
      data-state={payload.state}
      className={cn(STATE_STYLES[payload.state], className)}
    >
      <CardContent className="space-y-1 py-3 text-sm">
        <div className="flex items-center justify-between">
          <strong>{t(`headlines.${payload.state}`)}</strong>
          <span className="font-mono text-xs">
            {t("masterDd", { value: (payload.master_dd * 100).toFixed(2) })}
          </span>
        </div>
        <p className="text-xs">
          {t("killSwitchThreshold", {
            value: (payload.kill_switch_threshold * 100).toFixed(0),
          })}{" "}
          ·{" "}
          {t("perSleeveThreshold", {
            value: (payload.per_sleeve_threshold * 100).toFixed(0),
          })}
          {payload.slippage_trend_3m_bps != null
            ? ` · ${t("slippageTrend", { value: payload.slippage_trend_3m_bps.toFixed(1) })}`
            : ""}
        </p>
        {payload.alternative_defensive_ticket ? (
          <p data-testid="risk-banner-defensive-rationale" className="text-xs">
            {payload.alternative_defensive_ticket.rationale}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
