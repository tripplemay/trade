// @vitest-environment happy-dom
/**
 * B023 F003 — Ticket page: list + generate + void + Markdown preview +
 * download. The Markdown renderer is stubbed so we focus on page-level
 * wiring (fetch lifecycle + button labels + status transitions). Per
 * F003 acceptance, the page must NOT carry any "execute / place order /
 * send to broker" labelled buttons — covered by the safety spec
 * tests/safety/no-execution-buttons.spec.ts.
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
vi.mock("@/components/markdown/MarkdownRenderer", () => ({
  __esModule: true,
  default: ({ body }: { body: string }) => (
    <div data-testid="markdown-mock">{body.slice(0, 80)}</div>
  ),
}));

import { toast } from "sonner";
import TicketPage from "@/app/(protected)/execution/ticket/page";

type TicketListResponse = components["schemas"]["TicketListResponse"];
type GenerateTicketResponse = components["schemas"]["GenerateTicketResponse"];

const DISCLAIMER = "research-only; this is a manual review checklist, not a trading instruction";

const GENERATED: GenerateTicketResponse = {
  id: "tkt-20260519-abcdef01",
  ticket_date: "2026-05-19",
  snapshot_id: "snap-x",
  target_positions_id: "tp-2026-05-19",
  markdown_path: "docs/runs/2026-05-19/order-ticket-tkt-20260519-abcdef01.md",
  status: "generated",
  created_at: "2026-05-19T10:00:00",
  executed_at: null,
  markdown_body: `# Order Ticket — 2026-05-19\n\n## Trades to place\n\n_Disclaimer: ${DISCLAIMER}._`,
  disclaimer: DISCLAIMER,
};

const VOID_SUMMARY: components["schemas"]["TicketSummary"] = {
  id: GENERATED.id,
  ticket_date: GENERATED.ticket_date,
  snapshot_id: GENERATED.snapshot_id,
  target_positions_id: GENERATED.target_positions_id,
  markdown_path: GENERATED.markdown_path,
  status: "voided",
  created_at: GENERATED.created_at,
  executed_at: null,
};

const EMPTY_LIST: TicketListResponse = { items: [], total: 0, limit: 20, offset: 0 };
const SUMMARY_ROW: components["schemas"]["TicketSummary"] = {
  id: GENERATED.id,
  ticket_date: GENERATED.ticket_date,
  snapshot_id: GENERATED.snapshot_id,
  target_positions_id: GENERATED.target_positions_id,
  markdown_path: GENERATED.markdown_path,
  status: "generated",
  created_at: GENERATED.created_at,
  executed_at: null,
};
const ONE_ITEM_LIST: TicketListResponse = {
  items: [SUMMARY_ROW],
  total: 1,
  limit: 20,
  offset: 0,
};

interface MockState {
  listSequence: TicketListResponse[];
  generateResponse: GenerateTicketResponse;
  voidResponse: components["schemas"]["TicketSummary"];
  detailResponse: GenerateTicketResponse;
  posts: { url: string; method: string }[];
}

function buildFetch(state: MockState): typeof fetch {
  let listIndex = 0;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string" ? input : (input as Request).url ?? input.toString();
    const method = init?.method ?? "GET";
    state.posts.push({ url, method });

    if (url === "/api/execution/tickets" && method === "GET") {
      const body = state.listSequence[Math.min(listIndex, state.listSequence.length - 1)];
      listIndex += 1;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url === "/api/execution/tickets" && method === "POST") {
      return new Response(JSON.stringify(state.generateResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.startsWith("/api/execution/tickets/") && url.endsWith("/void")) {
      return new Response(JSON.stringify(state.voidResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.startsWith("/api/execution/tickets/") && method === "GET") {
      return new Response(JSON.stringify(state.detailResponse), {
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

describe("TicketPage (B023 F003)", () => {
  it("renders empty state when no tickets are on file", async () => {
    const state: MockState = {
      listSequence: [EMPTY_LIST],
      generateResponse: GENERATED,
      voidResponse: VOID_SUMMARY,
      detailResponse: GENERATED,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-history-empty")).toBeInTheDocument();
    });
    expect(getByTestId("ticket-generate")).not.toBeDisabled();
    expect(getByTestId("ticket-void")).toBeDisabled();
    expect(getByTestId("ticket-download")).toBeDisabled();
  });

  it("Generate → POST → Markdown preview surfaces the disclaimer text", async () => {
    const state: MockState = {
      listSequence: [EMPTY_LIST, ONE_ITEM_LIST],
      generateResponse: GENERATED,
      voidResponse: VOID_SUMMARY,
      detailResponse: GENERATED,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-history-empty")).toBeInTheDocument();
    });
    fireEvent.click(getByTestId("ticket-generate"));
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(getByTestId("markdown-mock")).toHaveTextContent("Order Ticket");
    expect(getByTestId("ticket-state")).toHaveTextContent("1 tickets on file");
    // Void becomes enabled once a generated ticket exists.
    expect(getByTestId("ticket-void")).not.toBeDisabled();
  });

  it("Void POST flips status; the void button then disables for that ticket", async () => {
    const state: MockState = {
      listSequence: [
        ONE_ITEM_LIST,
        { ...ONE_ITEM_LIST, items: [{ ...SUMMARY_ROW, status: "voided" }] },
      ],
      generateResponse: GENERATED,
      voidResponse: VOID_SUMMARY,
      detailResponse: GENERATED,
      posts: [],
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-void")).not.toBeDisabled();
    });
    fireEvent.click(getByTestId("ticket-void"));
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(state.posts.some((p) => p.url.endsWith("/void") && p.method === "POST")).toBe(true);
    await waitFor(() => {
      expect(getByTestId("ticket-void")).toBeDisabled();
    });
  });

  it("uses same-origin /api path (no 127.0.0.1, no absolute URL)", async () => {
    const state: MockState = {
      listSequence: [EMPTY_LIST],
      generateResponse: GENERATED,
      voidResponse: VOID_SUMMARY,
      detailResponse: GENERATED,
      posts: [],
    };
    const fetchMock = buildFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<TicketPage />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    for (const post of state.posts) {
      expect(post.url).not.toMatch(/127\.0\.0\.1/);
      expect(post.url.startsWith("/api/")).toBe(true);
    }
  });
});
