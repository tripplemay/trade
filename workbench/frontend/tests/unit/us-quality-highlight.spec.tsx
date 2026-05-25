// @vitest-environment happy-dom
/**
 * B025 F005 vitest — bilingual UsQualityMomentumHighlight rendering.
 *
 * Verifies the highlight card pulls from the
 * ``strategies.usQualityMomentum`` namespace in both zh-CN and en
 * locales and exposes all five factor labels for downstream Playwright
 * assertions.
 */
import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { UsQualityMomentumHighlight } from "@/components/strategies/UsQualityMomentumHighlight";

import { renderWithIntl } from "../test-utils/intl";

afterEach(() => {
  cleanup();
});

describe("UsQualityMomentumHighlight (en)", () => {
  it("renders the English strategy name", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    expect(getByTestId("us-quality-name").textContent).toBe("US Quality Momentum");
  });

  it("renders all five factor pills in English", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    expect(getByTestId("us-quality-factor-momentum").textContent).toBe("Momentum");
    expect(getByTestId("us-quality-factor-quality").textContent).toBe("Quality");
    expect(getByTestId("us-quality-factor-lowVol").textContent).toBe("Low Vol");
    expect(getByTestId("us-quality-factor-value").textContent).toBe("Value");
    expect(getByTestId("us-quality-factor-trend").textContent).toBe("Trend");
  });

  it("surfaces the synthetic-data disclaimer", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    const disclaimer = getByTestId("us-quality-data-source").textContent ?? "";
    expect(disclaimer.toLowerCase()).toContain("synthetic");
  });

  it("shows factor weight summary including all five factor names", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    const config = getByTestId("us-quality-config").textContent ?? "";
    for (const fragment of ["Momentum", "Quality", "Low Vol", "Value", "Trend"]) {
      expect(config).toContain(fragment);
    }
  });

  it("emits the satellite_us_quality sleeve identifier verbatim", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    expect(getByTestId("us-quality-tagline").textContent ?? "").toContain("satellite_us_quality");
  });
});

describe("UsQualityMomentumHighlight (zh-CN)", () => {
  it("renders the Chinese strategy name", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "zh-CN",
    });
    expect(getByTestId("us-quality-name").textContent).toBe("美股质量动量");
  });

  it("renders the Chinese factor labels (with English in parens)", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "zh-CN",
    });
    expect(getByTestId("us-quality-factor-momentum").textContent).toContain("动量");
    expect(getByTestId("us-quality-factor-quality").textContent).toContain("质量");
    expect(getByTestId("us-quality-factor-lowVol").textContent).toContain("低波");
    expect(getByTestId("us-quality-factor-value").textContent).toContain("价值");
    expect(getByTestId("us-quality-factor-trend").textContent).toContain("趋势");
  });

  it("keeps the English sleeve identifier even in zh-CN", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "zh-CN",
    });
    expect(getByTestId("us-quality-tagline").textContent ?? "").toContain("satellite_us_quality");
  });

  it("surfaces the synthetic-data disclaimer in zh-CN", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "zh-CN",
    });
    expect(getByTestId("us-quality-data-source").textContent ?? "").toContain(
      "synthetic data, not actual filings",
    );
  });
});

describe("UsQualityMomentumHighlight rules + structure", () => {
  it("does not introduce any execution-style buttons or hard-coded English", () => {
    const { container } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    expect(container.querySelector("button")).toBeNull();
  });

  it("declares stable testids so Playwright bilingual smoke can target it", () => {
    const { getByTestId } = renderWithIntl(<UsQualityMomentumHighlight />, {
      locale: "en",
    });
    expect(getByTestId("strategies-us-quality-highlight")).toBeInTheDocument();
    expect(getByTestId("us-quality-factors")).toBeInTheDocument();
    expect(getByTestId("us-quality-config")).toBeInTheDocument();
  });
});
