"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CnAttackOosDisclosure } from "@/components/recommendations/CnAttackOosDisclosure";
import { DataTable } from "@/components/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { workbenchFetch } from "@/lib/api-fetch";
import { ReverifyJobError, ReverifyTimeoutError, runReverify } from "@/lib/reverify-poll";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type MetricsResponse = components["schemas"]["MetricsResponse"];
type MetricRow = components["schemas"]["MetricRow"];
type TrialsResponse = components["schemas"]["TrialsResponse"];
type TrialRow = components["schemas"]["TrialRow"];
type ResearchCaveat = components["schemas"]["ResearchCaveat"];

// The two research-state modes the monitoring surface covers (spec §2 F004).
const MONITORED = [
  { id: "cn_attack_pure_momentum", label: "CN Attack · Pure Momentum" },
  { id: "cn_attack_quality_momentum", label: "CN Attack · Quality + Momentum" },
] as const;

// The metric rows a health card shows, in display order.
const HEALTH_METRICS = [
  "rolling_ic_5",
  "rolling_ic_10",
  "rolling_ic_20",
  "tracking_error",
  "exposure_hhi",
  "turnover_rebalance_count",
] as const;

function fmt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toFixed(3);
}

function trialColumns(t: ReturnType<typeof useTranslations<"monitoring">>): ColDef<TrialRow>[] {
  return [
    { field: "strategy_id", headerName: t("colStrategy"), width: 220 },
    { field: "verdict", headerName: t("colVerdict"), width: 120 },
    { field: "batch", headerName: t("colBatch"), width: 110 },
    { field: "oos_split", headerName: t("colOosSplit"), flex: 2 },
    { field: "notes", headerName: t("colNotes"), flex: 2 },
  ];
}

export default function MonitoringPage() {
  const t = useTranslations("monitoring");

  const [metrics, setMetrics] = useState<MetricRow[]>([]);
  const [trials, setTrials] = useState<TrialsResponse | null>(null);
  const [caveats, setCaveats] = useState<Record<string, ResearchCaveat | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Per-strategy re-validation trigger state.
  const [reverifying, setReverifying] = useState<string | null>(null);
  const [reverifyMsg, setReverifyMsg] = useState<Record<string, string>>({});
  const [reverifyErr, setReverifyErr] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        const [m, tr] = await Promise.all([
          workbenchFetch("/api/monitoring/metrics").then(
            (r) => r.json() as Promise<MetricsResponse>,
          ),
          workbenchFetch("/api/monitoring/trials").then((r) => r.json() as Promise<TrialsResponse>),
        ]);
        // OOS red-card status rides on each cn_attack mode's recommendations payload.
        const caveatEntries = await Promise.all(
          MONITORED.map(async (s) => {
            try {
              const res = await workbenchFetch(
                `/api/recommendations/current?strategy_id=${encodeURIComponent(s.id)}`,
              );
              const body = (await res.json()) as { research_caveat?: ResearchCaveat | null };
              return [s.id, body.research_caveat ?? null] as const;
            } catch {
              return [s.id, null] as const;
            }
          }),
        );
        if (cancelled) return;
        setMetrics(m.metrics);
        setTrials(tr);
        setCaveats(Object.fromEntries(caveatEntries));
      } catch (reason: unknown) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const metricsByStrategy = useMemo(() => {
    const out: Record<string, Record<string, MetricRow>> = {};
    for (const row of metrics) {
      (out[row.strategy_id] ??= {})[row.metric] = row;
    }
    return out;
  }, [metrics]);

  const handleReverify = useCallback(
    async (strategyId: string) => {
      setReverifying(strategyId);
      setReverifyErr((e) => ({ ...e, [strategyId]: "" }));
      setReverifyMsg((m) => ({ ...m, [strategyId]: t("reverifyRunning") }));
      try {
        const result = await runReverify(strategyId);
        setReverifyMsg((m) => ({
          ...m,
          [strategyId]: `${t("reverifyDone")}: ${result.verdict ?? "—"}`,
        }));
        setReloadKey((k) => k + 1);
      } catch (reason: unknown) {
        setReverifyMsg((m) => ({ ...m, [strategyId]: "" }));
        const msg =
          reason instanceof ReverifyJobError
            ? `${t("reverifyError")} (${reason.errorKind ?? "unknown"})`
            : reason instanceof ReverifyTimeoutError
              ? t("reverifyRunning")
              : reason instanceof Error
                ? reason.message
                : String(reason);
        setReverifyErr((e) => ({ ...e, [strategyId]: msg }));
      } finally {
        setReverifying(null);
      }
    },
    [t],
  );

  const trialCols = useMemo(() => trialColumns(t), [t]);

  return (
    <section data-testid="page-monitoring" className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>

      {error ? (
        <Card data-testid="monitoring-error" className="border-destructive/60">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {MONITORED.map((strategy) => {
        const byMetric = metricsByStrategy[strategy.id] ?? {};
        return (
          <Card key={strategy.id} data-testid={`monitoring-card-${strategy.id}`}>
            <CardHeader>
              <CardTitle>{strategy.label}</CardTitle>
              <CardDescription>{t("researchOnly")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <CnAttackOosDisclosure researchCaveat={caveats[strategy.id]} />

              <div>
                <h3 className="mb-2 text-sm font-medium text-foreground">{t("metricsTitle")}</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {HEALTH_METRICS.map((name) => {
                    const row = byMetric[name];
                    const partial = row?.meta?.partial === true;
                    return (
                      <div
                        key={name}
                        data-testid={`metric-${strategy.id}-${name}`}
                        className="rounded-md border border-border/60 bg-muted/20 p-3"
                      >
                        <div className="text-xs text-muted-foreground">{name}</div>
                        <div className="text-lg font-semibold text-foreground">
                          {fmt(row?.value)}
                        </div>
                        {partial ? (
                          <div className="text-[10px] text-amber-400">{t("partial")}</div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                {Object.keys(byMetric).length === 0 ? (
                  <p className="mt-2 text-xs text-muted-foreground">{t("noData")}</p>
                ) : null}
              </div>

              <div className="space-y-2 border-t border-border/50 pt-3">
                <h3 className="text-sm font-medium text-foreground">{t("reverifyTitle")}</h3>
                <p className="text-xs text-muted-foreground">{t("reverifyNote")}</p>
                <Button
                  data-testid={`monitoring-reverify-${strategy.id}`}
                  onClick={() => handleReverify(strategy.id)}
                  disabled={reverifying !== null}
                >
                  {t("reverifyButton")}
                </Button>
                {reverifyMsg[strategy.id] ? (
                  <p
                    data-testid={`monitoring-reverify-msg-${strategy.id}`}
                    className="text-xs text-muted-foreground"
                  >
                    {reverifyMsg[strategy.id]}
                  </p>
                ) : null}
                {reverifyErr[strategy.id] ? (
                  <p className="text-xs text-destructive">{reverifyErr[strategy.id]}</p>
                ) : null}
              </div>
            </CardContent>
          </Card>
        );
      })}

      <Card data-testid="monitoring-trials-card">
        <CardHeader>
          <CardTitle>{t("trialsTitle")}</CardTitle>
          <CardDescription>
            {t("trialCount")}: {trials ? trials.total : "—"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<TrialRow> rowData={trials?.trials ?? []} columnDefs={trialCols} />
        </CardContent>
      </Card>

      <Card
        data-testid="monitoring-disclaimer-card"
        className="border-amber-700/40 bg-amber-950/20"
      >
        <CardContent className="pt-6 text-xs text-amber-200/90">{t("subtitle")}</CardContent>
      </Card>
    </section>
  );
}
