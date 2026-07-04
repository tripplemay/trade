/**
 * B080 F003 — frozen re-validation client (enqueue + poll).
 *
 * ``POST /api/monitoring/reverify`` enqueues (deduped) and returns
 * ``202 {job_id, status:'queued'}``; we poll
 * ``GET /api/monitoring/reverify/{job_id}`` until the backtest-worker writes
 * ``done`` (resolve with the verdict + report ref) or ``error`` (reject). A
 * bounded attempt count degrades a stuck / offline worker to an honest timeout
 * instead of polling forever. The frozen re-validation (baostock fetch + backtest)
 * is far longer than a target refresh, so the bound is generous. fetch + sleep are
 * injectable for deterministic unit tests (mirrors refresh-target-poll.ts).
 */

import type { components } from "@/types/api";

export type ReverifyResponse = components["schemas"]["ReverifyResponse"];
export type ReverifyJobStatus = components["schemas"]["ReverifyJobStatus"];

export const DEFAULT_POLL_INTERVAL_MS = 3000;
// ~30 minutes (600 × 3s) — a survivorship-free re-validation appends prices for
// ~800 names then runs the frozen backtest; the bound still degrades an offline
// worker to a friendly timeout.
export const DEFAULT_MAX_ATTEMPTS = 600;

export class ReverifyTimeoutError extends Error {
  constructor(message = "re-validation timed out") {
    super(message);
    this.name = "ReverifyTimeoutError";
  }
}

/**
 * A terminal `error` re-validation job carrying the backend's structured
 * `error_kind` (e.g. the exception type / interrupted / data). The page maps it to
 * a bilingual message; the raw `message` is kept for diagnostics only.
 */
export class ReverifyJobError extends Error {
  readonly errorKind: string | null;
  constructor(message: string, errorKind: string | null = null) {
    super(message);
    this.name = "ReverifyJobError";
    this.errorKind = errorKind;
  }
}

export interface ReverifyOptions {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  intervalMs?: number;
  maxAttempts?: number;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export async function enqueueReverify(
  strategyId: string,
  { fetchImpl = fetch, asOf }: Pick<ReverifyOptions, "fetchImpl"> & { asOf?: string } = {},
): Promise<string> {
  const response = await fetchImpl(`/api/monitoring/reverify`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ strategy_id: strategyId, as_of: asOf ?? null }),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = (await response.json()) as ReverifyResponse;
  return data.job_id;
}

export async function pollReverify(
  jobId: string,
  {
    fetchImpl = fetch,
    sleep = defaultSleep,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
  }: ReverifyOptions = {},
): Promise<ReverifyJobStatus> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await fetchImpl(
      `/api/monitoring/reverify/${encodeURIComponent(jobId)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = (await response.json()) as ReverifyJobStatus;
    if (data.status === "done") return data;
    if (data.status === "error") {
      throw new ReverifyJobError(data.error ?? "re-validation failed", data.error_kind ?? null);
    }
    // queued / running → wait and poll again.
    await sleep(intervalMs);
  }
  throw new ReverifyTimeoutError();
}

/** Enqueue + poll to completion. Resolves with the done status, rejects on
 * error / timeout. */
export async function runReverify(
  strategyId: string,
  options: ReverifyOptions = {},
): Promise<ReverifyJobStatus> {
  const jobId = await enqueueReverify(strategyId, {
    fetchImpl: options.fetchImpl,
  });
  return pollReverify(jobId, options);
}
