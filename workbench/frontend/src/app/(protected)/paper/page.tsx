"use client";

/**
 * B056 F003 — 模拟盘 (Paper Trading / forward-simulation) page.
 *
 * Six sections (user-confirmed 2026-06-11, spec §6): ① summary (strategy
 * selector + NAV / total & today P&L + vs SPY), ② forward NAV curve with the
 * SPY benchmark overlay, ③ per-asset P&L table (+ cash row), ④ allocation-vs-
 * target drift, ⑤ simplified rebalance log (date + cost, no per-fill detail),
 * ⑥ settings / activation. Reads the auth-gated ``GET /api/paper/*`` endpoints;
 * everything is REAL already-computed mark-to-market values. Clearly labelled
 * "simulated, not real money".
 */

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EquityCurveChart, type EquityCurveSeries } from "@/components/chart";
import { SymbolLink } from "@/components/symbol/SymbolLink";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type PaperView = components["schemas"]["PaperView"];
type PaperStrategy = components["schemas"]["PaperStrategy"];
type RebalanceNowResponse = components["schemas"]["RebalanceNowResponse"];

const STRATEGIES_URL = "/api/paper/strategies";

function money(value: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function pct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

function signClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-foreground";
  return value > 0 ? "text-emerald-600" : "text-red-600";
}

function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function isNil(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined;
}

function moneyOrDash(value: number | null | undefined, currency: string): string {
  return isNil(value) ? "—" : money(value, currency);
}

export default function PaperPage() {
  const t = useTranslations("paper");
  const [strategies, setStrategies] = useState<PaperStrategy[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [view, setView] = useState<PaperView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [capital, setCapital] = useState<string>("100000");
  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState<string | null>(null);
  // B058 F005 — manual "align to current target" (synchronous rebalance once).
  const [rebalancing, setRebalancing] = useState(false);
  const [rebalanceResult, setRebalanceResult] = useState<RebalanceNowResponse | null>(null);
  const [rebalanceError, setRebalanceError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(STRATEGIES_URL)
      .then((r) => r.json())
      .then((body: components["schemas"]["PaperStrategiesResponse"]) => {
        if (!active) return;
        setStrategies(body.strategies ?? []);
        if (body.strategies?.length && !strategyId) {
          setStrategyId(body.strategies[0]!.strategy_id);
        }
      })
      .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadView = useCallback((sid: string) => {
    if (!sid) return;
    setError(null);
    fetch(`/api/paper/${encodeURIComponent(sid)}`)
      .then((r) => r.json())
      .then((body: PaperView) => setView(body))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (strategyId) loadView(strategyId);
  }, [strategyId, loadView]);

  const onActivate = useCallback(async () => {
    setActivating(true);
    setActivateError(null);
    try {
      const resp = await fetch("/api/paper/activate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          strategy_id: strategyId,
          initial_capital: Number(capital) || 100000,
        }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail.detail ?? `HTTP ${resp.status}`);
      }
      loadView(strategyId);
    } catch (e) {
      setActivateError(e instanceof Error ? e.message : String(e));
    } finally {
      setActivating(false);
    }
  }, [strategyId, capital, loadView]);

  const onRebalanceNow = useCallback(async () => {
    setRebalancing(true);
    setRebalanceError(null);
    setRebalanceResult(null);
    try {
      const resp = await fetch(`/api/paper/${encodeURIComponent(strategyId)}/rebalance-now`, {
        method: "POST",
        headers: { "content-type": "application/json" },
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail.detail ?? `HTTP ${resp.status}`);
      }
      const body = (await resp.json()) as RebalanceNowResponse;
      setRebalanceResult(body);
      loadView(strategyId); // refetch the view to show the aligned book
    } catch (e) {
      setRebalanceError(e instanceof Error ? e.message : String(e));
    } finally {
      setRebalancing(false);
    }
  }, [strategyId, loadView]);

  const navSeries = useMemo<EquityCurveSeries[]>(() => {
    if (!view?.nav_curve?.length) return [];
    const series: EquityCurveSeries[] = [
      {
        id: "paper-nav",
        name: t("navSeries"),
        color: "#00c853",
        data: view.nav_curve.map((p) => ({ time: p.date, value: p.nav })),
      },
    ];
    const spy = view.nav_curve
      .filter((p) => p.benchmark_nav !== null && p.benchmark_nav !== undefined)
      .map((p) => ({ time: p.date, value: p.benchmark_nav as number }));
    if (spy.length) {
      series.push({ id: "spy", name: t("benchmarkSeries"), color: "#9ca3af", data: spy });
    }
    return series;
  }, [view, t]);

  const currency = view?.summary?.base_currency ?? "USD";

  return (
    <div data-testid="paper-page" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("description")}</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            data-testid="paper-simulated-badge"
            className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-600"
          >
            {t("simulatedBadge")}
          </span>
          <label className="flex items-center gap-1 text-sm text-muted-foreground">
            {t("strategyLabel")}
            <select
              data-testid="paper-strategy-select"
              className="rounded-md border border-border bg-background px-2 py-1 text-sm"
              value={strategyId}
              onChange={(e) => setStrategyId(e.target.value)}
            >
              {strategies.map((s) => (
                <option key={s.strategy_id} value={s.strategy_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error ? (
        <p data-testid="paper-error" className="text-sm text-destructive">
          {t("error", { error })}
        </p>
      ) : view === null ? (
        <p className="text-sm text-muted-foreground">{t("loading")}</p>
      ) : !view.active ? (
        <InactiveCard
          t={t}
          capital={capital}
          setCapital={setCapital}
          onActivate={onActivate}
          activating={activating}
          activateError={activateError}
        />
      ) : (
        <ActiveView
          view={view}
          navSeries={navSeries}
          currency={currency}
          t={t}
          onRebalanceNow={onRebalanceNow}
          rebalancing={rebalancing}
          rebalanceResult={rebalanceResult}
          rebalanceError={rebalanceError}
        />
      )}
    </div>
  );
}

type T = ReturnType<typeof useTranslations<"paper">>;

function InactiveCard({
  t,
  capital,
  setCapital,
  onActivate,
  activating,
  activateError,
}: {
  t: T;
  capital: string;
  setCapital: (v: string) => void;
  onActivate: () => void;
  activating: boolean;
  activateError: string | null;
}) {
  return (
    <Card data-testid="paper-inactive">
      <CardHeader>
        <CardTitle>{t("inactiveTitle")}</CardTitle>
        <CardDescription>{t("inactiveBody")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex max-w-xs items-center gap-2 text-sm">
          {t("initialCapitalLabel")}
          <input
            data-testid="paper-capital-input"
            type="number"
            className="w-40 rounded-md border border-border bg-background px-2 py-1"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
          />
        </label>
        <button
          data-testid="paper-activate"
          type="button"
          disabled={activating}
          onClick={onActivate}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {activating ? t("activating") : t("activate")}
        </button>
        {activateError ? (
          <p data-testid="paper-activate-error" className="text-sm text-destructive">
            {t("activateError", { error: activateError })}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ActiveView({
  view,
  navSeries,
  currency,
  t,
  onRebalanceNow,
  rebalancing,
  rebalanceResult,
  rebalanceError,
}: {
  view: PaperView;
  navSeries: EquityCurveSeries[];
  currency: string;
  t: T;
  onRebalanceNow: () => void;
  rebalancing: boolean;
  rebalanceResult: RebalanceNowResponse | null;
  rebalanceError: string | null;
}) {
  const s = view.summary!;
  const positions = view.positions ?? [];
  const drift = view.drift ?? [];
  const rebalances = view.rebalances ?? [];
  const cash = view.cash ?? 0;
  return (
    <div className="space-y-4">
      {/* ① Summary */}
      <Card data-testid="paper-summary">
        <CardHeader>
          <CardTitle>{t("sectionSummary")}</CardTitle>
          <CardDescription>{t("forwardHint", { days: s.days_running })}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <Stat label={t("currentNav")} value={money(s.current_nav, currency)} />
          <Stat
            label={t("totalPnl")}
            value={`${money(s.total_pnl, currency)} (${pct(s.total_pnl_pct)})`}
            cls={signClass(s.total_pnl)}
          />
          <Stat
            label={t("todayPnl")}
            value={moneyOrDash(s.today_pnl, currency)}
            cls={signClass(s.today_pnl)}
          />
          <Stat
            label={t("vsBenchmark")}
            value={
              s.vs_benchmark_pct === null || s.vs_benchmark_pct === undefined
                ? "—"
                : `${s.vs_benchmark_pct >= 0 ? t("outperform") : t("underperform")} ${pct(Math.abs(s.vs_benchmark_pct))}`
            }
            cls={signClass(s.vs_benchmark_pct)}
            testId="paper-vs-benchmark"
          />
          <Stat label={t("initialCapitalLabel")} value={money(s.initial_capital, currency)} />
          <Stat label={t("activatedOn")} value={s.activated_on} />
          <Stat label={t("daysRunning")} value={`${s.days_running} ${t("daysUnit")}`} />
          <Stat label={t("nextRebalance")} value={s.next_rebalance ?? "—"} />
        </CardContent>
      </Card>

      {/* ② NAV curve + SPY overlay */}
      <Card data-testid="paper-nav-curve">
        <CardHeader>
          <CardTitle>{t("sectionNavCurve")}</CardTitle>
        </CardHeader>
        <CardContent>
          {navSeries.length ? (
            <EquityCurveChart series={navSeries} height={280} />
          ) : (
            <p className="text-sm text-muted-foreground">{t("curveEmpty")}</p>
          )}
        </CardContent>
      </Card>

      {/* ③ Per-asset P&L */}
      <Card data-testid="paper-positions">
        <CardHeader>
          <CardTitle>{t("sectionPositions")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {positions.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">{t("colSymbol")}</th>
                  <th className="py-1 text-right">{t("colShares")}</th>
                  <th className="py-1 text-right">{t("colAvgCost")}</th>
                  <th className="py-1 text-right">{t("colClose")}</th>
                  <th className="py-1 text-right">{t("colMarketValue")}</th>
                  <th className="py-1 text-right">{t("colWeight")}</th>
                  <th className="py-1 text-right">{t("colPnl")}</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr
                    key={p.symbol}
                    data-testid="paper-position-row"
                    className="border-t border-border"
                  >
                    <td className="py-1 font-medium">
                      <SymbolLink symbol={p.symbol} />
                    </td>
                    <td className="py-1 text-right">{num(p.shares, 4)}</td>
                    <td className="py-1 text-right">{num(p.avg_cost)}</td>
                    <td className="py-1 text-right">
                      {isNil(p.close) ? t("unpriced") : num(p.close)}
                    </td>
                    <td className="py-1 text-right">{moneyOrDash(p.market_value, currency)}</td>
                    <td className="py-1 text-right">{pct(p.weight)}</td>
                    <td className={`py-1 text-right ${signClass(p.unrealized_pnl)}`}>
                      {isNil(p.unrealized_pnl)
                        ? "—"
                        : `${money(p.unrealized_pnl, currency)} (${pct(p.unrealized_pnl_pct)})`}
                    </td>
                  </tr>
                ))}
                <tr
                  data-testid="paper-cash-row"
                  className="border-t border-border text-muted-foreground"
                >
                  <td className="py-1 font-medium">{t("cashRow")}</td>
                  <td colSpan={3} />
                  <td className="py-1 text-right">{money(cash, currency)}</td>
                  <td colSpan={2} />
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">{t("positionsEmpty")}</p>
          )}
        </CardContent>
      </Card>

      {/* ④ Allocation vs target drift */}
      <Card data-testid="paper-drift">
        <CardHeader>
          <CardTitle>{t("sectionDrift")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {drift.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">{t("colSymbol")}</th>
                  <th className="py-1 text-right">{t("colCurrent")}</th>
                  <th className="py-1 text-right">{t("colTarget")}</th>
                  <th className="py-1 text-right">{t("colDrift")}</th>
                </tr>
              </thead>
              <tbody>
                {drift.map((d) => (
                  <tr
                    key={d.symbol}
                    data-testid="paper-drift-row"
                    className="border-t border-border"
                  >
                    <td className="py-1 font-medium">
                      <SymbolLink symbol={d.symbol} />
                    </td>
                    <td className="py-1 text-right">{pct(d.current_weight)}</td>
                    <td className="py-1 text-right">{pct(d.target_weight)}</td>
                    <td className={`py-1 text-right ${signClass(d.drift)}`}>{pct(d.drift)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">{t("driftEmpty")}</p>
          )}
        </CardContent>
      </Card>

      {/* ⑤ Rebalance log (simplified) */}
      <Card data-testid="paper-rebalances">
        <CardHeader>
          <CardTitle>{t("sectionRebalances")}</CardTitle>
          <CardDescription>{t("rebalancesNote")}</CardDescription>
        </CardHeader>
        <CardContent>
          {rebalances.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">{t("colDate")}</th>
                  <th className="py-1 text-right">{t("colCost")}</th>
                  <th className="py-1 text-right">{t("colCumCost")}</th>
                </tr>
              </thead>
              <tbody>
                {rebalances.map((r) => (
                  <tr
                    key={r.date}
                    data-testid="paper-rebalance-row"
                    className="border-t border-border"
                  >
                    <td className="py-1">{r.date}</td>
                    <td className="py-1 text-right">{money(r.cost, currency)}</td>
                    <td className="py-1 text-right">{money(r.cumulative_cost, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">{t("rebalancesEmpty")}</p>
          )}
        </CardContent>
      </Card>

      {/* ⑥ Align to current target (manual, on-demand — B058 F005) */}
      <Card data-testid="paper-align">
        <CardHeader>
          <CardTitle>{t("alignTitle")}</CardTitle>
          <CardDescription>{t("alignNotice")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <button
            data-testid="paper-rebalance-now"
            type="button"
            disabled={rebalancing}
            onClick={onRebalanceNow}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {rebalancing ? t("aligning") : t("alignButton")}
          </button>
          {rebalanceResult ? (
            rebalanceResult.has_target ? (
              <div
                data-testid="paper-align-result"
                className="space-y-1 text-xs text-muted-foreground"
              >
                <p>{t("alignDone", { positions: rebalanceResult.positions })}</p>
                {(rebalanceResult.skipped_symbols ?? []).length ? (
                  <p data-testid="paper-align-skipped" className="text-amber-600">
                    {t("alignSkipped", {
                      count: (rebalanceResult.skipped_symbols ?? []).length,
                      symbols: (rebalanceResult.skipped_symbols ?? []).join(", "),
                    })}
                  </p>
                ) : null}
              </div>
            ) : (
              <p data-testid="paper-align-no-target" className="text-xs text-amber-600">
                {t("alignNoTarget")}
              </p>
            )
          ) : null}
          {rebalanceError ? (
            <p data-testid="paper-align-error" className="text-xs text-destructive">
              {t("alignError", { error: rebalanceError })}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {/* ⑦ Settings */}
      <Card data-testid="paper-settings">
        <CardHeader>
          <CardTitle>{t("sectionSettings")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-muted-foreground">
          <p>{t("settingsNote")}</p>
          <p>
            {t("feeBpsLabel")}: {s.fee_bps} · {t("slippageBpsLabel")}: {s.slippage_bps}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({
  label,
  value,
  cls,
  testId,
}: {
  label: string;
  value: string;
  cls?: string;
  testId?: string;
}) {
  return (
    <div data-testid={testId}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-base font-semibold ${cls ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}
