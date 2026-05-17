/**
 * Re-export barrel for the B022 F004 chart wrappers. Pages and feature
 * modules should import from this entry point instead of the individual
 * files so a future refactor can swap an internal layout without touching
 * call sites.
 */
export { default as EquityCurveChart } from "./EquityCurveChart";
export type {
  EquityCurveChartProps,
  EquityCurvePoint,
  EquityCurveRange,
  EquityCurveSeries,
} from "./EquityCurveChart";

export { default as DrawdownChart } from "./DrawdownChart";
export type { DrawdownChartProps, DrawdownPoint, DrawdownRange } from "./DrawdownChart";

export { default as SweepHeatmap } from "./SweepHeatmap";
export type { SweepHeatmapCell, SweepHeatmapProps } from "./SweepHeatmap";

export { default as AllocationPie } from "./AllocationPie";
export type { AllocationPieProps, AllocationSlice } from "./AllocationPie";

export { default as AllocationBar } from "./AllocationBar";
export type {
  AllocationBarItem,
  AllocationBarOrientation,
  AllocationBarProps,
} from "./AllocationBar";

export type { ChartHandle } from "./util";
