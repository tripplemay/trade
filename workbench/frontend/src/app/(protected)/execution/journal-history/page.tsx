"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ColDef } from "ag-grid-community";

import { AllocationBar, type AllocationBarItem } from "@/components/chart";
import {
  DataTable,
  type DataTableHandle,
  basisPointsColumn,
  currencyColumn,
  dateColumn,
} from "@/components/table";
import { ModeSelector } from "@/components/strategy/ModeSelector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { workbenchFetch } from "@/lib/api-fetch";
import { useStrategyMode } from "@/lib/strategy-mode";
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

function buildHistoryColumns(
  t: ReturnType<typeof useTranslations<"execution.journalHistory.columns">>,
): ColDef<JournalHistoryItem>[] {
  return [
    {
      field: "ticket_id",
      headerName: t("ticket"),
      width: 220,
      cellRenderer: (params: { value: string }) => params.value,
    },
    dateColumn<JournalHistoryItem>({ field: "ticket_date", headerName: t("date") }),
    {
      field: "status",
      headerName: t("status"),
      width: 110,
      valueFormatter: (params) => String(params.value ?? ""),
    },
    {
      field: "fill_count",
      headerName: t("fills"),
      width: 90,
      cellClass: "text-right",
      headerClass: "text-right",
    },
    basisPointsColumn<JournalHistoryItem>({
      field: "avg_bps",
      headerName: t("avgBps"),
      digits: 1,
    }),
    currencyColumn<JournalHistoryItem>({
      field: "total_dollar",
      headerName: t("totalDollar"),
    }),
  ];
}

export default function JournalHistoryPage() {
  const t = useTranslations("execution.journalHistory");
  const tCards = useTranslations("execution.journalHistory.cards");
  const tCols = useTranslations("execution.journalHistory.columns");
  const tWindow = useTranslations("execution.journalHistory.windowOptions");
  const tCommon = useTranslations("common");

  // B057 F005 — the journal + slippage analytics are the SELECTED mode's own
  // (the backend defaults to Master when the param is absent).
  const { strategyId } = useStrategyMode();

  const [history, setHistory] = useState<JournalHistoryResponse | null>(null);
  const [analytics, setAnalytics] = useState<SlippageAnalyticsResponse | null>(null);
  const [windowSel, setWindowSel] = useState<WindowOption>("3m");
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

  const modeQuery = `strategy_id=${encodeURIComponent(strategyId)}`;
  const historyColumns = useMemo(() => buildHistoryColumns(tCols), [tCols]);

  useEffect(() => {
    let cancelled = false;
    setHistory(null);
    workbenchFetch(`${HISTORY_URL}?${modeQuery}`)
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
  }, [modeQuery]);

  useEffect(() => {
    let cancelled = false;
    workbenchFetch(`${ANALYTICS_URL}?window=${windowSel}&${modeQuery}`)
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
  }, [windowSel, modeQuery]);

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

  const stateLabel = error
    ? tCommon("unreachableWithError", { error })
    : history
      ? t("ticketCount", { count: items.length })
      : tCommon("loading");

  return (
    <section data-testid="page-journal-history" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
          <p className="text-xs text-muted-foreground">{t("description")}</p>
        </div>
        <span data-testid="journal-history-state" className="text-xs text-muted-foreground">
          {stateLabel}
        </span>
      </header>

      <ModeSelector />

      <div className="grid gap-4 md:grid-cols-3">
        <Card data-testid="journal-card-count">
          <CardHeader>
            <CardTitle>{tCards("ticketsTitle")}</CardTitle>
            <CardDescription>{tCards("ticketsDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">{items.length}</p>
          </CardContent>
        </Card>
        <Card data-testid="journal-card-avg-bps">
          <CardHeader>
            <CardTitle>{tCards("avgBpsTitle")}</CardTitle>
            <CardDescription>{tCards("avgBpsDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">
              {overallAvgBps !== null ? `${overallAvgBps.toFixed(1)} bps` : "—"}
            </p>
          </CardContent>
        </Card>
        <Card data-testid="journal-card-total-dollar">
          <CardHeader>
            <CardTitle>{tCards("totalDollarTitle")}</CardTitle>
            <CardDescription>{tCards("totalDollarDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">${totalDollar.toFixed(2)}</p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="journal-trend-card">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>{t("trendCardTitle")}</CardTitle>
            <CardDescription>{t("trendCardDescription")}</CardDescription>
          </div>
          <select
            data-testid="journal-window-select"
            value={windowSel}
            onChange={(e) => setWindowSel(e.target.value as WindowOption)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="3m">{tWindow("3m")}</option>
            <option value="6m">{tWindow("6m")}</option>
            <option value="1y">{tWindow("1y")}</option>
          </select>
        </CardHeader>
        <CardContent>
          {analytics ? (
            analytics.trend.length > 0 ? (
              <AllocationBar data={trendBarItems} height={260} />
            ) : (
              <p data-testid="journal-trend-empty" className="text-sm text-muted-foreground">
                {t("trendEmpty", { window: tWindow(windowSel) })}
              </p>
            )
          ) : (
            <p className="text-sm text-muted-foreground">{t("loadingAnalytics")}</p>
          )}
          {analytics && analytics.outliers.length > 0 ? (
            <div className="mt-4 space-y-1">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {t("outliersTitle")}
              </p>
              <ul className="space-y-1 text-sm">
                {analytics.outliers.map((row) => (
                  <li
                    key={row.ticket_id}
                    data-testid={`journal-outlier-${row.ticket_id}`}
                    className="rounded-md border border-amber-700/40 bg-amber-950/20 px-2 py-1"
                  >
                    <strong>{row.ticket_id}</strong>{" "}
                    <span className="text-xs text-muted-foreground">
                      {t("outlierRowSuffix", {
                        date: row.ticket_date,
                        bps: row.avg_bps.toFixed(1),
                      })}
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
            <CardTitle>{t("tableCardTitle")}</CardTitle>
            <CardDescription>{t("tableCardDescription")}</CardDescription>
          </div>
          <Button
            data-testid="journal-history-export"
            variant="secondary"
            onClick={handleExportCsv}
            disabled={items.length === 0}
          >
            {tCommon("exportCsv")}
          </Button>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p data-testid="journal-history-empty" className="text-sm text-muted-foreground">
              {t("tableEmptyPrefix")}
              <Link href="/execution/ticket" className="underline">
                {t("tableEmptyLink")}
              </Link>
              {t("tableEmptySuffix")}
            </p>
          ) : (
            <div className="space-y-3">
              <DataTable<JournalHistoryItem>
                ref={tableRef}
                rowData={items}
                columnDefs={historyColumns}
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
                      {t("rowMeta", { date: row.ticket_date, count: row.fill_count })}
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
