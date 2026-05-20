// @vitest-environment happy-dom
/**
 * B022 F012 — Backlog page renders the list and lets the user create a
 * new entry through the dialog (POST → toast.success → refetch).
 *
 * AG Grid + Radix Dialog + Select + sonner are mocked; the dialog
 * stub strips Radix's portal so happy-dom can find the input fields.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

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
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children, ...rest }: { children: React.ReactNode }) => (
    <div {...rest}>{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    onValueChange,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (value: string) => void;
  }) => (
    <select
      value={value ?? ""}
      onChange={(e) => onValueChange?.(e.target.value)}
      data-testid="select-mock"
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ children, value }: { children: React.ReactNode; value: string }) => (
    <option value={value}>{children}</option>
  ),
}));

import BacklogPage from "@/app/(protected)/backlog/page";

const LIST_INITIAL: components["schemas"]["BacklogListResponse"] = {
  entries: [
    {
      id: "BL-WB-INITIAL",
      title: "Investigate vol-target smoothing",
      description: "Track research notes.",
      priority: "high",
      status: "open",
      created_at: "2026-05-15T00:00:00",
      updated_at: "2026-05-15T00:00:00",
    },
  ],
};

const LIST_AFTER: components["schemas"]["BacklogListResponse"] = {
  entries: [
    ...LIST_INITIAL.entries,
    {
      id: "BL-WB-NEW",
      title: "Pilot research",
      description: "",
      priority: "medium",
      status: "open",
      created_at: "2026-05-17T00:00:00",
      updated_at: "2026-05-17T00:00:00",
    },
  ],
};

const CREATED: components["schemas"]["BacklogEntry"] = LIST_AFTER.entries[1]!;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  successToast.mockClear();
  errorToast.mockClear();
});

describe("BacklogPage (B022 F012)", () => {
  it("renders the state line + DataTable rows after fetch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(LIST_INITIAL)) as unknown as typeof fetch,
    );
    const { getByTestId } = renderWithIntl(<BacklogPage />);
    await waitFor(() => {
      expect(getByTestId("backlog-state")).toHaveTextContent(/1 entries/);
      expect(getByTestId("ag-grid-mock")).toHaveTextContent(/rows=1/);
    });
  });

  it("Add → form → submit → POST → toast.success → refetch", async () => {
    let listGetCount = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : (input as Request).url ?? input.toString();
        if (url === "/api/backlog" && (!init || init.method === undefined)) {
          listGetCount += 1;
          return jsonResponse(listGetCount === 1 ? LIST_INITIAL : LIST_AFTER);
        }
        if (url === "/api/backlog" && init?.method === "POST") {
          return jsonResponse(CREATED, 201);
        }
        return jsonResponse({}, 404);
      },
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const { getByTestId } = renderWithIntl(<BacklogPage />);
    await waitFor(() => {
      expect(getByTestId("backlog-state")).toHaveTextContent(/1 entries/);
    });
    fireEvent.click(getByTestId("backlog-add"));
    fireEvent.change(getByTestId("backlog-form-title"), {
      target: { value: "Pilot research" },
    });
    fireEvent.click(getByTestId("backlog-form-submit"));
    await waitFor(() => {
      expect(successToast).toHaveBeenCalledWith("Backlog entry created");
      expect(getByTestId("backlog-state")).toHaveTextContent(/2 entries/);
    });
  });

  it("submit with empty title surfaces a toast.error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(LIST_INITIAL)) as unknown as typeof fetch,
    );
    const { getByTestId } = renderWithIntl(<BacklogPage />);
    await waitFor(() => {
      expect(getByTestId("backlog-state")).toHaveTextContent(/1 entries/);
    });
    fireEvent.click(getByTestId("backlog-add"));
    fireEvent.click(getByTestId("backlog-form-submit"));
    expect(errorToast).toHaveBeenCalledWith("Title is required.");
  });
});
