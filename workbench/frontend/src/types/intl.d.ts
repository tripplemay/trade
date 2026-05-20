/**
 * B024 F001 — translation key type chain.
 *
 * The zh-CN message bundle is the authoritative schema: every other
 * locale must mirror its key set bit-for-bit (enforced by the parity
 * unit test). Augmenting next-intl's `AppConfig` with `typeof
 * zhCNMessages` lets the compiler reject typos at every
 * `useTranslations()` / `t('common.foo.typo')` call site.
 *
 * `Locale` covers the supported runtime locales so passing an arbitrary
 * string into next-intl helpers also fails at compile time.
 */
import type zhCNMessages from "../../messages/zh-CN.json";

declare module "next-intl" {
  interface AppConfig {
    Messages: typeof zhCNMessages;
    Locale: "zh-CN" | "en";
  }
}
