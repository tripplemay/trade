// @vitest-environment happy-dom
/**
 * B022 F004 §5 — render + PNG-export assertion for EquityCurveChart.
 *
 * lightweight-charts requires a canvas which happy-dom does not provide,
 * so the module is mocked at import time. The mock records `addSeries` /
 * `setData` calls so the test can also confirm that the multi-series
 * legend and series diffing flow actually push data through to the
 * library on render.
 */
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import EquityCurveChart from "@/components/chart/EquityCurveChart";
import type { ChartHandle } from "@/components/chart/util";

const setData = vi.fn();
const applyOptions = vi.fn();
const removeSeries = vi.fn();
const remove = vi.fn();
const subscribeRange = vi.fn();
const unsubscribeRange = vi.fn();
const setVisibleRange = vi.fn();
const toBlobMock = vi.fn(
  (cb: (b: Blob | null) => void) => cb(new Blob(["x"], { type: "image/png" })),
);
const takeScreenshot = vi.fn(() => ({ toBlob: toBlobMock }) as unknown as HTMLCanvasElement);
const addSeriesMock = vi.fn(() => ({ setData, applyOptions }));

vi.mock("lightweight-charts", () => ({
  AreaSeries: { type: "Area" },
  createChart: vi.fn(() => ({
    addSeries: addSeriesMock,
    removeSeries,
    remove,
    takeScreenshot,
    timeScale: () => ({
      subscribeVisibleTimeRangeChange: subscribeRange,
      unsubscribeVisibleTimeRangeChange: unsubscribeRange,
      setVisibleRange,
    }),
  })),
}));

const sampleSeries = [
  {
    id: "master",
    name: "Master",
    color: "#00c853",
    data: [
      { time: "2024-01-01", value: 100 },
      { time: "2024-02-01", value: 105 },
    ],
  },
  {
    id: "spy",
    name: "SPY",
    color: "#888888",
    data: [
      { time: "2024-01-01", value: 100 },
      { time: "2024-02-01", value: 102 },
    ],
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EquityCurveChart", () => {
  it("renders the wrapper, canvas host, and a legend entry per series", () => {
    const { getByTestId } = render(<EquityCurveChart series={sampleSeries} />);
    expect(getByTestId("equity-curve-chart")).toBeInTheDocument();
    expect(getByTestId("equity-curve-chart-canvas")).toBeInTheDocument();
    expect(getByTestId("equity-curve-legend-master")).toHaveTextContent("Master");
    expect(getByTestId("equity-curve-legend-spy")).toHaveTextContent("SPY");
    // Each series should have been registered + data pushed through.
    expect(addSeriesMock).toHaveBeenCalledTimes(2);
    expect(setData).toHaveBeenCalledTimes(2);
  });

  it("exposes exportPng which emits a Blob via the chart screenshot path", async () => {
    const ref = createRef<ChartHandle>();
    render(<EquityCurveChart ref={ref} series={sampleSeries} />);
    const blob = await ref.current?.exportPng();
    expect(takeScreenshot).toHaveBeenCalledTimes(1);
    expect(toBlobMock).toHaveBeenCalledTimes(1);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.type).toBe("image/png");
  });
});
