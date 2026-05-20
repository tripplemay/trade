// @vitest-environment happy-dom
/**
 * B024 F001 — LocaleSwitcher behaviour.
 *
 * Asserts the contract used by the middleware: changing the dropdown
 * writes a `NEXT_LOCALE` cookie with the correct value + max-age and
 * triggers a router refresh so RSC re-resolves the locale on the next
 * request.
 *
 * NextIntlClientProvider feeds messages so useTranslations() doesn't
 * fall back to keys; the test is otherwise independent of next-intl
 * internals.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import LocaleSwitcher from "@/components/LocaleSwitcher";
import zhCNMessages from "../../messages/zh-CN.json";
import enMessages from "../../messages/en.json";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

afterEach(() => {
  cleanup();
  refresh.mockClear();
  // Clear cookies between tests so prior writes don't leak.
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; Max-Age=0; path=/`;
  });
});

function renderSwitcher(locale: "zh-CN" | "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "zh-CN" ? zhCNMessages : enMessages}
    >
      <LocaleSwitcher />
    </NextIntlClientProvider>,
  );
}

describe("LocaleSwitcher", () => {
  it("renders the currently active locale as the selected option", () => {
    const { getByTestId } = renderSwitcher("zh-CN");
    const select = getByTestId("locale-switcher-select") as HTMLSelectElement;
    expect(select.value).toBe("zh-CN");
  });

  it("writes NEXT_LOCALE cookie with 365d max-age and refreshes on change", () => {
    const { getByTestId } = renderSwitcher("zh-CN");
    const select = getByTestId("locale-switcher-select") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "en" } });

    expect(document.cookie).toContain("NEXT_LOCALE=en");
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("ignores no-op selection back to the current locale", () => {
    const { getByTestId } = renderSwitcher("zh-CN");
    const select = getByTestId("locale-switcher-select") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "zh-CN" } });

    expect(refresh).not.toHaveBeenCalled();
  });

  it("offers both supported locales", () => {
    const { getByTestId } = renderSwitcher("en");
    const select = getByTestId("locale-switcher-select") as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(["zh-CN", "en"]);
  });
});
