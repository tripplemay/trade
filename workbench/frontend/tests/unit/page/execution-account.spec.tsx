// @vitest-environment happy-dom
/**
 * B023 F002 — Account edit page: form validation + PUT round-trip +
 * empty-state seeding. Sonner is mocked so toasts are observable; the
 * page itself drives the fetch lifecycle.
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
import AccountEditPage from "@/app/(protected)/execution/account/page";

type AccountSnapshotPayload = components["schemas"]["AccountSnapshotPayload"];

const SAVED: AccountSnapshotPayload = {
  id: "snap-new-1",
  snapshot_at: "2026-05-18T11:00:00",
  cash: 60_000,
  base_currency: "USD",
  positions: [{ symbol: "B013", shares: 20, avg_cost: 500 }],
  source: "ui_edit",
};

interface MockState {
  latest: AccountSnapshotPayload | null;
  putBody: unknown | null;
  putResponse: AccountSnapshotPayload;
  putStatus: number;
}

function buildFetch(state: MockState): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string" ? input : (input as Request).url ?? input.toString();
    if (url === "/api/execution/account/latest") {
      return new Response(JSON.stringify(state.latest), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url === "/api/execution/account" && init?.method === "PUT") {
      state.putBody = init.body ? JSON.parse(init.body as string) : null;
      return new Response(JSON.stringify(state.putResponse), {
        status: state.putStatus,
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

describe("AccountEditPage (B023 F002)", () => {
  it("starts from empty state when no snapshot is on file", async () => {
    const state: MockState = {
      latest: null,
      putBody: null,
      putResponse: SAVED,
      putStatus: 200,
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<AccountEditPage />);
    await waitFor(() => {
      expect(getByTestId("account-latest-state")).toHaveTextContent(/no snapshot/);
    });
    expect((getByTestId("account-cash-input") as HTMLInputElement).value).toBe("0");
    expect((getByTestId("account-currency-input") as HTMLInputElement).value).toBe("USD");
  });

  it("PUT round-trip: fills form, submits, surfaces success toast + saved state", async () => {
    const state: MockState = {
      latest: null,
      putBody: null,
      putResponse: SAVED,
      putStatus: 200,
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<AccountEditPage />);
    await waitFor(() => {
      expect(getByTestId("account-latest-state")).toHaveTextContent(/no snapshot/);
    });

    fireEvent.change(getByTestId("account-cash-input"), { target: { value: "60000" } });
    fireEvent.change(getByTestId("account-symbol-0"), { target: { value: "B013" } });
    fireEvent.change(getByTestId("account-shares-0"), { target: { value: "20" } });
    fireEvent.change(getByTestId("account-avgcost-0"), { target: { value: "500" } });

    fireEvent.submit(getByTestId("account-edit-form"));
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(state.putBody).toEqual({
      cash: 60_000,
      base_currency: "USD",
      positions: [{ symbol: "B013", shares: 20, avg_cost: 500 }],
    });
    await waitFor(() => {
      expect(getByTestId("account-latest-state")).toHaveTextContent("snap-new-1");
    });
  });

  it("rejects duplicate symbols at the client (no PUT issued)", async () => {
    const state: MockState = {
      latest: null,
      putBody: null,
      putResponse: SAVED,
      putStatus: 200,
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<AccountEditPage />);
    await waitFor(() => {
      expect(getByTestId("account-latest-state")).toHaveTextContent(/no snapshot/);
    });

    fireEvent.change(getByTestId("account-cash-input"), { target: { value: "100" } });
    fireEvent.change(getByTestId("account-symbol-0"), { target: { value: "spy" } });
    fireEvent.change(getByTestId("account-shares-0"), { target: { value: "1" } });
    fireEvent.change(getByTestId("account-avgcost-0"), { target: { value: "100" } });
    fireEvent.click(getByTestId("account-add-row"));
    fireEvent.change(getByTestId("account-symbol-1"), { target: { value: "SPY" } });
    fireEvent.change(getByTestId("account-shares-1"), { target: { value: "1" } });
    fireEvent.change(getByTestId("account-avgcost-1"), { target: { value: "100" } });

    fireEvent.submit(getByTestId("account-edit-form"));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled();
    });
    expect(state.putBody).toBeNull();
  });

  it("rejects negative cash with an inline error message", async () => {
    const state: MockState = {
      latest: null,
      putBody: null,
      putResponse: SAVED,
      putStatus: 200,
    };
    vi.stubGlobal("fetch", buildFetch(state));
    const { getByTestId } = renderWithIntl(<AccountEditPage />);
    await waitFor(() => {
      expect(getByTestId("account-latest-state")).toHaveTextContent(/no snapshot/);
    });
    fireEvent.change(getByTestId("account-cash-input"), { target: { value: "-1" } });
    fireEvent.submit(getByTestId("account-edit-form"));
    await waitFor(() => {
      expect(getByTestId("account-cash-error")).toBeInTheDocument();
    });
    expect(state.putBody).toBeNull();
  });

  it("uses same-origin /api path (no 127.0.0.1, no absolute URL)", async () => {
    const state: MockState = {
      latest: null,
      putBody: null,
      putResponse: SAVED,
      putStatus: 200,
    };
    const fetchMock = buildFetch(state);
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<AccountEditPage />);
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
