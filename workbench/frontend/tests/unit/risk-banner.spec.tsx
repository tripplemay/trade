// @vitest-environment happy-dom
/**
 * B023 F006 — RiskBanner renders the 3 fixture states (green / yellow /
 * red) and the Ticket page surfaces the normal/defensive radio when red.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

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

import { RiskBanner } from "@/components/risk/RiskBanner";
import TicketPage from "@/app/(protected)/execution/ticket/page";

type RiskPanelResponse = components["schemas"]["RiskPanelResponse"];
type GenerateTicketResponse = components["schemas"]["GenerateTicketResponse"];
type TicketListResponse = components["schemas"]["TicketListResponse"];

const GREEN: RiskPanelResponse = {
  state: "green",
  master_dd: 0.01,
  kill_switch_threshold: 0.15,
  per_sleeve_threshold: 0.08,
  kill_switch_triggered: false,
  per_sleeve_dd: [{ sleeve: "master", drawdown: 0.01 }],
  slippage_trend_3m_bps: 12.3,
  alternative_defensive_ticket: null,
};

const YELLOW: RiskPanelResponse = {
  ...GREEN,
  state: "yellow",
  master_dd: 0.09,
  per_sleeve_dd: [{ sleeve: "master", drawdown: 0.09 }],
};

const RED: RiskPanelResponse = {
  ...GREEN,
  state: "red",
  master_dd: 0.2,
  kill_switch_triggered: true,
  per_sleeve_dd: [{ sleeve: "master", drawdown: 0.2 }],
  alternative_defensive_ticket: {
    target_positions: [
      { symbol: "SGOV", target_weight: 1.0, rationale: "kill-switch tripped" },
    ],
    rationale: "Master drawdown 20% ≥ kill-switch threshold (15%).",
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RiskBanner standalone (B023 F006)", () => {
  it("green state — neutral banner, no defensive rationale", () => {
    const { getByTestId, queryByTestId } = render(<RiskBanner data={GREEN} noFetch />);
    const banner = getByTestId("risk-banner");
    expect(banner.getAttribute("data-state")).toBe("green");
    expect(banner).toHaveTextContent(/Risk: OK/);
    expect(queryByTestId("risk-banner-defensive-rationale")).toBeNull();
  });

  it("yellow state — advisory banner without defensive payload", () => {
    const { getByTestId, queryByTestId } = render(<RiskBanner data={YELLOW} noFetch />);
    const banner = getByTestId("risk-banner");
    expect(banner.getAttribute("data-state")).toBe("yellow");
    expect(banner).toHaveTextContent(/advisory threshold/);
    expect(queryByTestId("risk-banner-defensive-rationale")).toBeNull();
  });

  it("red state — surfaces the alternative defensive rationale", () => {
    const { getByTestId } = render(<RiskBanner data={RED} noFetch />);
    const banner = getByTestId("risk-banner");
    expect(banner.getAttribute("data-state")).toBe("red");
    expect(banner).toHaveTextContent(/kill-switch tripped/);
    expect(getByTestId("risk-banner-defensive-rationale")).toHaveTextContent(/15%/);
  });
});

interface TicketMockState {
  risk: RiskPanelResponse;
  ticketList: TicketListResponse;
  generateResponse: GenerateTicketResponse;
  posts: { url: string; method: string; body: unknown }[];
}

function buildTicketFetch(state: TicketMockState): typeof fetch {
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
    if (url === "/api/execution/risk-panel") {
      return new Response(JSON.stringify(state.risk), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url === "/api/execution/tickets" && method === "GET") {
      return new Response(JSON.stringify(state.ticketList), {
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
    if (url.startsWith("/api/execution/tickets/") && method === "GET") {
      return new Response(JSON.stringify(state.generateResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not-found", { status: 404 });
  }) as unknown as typeof fetch;
}

const EMPTY_TICKETS: TicketListResponse = { items: [], total: 0, limit: 20, offset: 0 };
const TICKET_RESPONSE: GenerateTicketResponse = {
  id: "tkt-20260519-test",
  ticket_date: "2026-05-19",
  snapshot_id: "snap-x",
  target_positions_id: "tp-x",
  markdown_path: "docs/runs/2026-05-19/order-ticket-tkt-20260519-test.md",
  status: "generated",
  created_at: "2026-05-19T10:00:00",
  executed_at: null,
  markdown_body: "# Order Ticket — defensive",
  disclaimer: "research-only; this is a manual review checklist, not a trading instruction",
};

describe("TicketPage F006 integration", () => {
  it("red risk banner surfaces the mode card and defaults to defensive", async () => {
    const state: TicketMockState = {
      risk: RED,
      ticketList: EMPTY_TICKETS,
      generateResponse: TICKET_RESPONSE,
      posts: [],
    };
    vi.stubGlobal("fetch", buildTicketFetch(state));
    const { getByTestId } = render(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-mode-card")).toBeInTheDocument();
    });
    const defensive = getByTestId("ticket-mode-defensive") as HTMLInputElement;
    expect(defensive.checked).toBe(true);
    // Banner reflects red state.
    expect(getByTestId("risk-banner").getAttribute("data-state")).toBe("red");
  });

  it("green risk banner hides the mode card; Generate POSTs defensive=false", async () => {
    const state: TicketMockState = {
      risk: GREEN,
      ticketList: EMPTY_TICKETS,
      generateResponse: TICKET_RESPONSE,
      posts: [],
    };
    vi.stubGlobal("fetch", buildTicketFetch(state));
    const { getByTestId, queryByTestId } = render(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-history-empty")).toBeInTheDocument();
    });
    expect(queryByTestId("ticket-mode-card")).toBeNull();
    fireEvent.click(getByTestId("ticket-generate"));
    await waitFor(() => {
      const postCall = state.posts.find(
        (p) => p.url === "/api/execution/tickets" && p.method === "POST",
      );
      expect(postCall).toBeTruthy();
      expect(postCall?.body).toEqual({ defensive: false });
    });
  });

  it("red risk banner: switching to normal still posts defensive=false", async () => {
    const state: TicketMockState = {
      risk: RED,
      ticketList: EMPTY_TICKETS,
      generateResponse: TICKET_RESPONSE,
      posts: [],
    };
    vi.stubGlobal("fetch", buildTicketFetch(state));
    const { getByTestId } = render(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-mode-card")).toBeInTheDocument();
    });
    fireEvent.click(getByTestId("ticket-mode-normal"));
    fireEvent.click(getByTestId("ticket-generate"));
    await waitFor(() => {
      const postCall = state.posts.find(
        (p) => p.url === "/api/execution/tickets" && p.method === "POST",
      );
      expect(postCall?.body).toEqual({ defensive: false });
    });
  });

  it("red risk banner: keeping defensive posts defensive=true", async () => {
    const state: TicketMockState = {
      risk: RED,
      ticketList: EMPTY_TICKETS,
      generateResponse: TICKET_RESPONSE,
      posts: [],
    };
    vi.stubGlobal("fetch", buildTicketFetch(state));
    const { getByTestId } = render(<TicketPage />);
    await waitFor(() => {
      expect(getByTestId("ticket-mode-card")).toBeInTheDocument();
    });
    // Mode auto-flipped to defensive on red — click Generate.
    fireEvent.click(getByTestId("ticket-generate"));
    await waitFor(() => {
      const postCall = state.posts.find(
        (p) => p.url === "/api/execution/tickets" && p.method === "POST",
      );
      expect(postCall?.body).toEqual({ defensive: true });
    });
  });
});
