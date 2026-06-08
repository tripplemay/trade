/**
 * B047 F003 — on-demand async backtest client (enqueue + poll).
 *
 * ``POST /run`` enqueues and returns ``202 {run_id, status:'queued'}``; we then
 * poll ``GET /{run_id}`` until the worker writes ``done`` (resolve with the
 * result) or ``error`` (reject). A bounded attempt count makes "no worker /
 * stuck" degrade to an honest timeout instead of polling forever. The fetch +
 * sleep are injectable so the state machine unit-tests deterministically.
 */

import type { components } from "@/types/api";

export type BacktestRunResponse = components["schemas"]["BacktestRunResponse"];
export type BacktestRunRequest = components["schemas"]["BacktestRunRequest"];

const RUN_URL = "/api/backtests/run";

export const DEFAULT_POLL_INTERVAL_MS = 1500;
export const DEFAULT_MAX_ATTEMPTS = 40; // ~60s before the timeout fallback

export class BacktestTimeoutError extends Error {
  constructor(message = "backtest timed out") {
    super(message);
    this.name = "BacktestTimeoutError";
  }
}

/**
 * B047-OPS2 F002 — a terminal `error` run, carrying the backend's structured
 * `error_kind` (insufficient_history / no_signal_dates / data_unavailable /
 * unknown). The page maps `errorKind` to a bilingual friendly message; the raw
 * `message` (the English `error`) is kept for diagnostics only, never shown.
 */
export class BacktestRunError extends Error {
  readonly errorKind: string | null;
  constructor(message: string, errorKind: string | null = null) {
    super(message);
    this.name = "BacktestRunError";
    this.errorKind = errorKind;
  }
}

export interface RunOptions {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  intervalMs?: number;
  maxAttempts?: number;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export async function enqueueBacktest(
  body: BacktestRunRequest,
  { fetchImpl = fetch }: Pick<RunOptions, "fetchImpl"> = {},
): Promise<string> {
  const response = await fetchImpl(RUN_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = (await response.json()) as BacktestRunResponse;
  return data.run_id;
}

export async function pollBacktest(
  runId: string,
  {
    fetchImpl = fetch,
    sleep = defaultSleep,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
  }: RunOptions = {},
): Promise<BacktestRunResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await fetchImpl(`/api/backtests/${runId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = (await response.json()) as BacktestRunResponse;
    if (data.status === "done") return data;
    if (data.status === "error") {
      throw new BacktestRunError(data.error ?? "backtest failed", data.error_kind ?? null);
    }
    // queued / running → wait and poll again.
    await sleep(intervalMs);
  }
  throw new BacktestTimeoutError();
}

/** Enqueue + poll to completion. Resolves with the done result, rejects on
 * error / timeout. */
export async function runBacktest(
  body: BacktestRunRequest,
  options: RunOptions = {},
): Promise<BacktestRunResponse> {
  const runId = await enqueueBacktest(body, { fetchImpl: options.fetchImpl });
  return pollBacktest(runId, options);
}
