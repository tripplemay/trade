"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import {
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
  createChart,
} from "lightweight-charts";

import { type ChartHandle, canvasToPngBlob } from "@/components/chart/util";
import { cn } from "@/lib/utils";

export interface DrawdownPoint {
  time: Time;
  value: number;
}

export interface DrawdownRange {
  from: Time;
  to: Time;
}

export interface DrawdownChartProps {
  data: DrawdownPoint[];
  /** Color used for negative drawdown bars; defaults to the workbench --color-down hex. */
  color?: string;
  /** Initial chart height in pixels. */
  height?: number;
  /** Pairs with `visibleRange` on EquityCurveChart so the two share a time axis. */
  onVisibleRangeChange?: (range: DrawdownRange | null) => void;
  /** Controlled visible time range; usually wired to EquityCurveChart's range. */
  visibleRange?: DrawdownRange | null;
  className?: string;
}

/**
 * lightweight-charts histogram for the master drawdown series. Stacks
 * below EquityCurveChart in F008's Backtest viewer; the parent component
 * keeps the two time axes in sync via the `visibleRange` /
 * `onVisibleRangeChange` prop pair.
 */
const DrawdownChart = forwardRef<ChartHandle, DrawdownChartProps>(function DrawdownChart(
  { data, color = "#ff3b30", height = 160, onVisibleRangeChange, visibleRange, className },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const suppressNextRangeEvent = useRef(false);

  useImperativeHandle(
    ref,
    (): ChartHandle => ({
      async exportPng() {
        const chart = chartRef.current;
        if (!chart) return null;
        return canvasToPngBlob(chart.takeScreenshot());
      },
    }),
    [],
  );

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "rgba(255,255,255,0.65)",
        // B054 fix-round 1 — hide the "Charting by TradingView" attribution logo.
        attributionLogo: false,
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
    seriesRef.current = chart.addSeries(HistogramSeries, {
      color,
      priceFormat: { type: "percent", precision: 2, minMove: 0.0001 },
      priceLineVisible: false,
    });

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
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    seriesRef.current?.setData(data);
  }, [data]);

  useEffect(() => {
    seriesRef.current?.applyOptions({ color });
  }, [color]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !visibleRange) return;
    suppressNextRangeEvent.current = true;
    chart.timeScale().setVisibleRange({ from: visibleRange.from, to: visibleRange.to });
  }, [visibleRange]);

  return (
    <div
      ref={containerRef}
      data-testid="drawdown-chart"
      className={cn("w-full", className)}
      style={{ height }}
    />
  );
});

export default DrawdownChart;
