// @vitest-environment happy-dom
/**
 * B023 F004 — Fills page: CSV upload + manual entry + preview/history.
 * Focuses on the page-level fetch lifecycle and the row-level error
 * surface. CSV adapter coverage lives in the backend (test_fills.py).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

vi.mock("sonner", () => {
  const success = vi.fn();
  const error = vi.fn();
  return {
    toast: { success, error },
    Toaster: () => null,
  };
});

import { toast } from "sonner";
import FillsPage from "@/app/(protected)/execution/fills/page";

type TicketListResponse = components["schemas"]["TicketListResponse"];
type FillSubmitResponse = components["schemas"]["FillSubmitResponse"];
type FillsListResponse = components["schemas"]["FillsListResponse"];

const TICKET_LIST: TicketListResponse = {
  items: [
    {
      id: "tkt-20260519-aaaa",
      ticket_date: "2026-05-19",
      snapshot_id: "snap-x",
      target_positions_id: "tp-x",
      markdown_path: "docs/runs/2026-05-19/order-ticket-tkt-20260519-aaaa.md",
      status: "generated",
      created_at: "2026-05-19T10:00:00",
      executed_at: null,
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
};

const EMPTY_FILLS: FillsListResponse = {
  ticket_id: "tkt-20260519-aaaa",
  items: [],
};

const SUBMIT_RESPONSE: FillSubmitResponse = {
  ticket_id: "tkt-20260519-aaaa",
  inserted: [
    {
      id: "fill-1",
      ticket_id: "tkt-20260519-aaaa",
      order_seq: 1,
      symbol: "SPY",
      side: "buy",
      shares: 72,
      fill_price: 501.85,
      commission: 0,
      fees: 0,
      currency: "USD",
      filled_at: "2026-05-30T13:31:42",
      source: "manual_entry",
      notes: null,
      created_at: "2026-05-30T14:00:00",
      matched: true,
    },
  ],
  unmatched_count: 0,
  accepted_under_allow_unmatched: false,
};

interface MockState {
  ticketList: TicketListResponse;
  fillsList: FillsListResponse;
  submitResponse: FillSubmitResponse;
  submitStatus: number;
  submitDetail?: unknown;
  posts: { url: string; method: string; body: unknown }[];
}

function buildFetch(state: MockState): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string" ? input : (input as Request).url ?? input.toString();
    const method = init?.method ?? "GET";
    let body: unknown = null;
    if (init?.body && typeof init.body === "string") {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }
    state.posts.push({ url, method, body });

    if (url === "/api/execution/tickets" && method === "GET") {
      return new Response(JSON.stringify(state.ticketList), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.startsWith("/api/execution/fills?ticket_id=")) {
      return new Response(JSON.stringify(state.fillsList), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url === "/api/execution/fills" && method === "POST") {
      if (state.submitStatus !== 200) {
        return new Response(JSON.stringify({ detail: state.submitDetail }), {
          status: state.submitStatus,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(state.submitResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not-found", { status: 404 });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("FillsPage (B023 F004)", () => {
  it("loads tickets + auto-selects the first generated ticket on mount", async () => {
    const state: MockState = {
      ticketList: TICKET_LIST,
      fillsList: EMPTY_FILLS,
      submitResponse: SUBMIT_RESPONSE,
      submitStatus: 200,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<FillsPage />);
    await waitFor(() => {
      expect((getByTestId("fills-ticket-select") as HTMLSelectElement).value).toBe(
        "tkt-20260519-aaaa",
      );
    });
    expect(getByTestId("fills-history-empty")).toBeInTheDocument();
  });

  it("manual entry happy-path: row → JSON POST → preview surfaces", async () => {
    const state: MockState = {
      ticketList: TICKET_LIST,
      fillsList: EMPTY_FILLS,
      submitResponse: SUBMIT_RESPONSE,
      submitStatus: 200,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<FillsPage />);
    await waitFor(() => {
      expect((getByTestId("fills-ticket-select") as HTMLSelectElement).value).toBe(
        "tkt-20260519-aaaa",
      );
    });
    fireEvent.change(getByTestId("fills-manual-seq-0"), { target: { value: "1" } });
    fireEvent.change(getByTestId("fills-manual-symbol-0"), { target: { value: "SPY" } });
    fireEvent.change(getByTestId("fills-manual-shares-0"), { target: { value: "72" } });
    fireEvent.change(getByTestId("fills-manual-price-0"), { target: { value: "501.85" } });
    fireEvent.change(getByTestId("fills-manual-filled-at-0"), {
      target: { value: "2026-05-30T13:31:42" },
    });
    fireEvent.click(getByTestId("fills-manual-submit"));
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(getByTestId("fills-preview-row-fill-1")).toBeInTheDocument();
    const postCall = state.posts.find(
      (p) => p.url === "/api/execution/fills" && p.method === "POST",
    );
    expect(postCall).toBeTruthy();
    expect(postCall?.body).toMatchObject({
      ticket_id: "tkt-20260519-aaaa",
      fills: [
        {
          order_seq: 1,
          symbol: "SPY",
          side: "buy",
          shares: 72,
          fill_price: 501.85,
        },
      ],
    });
  });

  it("manual entry validation: missing shares blocks submit + shows error", async () => {
    const state: MockState = {
      ticketList: TICKET_LIST,
      fillsList: EMPTY_FILLS,
      submitResponse: SUBMIT_RESPONSE,
      submitStatus: 200,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<FillsPage />);
    await waitFor(() => {
      expect((getByTestId("fills-ticket-select") as HTMLSelectElement).value).toBe(
        "tkt-20260519-aaaa",
      );
    });
    fireEvent.change(getByTestId("fills-manual-symbol-0"), { target: { value: "SPY" } });
    fireEvent.change(getByTestId("fills-manual-filled-at-0"), {
      target: { value: "2026-05-30T13:31:42" },
    });
    fireEvent.click(getByTestId("fills-manual-submit"));
    await waitFor(() => {
      expect(getByTestId("fills-row-error-0")).toBeInTheDocument();
    });
    // No POST issued.
    expect(state.posts.find((p) => p.url === "/api/execution/fills" && p.method === "POST")).toBeUndefined();
  });

  it("server-side 400 with row errors surfaces in the errors card", async () => {
    const state: MockState = {
      ticketList: TICKET_LIST,
      fillsList: EMPTY_FILLS,
      submitResponse: SUBMIT_RESPONSE,
      submitStatus: 400,
      submitDetail: {
        errors: [
          { row: 0, error: "fill does not match a ticket line (allow_unmatched=true)" },
        ],
      },
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<FillsPage />);
    await waitFor(() => {
      expect((getByTestId("fills-ticket-select") as HTMLSelectElement).value).toBe(
        "tkt-20260519-aaaa",
      );
    });
    fireEvent.change(getByTestId("fills-manual-symbol-0"), { target: { value: "QQQ" } });
    fireEvent.change(getByTestId("fills-manual-shares-0"), { target: { value: "1" } });
    fireEvent.change(getByTestId("fills-manual-price-0"), { target: { value: "100" } });
    fireEvent.change(getByTestId("fills-manual-filled-at-0"), {
      target: { value: "2026-05-30T13:31:42" },
    });
    fireEvent.click(getByTestId("fills-manual-submit"));
    await waitFor(() => {
      expect(getByTestId("fills-row-error-0")).toHaveTextContent("allow_unmatched");
    });
  });

  it("uses same-origin /api path (no 127.0.0.1)", async () => {
    const state: MockState = {
      ticketList: TICKET_LIST,
      fillsList: EMPTY_FILLS,
      submitResponse: SUBMIT_RESPONSE,
      submitStatus: 200,
      posts: [],
    };
    const fetchMock = buildFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<FillsPage />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    for (const post of state.posts) {
      expect(post.url).not.toMatch(/127\.0\.0\.1/);
      expect(post.url.startsWith("/api/")).toBe(true);
    }
  });
});
