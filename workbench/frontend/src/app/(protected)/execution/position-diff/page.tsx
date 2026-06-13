"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ColDef } from "ag-grid-community";

import { AllocationBar, type AllocationBarItem } from "@/components/chart";
import { ModeSelector } from "@/components/strategy/ModeSelector";
import { SymbolLink } from "@/components/symbol/SymbolLink";
import { DataTable, type DataTableHandle, currencyColumn, percentColumn } from "@/components/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { workbenchFetch } from "@/lib/api-fetch";
import { useStrategyMode } from "@/lib/strategy-mode";
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

function buildDiffColumns(
  t: ReturnType<typeof useTranslations<"execution.positionDiff.columns">>,
): ColDef<PositionDiffEntry>[] {
  return [
    {
      field: "symbol",
      headerName: t("symbol"),
      width: 110,
      pinned: "left",
      cellRenderer: (params: { value?: string }) => <SymbolLink symbol={params.value ?? ""} />,
    },
    {
      field: "current_shares",
      headerName: t("currentShares"),
      cellClass: "text-right",
      headerClass: "text-right",
      valueFormatter: sharesValueFormatter,
      width: 140,
    },
    {
      field: "target_shares",
      headerName: t("targetShares"),
      cellClass: "text-right",
      headerClass: "text-right",
      valueFormatter: sharesValueFormatter,
      width: 140,
    },
    {
      field: "delta_shares",
      headerName: t("deltaShares"),
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
      headerName: t("currentWeight"),
      digits: 2,
    }),
    percentColumn<PositionDiffEntry>({
      field: "target_weight",
      headerName: t("targetWeight"),
      digits: 2,
    }),
    percentColumn<PositionDiffEntry>({
      field: "delta_weight",
      headerName: t("deltaWeight"),
      digits: 2,
    }),
    currencyColumn<PositionDiffEntry>({
      field: "delta_dollar",
      headerName: t("deltaDollar"),
    }),
    { field: "reason", headerName: t("reason"), flex: 2, minWidth: 240 },
  ];
}

export default function PositionDiffPage() {
  const t = useTranslations("execution.positionDiff");
  const tCols = useTranslations("execution.positionDiff.columns");
  const tCommon = useTranslations("common");

  // B057 F005 — the diff is computed against the SELECTED mode's account +
  // target (the backend defaults to Master when the param is absent).
  const { strategyId } = useStrategyMode();

  const [data, setData] = useState<PositionDiffResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<DataTableHandle>(null);

  const diffColumns = useMemo(() => buildDiffColumns(tCols), [tCols]);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    workbenchFetch(`${DIFF_URL}?strategy_id=${encodeURIComponent(strategyId)}`)
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
  }, [strategyId]);

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

  const stateLabel = error
    ? tCommon("unreachableWithError", { error })
    : data
      ? t("stateAsOfEquity", {
          date: data.as_of_date,
          equity: SHARE_FORMATTER.format(data.total_equity ?? 0),
        })
      : tCommon("loading");

  return (
    <section data-testid="page-position-diff" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
          <p className="text-xs text-muted-foreground">{t("description")}</p>
        </div>
        <span data-testid="position-diff-state" className="text-xs text-muted-foreground">
          {stateLabel}
        </span>
      </header>

      <ModeSelector />

      {data && !hasSnapshot ? (
        <Card data-testid="position-diff-empty">
          <CardHeader>
            <CardTitle>{t("emptyTitle")}</CardTitle>
            <CardDescription>
              {t("emptyDescriptionPrefix")}
              <code>{t("emptyDescriptionPath")}</code>
              {t("emptyDescriptionSuffix")}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("currentAllocationTitle")}</CardTitle>
            <CardDescription>{t("currentAllocationDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={currentBarItems} height={240} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("targetAllocationTitle")}</CardTitle>
            <CardDescription>{t("targetAllocationDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={targetBarItems} height={240} />
          </CardContent>
        </Card>
      </div>

      <Card data-testid="position-diff-table-card">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>{t("perSymbolTitle")}</CardTitle>
            <CardDescription>{t("perSymbolDescription")}</CardDescription>
          </div>
          <Button
            data-testid="position-diff-export-csv"
            variant="secondary"
            onClick={handleExportCsv}
            disabled={diffRows.length === 0}
          >
            {tCommon("exportCsv")}
          </Button>
        </CardHeader>
        <CardContent>
          <DataTable<PositionDiffEntry>
            ref={tableRef}
            rowData={diffRows}
            columnDefs={diffColumns}
            height={360}
          />
        </CardContent>
      </Card>

      <Card
        data-testid="position-diff-unmatched-card"
        className={cn(unmatchedRows.length === 0 && "opacity-70")}
      >
        <CardHeader>
          <CardTitle>{t("unmatchedTitle")}</CardTitle>
          <CardDescription>{t("unmatchedDescription")}</CardDescription>
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
                  <strong>
                    <SymbolLink symbol={row.symbol} />
                  </strong>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {t("unmatchedLabel", { weight: (row.target_weight * 100).toFixed(2) })}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p
              data-testid="position-diff-unmatched-empty"
              className="text-sm text-muted-foreground"
            >
              {t("unmatchedEmpty")}
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
