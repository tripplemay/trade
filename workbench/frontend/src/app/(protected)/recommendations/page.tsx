"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import {
  AllocationBar,
  AllocationPie,
  type AllocationBarItem,
  type AllocationSlice,
} from "@/components/chart";
import { RiskBanner } from "@/components/risk/RiskBanner";
import {
  DataTable,
  percentColumn,
  weightColumn,
} from "@/components/table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
    weightColumn<TargetPosition>({ field: "target_weight", headerName: t("columnTarget"), digits: 2 }),
    weightColumn<TargetPosition>({ field: "current_weight", headerName: t("columnCurrent"), digits: 2 }),
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
  const tWeights = useTranslations("recommendations.targetWeights");
  const tDeltas = useTranslations("recommendations.deltas");
  const tGates = useTranslations("recommendations.gates");
  const tWash = useTranslations("recommendations.wash");
  const tEmpty = useTranslations("recommendations.emptyAccount");
  const tExport = useTranslations("recommendations.exportCard");
  const tCommon = useTranslations("common");

  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportTicketResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const positionColumns = useMemo(() => buildPositionColumns(tPos), [tPos]);

  useEffect(() => {
    let cancelled = false;
    fetch(CURRENT_URL)
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
  }, []);

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

      <RiskBanner />

      <Card data-testid="recommendations-disclaimer-card" className="border-amber-700/40 bg-amber-950/20">
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
          <DataTable<TargetPosition>
            rowData={data?.target_positions ?? []}
            columnDefs={positionColumns}
            height={280}
          />
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
            <p data-testid="recommendations-export-result" className="text-xs text-muted-foreground">
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
    </section>
  );
}
