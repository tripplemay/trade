"use client";

import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import {
  AllCommunityModule,
  type ColDef,
  type GridApi,
  ModuleRegistry,
  colorSchemeDark,
  themeQuartz,
} from "ag-grid-community";
import { AgGridReact, type AgGridReactProps } from "ag-grid-react";

import { cn } from "@/lib/utils";

// AG Grid v33+ requires explicit module registration. `AllCommunityModule`
// pulls in client-side row model + CSV export + every other community
// feature; we register once at module load so every DataTable instance
// shares the same Module Registry without paying the cost N times.
ModuleRegistry.registerModules([AllCommunityModule]);

// Zinc dark surface to match the workbench shell. Calling
// `.withPart(colorSchemeDark)` overlays the dark color scheme onto the
// quartz theme without re-styling individual cells.
const WORKBENCH_THEME = themeQuartz.withPart(colorSchemeDark);

export interface DataTableHandle {
  /**
   * Trigger a CSV download via AG Grid's built-in exporter. Returns
   * false if the grid API hasn't initialised yet (e.g. ref called
   * before mount); true once the export request has been dispatched.
   */
  exportCsv(filename?: string): boolean;
}

export interface DataTableProps<T> {
  rowData: T[];
  columnDefs: ColDef<T>[];
  /** Default column overrides; merged on top of the table-wide defaults. */
  defaultColDef?: ColDef<T>;
  height?: number | string;
  className?: string;
  /** Forwarded to the underlying AgGridReact for advanced cases (rare). */
  agGridProps?: Partial<AgGridReactProps<T>>;
}

/**
 * Generic AG Grid Community wrapper used by every workbench page that
 * renders tabular data. Defaults enforce the table conventions called
 * out in B022 F005:
 *
 *  * sortable + filterable + resizable per column
 *  * sticky header (AG Grid's default; called out explicitly here so
 *    consumers can't drop it without noticing)
 *  * Zinc dark theme that matches the rest of the shell
 *  * imperative `exportCsv()` ref so a parent toolbar button can hand
 *    off without subscribing to grid lifecycle events
 *
 * Virtualization is AG Grid's responsibility; this wrapper just passes
 * `rowData` straight through. A 1000-row payload renders ~30 DOM rows
 * (one viewport's worth) when mounted in a real browser.
 */
const DataTable = forwardRef(function DataTable<T>(
  { rowData, columnDefs, defaultColDef, height = 480, className, agGridProps }: DataTableProps<T>,
  ref: React.Ref<DataTableHandle>,
) {
  const gridApiRef = useRef<GridApi<T> | null>(null);

  useImperativeHandle(
    ref,
    (): DataTableHandle => ({
      exportCsv(filename) {
        const api = gridApiRef.current;
        if (!api) return false;
        api.exportDataAsCsv({ fileName: filename });
        return true;
      },
    }),
    [],
  );

  const mergedDefaultColDef = useMemo<ColDef<T>>(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
      ...defaultColDef,
    }),
    [defaultColDef],
  );

  return (
    <div
      data-testid="data-table"
      className={cn("w-full", className)}
      style={{ height, width: "100%" }}
    >
      <AgGridReact<T>
        theme={WORKBENCH_THEME}
        rowData={rowData}
        columnDefs={columnDefs}
        defaultColDef={mergedDefaultColDef}
        animateRows
        rowSelection={{ mode: "singleRow", enableClickSelection: true }}
        suppressCellFocus
        onGridReady={(event) => {
          gridApiRef.current = event.api;
        }}
        {...agGridProps}
      />
    </div>
  );
}) as <T>(
  props: DataTableProps<T> & { ref?: React.Ref<DataTableHandle> },
) => React.ReactElement;

export default DataTable;
