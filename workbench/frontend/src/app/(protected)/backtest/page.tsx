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
import { BacktestRunError, BacktestTimeoutError, runBacktest } from "@/lib/backtest-poll";
import { cn } from "@/lib/utils";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type BacktestRunResponse = components["schemas"]["BacktestRunResponse"];
type BacktestDataRange = components["schemas"]["BacktestDataRangeResponse"];
type StrategyListResponse = components["schemas"]["StrategyListResponse"];
type StrategySummary = components["schemas"]["StrategySummary"];
type BacktestTrade = components["schemas"]["BacktestTrade"];

const STRATEGIES_URL = "/api/strategies";
const DATA_RANGE_URL = "/api/backtests/data-range";

const ERROR_KINDS = [
  "insufficient_history",
  "no_signal_dates",
  "data_unavailable",
  "unknown",
] as const;
type ErrorKind = (typeof ERROR_KINDS)[number];

function normaliseErrorKind(kind: string | null): ErrorKind {
  return (ERROR_KINDS as readonly string[]).includes(kind ?? "") ? (kind as ErrorKind) : "unknown";
}

/** ISO date minus one calendar year (UTC, rolls Feb-29 → Mar-1). */
function isoMinusOneYear(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC((y ?? 0) - 1, (m ?? 1) - 1, d ?? 1)).toISOString().slice(0, 10);
}

/** Default window that always lands in the usable band: end = data_end,
 * start = max(min_usable_start, data_end − 1y). ISO strings compare
 * chronologically, so `max` is a lexical comparison. */
function defaultWindow(range: BacktestDataRange): { start: string; end: string } {
  const end = range.data_end ?? "";
  const min = range.min_usable_start ?? "";
  const oneYearBack = end ? isoMinusOneYear(end) : min;
  return { start: oneYearBack > min ? oneYearBack : min, end };
}

type RangeStatus = "loading" | "empty" | "ready";

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
  const tErrorKind = useTranslations("backtest.errorKind");
  const tEquity = useTranslations("backtest.equity");
  const tDrawdown = useTranslations("backtest.drawdown");
  const tTrades = useTranslations("backtest.trades");
  const tCommon = useTranslations("common");

  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [snapshotId, setSnapshotId] = useState<string>("snap-fixture");
  // B047-OPS2 F002 (L1): no hardcoded default — the window is derived from the
  // real data-coverage range once it loads (so the default Run always lands in
  // the usable band). Empty until data-range resolves.
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [dataRange, setDataRange] = useState<BacktestDataRange | null>(null);
  const [rangeStatus, setRangeStatus] = useState<RangeStatus>("loading");
  const [comparisonOn, setComparisonOn] = useState<boolean>(true);
  const [result, setResult] = useState<BacktestRunResponse | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<string | null>(null);
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

  // B047-OPS2 F002 (L1/L2): load the real data-coverage window, then seed the
  // default range inside the usable band + clamp the picker. Empty / unreachable
  // → empty state (Run disabled, "run a data refresh" prompt).
  useEffect(() => {
    let cancelled = false;
    fetch(DATA_RANGE_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as BacktestDataRange;
      })
      .then((range) => {
        if (cancelled) return;
        setDataRange(range);
        if (range.data_start && range.data_end && range.min_usable_start) {
          const window = defaultWindow(range);
          setStartDate(window.start);
          setEndDate(window.end);
          setRangeStatus("ready");
        } else {
          setRangeStatus("empty");
        }
      })
      .catch(() => {
        if (!cancelled) setRangeStatus("empty");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const minUsableStart = dataRange?.min_usable_start ?? null;
  const dataEnd = dataRange?.data_end ?? null;
  // The selected window is valid when it loaded, both bounds are set, and it sits
  // within the coverage band (start ≥ min_usable_start, end ≤ data_end, ordered).
  const rangeValid =
    rangeStatus === "ready" &&
    startDate !== "" &&
    endDate !== "" &&
    (minUsableStart === null || startDate >= minUsableStart) &&
    (dataEnd === null || endDate <= dataEnd) &&
    startDate <= endDate;

  const handleRun = async () => {
    if (!strategyId || !rangeValid) return;
    setRunning(true);
    setError(null);
    setErrorKind(null);
    setResult(null);
    try {
      // B047 async: enqueue → poll until the worker finishes (or errors / times
      // out). The request path returns 202 immediately; the result lands later.
      const data = await runBacktest({
        strategy_id: strategyId,
        snapshot_id: snapshotId,
        start_date: startDate,
        end_date: endDate,
        parameters: {},
      });
      setResult(data);
      setSharedRange(null);
    } catch (reason: unknown) {
      // B047-OPS2 F002 (L3): a structured worker failure → bilingual friendly
      // message keyed by error_kind (never the raw English exception). Timeout
      // keeps its own copy; anything else falls back to the raw message.
      if (reason instanceof BacktestRunError) {
        setErrorKind(normaliseErrorKind(reason.errorKind));
      } else if (reason instanceof BacktestTimeoutError) {
        setError(t("timeout"));
      } else {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      setRunning(false);
    }
  };

  const equitySeries: EquityCurveSeries[] = useMemo(() => {
    if (!result) return [];
    const equity = result.equity ?? [];
    const masterData = equity.map((p) => ({ time: p.date, value: p.nav }));
    const series: EquityCurveSeries[] = [
      { id: "master", name: "Master", color: "#00c853", data: masterData },
    ];
    if (comparisonOn) {
      series.push({
        id: "spy",
        name: "SPY",
        color: "#888888",
        data: equity
          .filter(
            (p): p is typeof p & { benchmark_spy: number } => typeof p.benchmark_spy === "number",
          )
          .map((p) => ({ time: p.date, value: p.benchmark_spy })),
      });
      series.push({
        id: "60-40",
        name: "60/40",
        color: "#9ca3af",
        data: equity
          .filter(
            (p): p is typeof p & { benchmark_6040: number } => typeof p.benchmark_6040 === "number",
          )
          .map((p) => ({ time: p.date, value: p.benchmark_6040 })),
      });
    }
    return series;
  }, [result, comparisonOn]);

  const drawdownData = useMemo(() => {
    const equity = result?.equity ?? [];
    if (equity.length === 0) return [];
    let peak = equity[0]!.nav;
    return equity.map((p) => {
      peak = Math.max(peak, p.nav);
      const dd = peak === 0 ? 0 : (p.nav - peak) / peak;
      return { time: p.date, value: dd };
    });
  }, [result]);

  // error_kind (structured) → friendly bilingual copy; otherwise the raw error
  // string (timeout / network). The raw English worker exception is never shown.
  const displayError = errorKind
    ? tErrorKind(normaliseErrorKind(errorKind), { minUsableStart: minUsableStart ?? "" })
    : error;
  const stateLabel = displayError
    ? tCommon("errorPrefix", { error: displayError })
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
                      min={minUsableStart ?? undefined}
                      max={dataEnd ?? undefined}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                  <label className="block space-y-1 text-xs text-muted-foreground">
                    <span>{tSelector("endDate")}</span>
                    <Input
                      type="date"
                      data-testid="backtest-end-date"
                      value={endDate}
                      min={minUsableStart ?? undefined}
                      max={dataEnd ?? undefined}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                  </label>
                </div>
                {rangeStatus === "loading" && (
                  <p data-testid="backtest-range-loading" className="text-xs text-muted-foreground">
                    {tSelector("rangeLoading")}
                  </p>
                )}
                {rangeStatus === "empty" && (
                  <p data-testid="backtest-empty-data" className="text-xs text-amber-500">
                    {t("emptyData")}
                  </p>
                )}
                {rangeStatus === "ready" && dataRange?.data_start && dataEnd && (
                  <p data-testid="backtest-data-coverage" className="text-xs text-muted-foreground">
                    {tSelector("dataCoverage", { start: dataRange.data_start, end: dataEnd })}
                  </p>
                )}
                {rangeStatus === "ready" && !rangeValid && (
                  <p data-testid="backtest-invalid-range" className="text-xs text-amber-500">
                    {t("invalidRange", {
                      minUsableStart: minUsableStart ?? "",
                      dataEnd: dataEnd ?? "",
                    })}
                  </p>
                )}
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
                  disabled={running || !strategyId || !rangeValid}
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
                      {tTrades("rows", { count: result?.trades?.length ?? 0 })}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="backtest-export-trades"
                    onClick={() => tradesRef.current?.exportCsv("backtest-trades.csv")}
                    disabled={!result || (result.trades?.length ?? 0) === 0}
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
