// @vitest-environment happy-dom
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import AllocationBar from "@/components/chart/AllocationBar";
import type { ChartHandle } from "@/components/chart/util";

const getDataURL = vi.fn(() => "data:image/png;base64,AAA=");

vi.mock("echarts-for-react", () => ({
  default: function MockReactECharts(props: {
    onChartReady?: (instance: { getDataURL: ReturnType<typeof vi.fn> }) => void;
  }) {
    setTimeout(() => props.onChartReady?.({ getDataURL }), 0);
    return null;
  },
}));

const blobOut = new Blob(["bar"], { type: "image/png" });
global.fetch = vi.fn(async () => ({ blob: async () => blobOut })) as unknown as typeof fetch;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AllocationBar", () => {
  it("renders the host container in default horizontal orientation", () => {
    const { getByTestId } = render(
      <AllocationBar
        data={[
          { name: "AAA", value: 0.5 },
          { name: "BBB", value: 0.3 },
        ]}
      />,
    );
    expect(getByTestId("allocation-bar")).toBeInTheDocument();
  });

  it("exposes exportPng emitting a PNG Blob", async () => {
    const ref = createRef<ChartHandle>();
    render(<AllocationBar ref={ref} data={[{ name: "X", value: 1 }]} orientation="vertical" />);
    await new Promise((resolve) => setTimeout(resolve, 1));
    const blob = await ref.current?.exportPng();
    expect(getDataURL).toHaveBeenCalledTimes(1);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.type).toBe("image/png");
  });
});
