"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { components } from "@/types/api";

type ReportDetail = components["schemas"]["ReportDetail"];

export default function ReportDetailPage() {
  const t = useTranslations("reports.detail");
  const tCommon = useTranslations("common");

  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";

  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    fetch(`/api/reports/${encodeURIComponent(slug)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as ReportDetail;
        if (!cancelled) setDetail(data);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const stateLabel = error
    ? tCommon("unreachableWithError", { error })
    : detail
      ? `${detail.batch} · ${detail.kind} · ${detail.date}`
      : tCommon("loading");

  return (
    <section data-testid="page-report-detail" className="space-y-4">
      <header className="flex items-baseline justify-between">
        <div>
          <Link
            href="/reports"
            className="text-xs text-muted-foreground hover:underline"
          >
            {t("back")}
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            {detail?.title ?? slug}
          </h1>
        </div>
        <span data-testid="report-detail-state" className="text-xs text-muted-foreground">
          {stateLabel}
        </span>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("bodyTitle")}</CardTitle>
          <CardDescription>{t("bodyDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {detail ? (
            <MarkdownRenderer body={detail.body_markdown} />
          ) : (
            <p data-testid="report-detail-loading" className="text-sm text-muted-foreground">
              {t("bodyLoading")}
            </p>
          )}
        </CardContent>
      </Card>

      {detail && detail.cross_links && detail.cross_links.length > 0 ? (
        <Card data-testid="report-detail-cross-links">
          <CardHeader>
            <CardTitle>{t("crossLinksTitle")}</CardTitle>
            <CardDescription>
              {t("crossLinksDescriptionPrefix")}
              <code>{t("crossLinksDescriptionA")}</code>
              {t("crossLinksDescriptionMid")}
              <code>{t("crossLinksDescriptionB")}</code>
              {t("crossLinksDescriptionSuffix")}
              <code>{t("crossLinksDescriptionC")}</code>
              {t("crossLinksDescriptionEnd")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {detail.cross_links.map((path) => (
                <li key={path} className="truncate">
                  <Link href={`/docs/${path}`} className="text-foreground hover:underline">
                    {path}
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
