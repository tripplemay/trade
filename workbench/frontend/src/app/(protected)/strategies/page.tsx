"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  DrawdownChart,
  EquityCurveChart,
  SweepHeatmap,
  type SweepHeatmapCell,
} from "@/components/chart";
import {
  DataTable,
  type DataTableHandle,
  dateColumn,
} from "@/components/table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { components } from "@/types/api";
import type { ColDef } from "ag-grid-community";

type StrategySummary = components["schemas"]["StrategySummary"];
type StrategyDetail = components["schemas"]["StrategyDetail"];

const LIST_URL = "/api/strategies";

function buildStrategyColumns(
  t: ReturnType<typeof useTranslations<"strategies.list">>,
): ColDef<StrategySummary>[] {
  return [
    { field: "id", headerName: t("columnId"), flex: 1 },
    { field: "name", headerName: t("columnName"), flex: 2 },
    { field: "sleeve", headerName: t("columnSleeve"), width: 140 },
    { field: "status", headerName: t("columnStatus"), width: 120 },
    dateColumn<StrategySummary>({
      field: "last_sweep_date",
      headerName: t("columnLastSweep"),
      width: 140,
    }),
  ];
}

function ConfigList({ config }: { config: StrategyDetail["config"] }) {
  const t = useTranslations("strategies");
  const entries = Object.entries(config);
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("configEmpty")}</p>;
  }
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="font-medium text-muted-foreground">{key}</dt>
          <dd className="numeric break-all text-foreground">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function DocsLinkButton({
  path,
  label,
  testId,
}: {
  path: string | null | undefined;
  label: string;
  testId: string;
}) {
  const t = useTranslations("strategies.details");
  if (!path) {
    return (
      <Button variant="outline" disabled data-testid={`${testId}-empty`}>
        {t("linkUnavailable", { label })}
      </Button>
    );
  }
  // Surface the spec/code via /api/docs/{path} — F009 will render the
  // markdown body inline; for F007 we just deep-link to a viewer path
  // that 404s today and starts working when F009 ships.
  return (
    <Button variant="outline" asChild data-testid={testId}>
      <Link href={`/docs/${path}`}>{label}</Link>
    </Button>
  );
}

export default function StrategiesPage() {
  const t = useTranslations("strategies");
  const tList = useTranslations("strategies.list");
  const tDetails = useTranslations("strategies.details");
  const tEquity = useTranslations("strategies.equity");
  const tDrawdown = useTranslations("strategies.drawdown");
  const tHeatmap = useTranslations("strategies.heatmap");
  const tCommon = useTranslations("common");

  const searchParams = useSearchParams();
  const selected = searchParams?.get("selected") ?? null;

  const [list, setList] = useState<StrategySummary[]>([]);
  const [detail, setDetail] = useState<StrategyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

  const strategyColumns = useMemo(() => buildStrategyColumns(tList), [tList]);

  useEffect(() => {
    let cancelled = false;
    fetch(LIST_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as components["schemas"]["StrategyListResponse"];
        if (!cancelled) setList(data.strategies);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Resolve the currently-selected strategy id: ?selected URL param wins,
  // else first row of the loaded list. Detail fetch follows.
  const effectiveSelected = useMemo(
    () => selected ?? list[0]?.id ?? null,
    [selected, list],
  );

  useEffect(() => {
    if (!effectiveSelected) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    fetch(`${LIST_URL}/${encodeURIComponent(effectiveSelected)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as StrategyDetail;
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveSelected]);

  // Memo each derived array so downstream useMemos receive a stable
  // reference; without this the heatmap recomputes on every render.
  const heatmapData = useMemo(() => detail?.turnover_heatmap ?? [], [detail]);
  const equityData = useMemo(
    () => (detail?.equity_curve ?? []).map((p) => ({ time: p.date, value: p.value })),
    [detail],
  );
  const drawdownData = useMemo(
    () => (detail?.drawdown_series ?? []).map((p) => ({ time: p.date, value: p.value })),
    [detail],
  );
  const heatmapXCats = useMemo(
    () => Array.from(new Set(heatmapData.map((c) => c.period))),
    [heatmapData],
  );
  const heatmapYCats = useMemo(
    () => Array.from(new Set(heatmapData.map((c) => c.bucket))),
    [heatmapData],
  );
  const heatmapCells: SweepHeatmapCell[] = useMemo(
    () =>
      heatmapData.map((c) => ({
        xIndex: heatmapXCats.indexOf(c.period),
        yIndex: heatmapYCats.indexOf(c.bucket),
        value: c.turnover,
      })),
    [heatmapData, heatmapXCats, heatmapYCats],
  );

  return (
    <section data-testid="page-strategies" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <div className="flex items-center gap-2">
          <span data-testid="strategies-state" className="text-xs text-muted-foreground">
            {error
              ? tCommon("unreachableWithError", { error })
              : t("sleeveCount", { count: list.length })}
          </span>
          <Button
            variant="outline"
            data-testid="strategies-export-csv"
            onClick={() => tableRef.current?.exportCsv("strategies.csv")}
          >
            {t("exportCsv")}
          </Button>
        </div>
      </header>

      <Card data-testid="strategies-list-card">
        <CardHeader>
          <CardTitle>{tList("title")}</CardTitle>
          <CardDescription>
            {tList.rich("deeplinkHint", {
              param: () => <code>?selected=B013-regime-quarterly</code>,
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<StrategySummary>
            ref={tableRef}
            rowData={list}
            columnDefs={strategyColumns}
            height={360}
          />
        </CardContent>
      </Card>

      {detail ? (
        <div className="grid gap-4 lg:grid-cols-2" data-testid="strategy-detail">
          <Card data-testid="strategy-detail-config">
            <CardHeader>
              <CardTitle>{detail.name}</CardTitle>
              <CardDescription>
                {detail.sleeve} · {detail.status}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ConfigList config={detail.config} />
              <div className="flex flex-wrap gap-2">
                <DocsLinkButton
                  path={detail.provenance.spec_path}
                  label={tDetails("spec")}
                  testId="strategy-detail-spec-link"
                />
                <DocsLinkButton
                  path={detail.provenance.code_path}
                  label={tDetails("code")}
                  testId="strategy-detail-code-link"
                />
                <DocsLinkButton
                  path={detail.provenance.last_sweep_path}
                  label={tDetails("lastSweep")}
                  testId="strategy-detail-sweep-link"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{tEquity("title")}</CardTitle>
              <CardDescription>{tEquity("description")}</CardDescription>
            </CardHeader>
            <CardContent>
              <EquityCurveChart
                series={[
                  {
                    id: detail.id,
                    name: detail.name,
                    color: "#00c853",
                    data: equityData,
                  },
                ]}
                height={240}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{tDrawdown("title")}</CardTitle>
              <CardDescription>{tDrawdown("description")}</CardDescription>
            </CardHeader>
            <CardContent>
              <DrawdownChart data={drawdownData} height={160} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{tHeatmap("title")}</CardTitle>
              <CardDescription>{tHeatmap("description")}</CardDescription>
            </CardHeader>
            <CardContent>
              <SweepHeatmap
                xCategories={heatmapXCats}
                yCategories={heatmapYCats}
                data={heatmapCells}
                height={240}
              />
            </CardContent>
          </Card>
        </div>
      ) : (
        <p data-testid="strategy-detail-empty" className="text-sm text-muted-foreground">
          {tDetails("selectHint")}
        </p>
      )}
    </section>
  );
}
