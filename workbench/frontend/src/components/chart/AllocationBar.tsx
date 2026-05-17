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

export interface AllocationBarItem {
  name: string;
  value: number;
}

export type AllocationBarOrientation = "horizontal" | "vertical";

export interface AllocationBarProps {
  data: AllocationBarItem[];
  /** Horizontal bars read like allocation deltas; defaults to that orientation. */
  orientation?: AllocationBarOrientation;
  color?: string;
  height?: number;
  className?: string;
}

/**
 * ECharts bar chart for target weights vs current — F010 Recommendations
 * pairs this with AllocationPie to surface diff direction at a glance.
 */
const AllocationBar = forwardRef<ChartHandle, AllocationBarProps>(function AllocationBar(
  { data, orientation = "horizontal", color = "#00c853", height = 240, className },
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
    const labels = data.map((d) => d.name);
    const values = data.map((d) => d.value);
    const categoryAxis = {
      type: "category" as const,
      data: labels,
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.2)" } },
      axisLabel: { color: "rgba(255,255,255,0.65)" },
    };
    const valueAxis = {
      type: "value" as const,
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.2)" } },
      axisLabel: { color: "rgba(255,255,255,0.65)" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    };
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 60, right: 24, top: 16, bottom: 32 },
      xAxis: orientation === "horizontal" ? valueAxis : categoryAxis,
      yAxis: orientation === "horizontal" ? categoryAxis : valueAxis,
      series: [
        {
          name: "Allocation",
          type: "bar",
          data: values,
          itemStyle: { color },
          barMaxWidth: 24,
        },
      ],
    };
  }, [data, orientation, color]);

  return (
    <div data-testid="allocation-bar" className={cn("w-full", className)} style={{ height }}>
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

export default AllocationBar;
