"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { ColDef } from "ag-grid-community";

import {
  AllocationBar,
  type AllocationBarItem,
} from "@/components/chart";
import {
  DataTable,
  type DataTableHandle,
  basisPointsColumn,
  currencyColumn,
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

type JournalHistoryResponse = components["schemas"]["JournalHistoryResponse"];
type JournalHistoryItem = components["schemas"]["JournalHistoryItem"];
type SlippageAnalyticsResponse = components["schemas"]["SlippageAnalyticsResponse"];

const HISTORY_URL = "/api/execution/journal-history";
const ANALYTICS_URL = "/api/execution/slippage-analytics";

type WindowOption = "3m" | "6m" | "1y";

const STATUS_BADGE: Record<JournalHistoryItem["status"], string> = {
  generated: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  executed: "border-green-700/60 bg-green-950/30 text-green-200",
  voided: "border-zinc-700/60 bg-zinc-900/40 text-muted-foreground",
};

const HISTORY_COLUMNS: ColDef<JournalHistoryItem>[] = [
  {
    field: "ticket_id",
    headerName: "Ticket",
    width: 220,
    cellRenderer: (params: { value: string }) => params.value,
  },
  dateColumn<JournalHistoryItem>({ field: "ticket_date", headerName: "Date" }),
  {
    field: "status",
    headerName: "Status",
    width: 110,
    valueFormatter: (params) => String(params.value ?? ""),
  },
  {
    field: "fill_count",
    headerName: "Fills",
    width: 90,
    cellClass: "text-right",
    headerClass: "text-right",
  },
  basisPointsColumn<JournalHistoryItem>({
    field: "avg_bps",
    headerName: "Avg slippage (bps)",
    digits: 1,
  }),
  currencyColumn<JournalHistoryItem>({
    field: "total_dollar",
    headerName: "Total slippage $",
  }),
];

export default function JournalHistoryPage() {
  const [history, setHistory] = useState<JournalHistoryResponse | null>(null);
  const [analytics, setAnalytics] = useState<SlippageAnalyticsResponse | null>(null);
  const [windowSel, setWindowSel] = useState<WindowOption>("3m");
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(HISTORY_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as JournalHistoryResponse;
        if (!cancelled) setHistory(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${ANALYTICS_URL}?window=${windowSel}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as SlippageAnalyticsResponse;
        if (!cancelled) setAnalytics(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [windowSel]);

  const trendBarItems: AllocationBarItem[] = useMemo(
    () =>
      (analytics?.trend ?? []).map((point) => ({
        name: point.month,
        value: point.avg_bps,
      })),
    [analytics],
  );

  const handleExportCsv = () => {
    tableRef.current?.exportCsv(`journal-history-${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const items = history?.items ?? [];
  const totalDollar = items.reduce((acc, item) => acc + (item.total_dollar ?? 0), 0);
  const validBps = items
    .map((item) => item.avg_bps)
    .filter((b): b is number => b !== null && b !== undefined);
  const overallAvgBps =
    validBps.length > 0 ? validBps.reduce((a, b) => a + b, 0) / validBps.length : null;

  return (
    <section data-testid="page-journal-history" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Journal history
          </h1>
          <p className="text-xs text-muted-foreground">
            Past tickets, fills, and slippage analytics. Workbench is research-only.
          </p>
        </div>
        <span data-testid="journal-history-state" className="text-xs text-muted-foreground">
          {error
            ? `unreachable: ${error}`
            : history
              ? `${items.length} ticket(s) on file`
              : "loading…"}
        </span>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Card data-testid="journal-card-count">
          <CardHeader>
            <CardTitle>Tickets</CardTitle>
            <CardDescription>All-time count.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">{items.length}</p>
          </CardContent>
        </Card>
        <Card data-testid="journal-card-avg-bps">
          <CardHeader>
            <CardTitle>Avg slippage</CardTitle>
            <CardDescription>Mean of per-ticket avg bps.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">
              {overallAvgBps !== null ? `${overallAvgBps.toFixed(1)} bps` : "—"}
            </p>
          </CardContent>
        </Card>
        <Card data-testid="journal-card-total-dollar">
          <CardHeader>
            <CardTitle>Total slippage $</CardTitle>
            <CardDescription>Signed sum across tickets.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">
              ${totalDollar.toFixed(2)}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="journal-trend-card">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>Slippage trend</CardTitle>
            <CardDescription>
              Per-month avg bps over the selected rolling window.
            </CardDescription>
          </div>
          <select
            data-testid="journal-window-select"
            value={windowSel}
            onChange={(e) => setWindowSel(e.target.value as WindowOption)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="3m">3 months</option>
            <option value="6m">6 months</option>
            <option value="1y">1 year</option>
          </select>
        </CardHeader>
        <CardContent>
          {analytics ? (
            analytics.trend.length > 0 ? (
              <AllocationBar data={trendBarItems} height={260} />
            ) : (
              <p data-testid="journal-trend-empty" className="text-sm text-muted-foreground">
                No executed tickets in the {windowSel} window.
              </p>
            )
          ) : (
            <p className="text-sm text-muted-foreground">Loading analytics…</p>
          )}
          {analytics && analytics.outliers.length > 0 ? (
            <div className="mt-4 space-y-1">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Outliers</p>
              <ul className="space-y-1 text-sm">
                {analytics.outliers.map((row) => (
                  <li
                    key={row.ticket_id}
                    data-testid={`journal-outlier-${row.ticket_id}`}
                    className="rounded-md border border-amber-700/40 bg-amber-950/20 px-2 py-1"
                  >
                    <strong>{row.ticket_id}</strong>{" "}
                    <span className="text-xs text-muted-foreground">
                      {row.ticket_date} · {row.avg_bps.toFixed(1)} bps
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card data-testid="journal-history-table-card">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>Tickets</CardTitle>
            <CardDescription>Sortable, filterable. Click a ticket id to open the read-only viewer.</CardDescription>
          </div>
          <Button
            data-testid="journal-history-export"
            variant="secondary"
            onClick={handleExportCsv}
            disabled={items.length === 0}
          >
            Export CSV
          </Button>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p data-testid="journal-history-empty" className="text-sm text-muted-foreground">
              No tickets recorded yet. Generate one in <Link href="/execution/ticket" className="underline">the ticket page</Link>.
            </p>
          ) : (
            <div className="space-y-3">
              <DataTable<JournalHistoryItem>
                ref={tableRef}
                rowData={items}
                columnDefs={HISTORY_COLUMNS}
                height={420}
              />
              <ul className="space-y-1 text-xs">
                {items.slice(0, 10).map((row) => (
                  <li
                    key={row.ticket_id}
                    data-testid={`journal-history-link-${row.ticket_id}`}
                    className="flex items-center gap-3"
                  >
                    <span
                      className={`rounded-md border px-2 py-0.5 text-[10px] uppercase ${
                        STATUS_BADGE[row.status]
                      }`}
                    >
                      {row.status}
                    </span>
                    <Link
                      href={`/execution/ticket/${encodeURIComponent(row.ticket_id)}`}
                      className="font-mono underline-offset-2 hover:underline"
                    >
                      {row.ticket_id}
                    </Link>
                    <span className="text-muted-foreground">
                      {row.ticket_date} · {row.fill_count} fills
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
