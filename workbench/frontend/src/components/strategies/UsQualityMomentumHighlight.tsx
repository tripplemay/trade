"use client";

import { useTranslations } from "next-intl";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * B025 F005 — bilingual highlight card for the satellite_us_quality sleeve.
 *
 * Surfaces strategy name, 5 factor labels, rebalance cadence, Top-N rule,
 * earnings avoidance window, factor weights, and the synthetic-data
 * disclaimer. All copy is sourced from the
 * ``strategies.usQualityMomentum`` namespace so the panel renders in
 * whichever locale is active — never hard-coded.
 */
export function UsQualityMomentumHighlight() {
  const t = useTranslations("strategies.usQualityMomentum");
  const tFactors = useTranslations("strategies.usQualityMomentum.factors");
  return (
    <Card data-testid="strategies-us-quality-highlight">
      <CardHeader>
        <CardTitle data-testid="us-quality-name">{t("name")}</CardTitle>
        <CardDescription data-testid="us-quality-tagline">
          <span className="font-mono mr-2">{t("sleeveLabel")}</span>·{" "}
          {t("tagline")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <ul
          data-testid="us-quality-factors"
          className="flex flex-wrap gap-2"
        >
          {(["momentum", "quality", "lowVol", "value", "trend"] as const).map(
            (key) => (
              <li
                key={key}
                data-testid={`us-quality-factor-${key}`}
                className="rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-xs"
              >
                {tFactors(key)}
              </li>
            ),
          )}
        </ul>
        <dl
          data-testid="us-quality-config"
          className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs"
        >
          <dt className="text-muted-foreground">{t("factorWeightsLabel")}</dt>
          <dd className="numeric">{t("factorWeights")}</dd>
          <dt className="text-muted-foreground">{t("rebalanceLabel")}</dt>
          <dd>{t("rebalanceValue")}</dd>
          <dt className="text-muted-foreground">{t("topNLabel")}</dt>
          <dd>{t("topNValue")}</dd>
          <dt className="text-muted-foreground">{t("earningsWindowLabel")}</dt>
          <dd>{t("earningsWindowValue")}</dd>
        </dl>
        <p
          data-testid="us-quality-data-source"
          className="text-xs text-muted-foreground"
        >
          {t("dataSource")}
        </p>
      </CardContent>
    </Card>
  );
}
