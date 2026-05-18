"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ColDef } from "ag-grid-community";

import {
  AllocationBar,
  type AllocationBarItem,
} from "@/components/chart";
import {
  DataTable,
  type DataTableHandle,
  currencyColumn,
  percentColumn,
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
import type { components } from "@/types/api";

type PositionDiffResponse = components["schemas"]["PositionDiffResponse"];
type PositionDiffEntry = components["schemas"]["PositionDiffEntry"];

const DIFF_URL = "/api/execution/position-diff";

const SHARE_FORMATTER = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
});

function sharesValueFormatter(params: { value: unknown }): string {
  const v = params.value;
  if (typeof v !== "number" || Number.isNaN(v)) return "";
  return SHARE_FORMATTER.format(v);
}

const DIFF_COLUMNS: ColDef<PositionDiffEntry>[] = [
  { field: "symbol", headerName: "Symbol", width: 110, pinned: "left" },
  {
    field: "current_shares",
    headerName: "Current shares",
    cellClass: "text-right",
    headerClass: "text-right",
    valueFormatter: sharesValueFormatter,
    width: 140,
  },
  {
    field: "target_shares",
    headerName: "Target shares",
    cellClass: "text-right",
    headerClass: "text-right",
    valueFormatter: sharesValueFormatter,
    width: 140,
  },
  {
    field: "delta_shares",
    headerName: "Δ shares",
    cellClass: (params) => {
      const v = params.value as number | undefined;
      if (typeof v !== "number") return "text-right";
      if (v > 0) return "text-right text-[var(--color-up)]";
      if (v < 0) return "text-right text-[var(--color-down)]";
      return "text-right";
    },
    headerClass: "text-right",
    valueFormatter: (params) => {
      const v = params.value as number | undefined;
      if (typeof v !== "number" || Number.isNaN(v)) return "";
      return (v > 0 ? "+" : "") + SHARE_FORMATTER.format(v);
    },
    width: 140,
  },
  percentColumn<PositionDiffEntry>({
    field: "current_weight",
    headerName: "Current %",
    digits: 2,
  }),
  percentColumn<PositionDiffEntry>({
    field: "target_weight",
    headerName: "Target %",
    digits: 2,
  }),
  percentColumn<PositionDiffEntry>({
    field: "delta_weight",
    headerName: "Δ %",
    digits: 2,
  }),
  currencyColumn<PositionDiffEntry>({
    field: "delta_dollar",
    headerName: "Δ $",
  }),
  { field: "reason", headerName: "Reason", flex: 2, minWidth: 240 },
];

export default function PositionDiffPage() {
  const [data, setData] = useState<PositionDiffResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(DIFF_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as PositionDiffResponse;
        if (!cancelled) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const currentBarItems: AllocationBarItem[] = useMemo(
    () =>
      (data?.current?.positions ?? []).map((p) => ({
        name: p.symbol,
        value: p.shares * p.avg_cost,
      })),
    [data],
  );
  const targetBarItems: AllocationBarItem[] = useMemo(
    () =>
      (data?.target ?? []).map((p) => ({
        name: p.symbol,
        value: p.shares * p.avg_cost,
      })),
    [data],
  );

  const handleExportCsv = () => {
    tableRef.current?.exportCsv(`position-diff-${data?.as_of_date ?? "current"}.csv`);
  };

  const hasSnapshot = data?.current != null;
  const diffRows = data?.diff ?? [];
  const unmatchedRows = data?.unmatched ?? [];

  return (
    <section data-testid="page-position-diff" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Position diff</h1>
          <p className="text-xs text-muted-foreground">
            Current account state vs target portfolio. Workbench is research-only; review and execute
            manually in your broker.
          </p>
        </div>
        <span data-testid="position-diff-state" className="text-xs text-muted-foreground">
          {error
            ? `unreachable: ${error}`
            : data
              ? `as of ${data.as_of_date} · equity $${SHARE_FORMATTER.format(data.total_equity ?? 0)}`
              : "loading…"}
        </span>
      </header>

      {data && !hasSnapshot ? (
        <Card data-testid="position-diff-empty">
          <CardHeader>
            <CardTitle>No account snapshot on file</CardTitle>
            <CardDescription>
              Edit your account on the <code>/execution/account</code> page to seed a baseline
              snapshot. The diff renders once cash + positions are recorded.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current allocation</CardTitle>
            <CardDescription>$ per symbol from the latest snapshot.</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={currentBarItems} height={240} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Target allocation</CardTitle>
            <CardDescription>$ per symbol if rebalanced to target weights.</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={targetBarItems} height={240} />
          </CardContent>
        </Card>
      </div>

      <Card data-testid="position-diff-table-card">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>Per-symbol diff</CardTitle>
            <CardDescription>
              Positive Δ = buy, negative Δ = sell. Reference price = position cost basis;
              target-only symbols are flagged below.
            </CardDescription>
          </div>
          <Button
            data-testid="position-diff-export-csv"
            variant="secondary"
            onClick={handleExportCsv}
            disabled={diffRows.length === 0}
          >
            Export CSV
          </Button>
        </CardHeader>
        <CardContent>
          <DataTable<PositionDiffEntry>
            ref={tableRef}
            rowData={diffRows}
            columnDefs={DIFF_COLUMNS}
            height={360}
          />
        </CardContent>
      </Card>

      <Card
        data-testid="position-diff-unmatched-card"
        className={cn(unmatchedRows.length === 0 && "opacity-70")}
      >
        <CardHeader>
          <CardTitle>Unmatched targets</CardTitle>
          <CardDescription>
            Target symbols with no current position to anchor a price reference. Share calculations
            for these rows fall back to the cash basis until the symbol has a cost-basis record.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {unmatchedRows.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {unmatchedRows.map((row) => (
                <li
                  key={row.symbol}
                  data-testid={`position-diff-unmatched-${row.symbol}`}
                  className="rounded-md border border-amber-700/40 bg-amber-950/20 px-3 py-2"
                >
                  <strong>{row.symbol}</strong>
                  <span className="ml-2 text-xs text-muted-foreground">
                    target weight {(row.target_weight * 100).toFixed(2)}% — no cost basis on file
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p data-testid="position-diff-unmatched-empty" className="text-sm text-muted-foreground">
              None — every target symbol has a price reference.
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
