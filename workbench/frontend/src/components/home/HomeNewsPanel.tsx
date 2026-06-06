"use client";

/**
 * B038 F002 — Home "Today's market news" panel.
 *
 * Renders the newest-first global market-news feed from the same-origin,
 * auth-gated ``GET /api/news/latest`` endpoint (personas §2 mockup). It is
 * **purely structured** — title, source, date, deterministic topic chips —
 * with no AI-generated commentary (B034 non-generative boundary §3) and no
 * execution affordance (research-only surface). External source links open
 * in a new tab with ``rel="noopener noreferrer"``.
 *
 * Unlike the sleeve-scoped recommendations NewsPanel this has no filters —
 * it is a compact, read-only headline list for the Home third section.
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type LatestNewsItem = components["schemas"]["LatestNewsItem"];
type LatestNewsResponse = components["schemas"]["LatestNewsResponse"];

const NEWS_URL = "/api/news/latest";

/** How many headlines to show on Home (the backend returns up to 20;
 * the Home section stays compact). */
const MAX_HEADLINES = 8;

export function HomeNewsPanel() {
  const t = useTranslations("home.news");
  const [items, setItems] = useState<LatestNewsItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(NEWS_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as LatestNewsResponse;
      })
      .then((payload) => {
        if (!cancelled) setItems(payload.items ?? []);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card data-testid="home-news-card">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p data-testid="home-news-error" className="text-sm text-destructive">
            {t("error", { error })}
          </p>
        ) : items === null ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : items.length === 0 ? (
          <p data-testid="home-news-empty" className="text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul data-testid="home-news-list" className="space-y-3">
            {items.slice(0, MAX_HEADLINES).map((item) => {
              const topics = item.topics ?? [];
              return (
                <li
                  key={item.news_id}
                  data-testid="home-news-item"
                  className="border-b border-border/50 pb-2 last:border-0"
                >
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-foreground underline-offset-2 hover:underline"
                  >
                    {item.title}
                  </a>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{item.source}</span>
                    <span>·</span>
                    <span>{item.published_at}</span>
                    {topics.length > 0 ? (
                      <span className="flex flex-wrap gap-1">
                        {topics.map((tag) => (
                          <span
                            key={tag}
                            data-testid="home-news-topic-chip"
                            className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] text-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </span>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
