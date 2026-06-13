"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import PriceChart from "@/components/chart/PriceChart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { workbenchFetch } from "@/lib/api-fetch";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type SymbolPriceDetail = components["schemas"]["SymbolPriceDetail"];
type SymbolFundamentals = components["schemas"]["SymbolFundamentals"];
type SymbolNewsResponse = components["schemas"]["SymbolNewsResponse"];

const PRICE_URL = (symbol: string) => `/api/symbols/${encodeURIComponent(symbol)}/price`;
const FUNDAMENTALS_URL = (symbol: string) =>
  `/api/symbols/${encodeURIComponent(symbol)}/fundamentals`;
const NEWS_URL = (symbol: string) => `/api/symbols/${encodeURIComponent(symbol)}/news`;

type ChartMode = "candle" | "line";

function formatCompact(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatRatio(value: number | null): string {
  if (value === null) return "—";
  return value.toFixed(2);
}

function formatPctRaw(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatMoney(value: number, currency: string): string {
  // B061 F004 — currency-aware price formatting: ¥ for A-share (CNY), $ for US
  // (USD) via the narrow symbol. The explicit ISO code is also surfaced in a
  // badge so CNY is honestly labelled (¥ alone is ambiguous with JPY).
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      currencyDisplay: "narrowSymbol",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    // Defensive: an unexpected currency code must never break the page.
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }
}

function formatPct(value: number | null): string {
  if (value === null) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function pctClass(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-muted-foreground";
}

export default function SymbolsPage() {
  const t = useTranslations("symbols");
  const searchParams = useSearchParams();
  const router = useRouter();

  const initialSymbol = (searchParams.get("symbol") ?? "").toUpperCase();
  const [query, setQuery] = useState(initialSymbol);
  const [activeSymbol, setActiveSymbol] = useState(initialSymbol);
  const [mode, setMode] = useState<ChartMode>("candle");

  const [data, setData] = useState<SymbolPriceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeSymbol) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);
    workbenchFetch(PRICE_URL(activeSymbol))
      .then(async (response) => {
        if (!response.ok) {
          // Surface the backend's actionable, locale-aware detail (400/404/429).
          let detail = `HTTP ${response.status}`;
          try {
            const body = (await response.json()) as { detail?: string };
            if (body?.detail) detail = body.detail;
          } catch {
            /* non-JSON error body — keep the status fallback */
          }
          throw new Error(detail);
        }
        return (await response.json()) as SymbolPriceDetail;
      })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSymbol]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const next = query.trim().toUpperCase();
    if (!next) return;
    setActiveSymbol(next);
    router.replace(`/symbols?symbol=${encodeURIComponent(next)}`);
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </header>

      <Card data-testid="symbols-disclaimer-card" className="border-amber-700/40 bg-amber-950/20">
        <CardContent className="p-4 text-sm text-amber-100">{t("disclaimer")}</CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPlaceholder")}
          data-testid="symbols-search-input"
          className="max-w-xs"
        />
        <Button type="submit" data-testid="symbols-search-button">
          {t("searchButton")}
        </Button>
      </form>

      {!activeSymbol ? (
        <p className="text-sm text-muted-foreground" data-testid="symbols-empty-prompt">
          {t("emptyPrompt")}
        </p>
      ) : loading ? (
        <p className="text-sm text-muted-foreground" data-testid="symbols-loading">
          {t("loading", { symbol: activeSymbol })}
        </p>
      ) : error ? (
        <p className="text-sm text-destructive" data-testid="symbols-error">
          {error}
        </p>
      ) : data ? (
        <SymbolDetail data={data} mode={mode} onModeChange={setMode} t={t} />
      ) : null}
    </section>
  );
}

function SymbolDetail({
  data,
  mode,
  onModeChange,
  t,
}: {
  data: SymbolPriceDetail;
  mode: ChartMode;
  onModeChange: (mode: ChartMode) => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const returns: Array<[string, number | null]> = [
    [t("return1M"), data.returns.one_month],
    [t("return3M"), data.returns.three_month],
    [t("return6M"), data.returns.six_month],
    [t("return1Y"), data.returns.one_year],
    [t("returnYTD"), data.returns.ytd],
  ];

  return (
    <div className="space-y-4" data-testid="symbols-detail">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-baseline gap-3">
            <span className="text-lg">{data.symbol}</span>
            <span className="text-2xl font-semibold" data-testid="symbols-close">
              {formatMoney(data.close, data.currency)}
            </span>
            <span
              className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300"
              data-testid="symbols-source-badge"
            >
              {t("sourceBadge", { source: data.source })}
            </span>
            <span
              className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300"
              data-testid="symbols-currency-badge"
            >
              {data.currency}
            </span>
          </CardTitle>
          <CardDescription data-testid="symbols-eod-note">
            {t("eodNote", { asOf: data.as_of })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant={mode === "candle" ? "default" : "outline"}
              onClick={() => onModeChange("candle")}
              data-testid="symbols-mode-candle"
            >
              {t("chartCandle")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={mode === "line" ? "default" : "outline"}
              onClick={() => onModeChange("line")}
              data-testid="symbols-mode-line"
            >
              {t("chartLine")}
            </Button>
          </div>
          {data.bars.length > 0 ? (
            <PriceChart key={mode} bars={data.bars} mode={mode} />
          ) : (
            <p className="text-sm text-muted-foreground">{t("noChartData")}</p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("rangeTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("week52High")}</span>
              <span data-testid="symbols-week52-high">
                {data.week52_high === null ? "—" : formatMoney(data.week52_high, data.currency)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("week52Low")}</span>
              <span data-testid="symbols-week52-low">
                {data.week52_low === null ? "—" : formatMoney(data.week52_low, data.currency)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("returnsTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm" data-testid="symbols-returns">
            {returns.map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <span className="text-muted-foreground">{label}</span>
                <span className={cn(pctClass(value))}>{formatPct(value)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <FundamentalsSection symbol={data.symbol} t={t} />
      <NewsSection symbol={data.symbol} t={t} />
    </div>
  );
}

function FundamentalsSection({
  symbol,
  t,
}: {
  symbol: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const [data, setData] = useState<SymbolFundamentals | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);
    workbenchFetch(FUNDAMENTALS_URL(symbol))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as SymbolFundamentals;
      })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  function unavailableMsg(reason: string | null): string {
    if (reason === "non_us") return t("fundUnavailableNonUs");
    if (reason === "not_equity") return t("fundUnavailableNotEquity");
    return t("fundUnavailableNoData");
  }

  const rows: Array<[string, string]> =
    data && data.available
      ? [
          [t("fundMarketCap"), formatCompact(data.market_cap)],
          [t("fundTrailingPe"), formatRatio(data.trailing_pe)],
          [t("fundForwardPe"), formatRatio(data.forward_pe)],
          [t("fundPriceToBook"), formatRatio(data.price_to_book)],
          [t("fundDividendYield"), formatPctRaw(data.dividend_yield)],
          [t("fundProfitMargin"), formatPctRaw(data.profit_margins)],
          [t("fundGrossMargin"), formatPctRaw(data.gross_margins)],
          [t("fundRevenue"), formatCompact(data.revenue)],
          [t("fundRoe"), formatPctRaw(data.return_on_equity)],
          [t("fundDebtToEquity"), formatRatio(data.debt_to_equity)],
        ]
      : [];

  return (
    <Card data-testid="symbols-fundamentals">
      <CardHeader>
        <CardTitle>{t("fundTitle")}</CardTitle>
        {data && data.available ? (
          <CardDescription>{t("fundSource", { source: data.source })}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {loading ? (
          <p className="text-muted-foreground" data-testid="symbols-fundamentals-loading">
            {t("fundLoading")}
          </p>
        ) : error ? (
          <p className="text-destructive">{error}</p>
        ) : data && data.available ? (
          <>
            {data.sector ? (
              <div className="mb-2 text-xs text-muted-foreground">
                {t("fundSector")}: {data.sector}
                {data.industry ? ` · ${t("fundIndustry")}: ${data.industry}` : ""}
              </div>
            ) : null}
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <span className="text-muted-foreground">{label}</span>
                <span>{value}</span>
              </div>
            ))}
          </>
        ) : (
          <p className="text-muted-foreground" data-testid="symbols-fundamentals-unavailable">
            {unavailableMsg(data?.reason ?? null)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function NewsSection({ symbol, t }: { symbol: string; t: ReturnType<typeof useTranslations> }) {
  const [items, setItems] = useState<SymbolNewsResponse["items"] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setItems(null);
    workbenchFetch(NEWS_URL(symbol))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as SymbolNewsResponse;
      })
      .then((payload) => {
        if (!cancelled) setItems(payload.items);
      })
      .catch(() => {
        // News is a secondary surface — on failure show the empty state
        // rather than break the page.
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  return (
    <Card data-testid="symbols-news">
      <CardHeader>
        <CardTitle>{t("newsTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {loading ? (
          <p className="text-muted-foreground" data-testid="symbols-news-loading">
            {t("newsLoading")}
          </p>
        ) : items && items.length > 0 ? (
          items.map((item) => (
            <div key={item.news_id} className="space-y-1 border-b border-border pb-2 last:border-0">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground hover:underline"
              >
                {item.title}
              </a>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>{item.source}</span>
                <span>·</span>
                <span>{item.published_at.slice(0, 10)}</span>
                {(item.topics ?? []).map((topic) => (
                  <span
                    key={topic}
                    className="rounded bg-neutral-800 px-1.5 py-0.5 text-neutral-300"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          ))
        ) : (
          <p className="text-muted-foreground" data-testid="symbols-news-empty">
            {t("newsEmpty")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
