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

export interface AllocationSlice {
  name: string;
  value: number;
}

export interface AllocationPieProps {
  data: AllocationSlice[];
  /** Optional palette; ECharts theme default is used when omitted. */
  colors?: string[];
  height?: number;
  className?: string;
}

/**
 * ECharts donut/pie for target portfolio weights — F010 Recommendations
 * uses this to render the target allocation card.
 */
const AllocationPie = forwardRef<ChartHandle, AllocationPieProps>(function AllocationPie(
  { data, colors, height = 240, className },
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

  const option = useMemo<EChartsOption>(
    () => ({
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      legend: {
        bottom: 0,
        textStyle: { color: "rgba(255,255,255,0.65)" },
      },
      ...(colors ? { color: colors } : {}),
      series: [
        {
          name: "Allocation",
          type: "pie",
          radius: ["45%", "70%"],
          center: ["50%", "45%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#0a0a0a", borderWidth: 2 },
          label: { show: false },
          data,
        },
      ],
    }),
    [data, colors],
  );

  return (
    <div data-testid="allocation-pie" className={cn("w-full", className)} style={{ height }}>
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

export default AllocationPie;
