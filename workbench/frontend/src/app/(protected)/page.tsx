"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AdvisorSection } from "@/components/advisor/AdvisorSection";
import { HomeNewsPanel } from "@/components/home/HomeNewsPanel";
import { MarketContextCard } from "@/components/market/MarketContextCard";
import { formatCurrency, formatPercent } from "@/components/table/columns";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type HomeResponse = components["schemas"]["HomeResponse"];
type DayPnl = components["schemas"]["DayPnl"];

const HOME_URL = "/api/home";

/** Tailwind text colour for a signed P&L value (emerald up / red down /
 * muted flat). Read-only colour coding — no execution affordance. */
function pnlColor(value: number | undefined): string {
  if (value === undefined || value === 0) return "text-muted-foreground";
  return value > 0 ? "text-emerald-400" : "text-red-400";
}

function DayPnlText({ pnl, emptyLabel }: { pnl: DayPnl | null | undefined; emptyLabel: string }) {
  if (!pnl) {
    return <span className="text-muted-foreground">{emptyLabel}</span>;
  }
  const sign = pnl.value > 0 ? "+" : "";
  return (
    <span className={cn("numeric", pnlColor(pnl.value))}>
      {sign}
      {formatCurrency(pnl.value)} ({sign}
      {formatPercent(pnl.pct)})
    </span>
  );
}

/** Display label for a sleeve key — translate the synthetic
 * "unclassified" bucket, pass real sleeve ids through untouched. */
function sleeveLabel(sleeve: string, unclassified: string): string {
  return sleeve === "unclassified" ? unclassified : sleeve;
}

export default function HomePage() {
  const t = useTranslations("home");
  const tCommon = useTranslations("common");
  const [data, setData] = useState<HomeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(HOME_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as HomeResponse;
        if (!cancelled) setData(payload);
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

  const navValue = data ? formatCurrency(data.nav) : "—";
  const stateLabel = data
    ? tCommon("live")
    : error
      ? tCommon("unreachableWithError", { error })
      : tCommon("loading");

  return (
    <section data-testid="workbench-home" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <span
          data-testid="home-state"
          className="flex items-center gap-2 text-xs text-muted-foreground"
        >
          <span
            aria-hidden
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              data ? "bg-emerald-400" : "bg-muted-foreground/50",
            )}
          />
          {stateLabel}
        </span>
      </header>

      {/* ① NAV + Day P&L hero */}
      <Card data-testid="home-hero">
        <CardHeader>
          <CardDescription>{t("hero.navLabel")}</CardDescription>
          <CardTitle data-testid="home-nav" className="numeric text-4xl">
            {navValue}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className="flex items-baseline gap-2 text-lg">
            <span className="text-sm text-muted-foreground">{t("hero.dayPnlLabel")}</span>
            <span data-testid="home-day-pnl">
              <DayPnlText pnl={data?.day_pnl} emptyLabel={t("hero.dayPnlEmpty")} />
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{t("hero.dayPnlDescription")}</p>
        </CardContent>
      </Card>

      {/* ② AI Advisor (B036 — reused in the restructured Home; B039 refines) */}
      <AdvisorSection />

      {/* ③ Market context (B035 — reused) + today's market news (B038) + sleeve breakdown */}
      <MarketContextCard />

      <HomeNewsPanel />

      <Card data-testid="home-sleeves">
        <CardHeader>
          <CardTitle>{t("sleeves.title")}</CardTitle>
          <CardDescription>{t("sleeves.description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {(data?.sleeves ?? []).map((sleeve) => (
              <li
                key={sleeve.sleeve}
                data-testid={`home-sleeve-${sleeve.sleeve}`}
                className="flex items-center justify-between gap-3 border-b border-border/50 pb-2 text-sm last:border-0"
              >
                <span className="font-medium text-foreground">
                  {sleeveLabel(sleeve.sleeve, t("sleeves.unclassified"))}
                </span>
                <span className="flex items-center gap-4 text-xs">
                  <span className="text-muted-foreground">{sleeve.positions_summary}</span>
                  <span className="numeric w-16 text-right text-muted-foreground">
                    {sleeve.nav_share === null || sleeve.nav_share === undefined
                      ? t("sleeves.empty")
                      : formatPercent(sleeve.nav_share)}
                  </span>
                  <span className="numeric w-28 text-right">
                    <DayPnlText pnl={sleeve.day_pnl} emptyLabel={t("sleeves.empty")} />
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}
