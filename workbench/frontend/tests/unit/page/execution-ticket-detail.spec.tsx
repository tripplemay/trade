// @vitest-environment happy-dom
/**
 * B023 F003 — Ticket detail viewer (read-only): renders metadata +
 * Markdown body fetched via /api/execution/tickets/{ticket_id}.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import type { components } from "@/types/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ ticket_id: "tkt-20260519-abcdef01" }),
}));
vi.mock("@/components/markdown/MarkdownRenderer", () => ({
  __esModule: true,
  default: ({ body }: { body: string }) => (
    <div data-testid="markdown-mock">{body.slice(0, 80)}</div>
  ),
}));

import TicketDetailPage from "@/app/(protected)/execution/ticket/[ticket_id]/page";

type TicketDetail = components["schemas"]["TicketDetail"];

const DISCLAIMER = "research-only; this is a manual review checklist, not a trading instruction";

const DETAIL: TicketDetail = {
  id: "tkt-20260519-abcdef01",
  ticket_date: "2026-05-19",
  snapshot_id: "snap-x",
  target_positions_id: "tp-2026-05-19",
  markdown_path: "docs/runs/2026-05-19/order-ticket-tkt-20260519-abcdef01.md",
  status: "executed",
  created_at: "2026-05-19T10:00:00",
  executed_at: "2026-05-19T17:30:00",
  markdown_body: `# Order Ticket — 2026-05-19\n\n_Disclaimer: ${DISCLAIMER}._`,
  disclaimer: DISCLAIMER,
};

function buildFetch(body: TicketDetail): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url ?? input.toString();
    if (url.startsWith("/api/execution/tickets/")) {
      return new Response(JSON.stringify(body), {
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

describe("TicketDetailPage (B023 F003)", () => {
  it("renders metadata + Markdown body for the requested ticket", async () => {
    vi.stubGlobal("fetch", buildFetch(DETAIL));
    const { getByTestId } = render(<TicketDetailPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-detail-state")).toHaveTextContent(/executed/);
    });
    expect(getByTestId("ticket-detail-meta-card")).toHaveTextContent(DETAIL.markdown_path);
    expect(getByTestId("ticket-detail-meta-card")).toHaveTextContent(DETAIL.snapshot_id);
    expect(getByTestId("markdown-mock")).toHaveTextContent("Order Ticket");
  });

  it("uses same-origin /api path", async () => {
    const fetchMock = buildFetch(DETAIL);
    vi.stubGlobal("fetch", fetchMock);
    render(<TicketDetailPage />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const [arg] of calls) {
      const url = typeof arg === "string" ? arg : (arg as Request | URL).toString();
      expect(url).not.toMatch(/127\.0\.0\.1/);
      expect(url.startsWith("/api/")).toBe(true);
    }
  });
});
