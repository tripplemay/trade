/**
 * B058 F003/F005 — on-demand manual target-refresh client (enqueue + poll).
 *
 * ``POST /api/strategy-modes/{strategy_id}/refresh-target`` enqueues and returns
 * ``202 {job_id, status:'queued'}``; we poll
 * ``GET /api/strategy-modes/refresh-target/{job_id}`` until the worker writes
 * ``done`` (resolve with the result) or ``error`` (reject). A bounded attempt
 * count makes "no worker / stuck" degrade to an honest timeout instead of
 * polling forever. The fetch + sleep are injectable so the state machine
 * unit-tests deterministically (mirrors ``backtest-poll.ts``).
 */

import type { components } from "@/types/api";

export type TargetRefreshResponse = components["schemas"]["TargetRefreshResponse"];
export type TargetRefreshJobStatus = components["schemas"]["TargetRefreshJobStatus"];

export const DEFAULT_POLL_INTERVAL_MS = 1500;
// ~5 minutes (200 × 1.5s). A target precompute is shorter than a full backtest,
// but the bound still degrades an offline worker to a friendly timeout.
export const DEFAULT_MAX_ATTEMPTS = 200;

export class RefreshTimeoutError extends Error {
  constructor(message = "target refresh timed out") {
    super(message);
    this.name = "RefreshTimeoutError";
  }
}

/**
 * A terminal `error` refresh job carrying the backend's structured `error_kind`
 * (producer_error / empty_target / interrupted). The page maps `errorKind` to a
 * bilingual friendly message; the raw `message` is kept for diagnostics only.
 */
export class RefreshJobError extends Error {
  readonly errorKind: string | null;
  constructor(message: string, errorKind: string | null = null) {
    super(message);
    this.name = "RefreshJobError";
    this.errorKind = errorKind;
  }
}

export interface RefreshOptions {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  intervalMs?: number;
  maxAttempts?: number;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export async function enqueueRefreshTarget(
  strategyId: string,
  { fetchImpl = fetch }: Pick<RefreshOptions, "fetchImpl"> = {},
): Promise<string> {
  const response = await fetchImpl(
    `/api/strategy-modes/${encodeURIComponent(strategyId)}/refresh-target`,
    { method: "POST", headers: { "content-type": "application/json" } },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = (await response.json()) as TargetRefreshResponse;
  return data.job_id;
}

export async function pollRefreshTarget(
  jobId: string,
  {
    fetchImpl = fetch,
    sleep = defaultSleep,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
  }: RefreshOptions = {},
): Promise<TargetRefreshJobStatus> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await fetchImpl(
      `/api/strategy-modes/refresh-target/${encodeURIComponent(jobId)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = (await response.json()) as TargetRefreshJobStatus;
    if (data.status === "done") return data;
    if (data.status === "error") {
      throw new RefreshJobError(data.error ?? "target refresh failed", data.error_kind ?? null);
    }
    // queued / running → wait and poll again.
    await sleep(intervalMs);
  }
  throw new RefreshTimeoutError();
}

/** Enqueue + poll to completion. Resolves with the done status, rejects on
 * error / timeout. */
export async function runRefreshTarget(
  strategyId: string,
  options: RefreshOptions = {},
): Promise<TargetRefreshJobStatus> {
  const jobId = await enqueueRefreshTarget(strategyId, { fetchImpl: options.fetchImpl });
  return pollRefreshTarget(jobId, options);
}
