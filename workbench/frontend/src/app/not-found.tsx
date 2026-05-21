import Link from "next/link";
import { getTranslations } from "next-intl/server";

/**
 * B024 F003 — 404 page.
 *
 * Matches the dark-first shell of `/login` so the disclaimer footer and
 * background colour stay consistent for anonymous visitors landing on
 * an unknown route. Translated through next-intl; the `errorPage`
 * namespace also drives the runtime `error.tsx` fallback.
 */
export default async function NotFound() {
  const t = await getTranslations("errorPage");
  return (
    <main
      data-testid="not-found-page"
      className="flex flex-1 flex-col items-center justify-center px-6 py-16"
    >
      <section className="w-full max-w-md rounded-lg border border-neutral-800 bg-neutral-900 p-8 text-center shadow-lg">
        <h1 className="text-2xl font-semibold text-neutral-100">{t("notFoundTitle")}</h1>
        <p className="mt-3 text-sm text-neutral-400">{t("notFoundDescription")}</p>
        <Link
          data-testid="not-found-back-home"
          href="/"
          className="mt-6 inline-block rounded-md border border-neutral-700 bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white"
        >
          {t("notFoundBackHome")}
        </Link>
      </section>
    </main>
  );
}
