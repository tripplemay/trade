"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import {
  AllocationBar,
  AllocationPie,
  type AllocationBarItem,
  type AllocationSlice,
} from "@/components/chart";
import { NewsPanel } from "@/components/recommendations/NewsPanel";
import { PositionCards } from "@/components/recommendations/PositionCards";
import { RiskBanner } from "@/components/risk/RiskBanner";
import { ModeSelector } from "@/components/strategy/ModeSelector";
import { DataTable, percentColumn, weightColumn } from "@/components/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { workbenchFetch } from "@/lib/api-fetch";
import {
  RefreshJobError,
  RefreshTimeoutError,
  runRefreshTarget,
  type TargetRefreshJobStatus,
} from "@/lib/refresh-target-poll";
import { useStrategyMode } from "@/lib/strategy-mode";
import { cn } from "@/lib/utils";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type RecommendationsResponse = components["schemas"]["RecommendationsResponse"];
type TargetPosition = components["schemas"]["TargetPosition"];
type GateCheck = components["schemas"]["GateCheck"];
type ExportTicketResponse = components["schemas"]["ExportTicketResponse"];

const CURRENT_URL = "/api/recommendations/current";
const EXPORT_URL = "/api/recommendations/export-ticket";

function buildPositionColumns(
  t: ReturnType<typeof useTranslations<"recommendations.positions">>,
): ColDef<TargetPosition>[] {
  return [
    { field: "symbol", headerName: t("columnSymbol"), width: 110 },
    weightColumn<TargetPosition>({
      field: "target_weight",
      headerName: t("columnTarget"),
      digits: 2,
    }),
    weightColumn<TargetPosition>({
      field: "current_weight",
      headerName: t("columnCurrent"),
      digits: 2,
    }),
    percentColumn<TargetPosition>({ field: "diff", headerName: t("columnDiff"), digits: 2 }),
    { field: "rationale", headerName: t("columnRationale"), flex: 2 },
  ];
}

const GATE_STYLES: Record<string, string> = {
  pass: "border-green-700/50 bg-green-950/30 text-green-200",
  warn: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  fail: "border-destructive/60 bg-destructive/10 text-destructive-foreground",
};

export default function RecommendationsPage() {
  const t = useTranslations("recommendations");
  const tPos = useTranslations("recommendations.positions");
  const tView = useTranslations("recommendations.view");
  const tWeights = useTranslations("recommendations.targetWeights");
  const tDeltas = useTranslations("recommendations.deltas");
  const tGates = useTranslations("recommendations.gates");
  const tWash = useTranslations("recommendations.wash");
  const tEmpty = useTranslations("recommendations.emptyAccount");
  const tExport = useTranslations("recommendations.exportCard");
  const tRefresh = useTranslations("recommendations.refreshTarget");
  const tCommon = useTranslations("common");

  // B057 F005 — the recommendations page shows the SELECTED mode's target +
  // account (the backend defaults to Master when the param is absent).
  const { strategyId } = useStrategyMode();

  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportTicketResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  // B058 F005 — manual "refresh this mode's target" (enqueue + poll).
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<TargetRefreshJobStatus | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshErrorKind, setRefreshErrorKind] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const positionColumns = useMemo(() => buildPositionColumns(tPos), [tPos]);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    workbenchFetch(`${CURRENT_URL}?strategy_id=${encodeURIComponent(strategyId)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as RecommendationsResponse;
        if (!cancelled) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [strategyId, reloadKey]);

  const pieSlices: AllocationSlice[] = useMemo(
    () =>
      (data?.target_positions ?? []).map((p) => ({
        name: p.symbol,
        value: p.target_weight,
      })),
    [data],
  );
  const barItems: AllocationBarItem[] = useMemo(
    () =>
      (data?.target_positions ?? []).map((p) => ({
        name: p.symbol,
        value: p.diff,
      })),
    [data],
  );

  const handleExport = async () => {
    if (!data) return;
    setExporting(true);
    setExportError(null);
    try {
      const response = await fetch(EXPORT_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ as_of_date: data.as_of_date }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()) as ExportTicketResponse;
      setExportResult(payload);
    } catch (reason: unknown) {
      setExportError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setExporting(false);
    }
  };

  const refreshErrorMessage = (kind: string | null): string => {
    switch (kind) {
      case "data_not_covered":
        return tRefresh("errorKind.data_not_covered");
      case "scoring_error":
        return tRefresh("errorKind.scoring_error");
      case "producer_error":
        return tRefresh("errorKind.producer_error");
      case "empty_target":
        return tRefresh("errorKind.empty_target");
      case "interrupted":
        return tRefresh("errorKind.interrupted");
      default:
        return tRefresh("errorKind.unknown");
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshError(null);
    setRefreshErrorKind(null);
    setRefreshResult(null);
    try {
      const result = await runRefreshTarget(strategyId);
      setRefreshResult(result);
      setReloadKey((k) => k + 1); // re-fetch the (now refreshed) target
    } catch (reason: unknown) {
      if (reason instanceof RefreshJobError) {
        setRefreshErrorKind(reason.errorKind ?? "unknown");
      } else if (reason instanceof RefreshTimeoutError) {
        setRefreshError(tRefresh("timeout"));
      } else {
        setRefreshError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      setRefreshing(false);
    }
  };

  const accountPresent = data?.account_present ?? false;

  const stateLabel = error
    ? tCommon("unreachableWithError", { error })
    : data
      ? t("statePrefix", {
          date: data.as_of_date,
          accountStatus: accountPresent ? t("accountPresent") : t("accountMissing"),
        })
      : tCommon("loading");

  return (
    <section data-testid="page-recommendations" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <span data-testid="recommendations-state" className="text-xs text-muted-foreground">
          {stateLabel}
        </span>
      </header>

      <ModeSelector />

      <RiskBanner />

      <Card data-testid="recommendations-refresh-card">
        <CardHeader>
          <CardTitle>{tRefresh("title")}</CardTitle>
          <CardDescription>{tRefresh("description")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            data-testid="recommendations-refresh-target"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? tRefresh("refreshing") : tRefresh("button")}
          </Button>
          {refreshResult ? (
            <p
              data-testid="recommendations-refresh-result"
              className="text-xs text-muted-foreground"
            >
              {tRefresh("resultDone", {
                date: refreshResult.as_of_date ?? "—",
                count: refreshResult.saved_count ?? 0,
                source: refreshResult.data_source ?? "—",
              })}
            </p>
          ) : null}
          {refreshErrorKind || refreshError ? (
            <p data-testid="recommendations-refresh-error" className="text-xs text-destructive">
              {refreshErrorKind ? refreshErrorMessage(refreshErrorKind) : refreshError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card
        data-testid="recommendations-disclaimer-card"
        className="border-amber-700/40 bg-amber-950/20"
      >
        <CardContent className="py-3 text-xs text-amber-100">
          <strong>{t("disclaimerBold")}</strong> {t("disclaimerBody")}
        </CardContent>
      </Card>

      {data && !accountPresent ? (
        <Card data-testid="recommendations-empty">
          <CardHeader>
            <CardTitle>{tEmpty("title")}</CardTitle>
            <CardDescription>
              {tEmpty("descriptionPrefix")}
              <code>{tEmpty("descriptionPath")}</code>
              {tEmpty("descriptionSuffix")}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{tWeights("title")}</CardTitle>
            <CardDescription>{tWeights("description")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationPie data={pieSlices} height={240} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{tDeltas("title")}</CardTitle>
            <CardDescription>{tDeltas("description")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={barItems} height={240} />
          </CardContent>
        </Card>
      </div>

      <Card data-testid="recommendations-positions-card">
        <CardHeader>
          <CardTitle>{tPos("title")}</CardTitle>
          <CardDescription>
            {accountPresent
              ? tPos("subtitleCount", { count: data?.target_positions.length ?? 0 })
              : tPos("subtitleEmpty")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* B041: simplified card view (default) ⟷ professional table toggle.
              Only the target-positions presentation changes; charts / gate /
              wash-sale / export-to-ticket / NewsPanel are untouched. */}
          <Tabs
            defaultValue="simple"
            activationMode="manual"
            data-testid="recommendations-view-toggle"
          >
            <TabsList>
              <TabsTrigger value="simple" data-testid="view-toggle-simple">
                {tView("simple")}
              </TabsTrigger>
              <TabsTrigger value="professional" data-testid="view-toggle-professional">
                {tView("professional")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="simple">
              <PositionCards positions={data?.target_positions ?? []} />
            </TabsContent>
            <TabsContent value="professional">
              <DataTable<TargetPosition>
                rowData={data?.target_positions ?? []}
                columnDefs={positionColumns}
                height={280}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="recommendations-gate-panel">
          <CardHeader>
            <CardTitle>{tGates("title")}</CardTitle>
            <CardDescription>{tGates("description")}</CardDescription>
          </CardHeader>
          <CardContent>
            {data && data.gate_checks.length > 0 ? (
              <ul className="space-y-2">
                {data.gate_checks.map((gate: GateCheck) => (
                  <li
                    key={gate.name}
                    data-testid={`gate-${gate.name}`}
                    className={cn(
                      "rounded-md border px-3 py-2 text-sm",
                      GATE_STYLES[gate.status] ?? GATE_STYLES.warn,
                    )}
                  >
                    <span className="mr-2 text-[10px] font-semibold uppercase">{gate.status}</span>
                    <span className="font-medium">{gate.name}</span>
                    {gate.detail ? (
                      <span className="ml-2 text-xs text-muted-foreground">{gate.detail}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">{tGates("empty")}</p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="recommendations-wash-flags">
          <CardHeader>
            <CardTitle>{tWash("title")}</CardTitle>
            <CardDescription>{tWash("description")}</CardDescription>
          </CardHeader>
          <CardContent>
            {data && (data.wash_sale_flags ?? []).length > 0 ? (
              <ul className="space-y-1 text-sm">
                {(data.wash_sale_flags ?? []).map((flag) => (
                  <li key={flag.symbol}>
                    <strong>{flag.symbol}</strong>
                    {" — "}
                    {tWash("lastBuy", { date: flag.last_buy_date, days: flag.days_since })}
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="recommendations-wash-empty" className="text-sm text-muted-foreground">
                {tWash("empty")}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="recommendations-export-card">
        <CardHeader>
          <CardTitle>{tExport("title")}</CardTitle>
          <CardDescription>
            {tExport("descriptionPrefix")}
            <code>{tExport("descriptionPath")}</code>
            {tExport("descriptionSuffix")}
            <code>{tExport("descriptionTest")}</code>
            {tExport("descriptionEnd")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            data-testid="recommendations-export"
            onClick={handleExport}
            disabled={!data || exporting}
          >
            {exporting ? tExport("buttonExporting") : tExport("button")}
          </Button>
          {exportResult ? (
            <p
              data-testid="recommendations-export-result"
              className="text-xs text-muted-foreground"
            >
              {tExport("resultPrefix")}
              <code>{exportResult.path}</code>
              {tExport("resultSuffix")}
            </p>
          ) : null}
          {exportError ? (
            <p data-testid="recommendations-export-error" className="text-xs text-destructive">
              {tExport("errorPrefix")} {exportError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <NewsPanel />
    </section>
  );
}
