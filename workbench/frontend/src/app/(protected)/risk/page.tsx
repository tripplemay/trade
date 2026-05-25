"use client";

import { useTranslations } from "next-intl";

import { RiskBanner } from "@/components/risk/RiskBanner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * B025 F005 fix-round 1: dedicated `/risk` route.
 *
 * Codex F006 L1 flagged that the F005/F006 acceptance text references a
 * standalone `/risk` page but the app tree only embedded ``RiskBanner``
 * inside ``/recommendations`` and the execution surface. This page makes
 * the banner first-class: bilingual page header + the existing
 * ``RiskBanner`` (kill-switch state + master drawdown + per-sleeve
 * drawdown list including ``satellite_us_quality``) + a context card so
 * users understand what the panel is showing without leaving the page.
 */
export default function RiskPage() {
  const t = useTranslations("risk.page");
  const tBanner = useTranslations("risk");
  return (
    <section data-testid="page-risk" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <span
          data-testid="risk-page-subtitle"
          className="text-xs text-muted-foreground"
        >
          {t("subtitle")}
        </span>
      </header>

      <RiskBanner />

      <Card data-testid="risk-page-context-card">
        <CardHeader>
          <CardTitle>{t("contextTitle")}</CardTitle>
          <CardDescription>{t("contextDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <strong>{tBanner("masterDd", { value: "—" })}</strong>{" "}
            {t("explainMaster")}
          </p>
          <p>
            <strong>
              {tBanner("killSwitchThreshold", { value: "15" })}
            </strong>{" "}
            {t("explainKillSwitch")}
          </p>
          <p>
            <strong>
              {tBanner("perSleeveThreshold", { value: "8" })}
            </strong>{" "}
            {t("explainPerSleeve")}
          </p>
          <p data-testid="risk-page-sleeve-note">{t("sleeveNote")}</p>
        </CardContent>
      </Card>
    </section>
  );
}
