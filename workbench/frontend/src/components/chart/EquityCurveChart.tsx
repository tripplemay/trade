"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AreaSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
  createChart,
} from "lightweight-charts";

import {
  type ChartHandle,
  canvasToPngBlob,
} from "@/components/chart/util";
import { cn } from "@/lib/utils";

export interface EquityCurvePoint {
  time: Time;
  value: number;
}

export interface EquityCurveSeries {
  id: string;
  name: string;
  /** Hex / rgb / CSS-var-resolved color for the line + area fill. */
  color: string;
  data: EquityCurvePoint[];
}

export interface EquityCurveRange {
  from: Time;
  to: Time;
}

export interface EquityCurveChartProps {
  series: EquityCurveSeries[];
  /** Initial chart height in pixels. */
  height?: number;
  /** Fires when the user pans/zooms the chart (lightweight-charts v5 idiom for "brush"). */
  onVisibleRangeChange?: (range: EquityCurveRange | null) => void;
  /** Controlled visible time range — keeps multi-chart layouts in sync. */
  visibleRange?: EquityCurveRange | null;
  className?: string;
}

/**
 * lightweight-charts area chart with multi-series overlay, a legend
 * that toggles series visibility, native crosshair, and a brush-style
 * range callback (the v5 API exposes this via subscribeVisibleTimeRangeChange).
 *
 * F008 (Backtest viewer) consumes both this and DrawdownChart and wires
 * their visible ranges together via `visibleRange` / `onVisibleRangeChange`
 * so the time axes stay locked. F004 ships the /dev/charts route that
 * demos that wiring with seeded sample data.
 */
const EquityCurveChart = forwardRef<ChartHandle, EquityCurveChartProps>(function EquityCurveChart(
  { series, height = 320, onVisibleRangeChange, visibleRange, className },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesMapRef = useRef<Map<string, ISeriesApi<"Area">>>(new Map());
  // Toggles a one-shot suppression when we set the range programmatically
  // from props — otherwise the subscribeVisibleTimeRangeChange handler
  // would echo back and the parent loop would bounce.
  const suppressNextRangeEvent = useRef(false);
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());

  useImperativeHandle(
    ref,
    (): ChartHandle => ({
      async exportPng() {
        const chart = chartRef.current;
        if (!chart) return null;
        const canvas = chart.takeScreenshot();
        return canvasToPngBlob(canvas);
      },
    }),
    [],
  );

  // Create the chart once on mount; tear it down on unmount.
  useEffect(() => {
    if (!containerRef.current) return undefined;
    // Capture the Map up front so the cleanup function does not reach
    // through the ref (ESLint react-hooks/exhaustive-deps flags that as
    // a stale-ref risk). The Map instance is stable for the chart's
    // lifetime so the captured reference and the live ref are equal.
    const seriesMap = seriesMapRef.current;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "rgba(255,255,255,0.65)",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      height,
      autoSize: true,
    });
    chartRef.current = chart;

    const handleRange = (range: { from: Time; to: Time } | null) => {
      if (suppressNextRangeEvent.current) {
        suppressNextRangeEvent.current = false;
        return;
      }
      if (!onVisibleRangeChange) return;
      onVisibleRangeChange(range ? { from: range.from, to: range.to } : null);
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(handleRange);

    return () => {
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handleRange);
      chart.remove();
      chartRef.current = null;
      seriesMap.clear();
    };
    // We intentionally exclude height from this effect — resizing happens
    // via autoSize so we don't want to teardown/recreate on a height change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Diff series in / out and push data on every change.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const seen = new Set<string>();
    for (const s of series) {
      seen.add(s.id);
      let api = seriesMapRef.current.get(s.id);
      if (!api) {
        api = chart.addSeries(AreaSeries, {
          lineColor: s.color,
          topColor: s.color,
          bottomColor: "transparent",
          lineWidth: 2,
          priceLineVisible: false,
          title: s.name,
        });
        seriesMapRef.current.set(s.id, api);
      } else {
        api.applyOptions({ lineColor: s.color, topColor: s.color, title: s.name });
      }
      api.setData(s.data);
      api.applyOptions({ visible: !hiddenSeries.has(s.id) });
    }
    // Remove series that disappeared from the props array.
    for (const [id, api] of seriesMapRef.current.entries()) {
      if (!seen.has(id)) {
        chart.removeSeries(api);
        seriesMapRef.current.delete(id);
      }
    }
  }, [series, hiddenSeries]);

  // Apply controlled visible range (skip echo on the next event).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !visibleRange) return;
    suppressNextRangeEvent.current = true;
    chart.timeScale().setVisibleRange({ from: visibleRange.from, to: visibleRange.to });
  }, [visibleRange]);

  const legendItems = useMemo(
    () =>
      series.map((s) => ({
        id: s.id,
        name: s.name,
        color: s.color,
        active: !hiddenSeries.has(s.id),
      })),
    [series, hiddenSeries],
  );

  const toggleSeries = useCallback((id: string) => {
    setHiddenSeries((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  return (
    <div
      data-testid="equity-curve-chart"
      className={cn("flex flex-col gap-2", className)}
    >
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        {legendItems.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`equity-curve-legend-${item.id}`}
            onClick={() => toggleSeries(item.id)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded border border-border/60 px-2 py-0.5 transition-opacity",
              item.active ? "opacity-100" : "opacity-40",
            )}
          >
            <span
              aria-hidden
              style={{ backgroundColor: item.color }}
              className="h-2 w-2 rounded-sm"
            />
            <span>{item.name}</span>
          </button>
        ))}
      </div>
      <div
        ref={containerRef}
        data-testid="equity-curve-chart-canvas"
        className="w-full"
        style={{ height }}
      />
    </div>
  );
});

export default EquityCurveChart;
