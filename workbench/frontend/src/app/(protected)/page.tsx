"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatPercent } from "@/components/table/columns";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type DashboardResponse = components["schemas"]["DashboardResponse"];

const DASHBOARD_URL = "/api/dashboard";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-destructive/60 bg-destructive/10 text-destructive-foreground",
  warning: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  info: "border-border bg-muted text-muted-foreground",
};

function DashboardCard({
  label,
  value,
  description,
  testId,
}: {
  label: string;
  value: string;
  description?: string;
  testId: string;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="numeric text-2xl">{value}</CardTitle>
      </CardHeader>
      {description ? <CardContent className="text-xs text-muted-foreground">{description}</CardContent> : null}
    </Card>
  );
}

export default function HomePage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(DASHBOARD_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as DashboardResponse;
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
  const drawdownValue = data ? formatPercent(data.master_drawdown) : "—";
  const killSwitchValue = data ? formatPercent(data.kill_switch_threshold) : "—";
  const daysToRebalanceValue = data ? String(data.days_to_next_rebalance) : "—";
  const lastRebalance = data?.last_rebalance ?? null;

  return (
    <section data-testid="workbench-home" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Home</h1>
        <span data-testid="dashboard-state" className="text-xs text-muted-foreground">
          {data ? "live" : error ? `unreachable: ${error}` : "loading…"}
        </span>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard
          testId="dashboard-card-nav"
          label="NAV"
          value={navValue}
          description={lastRebalance ? `as of ${lastRebalance.date}` : "Cash + equity_value"}
        />
        <DashboardCard
          testId="dashboard-card-drawdown"
          label="Master drawdown"
          value={drawdownValue}
          description="From equity peak"
        />
        <DashboardCard
          testId="dashboard-card-killswitch"
          label="Kill-switch threshold"
          value={killSwitchValue}
          description="Manual halt arms at this DD"
        />
        <DashboardCard
          testId="dashboard-card-rebalance"
          label="Days to next rebalance"
          value={daysToRebalanceValue}
          description={
            lastRebalance
              ? `Last: ${lastRebalance.date} · ${lastRebalance.fill_count} fills`
              : "No rebalance recorded"
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="dashboard-recent-reports">
          <CardHeader>
            <CardTitle>Recent reports</CardTitle>
            <CardDescription>Sign-offs, sweeps, and reviews from docs/test-reports/.</CardDescription>
          </CardHeader>
          <CardContent>
            {data && data.recent_reports.length > 0 ? (
              <ul className="space-y-2">
                {data.recent_reports.map((report) => (
                  <li key={report.id} className="flex items-center justify-between gap-3 text-sm">
                    <Link
                      href={`/reports/${report.id}`}
                      data-testid={`recent-report-${report.id}`}
                      className="truncate text-foreground hover:underline"
                    >
                      {report.title}
                    </Link>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {report.status} · {report.date}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="recent-reports-empty" className="text-sm text-muted-foreground">
                No recent reports surfaced. Drop sign-off markdown files under{" "}
                <code className="rounded bg-muted px-1 py-0.5">docs/test-reports/</code>.
              </p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="dashboard-action-items">
          <CardHeader>
            <CardTitle>Action items</CardTitle>
            <CardDescription>Things the workbench wants you to look at.</CardDescription>
          </CardHeader>
          <CardContent>
            {data && data.action_items.length > 0 ? (
              <ul className="space-y-2">
                {data.action_items.map((item) => (
                  <li
                    key={item.id}
                    data-testid={`action-item-${item.id}`}
                    className={cn(
                      "rounded-md border px-3 py-2 text-sm",
                      SEVERITY_STYLES[item.severity] ?? SEVERITY_STYLES.info,
                    )}
                  >
                    <span className="mr-2 text-[10px] font-semibold uppercase">
                      {item.severity}
                    </span>
                    {item.message}
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="action-items-empty" className="text-sm text-muted-foreground">
                Nothing flagged. Action items light up when a strategy gate trips or a wash-sale
                heuristic fires (B022 F010).
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
