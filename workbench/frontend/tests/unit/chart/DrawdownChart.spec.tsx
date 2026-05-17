// @vitest-environment happy-dom
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import DrawdownChart from "@/components/chart/DrawdownChart";
import type { ChartHandle } from "@/components/chart/util";

const setData = vi.fn();
const applyOptions = vi.fn();
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
  HistogramSeries: { type: "Histogram" },
  createChart: vi.fn(() => ({
    addSeries: addSeriesMock,
    remove,
    takeScreenshot,
    timeScale: () => ({
      subscribeVisibleTimeRangeChange: subscribeRange,
      unsubscribeVisibleTimeRangeChange: unsubscribeRange,
      setVisibleRange,
    }),
  })),
}));

const sample = [
  { time: "2024-01-01" as const, value: -0.05 },
  { time: "2024-02-01" as const, value: -0.02 },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DrawdownChart", () => {
  it("renders the host div and pushes data into the histogram series", () => {
    const { getByTestId } = render(<DrawdownChart data={sample} />);
    expect(getByTestId("drawdown-chart")).toBeInTheDocument();
    expect(addSeriesMock).toHaveBeenCalledTimes(1);
    expect(setData).toHaveBeenCalledWith(sample);
  });

  it("applies controlled visibleRange via setVisibleRange on the time scale", () => {
    const range = { from: "2024-01-15" as const, to: "2024-02-15" as const };
    render(<DrawdownChart data={sample} visibleRange={range} />);
    expect(setVisibleRange).toHaveBeenCalledWith(range);
  });

  it("exposes exportPng emitting a PNG Blob", async () => {
    const ref = createRef<ChartHandle>();
    render(<DrawdownChart ref={ref} data={sample} />);
    const blob = await ref.current?.exportPng();
    expect(takeScreenshot).toHaveBeenCalledTimes(1);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.type).toBe("image/png");
  });
});
