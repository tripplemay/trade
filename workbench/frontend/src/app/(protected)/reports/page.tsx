"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type ReportSummary = components["schemas"]["ReportSummary"];
type ReportListResponse = components["schemas"]["ReportListResponse"];

const LIST_URL = "/api/reports";

export default function ReportsPage() {
  const t = useTranslations("reports");
  const tCommon = useTranslations("common");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(LIST_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as ReportListResponse;
        if (!cancelled) setReports(data.reports);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section data-testid="page-reports" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <span data-testid="reports-state" className="text-xs text-muted-foreground">
          {error
            ? tCommon("unreachableWithError", { error })
            : t("count", { count: reports.length })}
        </span>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("card.title")}</CardTitle>
          <CardDescription>
            {t("card.descriptionPrefix")}
            <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">
              {t("card.descriptionPath")}
            </code>
            {t("card.descriptionSuffix")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {reports.length === 0 ? (
            <p data-testid="reports-empty" className="text-sm text-muted-foreground">
              {t("empty")}
            </p>
          ) : (
            <ul className="space-y-2">
              {reports.map((report) => (
                <li
                  key={report.slug}
                  className="flex items-center justify-between gap-3 rounded-md border border-border/60 px-3 py-2 text-sm"
                >
                  <Link
                    href={`/reports/${report.slug}`}
                    data-testid={`report-link-${report.slug}`}
                    className="truncate text-foreground hover:underline"
                  >
                    {report.title}
                  </Link>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {report.batch} · {report.kind} · {report.date}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
