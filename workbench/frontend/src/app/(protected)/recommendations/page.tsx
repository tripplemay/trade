"use client";

import { useEffect, useMemo, useState } from "react";

import {
  AllocationBar,
  AllocationPie,
  type AllocationBarItem,
  type AllocationSlice,
} from "@/components/chart";
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

const POSITION_COLUMNS: ColDef<TargetPosition>[] = [
  { field: "symbol", headerName: "Symbol", width: 110 },
  weightColumn<TargetPosition>({ field: "target_weight", headerName: "Target", digits: 2 }),
  weightColumn<TargetPosition>({ field: "current_weight", headerName: "Current", digits: 2 }),
  percentColumn<TargetPosition>({ field: "diff", headerName: "Diff", digits: 2 }),
  { field: "rationale", headerName: "Rationale", flex: 2 },
];

const GATE_STYLES: Record<string, string> = {
  pass: "border-green-700/50 bg-green-950/30 text-green-200",
  warn: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  fail: "border-destructive/60 bg-destructive/10 text-destructive-foreground",
};

export default function RecommendationsPage() {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportTicketResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

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

  return (
    <section data-testid="page-recommendations" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Recommendations</h1>
        <span data-testid="recommendations-state" className="text-xs text-muted-foreground">
          {error
            ? `unreachable: ${error}`
            : data
              ? `as of ${data.as_of_date} · account ${accountPresent ? "present" : "missing"}`
              : "loading…"}
        </span>
      </header>

      <Card data-testid="recommendations-disclaimer-card" className="border-amber-700/40 bg-amber-950/20">
        <CardContent className="py-3 text-xs text-amber-100">
          <strong>Research-only.</strong> This page produces a manual review checklist; the workbench
          never places orders. Export the markdown ticket and execute manually after independent review.
        </CardContent>
      </Card>

      {data && !accountPresent ? (
        <Card data-testid="recommendations-empty">
          <CardHeader>
            <CardTitle>No account on file</CardTitle>
            <CardDescription>
              Drop a <code>accounts/me.json</code> with cash + equity to surface target positions.
              Until then, gate checks render but positions stay empty.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Target sleeve weights</CardTitle>
            <CardDescription>F011 wires real master-portfolio weights.</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationPie data={pieSlices} height={240} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Rebalance deltas</CardTitle>
            <CardDescription>Target − current per sleeve (sign = buy/sell direction).</CardDescription>
          </CardHeader>
          <CardContent>
            <AllocationBar data={barItems} height={240} />
          </CardContent>
        </Card>
      </div>

      <Card data-testid="recommendations-positions-card">
        <CardHeader>
          <CardTitle>Target positions</CardTitle>
          <CardDescription>
            {accountPresent ? `${data?.target_positions.length ?? 0} sleeves` : "Empty until account lands"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<TargetPosition>
            rowData={data?.target_positions ?? []}
            columnDefs={POSITION_COLUMNS}
            height={280}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="recommendations-gate-panel">
          <CardHeader>
            <CardTitle>Gate checks</CardTitle>
            <CardDescription>Pre-trade safety filters. All must pass before manual execution.</CardDescription>
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
              <p className="text-sm text-muted-foreground">No gate checks reported.</p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="recommendations-wash-flags">
          <CardHeader>
            <CardTitle>Wash-sale flags</CardTitle>
            <CardDescription>30-day same-symbol buy heuristic from the trade journal.</CardDescription>
          </CardHeader>
          <CardContent>
            {data && (data.wash_sale_flags ?? []).length > 0 ? (
              <ul className="space-y-1 text-sm">
                {(data.wash_sale_flags ?? []).map((flag) => (
                  <li key={flag.symbol}>
                    <strong>{flag.symbol}</strong> — last buy {flag.last_buy_date} ({flag.days_since}d)
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="recommendations-wash-empty" className="text-sm text-muted-foreground">
                None flagged.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="recommendations-export-card">
        <CardHeader>
          <CardTitle>Export markdown ticket</CardTitle>
          <CardDescription>
            Writes a checklist to <code>docs/runs/&lt;date&gt;/order-ticket-&lt;date&gt;.md</code>.
            The exported file carries the same research-only disclaimer pinned in
            <code>tests/unit/test_recommendations.py</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            data-testid="recommendations-export"
            onClick={handleExport}
            disabled={!data || exporting}
          >
            {exporting ? "Exporting…" : "Export markdown ticket"}
          </Button>
          {exportResult ? (
            <p data-testid="recommendations-export-result" className="text-xs text-muted-foreground">
              Wrote <code>{exportResult.path}</code> — review manually before any execution.
            </p>
          ) : null}
          {exportError ? (
            <p data-testid="recommendations-export-error" className="text-xs text-destructive">
              Export failed: {exportError}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
