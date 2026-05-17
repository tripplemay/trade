// @vitest-environment happy-dom
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import SweepHeatmap from "@/components/chart/SweepHeatmap";
import type { ChartHandle } from "@/components/chart/util";

let lastInstance: { getDataURL: ReturnType<typeof vi.fn> } | null = null;
const getDataURL = vi.fn(
  () => "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9ZcA8w8AAAAASUVORK5CYII=",
);

vi.mock("echarts-for-react", () => ({
  default: function MockReactECharts(props: {
    onChartReady?: (instance: { getDataURL: ReturnType<typeof vi.fn> }) => void;
  }) {
    const instance = { getDataURL };
    lastInstance = instance;
    setTimeout(() => props.onChartReady?.(instance), 0);
    return null;
  },
}));

// fetch in happy-dom can resolve data: URLs but returning a Blob is
// awkward; stub it instead so we control the output.
const blobFromUrl = new Blob(["mock"], { type: "image/png" });
global.fetch = vi.fn(async () => ({ blob: async () => blobFromUrl })) as unknown as typeof fetch;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  lastInstance = null;
});

describe("SweepHeatmap", () => {
  it("renders the host container", () => {
    const { getByTestId } = render(
      <SweepHeatmap
        xCategories={["Q1", "Q2"]}
        yCategories={["A", "B"]}
        data={[
          { xIndex: 0, yIndex: 0, value: 0.1 },
          { xIndex: 1, yIndex: 1, value: 0.4 },
        ]}
      />,
    );
    expect(getByTestId("sweep-heatmap")).toBeInTheDocument();
  });

  it("exposes exportPng emitting a PNG Blob via the echarts dataURL path", async () => {
    const ref = createRef<ChartHandle>();
    render(
      <SweepHeatmap
        ref={ref}
        xCategories={["Q1"]}
        yCategories={["A"]}
        data={[{ xIndex: 0, yIndex: 0, value: 0.5 }]}
      />,
    );
    // Let the mocked onChartReady fire so the chart ref is populated.
    await new Promise((resolve) => setTimeout(resolve, 1));
    const blob = await ref.current?.exportPng();
    expect(getDataURL).toHaveBeenCalledTimes(1);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.type).toBe("image/png");
  });
});
