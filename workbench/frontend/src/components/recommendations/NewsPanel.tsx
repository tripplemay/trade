"use client";

/**
 * B034 F003 — Sleeve news panel.
 *
 * Renders the relevance-ranked news affecting a sleeve from the
 * same-origin, auth-gated ``GET /api/recommendations/news`` endpoint.
 * The panel is **purely structured** — title, source, date, topic
 * chips, matched tickers, and a numeric relevance score — with no
 * AI-generated commentary (B034 non-generative boundary §3). External
 * source links open in a new tab with ``rel="noopener noreferrer"``.
 *
 * Filters (sleeve / source / form type / topic) re-query the backend;
 * the backend returns items already sorted most-relevant first.
 */

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type SleeveNewsItem = components["schemas"]["SleeveNewsItem"];
type SleeveNewsResponse = components["schemas"]["SleeveNewsResponse"];

const NEWS_URL = "/api/recommendations/news";

const SLEEVES = ["satellite_us_quality", "master"] as const;
const SOURCES = ["", "sec_edgar", "yahoo_rss"] as const;
const FORM_TYPES = ["", "10-K", "10-Q", "8-K", "4"] as const;
const TOPICS = [
  "",
  "财报",
  "重大事件",
  "内部人交易",
  "股息",
  "业绩指引",
  "评级变动",
  "并购",
  "其他",
] as const;

const SELECT_CLASS =
  "rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground";

function Filter({
  testId,
  label,
  value,
  options,
  allLabel,
  onChange,
}: {
  testId: string;
  label: string;
  value: string;
  options: readonly string[];
  allLabel: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex items-center gap-1 text-xs text-muted-foreground">
      {label}
      <select
        data-testid={testId}
        className={SELECT_CLASS}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option === "" ? allLabel : option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function NewsPanel() {
  const t = useTranslations("recommendations.news");

  const [sleeve, setSleeve] = useState<string>(SLEEVES[0]);
  const [source, setSource] = useState("");
  const [formType, setFormType] = useState("");
  const [topic, setTopic] = useState("");
  const [items, setItems] = useState<SleeveNewsItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ sleeve });
    if (source) params.set("source", source);
    if (formType) params.set("form_type", formType);
    if (topic) params.set("topic", topic);
    return params.toString();
  }, [sleeve, source, formType, topic]);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    fetch(`${NEWS_URL}?${query}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as SleeveNewsResponse;
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
  }, [query]);

  return (
    <Card data-testid="recommendations-news-card">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
        <div className="flex flex-wrap gap-3 pt-2">
          <Filter
            testId="news-filter-sleeve"
            label={t("sleeveLabel")}
            value={sleeve}
            options={SLEEVES}
            allLabel={t("all")}
            onChange={setSleeve}
          />
          <Filter
            testId="news-filter-source"
            label={t("sourceLabel")}
            value={source}
            options={SOURCES}
            allLabel={t("all")}
            onChange={setSource}
          />
          <Filter
            testId="news-filter-form-type"
            label={t("formTypeLabel")}
            value={formType}
            options={FORM_TYPES}
            allLabel={t("all")}
            onChange={setFormType}
          />
          <Filter
            testId="news-filter-topic"
            label={t("topicLabel")}
            value={topic}
            options={TOPICS}
            allLabel={t("all")}
            onChange={setTopic}
          />
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <p data-testid="news-error" className="text-sm text-destructive">
            {t("error", { error })}
          </p>
        ) : items === null ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : items.length === 0 ? (
          <p data-testid="news-empty" className="text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul data-testid="news-list" className="space-y-3">
            {items.map((item) => {
              const tickers = item.matched_tickers ?? [];
              const topics = item.topics ?? [];
              return (
                <li
                  key={item.news_id}
                  data-testid="news-item"
                  className="rounded-md border border-border px-3 py-2"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-foreground underline-offset-2 hover:underline"
                    >
                      {item.title}
                    </a>
                    <span
                      data-testid="news-score"
                      className="shrink-0 text-xs text-muted-foreground"
                    >
                      {t("scoreLabel")} {item.score.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{item.source}</span>
                    <span>·</span>
                    <span>{item.published_at}</span>
                    {tickers.length > 0 ? (
                      <span data-testid="news-tickers">
                        {t("tickersLabel")}: {tickers.join(", ")}
                      </span>
                    ) : null}
                  </div>
                  {topics.length > 0 ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {topics.map((tag) => (
                        <span
                          key={tag}
                          data-testid="news-topic-chip"
                          className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] text-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
