// @vitest-environment happy-dom
/**
 * B022 F005 §1 + §2 — wrapper plumbing + CSV export hook.
 *
 * ag-grid-react is mocked at module level so:
 *
 *  1. The 1000-row payload assertion runs without paying AG Grid's
 *     real init cost (which happy-dom mishandles around CSS-grid
 *     measurement; the mock keeps the assertion focused on the
 *     wrapper's responsibility — forwarding row data through).
 *  2. We can synthesise a `gridReady` event with a controlled `api`
 *     stub so the `exportCsv` ref method's call path can be observed
 *     end-to-end (parent → ref → AG Grid api).
 *
 * Real virtualization behaviour (≤30 DOM rows per viewport) is AG
 * Grid's own contract; Codex L2 exercises it on the live VM during
 * F014 in a real Chromium.
 */
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import type { ColDef } from "ag-grid-community";

interface MockGridProps {
  rowData?: unknown[];
  columnDefs?: unknown[];
  // Use a permissive `unknown` for `api` so the mock signature stays
  // assignment-compatible with the real AgGridReactProps.onGridReady
  // (which passes a full GridReadyEvent). The mock provides a narrower
  // shape at runtime; the test casts back when reading.
  onGridReady?: (e: { api: unknown }) => void;
}

let lastProps: MockGridProps = {};

const exportDataAsCsv = vi.fn();

vi.mock("ag-grid-react", () => ({
  AgGridReact: function MockAgGrid(props: MockGridProps) {
    lastProps = props;
    setTimeout(() => props.onGridReady?.({ api: { exportDataAsCsv } }), 0);
    return null;
  },
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: vi.fn() },
  themeQuartz: { withPart: () => ({}) },
  colorSchemeDark: {},
}));

import DataTable, { type DataTableHandle } from "@/components/table/DataTable";

afterEach(() => {
  cleanup();
  exportDataAsCsv.mockClear();
  lastProps = {};
});

interface Row {
  id: number;
  value: number;
}

function seed(rows: number): Row[] {
  return Array.from({ length: rows }, (_, i) => ({ id: i, value: i * 1.5 }));
}

describe("DataTable", () => {
  it("renders the host container and forwards rowData/columnDefs", () => {
    const data = seed(1000);
    const columnDefs: ColDef<Row>[] = [
      { field: "id", headerName: "ID" },
      { field: "value", headerName: "Value" },
    ];
    const { getByTestId } = render(<DataTable<Row> rowData={data} columnDefs={columnDefs} />);
    expect(getByTestId("data-table")).toBeInTheDocument();
    expect(lastProps.rowData).toBe(data);
    expect(lastProps.rowData?.length).toBe(1000);
    expect(lastProps.columnDefs).toBe(columnDefs);
  });

  it("exportCsv ref method forwards to api.exportDataAsCsv with the supplied filename", async () => {
    const ref = createRef<DataTableHandle>();
    const columnDefs: ColDef<Row>[] = [{ field: "id" }];
    render(<DataTable<Row> ref={ref} rowData={seed(10)} columnDefs={columnDefs} />);
    // Wait for the mocked onGridReady microtask to register the api.
    await new Promise((resolve) => setTimeout(resolve, 1));
    const dispatched = ref.current?.exportCsv("my-export.csv");
    expect(dispatched).toBe(true);
    expect(exportDataAsCsv).toHaveBeenCalledWith({ fileName: "my-export.csv" });
  });

  it("exportCsv returns false when the grid api has not initialised yet", () => {
    // Skip the mocked onGridReady microtask: call exportCsv synchronously
    // before the setTimeout fires.
    const ref = createRef<DataTableHandle>();
    const columnDefs: ColDef<Row>[] = [{ field: "id" }];
    render(<DataTable<Row> ref={ref} rowData={seed(10)} columnDefs={columnDefs} />);
    expect(ref.current?.exportCsv()).toBe(false);
    expect(exportDataAsCsv).not.toHaveBeenCalled();
  });
});
