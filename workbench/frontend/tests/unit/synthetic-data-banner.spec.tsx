// @vitest-environment happy-dom
/**
 * B026 F001 — SyntheticDataBanner unit coverage.
 *
 * Acceptance (spec §5):
 *   - env enabled + not dismissed → renders, headline + close button visible
 *   - env enabled + user clicks close → component returns null
 *   - env disabled (NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false) → never renders
 *   - bilingual headline assertions (zh-CN + en)
 *   - syntheticBanner namespace present in both message bundles
 *   - aria affordances (role=status / aria-live=polite / aria-label)
 *
 * The shared key-set parity (messages-key-parity.spec.ts) already enforces
 * structural symmetry; the per-locale headline assertions below verify
 * the *content* of the new namespace specifically, which the parity guard
 * alone can't catch.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent } from "@testing-library/react";

import { renderWithIntl } from "../test-utils/intl";
import { SyntheticDataBanner } from "@/components/SyntheticDataBanner";
import enMessages from "../../messages/en.json";
import zhCNMessages from "../../messages/zh-CN.json";

const ZH_HEADLINE = "研究原型 · 仅含合成数据 · 不构成投资决策依据";
const EN_HEADLINE = "Research prototype · Synthetic data only · Not for investment decisions";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("SyntheticDataBanner (B026 F001)", () => {
  it("renders when env flag is unset (default = enabled)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "");
    const { getByTestId } = renderWithIntl(<SyntheticDataBanner />);
    expect(getByTestId("synthetic-data-banner")).toBeInTheDocument();
    expect(getByTestId("synthetic-data-banner-close")).toBeInTheDocument();
  });

  it("renders when env flag is the literal string 'true'", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithIntl(<SyntheticDataBanner />);
    expect(getByTestId("synthetic-data-banner")).toBeInTheDocument();
  });

  it("does NOT render when env flag is the literal string 'false'", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "false");
    const { queryByTestId } = renderWithIntl(<SyntheticDataBanner />);
    expect(queryByTestId("synthetic-data-banner")).toBeNull();
  });

  it("dismisses when the close button is clicked (session-only)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId, queryByTestId } = renderWithIntl(<SyntheticDataBanner />);
    expect(getByTestId("synthetic-data-banner")).toBeInTheDocument();
    fireEvent.click(getByTestId("synthetic-data-banner-close"));
    expect(queryByTestId("synthetic-data-banner")).toBeNull();
  });

  it("renders the zh-CN headline when locale=zh-CN", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithIntl(<SyntheticDataBanner />, { locale: "zh-CN" });
    expect(getByTestId("synthetic-data-banner-headline")).toHaveTextContent(ZH_HEADLINE);
  });

  it("renders the en headline when locale=en", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithIntl(<SyntheticDataBanner />, { locale: "en" });
    expect(getByTestId("synthetic-data-banner-headline")).toHaveTextContent(EN_HEADLINE);
  });

  it("declares role=status + aria-live=polite + bilingual aria-label on close", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId, rerender } = renderWithIntl(<SyntheticDataBanner />, { locale: "zh-CN" });
    const zhBanner = getByTestId("synthetic-data-banner");
    expect(zhBanner).toHaveAttribute("role", "status");
    expect(zhBanner).toHaveAttribute("aria-live", "polite");
    expect(getByTestId("synthetic-data-banner-close")).toHaveAttribute(
      "aria-label",
      zhCNMessages.syntheticBanner.ariaClose,
    );

    // Verify the same structure honours the en aria-label.
    cleanup();
    const enRender = renderWithIntl(<SyntheticDataBanner />, { locale: "en" });
    expect(enRender.getByTestId("synthetic-data-banner-close")).toHaveAttribute(
      "aria-label",
      enMessages.syntheticBanner.ariaClose,
    );
    rerender; // silence unused destructure
  });

  it("ships the syntheticBanner namespace with both keys in both bundles", () => {
    expect(zhCNMessages.syntheticBanner.headline).toBe(ZH_HEADLINE);
    expect(zhCNMessages.syntheticBanner.ariaClose).toBeTruthy();
    expect(enMessages.syntheticBanner.headline).toBe(EN_HEADLINE);
    expect(enMessages.syntheticBanner.ariaClose).toBeTruthy();
  });

  it("native click also dismisses via the DOM fallback path (fix-round 2)", () => {
    // Codex F002 L2 reverify saw the React `onClick → setState → return
    // null` path fail to visually hide the banner on the production VM
    // even though the dev/start/unit builds were all green. The
    // component now also binds a vanilla DOM `click` listener via
    // useEffect that sets `display: none` on the container, so the
    // dismiss visibly succeeds even if React's synthetic-event path is
    // broken. Dispatching a native MouseEvent (rather than RTL's
    // fireEvent, which goes through React's delegation) exercises both
    // paths; the assertion accepts either outcome — fully unmounted
    // (React path won) or display:none (DOM fallback won).
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId, queryByTestId } = renderWithIntl(<SyntheticDataBanner />);
    const btn = getByTestId("synthetic-data-banner-close");
    btn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const node = queryByTestId("synthetic-data-banner") as HTMLElement | null;
    const visuallyHidden = node === null || node.style.display === "none";
    expect(visuallyHidden).toBe(true);
  });
});
