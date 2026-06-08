/**
 * B047 F003 — async backtest client (enqueue + poll) state machine.
 */
import { describe, expect, it, vi } from "vitest";

import {
  BacktestRunError,
  BacktestTimeoutError,
  enqueueBacktest,
  pollBacktest,
  runBacktest,
} from "@/lib/backtest-poll";
import type { components } from "@/types/api";

type Resp = components["schemas"]["BacktestRunResponse"];

const REQUEST: components["schemas"]["BacktestRunRequest"] = {
  strategy_id: "momentum",
  snapshot_id: "snap",
  start_date: "2024-01-01",
  end_date: "2024-12-31",
  parameters: {},
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** A fetch that returns the queued/running statuses in order, then done. */
function sequenceFetch(getResponses: Resp[]): typeof fetch {
  let i = 0;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/run") && init?.method === "POST") {
      return jsonResponse({ run_id: "bt-1", status: "queued" } satisfies Partial<Resp>);
    }
    const next = getResponses[Math.min(i, getResponses.length - 1)];
    i += 1;
    return jsonResponse(next);
  }) as unknown as typeof fetch;
}

const noSleep = () => Promise.resolve();

function done(): Resp {
  return {
    run_id: "bt-1",
    status: "done",
    metrics: {
      cagr: 0.1,
      sharpe: 1.0,
      sortino: null,
      max_drawdown: -0.2,
      turnover: 2,
      win_rate: null,
    },
    equity: [{ date: "2024-12-31", nav: 110 }],
    allocations: [],
    trades: [],
    report_markdown: "# r",
    error: null,
  };
}

function status(
  s: Resp["status"],
  error: string | null = null,
  error_kind: string | null = null,
): Resp {
  return {
    run_id: "bt-1",
    status: s,
    metrics: null,
    equity: [],
    allocations: [],
    trades: [],
    report_markdown: null,
    error,
    error_kind,
  };
}

describe("enqueueBacktest", () => {
  it("returns the run_id from the 202 enqueue response", async () => {
    const fetchImpl = sequenceFetch([done()]);
    const runId = await enqueueBacktest(REQUEST, { fetchImpl });
    expect(runId).toBe("bt-1");
  });

  it("throws on a non-ok enqueue", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("no", { status: 404 }),
    ) as unknown as typeof fetch;
    await expect(enqueueBacktest(REQUEST, { fetchImpl })).rejects.toThrow(/HTTP 404/);
  });
});

describe("pollBacktest", () => {
  it("polls queued → running → done and resolves with the result", async () => {
    const fetchImpl = sequenceFetch([status("queued"), status("running"), done()]);
    const result = await pollBacktest("bt-1", { fetchImpl, sleep: noSleep });
    expect(result.status).toBe("done");
    expect(result.metrics?.cagr).toBe(0.1);
  });

  it("rejects with the error message when status is error", async () => {
    const fetchImpl = sequenceFetch([status("running"), status("error", "engine blew up")]);
    await expect(pollBacktest("bt-1", { fetchImpl, sleep: noSleep })).rejects.toThrow(
      /engine blew up/,
    );
  });

  it("rejects with a BacktestRunError carrying the structured error_kind (B047-OPS2)", async () => {
    const fetchImpl = sequenceFetch([
      status("error", "insufficient price history…", "insufficient_history"),
    ]);
    await expect(pollBacktest("bt-1", { fetchImpl, sleep: noSleep })).rejects.toMatchObject({
      name: "BacktestRunError",
      errorKind: "insufficient_history",
    });
  });

  it("BacktestRunError defaults errorKind to null when the backend omits it", async () => {
    const fetchImpl = sequenceFetch([status("error", "boom")]);
    const err = await pollBacktest("bt-1", { fetchImpl, sleep: noSleep }).catch((e) => e);
    expect(err).toBeInstanceOf(BacktestRunError);
    expect((err as BacktestRunError).errorKind).toBeNull();
  });

  it("times out after maxAttempts of non-terminal status", async () => {
    const fetchImpl = sequenceFetch([status("running")]);
    await expect(
      pollBacktest("bt-1", { fetchImpl, sleep: noSleep, maxAttempts: 3 }),
    ).rejects.toBeInstanceOf(BacktestTimeoutError);
  });
});

describe("runBacktest", () => {
  it("enqueues then polls to the done result", async () => {
    const fetchImpl = sequenceFetch([status("queued"), done()]);
    const result = await runBacktest(REQUEST, { fetchImpl, sleep: noSleep });
    expect(result.status).toBe("done");
    expect(result.run_id).toBe("bt-1");
  });
});
