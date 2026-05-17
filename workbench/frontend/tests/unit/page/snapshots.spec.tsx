// @vitest-environment happy-dom
/**
 * B022 F011 — Snapshots page renders the list and streams refresh
 * events through the SSE helper.
 *
 * AG Grid + Radix Dialog + sonner are mocked; the SSE helper is
 * replaced with a synchronous mock that calls onEvent with two events
 * (stage:fetch + stage:complete) so the page's "complete → toast +
 * refetch list" path is exercised without a real ReadableStream.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import type { components } from "@/types/api";

const refreshEvents: Array<Record<string, unknown>> = [
  { stage: "fetch", detail: "stage one", ts: "2026-05-17T00:00:00Z" },
  { stage: "complete", detail: "all done", ts: "2026-05-17T00:00:01Z" },
];

const successToast = vi.fn();
const errorToast = vi.fn();

vi.mock("ag-grid-react", () => ({
  AgGridReact: ({ rowData }: { rowData?: unknown[] }) => (
    <div data-testid="ag-grid-mock">rows={rowData?.length ?? 0}</div>
  ),
}));
vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: vi.fn() },
  themeQuartz: { withPart: () => ({}) },
  colorSchemeDark: {},
}));

vi.mock("sonner", () => ({
  toast: {
    success: (message: string) => successToast(message),
    error: (message: string) => errorToast(message),
  },
}));
vi.mock("@/components/ui/sonner", () => ({
  Toaster: () => null,
}));
// Bypass Radix Dialog (happy-dom can't host its portal cleanly).
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
}));

vi.mock("@/lib/sse-stream", () => ({
  streamSse: vi.fn(async (_url, _opts, onEvent: (e: Record<string, unknown>) => void) => {
    for (const event of refreshEvents) {
      onEvent(event);
    }
  }),
}));

import SnapshotsPage from "@/app/(protected)/snapshots/page";

const LIST_INITIAL: components["schemas"]["SnapshotListResponse"] = {
  snapshots: [
    {
      id: "snap-1",
      as_of_date: "2026-05-15",
      created_at: "2026-05-15T00:00:00",
      quality_status: "ok",
      file_path: "data/public-cache/snap-1/manifest.json",
    },
  ],
};

const LIST_AFTER: components["schemas"]["SnapshotListResponse"] = {
  snapshots: [
    ...LIST_INITIAL.snapshots,
    {
      id: "snap-2",
      as_of_date: "2026-05-17",
      created_at: "2026-05-17T00:00:00",
      quality_status: "ok",
      file_path: "data/public-cache/snap-2/manifest.json",
    },
  ],
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  successToast.mockClear();
  errorToast.mockClear();
});

describe("SnapshotsPage (B022 F011)", () => {
  it("renders the list state and DataTable rows once the fetch resolves", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(LIST_INITIAL)) as unknown as typeof fetch,
    );
    const { getByTestId } = render(<SnapshotsPage />);
    await waitFor(() => {
      expect(getByTestId("snapshots-state")).toHaveTextContent(/1 snapshots/);
      expect(getByTestId("ag-grid-mock")).toHaveTextContent(/rows=1/);
    });
  });

  it("clicking Refresh streams SSE events + toast success + refetches list", async () => {
    let callCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        callCount += 1;
        return jsonResponse(callCount === 1 ? LIST_INITIAL : LIST_AFTER);
      }) as unknown as typeof fetch,
    );
    const { getByTestId } = render(<SnapshotsPage />);
    await waitFor(() => {
      expect(getByTestId("snapshots-refresh")).not.toBeDisabled();
    });
    fireEvent.click(getByTestId("snapshots-refresh"));
    await waitFor(() => {
      // Two stages should now have streamed into the modal list.
      expect(getByTestId("snapshot-event-fetch")).toBeInTheDocument();
      expect(getByTestId("snapshot-event-complete")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(successToast).toHaveBeenCalledWith("Snapshot refreshed");
      expect(getByTestId("snapshots-state")).toHaveTextContent(/2 snapshots/);
    });
  });
});
