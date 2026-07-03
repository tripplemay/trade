// @vitest-environment happy-dom
/**
 * B060 F001 vitest — shared SymbolLink component.
 *
 * Verifies the site-wide clickable-symbol behaviour: render-as-link, the B059
 * deep-link target (`/symbols?symbol=XXX`), uppercase normalisation, the
 * bilingual "view quote" tooltip/aria-label, className passthrough, A-share
 * code encoding, and the empty-symbol defensive fallback.
 */
import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SymbolLink } from "@/components/symbol/SymbolLink";

import { renderWithIntl } from "../test-utils/intl";

afterEach(() => {
  cleanup();
});

describe("SymbolLink", () => {
  it("renders the symbol as a link to the /symbols deep link", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="AAPL" />);
    const link = getByTestId("symbol-link");
    expect(link.tagName).toBe("A");
    expect(link.getAttribute("href")).toBe("/symbols?symbol=AAPL");
    expect(link.textContent).toBe("AAPL");
  });

  it("uppercase-normalises the deep-link target from lowercase input", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="aapl" />);
    const link = getByTestId("symbol-link");
    expect(link.getAttribute("href")).toBe("/symbols?symbol=AAPL");
    expect(link.getAttribute("data-symbol")).toBe("AAPL");
  });

  it("trims surrounding whitespace before normalising", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="  spy  " />);
    expect(getByTestId("symbol-link").getAttribute("href")).toBe("/symbols?symbol=SPY");
  });

  it("encodes A-share codes (dotted suffix) safely", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="600519.SH" />);
    const link = getByTestId("symbol-link");
    // The dot is preserved (encodeURIComponent leaves '.'); the link is valid.
    expect(link.getAttribute("href")).toBe("/symbols?symbol=600519.SH");
    expect(link.textContent).toBe("600519.SH");
  });

  it("exposes the English tooltip/aria-label via i18n", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="NVDA" />, { locale: "en" });
    const link = getByTestId("symbol-link");
    expect(link.getAttribute("aria-label")).toBe("View NVDA quote");
    expect(link.getAttribute("title")).toBe("View NVDA quote");
  });

  it("exposes the Chinese tooltip/aria-label via i18n", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="NVDA" />, { locale: "zh-CN" });
    const link = getByTestId("symbol-link");
    expect(link.getAttribute("aria-label")).toBe("查看 NVDA 行情");
  });

  it("merges a caller className onto the link (e.g. mono/bold context)", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="SGOV" className="font-mono" />);
    expect(getByTestId("symbol-link").className).toContain("font-mono");
  });

  it("falls back to raw text without a link for an empty symbol", () => {
    const { queryByTestId, container } = renderWithIntl(<SymbolLink symbol="   " />);
    expect(queryByTestId("symbol-link")).toBeNull();
    expect(container.textContent).toBe("   ");
  });

  // B079 — name-primary / code-secondary display (名称为主，代码次之).
  it("renders name-primary with the code as a secondary suffix when name is given", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="600519.SH" name="贵州茅台" />);
    const link = getByTestId("symbol-link");
    // Both the name and the raw code are shown; the deep link stays code-based.
    expect(link.textContent).toContain("贵州茅台");
    expect(link.textContent).toContain("600519.SH");
    expect(link.getAttribute("href")).toBe("/symbols?symbol=600519.SH");
  });

  it("falls back to the raw code when name is null (graceful 缺失兜底)", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="AAPL" name={null} />);
    expect(getByTestId("symbol-link").textContent).toBe("AAPL");
  });

  it("falls back to the raw code when name is blank whitespace", () => {
    const { getByTestId } = renderWithIntl(<SymbolLink symbol="AAPL" name="   " />);
    expect(getByTestId("symbol-link").textContent).toBe("AAPL");
  });
});
