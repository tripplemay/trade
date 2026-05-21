"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

/**
 * B024 F003 — root error boundary.
 *
 * `error.tsx` must be a client component per Next.js; we log the
 * digest on mount (useful in B022 F014's recent-errors ring buffer)
 * and render a translated retry surface.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errorPage");

  useEffect(() => {
    // Keep the digest in the browser console so the user can copy it
    // into a bug report — the server-side ring buffer already has the
    // structured record.
    if (error?.digest) {
      console.error(`[error.tsx] digest=${error.digest}`);
    }
  }, [error]);

  return (
    <main
      data-testid="error-boundary-page"
      className="flex flex-1 flex-col items-center justify-center px-6 py-16"
    >
      <section className="w-full max-w-md rounded-lg border border-destructive/40 bg-neutral-900 p-8 text-center shadow-lg">
        <h1 className="text-2xl font-semibold text-neutral-100">{t("errorTitle")}</h1>
        <p className="mt-3 text-sm text-neutral-400">{t("errorDescription")}</p>
        {error?.digest ? (
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            digest: <code>{error.digest}</code>
          </p>
        ) : null}
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            data-testid="error-retry"
            onClick={() => reset()}
            className="rounded-md border border-neutral-700 bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white"
          >
            {t("retry")}
          </button>
          <Link
            data-testid="error-back-home"
            href="/"
            className="rounded-md border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
          >
            {t("backHome")}
          </Link>
        </div>
      </section>
    </main>
  );
}
