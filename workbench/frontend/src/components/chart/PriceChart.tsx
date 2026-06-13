"use client";

import {
  CandlestickSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type PriceBarPoint = components["schemas"]["PriceBarPoint"];

export interface PriceChartProps {
  /** EOD OHLCV bars, oldest first (from GET /api/symbols/{symbol}/price). */
  bars: PriceBarPoint[];
  /** Candlestick (OHLC) or line (close) — B059 F002 spec offers both. */
  mode: "candle" | "line";
  height?: number;
  className?: string;
}

/**
 * B059 F002 — research-only EOD price chart for the symbol-lookup page.
 *
 * Mirrors the existing lightweight-charts components (DrawdownChart /
 * EquityCurveChart): a single chart created in a useEffect that fully
 * recreates on data/mode change (data only changes on a new symbol, so
 * recreation is cheap and avoids series-swap bugs). Time is the EOD
 * ``obs_date`` string ("yyyy-mm-dd"); the series is EOD close — never live.
 */
export default function PriceChart({
  bars,
  mode,
  height = 360,
  className,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "rgba(255,255,255,0.65)",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: false },
      height,
      autoSize: true,
    });
    chartRef.current = chart;

    if (mode === "candle") {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: "#00c853",
        downColor: "#ff3b30",
        wickUpColor: "#00c853",
        wickDownColor: "#ff3b30",
        borderVisible: false,
      });
      series.setData(
        bars.map((bar) => ({
          time: bar.obs_date as Time,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })),
      );
    } else {
      const series = chart.addSeries(LineSeries, {
        color: "#3b82f6",
        lineWidth: 2,
      });
      series.setData(
        bars.map((bar) => ({ time: bar.obs_date as Time, value: bar.close })),
      );
    }
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [bars, mode, height]);

  return (
    <div
      ref={containerRef}
      data-testid="price-chart"
      className={cn("w-full", className)}
      style={{ height }}
    />
  );
}
