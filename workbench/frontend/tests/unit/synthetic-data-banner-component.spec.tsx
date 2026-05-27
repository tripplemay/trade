// @vitest-environment happy-dom
/**
 * B026 / B030 F004 — `SyntheticDataBanner` component behaviour in
 * isolation.
 *
 * The component is **decommissioned** from the protected layout
 * (B030 F004 fix-round 1) so the active codepath never renders it.
 * These tests pin the component's behaviour when imported directly
 * — the canonical reactivation path is "restore the import + JSX in
 * `(protected)/layout.tsx`", and any future restorer needs the
 * isolation tests to confirm the env gate, the bilingual headline,
 * the dismiss path, and the close-button affordances still work
 * before re-deploying.
 *
 * Compared to the original B026 vitest spec, this file (a) no
 * longer reads translations from `messages/{zh-CN,en}.json` —
 * those keys are removed; the component now carries hardcoded
 * bilingual literals — and (b) uses `NextIntlClientProvider` only
 * to feed `useLocale` (the component no longer calls
 * `useTranslations`).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { SyntheticDataBanner } from "@/components/SyntheticDataBanner";

const ZH_HEADLINE = "研究原型 · 仅含合成数据 · 不构成投资决策依据";
const EN_HEADLINE = "Research prototype · Synthetic data only · Not for investment decisions";
const ZH_ARIA_CLOSE = "关闭此提示";
const EN_ARIA_CLOSE = "Dismiss this notice";

function renderWithLocale(
  ui: React.ReactElement,
  locale: "zh-CN" | "en" = "zh-CN",
) {
  return render(
    <NextIntlClientProvider locale={locale} messages={{}} timeZone="UTC">
      {ui}
    </NextIntlClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("SyntheticDataBanner (component, post-decommission)", () => {
  it("returns null when env flag is the literal 'false'", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "false");
    const { queryByTestId } = renderWithLocale(<SyntheticDataBanner />);
    // The kill-switch is the env-gate; nothing must render even if
    // someone imports the component directly.
    expect(queryByTestId("synthetic-data-banner")).toBeNull();
    expect(queryByTestId("synthetic-data-banner-headline")).toBeNull();
    expect(queryByTestId("synthetic-data-banner-close")).toBeNull();
  });

  it("renders when env flag is unset (default = enabled, reactivation path)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />);
    expect(getByTestId("synthetic-data-banner")).toBeTruthy();
    expect(getByTestId("synthetic-data-banner-close")).toBeTruthy();
  });

  it("renders the zh-CN headline when locale=zh-CN", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />, "zh-CN");
    expect(getByTestId("synthetic-data-banner-headline").textContent).toBe(
      ZH_HEADLINE,
    );
  });

  it("renders the en headline when locale=en", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />, "en");
    expect(getByTestId("synthetic-data-banner-headline").textContent).toBe(
      EN_HEADLINE,
    );
  });

  it("close button carries the locale-specific aria-label (zh-CN)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />, "zh-CN");
    expect(getByTestId("synthetic-data-banner-close").getAttribute("aria-label")).toBe(
      ZH_ARIA_CLOSE,
    );
  });

  it("close button carries the locale-specific aria-label (en)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />, "en");
    expect(getByTestId("synthetic-data-banner-close").getAttribute("aria-label")).toBe(
      EN_ARIA_CLOSE,
    );
  });

  it("declares role=status + aria-live=polite", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId } = renderWithLocale(<SyntheticDataBanner />);
    const banner = getByTestId("synthetic-data-banner");
    expect(banner.getAttribute("role")).toBe("status");
    expect(banner.getAttribute("aria-live")).toBe("polite");
  });

  it("dismisses when close button is clicked (React state path)", () => {
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId, queryByTestId } = renderWithLocale(<SyntheticDataBanner />);
    fireEvent.click(getByTestId("synthetic-data-banner-close"));
    expect(queryByTestId("synthetic-data-banner")).toBeNull();
  });

  it("native click also dismisses via the DOM fallback path", () => {
    // The component carries a vanilla DOM click listener as
    // belt-and-braces against any production-only edge case that
    // breaks React's synthetic event delegation. Dispatching a
    // native MouseEvent (bypassing RTL's fireEvent → React path)
    // exercises that fallback specifically.
    vi.stubEnv("NEXT_PUBLIC_SYNTHETIC_DATA_BANNER", "true");
    const { getByTestId, queryByTestId } = renderWithLocale(<SyntheticDataBanner />);
    const btn = getByTestId("synthetic-data-banner-close");
    btn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const node = queryByTestId("synthetic-data-banner") as HTMLElement | null;
    const visuallyHidden = node === null || node.style.display === "none";
    expect(visuallyHidden).toBe(true);
  });
});
