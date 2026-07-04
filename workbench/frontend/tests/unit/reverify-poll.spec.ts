/**
 * B080 F003 — frozen re-validation client (enqueue + poll) state machine.
 */
import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_MAX_ATTEMPTS,
  DEFAULT_POLL_INTERVAL_MS,
  enqueueReverify,
  pollReverify,
  ReverifyJobError,
  ReverifyTimeoutError,
  runReverify,
} from "@/lib/reverify-poll";
import type { components } from "@/types/api";

type Status = components["schemas"]["ReverifyJobStatus"];

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** A fetch that answers POST /reverify with a queued job, then returns the given
 * GET statuses in order. */
function sequenceFetch(getResponses: Status[]): typeof fetch {
  let i = 0;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/reverify") && init?.method === "POST") {
      return jsonResponse({
        job_id: "rvf-1",
        strategy_id: "cn_attack_pure_momentum",
        status: "queued",
      });
    }
    const next = getResponses[Math.min(i, getResponses.length - 1)];
    i += 1;
    return jsonResponse(next);
  }) as unknown as typeof fetch;
}

const noSleep = () => Promise.resolve();

function status(
  s: Status["status"],
  error: string | null = null,
  error_kind: string | null = null,
): Status {
  return {
    job_id: "rvf-1",
    strategy_id: "cn_attack_pure_momentum",
    status: s,
    as_of: null,
    report_ref: s === "done" ? "docs/test-reports/auto/reverify-x.md" : null,
    verdict: s === "done" ? "GO" : null,
    error,
    error_kind,
  };
}

describe("enqueueReverify", () => {
  it("returns the job_id from the 202 enqueue response", async () => {
    const fetchImpl = sequenceFetch([status("done")]);
    expect(await enqueueReverify("cn_attack_pure_momentum", { fetchImpl })).toBe("rvf-1");
  });

  it("throws on a non-ok enqueue", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("no", { status: 404 }),
    ) as unknown as typeof fetch;
    await expect(enqueueReverify("nope", { fetchImpl })).rejects.toThrow(/HTTP 404/);
  });
});

describe("pollReverify", () => {
  it("polls queued → running → done and resolves with the verdict", async () => {
    const fetchImpl = sequenceFetch([status("queued"), status("running"), status("done")]);
    const result = await pollReverify("rvf-1", { fetchImpl, sleep: noSleep });
    expect(result.status).toBe("done");
    expect(result.verdict).toBe("GO");
  });

  it("rejects with a ReverifyJobError carrying the structured error_kind", async () => {
    const fetchImpl = sequenceFetch([status("error", "baostock unreachable", "RuntimeError")]);
    await expect(pollReverify("rvf-1", { fetchImpl, sleep: noSleep })).rejects.toMatchObject({
      name: "ReverifyJobError",
      errorKind: "RuntimeError",
    });
  });

  it("defaults errorKind to null when the backend omits it", async () => {
    const fetchImpl = sequenceFetch([status("error", "boom")]);
    const err = await pollReverify("rvf-1", { fetchImpl, sleep: noSleep }).catch((e) => e);
    expect(err).toBeInstanceOf(ReverifyJobError);
    expect((err as ReverifyJobError).errorKind).toBeNull();
  });

  it("times out after maxAttempts of non-terminal status", async () => {
    const fetchImpl = sequenceFetch([status("running")]);
    await expect(
      pollReverify("rvf-1", { fetchImpl, sleep: noSleep, maxAttempts: 3 }),
    ).rejects.toBeInstanceOf(ReverifyTimeoutError);
  });
});

describe("default poll budget", () => {
  it("tolerates a long survivorship-free re-validation (~30 minutes) yet stays bounded", () => {
    const budgetMs = DEFAULT_MAX_ATTEMPTS * DEFAULT_POLL_INTERVAL_MS;
    expect(budgetMs).toBeGreaterThanOrEqual(20 * 60 * 1000);
    expect(Number.isFinite(DEFAULT_MAX_ATTEMPTS)).toBe(true);
  });
});

describe("runReverify", () => {
  it("enqueues then polls to the done result", async () => {
    const fetchImpl = sequenceFetch([status("queued"), status("done")]);
    const result = await runReverify("cn_attack_pure_momentum", { fetchImpl, sleep: noSleep });
    expect(result.status).toBe("done");
    expect(result.job_id).toBe("rvf-1");
  });
});
