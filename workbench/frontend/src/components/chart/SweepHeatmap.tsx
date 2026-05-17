"use client";

import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import type { EChartsOption } from "echarts";
import type { EChartsInstance } from "echarts-for-react";
import ReactECharts from "echarts-for-react";

import {
  type ChartHandle,
  dataUrlToPngBlob,
} from "@/components/chart/util";
import { cn } from "@/lib/utils";

export interface SweepHeatmapCell {
  /** Category index (matches `xCategories[xIndex]`). */
  xIndex: number;
  /** Category index (matches `yCategories[yIndex]`). */
  yIndex: number;
  value: number;
}

export interface SweepHeatmapProps {
  xCategories: string[];
  yCategories: string[];
  data: SweepHeatmapCell[];
  /** [min, max] for the visualMap colour ramp; defaults to data min/max. */
  valueRange?: [number, number];
  /** Color anchors for the visualMap (low/mid/high); workbench P&L palette by default. */
  colorRange?: [string, string, string];
  height?: number;
  className?: string;
}

/**
 * ECharts heatmap used by F007 Strategies for turnover-by-period and by
 * F009 Reports for sweep matrix visualisation. Wrapping echarts-for-react
 * lets the parent stay declarative while exposing a ref-based PNG export
 * for screenshot/report embed flows.
 */
const SweepHeatmap = forwardRef<ChartHandle, SweepHeatmapProps>(function SweepHeatmap(
  {
    xCategories,
    yCategories,
    data,
    valueRange,
    colorRange = ["#ff3b30", "#525252", "#00c853"],
    height = 320,
    className,
  },
  ref,
) {
  const chartRef = useRef<EChartsInstance | null>(null);

  useImperativeHandle(
    ref,
    (): ChartHandle => ({
      async exportPng() {
        const chart = chartRef.current;
        if (!chart || typeof chart.getDataURL !== "function") return null;
        const url = chart.getDataURL({
          type: "png",
          backgroundColor: "#0a0a0a",
          pixelRatio: 2,
        });
        return dataUrlToPngBlob(url);
      },
    }),
    [],
  );

  const option = useMemo<EChartsOption>(() => {
    const values = data.map((d) => d.value);
    const min = valueRange?.[0] ?? (values.length ? Math.min(...values) : 0);
    const max = valueRange?.[1] ?? (values.length ? Math.max(...values) : 1);
    return {
      tooltip: { position: "top" },
      grid: { left: 60, right: 24, top: 16, bottom: 60 },
      xAxis: { type: "category", data: xCategories, splitArea: { show: true } },
      yAxis: { type: "category", data: yCategories, splitArea: { show: true } },
      visualMap: {
        min,
        max,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        inRange: { color: colorRange },
        textStyle: { color: "rgba(255,255,255,0.65)" },
      },
      series: [
        {
          name: "Sweep value",
          type: "heatmap",
          data: data.map((d) => [d.xIndex, d.yIndex, d.value]),
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.5)" } },
        },
      ],
    };
  }, [xCategories, yCategories, data, valueRange, colorRange]);

  return (
    <div data-testid="sweep-heatmap" className={cn("w-full", className)} style={{ height }}>
      <ReactECharts
        option={option}
        style={{ height: "100%", width: "100%" }}
        notMerge
        lazyUpdate
        onChartReady={(instance: EChartsInstance) => {
          chartRef.current = instance;
        }}
        opts={{ renderer: "canvas" }}
        theme="dark"
      />
    </div>
  );
});

export default SweepHeatmap;
