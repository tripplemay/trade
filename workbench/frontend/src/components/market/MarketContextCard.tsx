"use client";

/**
 * B035 F003 — Home market-context card.
 *
 * Renders the latest value per market-context series from the
 * same-origin, auth-gated ``GET /api/market-context`` endpoint. Purely
 * structured (label / value / date / source) — no AI text (B035 is a
 * non-AI data-display batch). A series not yet ingested renders an em
 * dash for value + date (empty state).
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { components } from "@/types/api";

type MarketContextResponse = components["schemas"]["MarketContextResponse"];
type MarketContextSeries = components["schemas"]["MarketContextSeries"];

const MARKET_CONTEXT_URL = "/api/market-context";

const SOURCE_LABELS: Record<string, string> = {
  fred: "FRED",
  alpha_vantage: "Alpha Vantage",
};

function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(2);
}

export function MarketContextCard() {
  const t = useTranslations("home.marketContext");
  const [series, setSeries] = useState<MarketContextSeries[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(MARKET_CONTEXT_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as MarketContextResponse;
      })
      .then((payload) => {
        if (!cancelled) setSeries(payload.series ?? []);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card data-testid="home-market-context-card">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p data-testid="market-context-error" className="text-sm text-destructive">
            {t("error", { error })}
          </p>
        ) : series === null ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : series.length === 0 ? (
          <p data-testid="market-context-empty" className="text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul
            data-testid="market-context-list"
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
          >
            {series.map((item) => (
              <li
                key={item.series_id}
                data-testid="market-context-series"
                className="rounded-md border border-border px-3 py-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-xs text-muted-foreground">{item.label}</span>
                  <span
                    data-testid="market-context-source"
                    className="shrink-0 rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] text-foreground"
                  >
                    {SOURCE_LABELS[item.source] ?? item.source}
                  </span>
                </div>
                <div className="mt-1 flex items-baseline justify-between gap-2">
                  <span data-testid="market-context-value" className="numeric text-lg font-semibold text-foreground">
                    {formatValue(item.latest_value)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {item.latest_date ?? "—"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
