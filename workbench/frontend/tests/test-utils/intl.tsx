/**
 * B024 F002 test helper — wraps a component tree with
 * `NextIntlClientProvider` so any descendant calling `useTranslations`
 * resolves against the zh-CN bundle (the schema-of-record).
 *
 * Page-level unit specs that render `<HomePage />`, `<StrategiesPage />`,
 * etc., must wrap with this helper because those pages now reach for
 * translations on first render. Tests that pre-date B024 typically
 * call `render(<Page />)` directly — swap that for `renderWithIntl`.
 *
 * Defaults to zh-CN since that is the workbench default locale; pass
 * `locale: 'en'` if you need to assert English-specific text (which is
 * usually a smell — prefer key-set parity guard tests instead of
 * per-language hard-coded copy).
 */
import type { ReactElement, ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";

import enMessages from "../../messages/en.json";
import zhCNMessages from "../../messages/zh-CN.json";

export const TEST_MESSAGES = {
  "zh-CN": zhCNMessages,
  en: enMessages,
} as const;

export type TestLocale = keyof typeof TEST_MESSAGES;

export interface RenderWithIntlOptions extends RenderOptions {
  locale?: TestLocale;
}

/**
 * The test default is `en` to keep pre-i18n assertions (which expect
 * English UI copy) green. A separate `locale-default-renders-zh-CN`
 * spec covers the zh-CN production default; per-locale assertions
 * should opt into a locale explicitly to stay locale-agnostic at the
 * page-render layer.
 */
export const DEFAULT_TEST_LOCALE: TestLocale = "en";

export function withIntl(children: ReactNode, locale: TestLocale = DEFAULT_TEST_LOCALE): ReactElement {
  return (
    <NextIntlClientProvider locale={locale} messages={TEST_MESSAGES[locale]}>
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(
  ui: ReactElement,
  { locale = DEFAULT_TEST_LOCALE, ...options }: RenderWithIntlOptions = {},
): RenderResult {
  return render(withIntl(ui, locale), options);
}
