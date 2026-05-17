"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  DrawdownChart,
  EquityCurveChart,
  type EquityCurveRange,
  type EquityCurveSeries,
} from "@/components/chart";
import {
  DataTable,
  type DataTableHandle,
  currencyColumn,
  dateColumn,
  percentColumn,
} from "@/components/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type BacktestRunResponse = components["schemas"]["BacktestRunResponse"];
type StrategyListResponse = components["schemas"]["StrategyListResponse"];
type StrategySummary = components["schemas"]["StrategySummary"];
type BacktestTrade = components["schemas"]["BacktestTrade"];

const STRATEGIES_URL = "/api/strategies";
const RUN_URL = "/api/backtests/run";

const TRADE_COLUMNS: ColDef<BacktestTrade>[] = [
  dateColumn<BacktestTrade>({ field: "date", headerName: "Date", width: 130 }),
  { field: "symbol", headerName: "Symbol", width: 110 },
  { field: "side", headerName: "Side", width: 90 },
  percentColumn<BacktestTrade>({ field: "quantity", headerName: "Qty", digits: 2 }),
  currencyColumn<BacktestTrade>({ field: "price", headerName: "Price" }),
  currencyColumn<BacktestTrade>({ field: "notional", headerName: "Notional" }),
];

function MetricsCard({ metrics }: { metrics: BacktestRunResponse["metrics"] | null }) {
  const Stat = ({ label, value }: { label: string; value: string }) => (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="numeric text-lg text-foreground">{value}</div>
    </div>
  );
  return (
    <Card data-testid="backtest-metrics">
      <CardHeader>
        <CardTitle>Headline metrics</CardTitle>
        <CardDescription>Synthetic engine in F008 — real numbers land in B023.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-3 gap-4 sm:grid-cols-6">
        <Stat label="CAGR" value={metrics ? `${(metrics.cagr * 100).toFixed(2)}%` : "—"} />
        <Stat label="Sharpe" value={metrics ? metrics.sharpe.toFixed(2) : "—"} />
        <Stat label="Sortino" value={metrics?.sortino ? metrics.sortino.toFixed(2) : "—"} />
        <Stat label="Max DD" value={metrics ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "—"} />
        <Stat label="Turnover" value={metrics ? metrics.turnover.toFixed(2) : "—"} />
        <Stat
          label="Win rate"
          value={metrics?.win_rate ? `${(metrics.win_rate * 100).toFixed(2)}%` : "—"}
        />
      </CardContent>
    </Card>
  );
}

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [snapshotId, setSnapshotId] = useState<string>("snap-fixture");
  const [startDate, setStartDate] = useState<string>("2024-01-01");
  const [endDate, setEndDate] = useState<string>("2024-06-30");
  const [comparisonOn, setComparisonOn] = useState<boolean>(true);
  const [result, setResult] = useState<BacktestRunResponse | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sharedRange, setSharedRange] = useState<EquityCurveRange | null>(null);
  const tradesRef = useRef<DataTableHandle>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(STRATEGIES_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as StrategyListResponse;
        if (!cancelled) {
          setStrategies(data.strategies);
          if (data.strategies[0]) setStrategyId(data.strategies[0].id);
        }
      })
      .catch(() => {
        /* ignore — Run button stays disabled until a strategy is picked */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRun = async () => {
    if (!strategyId) return;
    setRunning(true);
    setError(null);
    try {
      const response = await fetch(RUN_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          strategy_id: strategyId,
          snapshot_id: snapshotId,
          start_date: startDate,
          end_date: endDate,
          parameters: {},
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as BacktestRunResponse;
      setResult(data);
      setSharedRange(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(false);
    }
  };

  const equitySeries: EquityCurveSeries[] = useMemo(() => {
    if (!result) return [];
    const masterData = result.equity.map((p) => ({ time: p.date, value: p.nav }));
    const series: EquityCurveSeries[] = [
      { id: "master", name: "Master", color: "#00c853", data: masterData },
    ];
    if (comparisonOn) {
      series.push({
        id: "spy",
        name: "SPY",
        color: "#888888",
        data: result.equity
          .filter((p): p is typeof p & { benchmark_spy: number } => typeof p.benchmark_spy === "number")
          .map((p) => ({ time: p.date, value: p.benchmark_spy })),
      });
      series.push({
        id: "60-40",
        name: "60/40",
        color: "#9ca3af",
        data: result.equity
          .filter((p): p is typeof p & { benchmark_6040: number } => typeof p.benchmark_6040 === "number")
          .map((p) => ({ time: p.date, value: p.benchmark_6040 })),
      });
    }
    return series;
  }, [result, comparisonOn]);

  const drawdownData = useMemo(() => {
    if (!result || result.equity.length === 0) return [];
    let peak = result.equity[0]!.nav;
    return result.equity.map((p) => {
      peak = Math.max(peak, p.nav);
      const dd = peak === 0 ? 0 : (p.nav - peak) / peak;
      return { time: p.date, value: dd };
    });
  }, [result]);

  return (
    <section
      data-testid="page-backtest"
      className={cn("flex h-[calc(100vh-12rem)] flex-col gap-3")}
    >
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Backtest viewer</h1>
        <span data-testid="backtest-state" className="text-xs text-muted-foreground">
          {error ? `error: ${error}` : running ? "running…" : result ? `run ${result.run_id}` : "idle"}
        </span>
      </header>

      <div
        data-testid="backtest-resizable-group"
        className="flex-1 overflow-hidden rounded-lg border border-border"
      >
      <ResizablePanelGroup
        orientation="horizontal"
        className="h-full w-full"
      >
        <ResizablePanel defaultSize={28} minSize={20} className="overflow-y-auto">
          <Card className="m-0 rounded-none border-0 shadow-none">
            <CardHeader>
              <CardTitle>Selector</CardTitle>
              <CardDescription>Pick a strategy + snapshot + window, then Run.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="block space-y-1 text-xs text-muted-foreground">
                <span>Strategy</span>
                <Select value={strategyId} onValueChange={setStrategyId}>
                  <SelectTrigger data-testid="backtest-strategy-select">
                    <SelectValue placeholder="Pick a strategy" />
                  </SelectTrigger>
                  <SelectContent>
                    {strategies.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
              <label className="block space-y-1 text-xs text-muted-foreground">
                <span>Snapshot id</span>
                <Input
                  data-testid="backtest-snapshot-input"
                  value={snapshotId}
                  onChange={(e) => setSnapshotId(e.target.value)}
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block space-y-1 text-xs text-muted-foreground">
                  <span>Start date</span>
                  <Input
                    type="date"
                    data-testid="backtest-start-date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </label>
                <label className="block space-y-1 text-xs text-muted-foreground">
                  <span>End date</span>
                  <Input
                    type="date"
                    data-testid="backtest-end-date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </label>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  data-testid="backtest-comparison-toggle"
                  checked={comparisonOn}
                  onChange={(e) => setComparisonOn(e.target.checked)}
                />
                <span>Compare to SPY + 60/40</span>
              </label>
              <Button
                data-testid="backtest-run"
                onClick={handleRun}
                disabled={running || !strategyId}
                className="w-full"
              >
                {running ? "Running…" : "Run backtest"}
              </Button>
            </CardContent>
          </Card>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel defaultSize={72} minSize={40} className="overflow-y-auto">
          <div className="space-y-4 p-4">
            <MetricsCard metrics={result?.metrics ?? null} />
            <Card>
              <CardHeader>
                <CardTitle>Equity curve</CardTitle>
                <CardDescription>
                  Master vs benchmarks; pan/zoom syncs the drawdown chart below.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EquityCurveChart
                  series={equitySeries}
                  visibleRange={sharedRange}
                  onVisibleRangeChange={setSharedRange}
                  height={260}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Drawdown</CardTitle>
              </CardHeader>
              <CardContent>
                <DrawdownChart
                  data={drawdownData}
                  visibleRange={sharedRange}
                  onVisibleRangeChange={setSharedRange}
                  height={160}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Trades</CardTitle>
                  <CardDescription>{result?.trades.length ?? 0} rows</CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="backtest-export-trades"
                  onClick={() => tradesRef.current?.exportCsv("backtest-trades.csv")}
                  disabled={!result || result.trades.length === 0}
                >
                  Export trades CSV
                </Button>
              </CardHeader>
              <CardContent>
                <DataTable<BacktestTrade>
                  ref={tradesRef}
                  rowData={result?.trades ?? []}
                  columnDefs={TRADE_COLUMNS}
                  height={320}
                />
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
      </div>
    </section>
  );
}
