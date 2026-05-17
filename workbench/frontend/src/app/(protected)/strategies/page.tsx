"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
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

const STRATEGY_COLUMNS: ColDef<StrategySummary>[] = [
  { field: "id", headerName: "ID", flex: 1 },
  { field: "name", headerName: "Name", flex: 2 },
  { field: "sleeve", headerName: "Sleeve", width: 140 },
  { field: "status", headerName: "Status", width: 120 },
  dateColumn<StrategySummary>({ field: "last_sweep_date", headerName: "Last sweep", width: 140 }),
];

function ConfigList({ config }: { config: StrategyDetail["config"] }) {
  const entries = Object.entries(config);
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No config recorded.</p>;
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
  if (!path) {
    return (
      <Button variant="outline" disabled data-testid={`${testId}-empty`}>
        {label} — n/a
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
  const searchParams = useSearchParams();
  const selected = searchParams?.get("selected") ?? null;

  const [list, setList] = useState<StrategySummary[]>([]);
  const [detail, setDetail] = useState<StrategyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

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

  const heatmapData = detail?.turnover_heatmap ?? [];
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
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Strategies</h1>
        <div className="flex items-center gap-2">
          <span data-testid="strategies-state" className="text-xs text-muted-foreground">
            {error ? `unreachable: ${error}` : `${list.length} sleeves`}
          </span>
          <Button
            variant="outline"
            data-testid="strategies-export-csv"
            onClick={() => tableRef.current?.exportCsv("strategies.csv")}
          >
            Export CSV
          </Button>
        </div>
      </header>

      <Card data-testid="strategies-list-card">
        <CardHeader>
          <CardTitle>Sleeves</CardTitle>
          <CardDescription>
            Append <code>?selected=B013-regime-quarterly</code> to deep-link a detail panel.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<StrategySummary>
            ref={tableRef}
            rowData={list}
            columnDefs={STRATEGY_COLUMNS}
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
                  label="Spec"
                  testId="strategy-detail-spec-link"
                />
                <DocsLinkButton
                  path={detail.provenance.code_path}
                  label="Code"
                  testId="strategy-detail-code-link"
                />
                <DocsLinkButton
                  path={detail.provenance.last_sweep_path}
                  label="Last sweep"
                  testId="strategy-detail-sweep-link"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Equity curve</CardTitle>
              <CardDescription>
                Populated by the F008 backtest runner — wraps the F004 EquityCurveChart.
              </CardDescription>
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
              <CardTitle>Drawdown</CardTitle>
              <CardDescription>Shares the time axis with the equity curve (F008).</CardDescription>
            </CardHeader>
            <CardContent>
              <DrawdownChart data={drawdownData} height={160} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Turnover heatmap</CardTitle>
              <CardDescription>
                Cells appear when sweep data lands (F008/F009 wire real values).
              </CardDescription>
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
          Select a sleeve from the list above to see config + provenance + charts.
        </p>
      )}
    </section>
  );
}
