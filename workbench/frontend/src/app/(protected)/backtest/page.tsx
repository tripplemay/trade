"use client";

import { useTranslations } from "next-intl";
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
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MetricsDisplay, type MetricStat } from "@/components/metrics/MetricsDisplay";
import { cn } from "@/lib/utils";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type BacktestRunResponse = components["schemas"]["BacktestRunResponse"];
type StrategyListResponse = components["schemas"]["StrategyListResponse"];
type StrategySummary = components["schemas"]["StrategySummary"];
type BacktestTrade = components["schemas"]["BacktestTrade"];

const STRATEGIES_URL = "/api/strategies";
const RUN_URL = "/api/backtests/run";

function buildTradeColumns(
  t: ReturnType<typeof useTranslations<"backtest.trades">>,
): ColDef<BacktestTrade>[] {
  return [
    dateColumn<BacktestTrade>({ field: "date", headerName: t("columnDate"), width: 130 }),
    { field: "symbol", headerName: t("columnSymbol"), width: 110 },
    { field: "side", headerName: t("columnSide"), width: 90 },
    percentColumn<BacktestTrade>({ field: "quantity", headerName: t("columnQty"), digits: 2 }),
    currencyColumn<BacktestTrade>({ field: "price", headerName: t("columnPrice") }),
    currencyColumn<BacktestTrade>({ field: "notional", headerName: t("columnNotional") }),
  ];
}

function MetricsCard({ metrics }: { metrics: BacktestRunResponse["metrics"] | null }) {
  const t = useTranslations("backtest.metrics");
  // Calmar is derived (BacktestMetrics has no Calmar field): CAGR / |MDD|.
  const calmar =
    metrics && metrics.max_drawdown !== 0 ? metrics.cagr / Math.abs(metrics.max_drawdown) : null;
  const stats: MetricStat[] = [
    { key: "cagr", value: metrics?.cagr ?? null, format: "percent" },
    { key: "sharpe", value: metrics?.sharpe ?? null, format: "ratio" },
    { key: "sortino", value: metrics?.sortino ?? null, format: "ratio" },
    { key: "calmar", value: calmar, format: "ratio" },
    { key: "maxDrawdown", value: metrics?.max_drawdown ?? null, format: "percent" },
    { key: "turnover", value: metrics?.turnover ?? null, format: "ratio" },
  ];
  return (
    <Card data-testid="backtest-metrics">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <MetricsDisplay stats={stats} />
      </CardContent>
    </Card>
  );
}

export default function BacktestPage() {
  const t = useTranslations("backtest");
  const tSelector = useTranslations("backtest.selector");
  const tEquity = useTranslations("backtest.equity");
  const tDrawdown = useTranslations("backtest.drawdown");
  const tTrades = useTranslations("backtest.trades");
  const tCommon = useTranslations("common");

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

  const tradeColumns = useMemo(() => buildTradeColumns(tTrades), [tTrades]);

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
          .filter(
            (p): p is typeof p & { benchmark_spy: number } => typeof p.benchmark_spy === "number",
          )
          .map((p) => ({ time: p.date, value: p.benchmark_spy })),
      });
      series.push({
        id: "60-40",
        name: "60/40",
        color: "#9ca3af",
        data: result.equity
          .filter(
            (p): p is typeof p & { benchmark_6040: number } => typeof p.benchmark_6040 === "number",
          )
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

  const stateLabel = error
    ? tCommon("errorPrefix", { error })
    : running
      ? t("stateRunning")
      : result
        ? t("stateRunWithId", { id: result.run_id })
        : t("stateIdle");

  return (
    <section
      data-testid="page-backtest"
      className={cn("flex h-[calc(100vh-12rem)] flex-col gap-3")}
    >
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <span data-testid="backtest-state" className="text-xs text-muted-foreground">
          {stateLabel}
        </span>
      </header>

      <div
        data-testid="backtest-resizable-group"
        className="flex-1 overflow-hidden rounded-lg border border-border"
      >
        <ResizablePanelGroup orientation="horizontal" className="h-full w-full">
          <ResizablePanel defaultSize={28} minSize={20} className="overflow-y-auto">
            <Card className="m-0 rounded-none border-0 shadow-none">
              <CardHeader>
                <CardTitle>{tSelector("title")}</CardTitle>
                <CardDescription>{tSelector("description")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="block space-y-1 text-xs text-muted-foreground">
                  <span>{tSelector("strategyLabel")}</span>
                  <Select value={strategyId} onValueChange={setStrategyId}>
                    <SelectTrigger data-testid="backtest-strategy-select">
                      <SelectValue placeholder={tSelector("strategyPlaceholder")} />
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
                  <span>{tSelector("snapshotLabel")}</span>
                  <Input
                    data-testid="backtest-snapshot-input"
                    value={snapshotId}
                    onChange={(e) => setSnapshotId(e.target.value)}
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block space-y-1 text-xs text-muted-foreground">
                    <span>{tSelector("startDate")}</span>
                    <Input
                      type="date"
                      data-testid="backtest-start-date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                  <label className="block space-y-1 text-xs text-muted-foreground">
                    <span>{tSelector("endDate")}</span>
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
                  <span>{tSelector("compare")}</span>
                </label>
                <Button
                  data-testid="backtest-run"
                  onClick={handleRun}
                  disabled={running || !strategyId}
                  className="w-full"
                >
                  {running ? tSelector("running") : tSelector("run")}
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
                  <CardTitle>{tEquity("title")}</CardTitle>
                  <CardDescription>{tEquity("description")}</CardDescription>
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
                  <CardTitle>{tDrawdown("title")}</CardTitle>
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
                    <CardTitle>{tTrades("title")}</CardTitle>
                    <CardDescription>
                      {tTrades("rows", { count: result?.trades.length ?? 0 })}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="backtest-export-trades"
                    onClick={() => tradesRef.current?.exportCsv("backtest-trades.csv")}
                    disabled={!result || result.trades.length === 0}
                  >
                    {tTrades("export")}
                  </Button>
                </CardHeader>
                <CardContent>
                  <DataTable<BacktestTrade>
                    ref={tradesRef}
                    rowData={result?.trades ?? []}
                    columnDefs={tradeColumns}
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
