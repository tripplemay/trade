/**
 * Reusable AG Grid column definition helpers (B022 F005).
 *
 * Each helper returns a partial `ColDef<T>` you can spread into a
 * `columnDefs` entry; pages combine the helpers with their own
 * field / headerName overrides. The five surfaces here cover every
 * tabular type the workbench renders: dates, currency, percentages,
 * basis points, and weights. Each formatter:
 *
 *  * right-aligns the cell ("financial tables always read right-edge")
 *  * adds the `.numeric` className so JetBrains Mono + tabular-nums
 *    kick in (defined in src/styles/globals.css, F001 §financial pre-config)
 *  * accepts `null` / `undefined` and returns "—" so empty rows don't
 *    shift column width or look like literal zeros
 *
 * Pure-functional formatters are exported alongside so unit tests can
 * snapshot the output without instantiating AG Grid.
 */

import type { ColDef, ColDefField } from "ag-grid-community";

const EMPTY = "—";

function isMissing(value: unknown): value is null | undefined | "" {
  return value === null || value === undefined || value === "";
}

const RIGHT_ALIGN_CLASS = "ag-right-aligned-cell numeric";

const NUMERIC_HEADER_CLASS = "ag-right-aligned-header";

/* ----- Pure formatters (exported for tests + downstream consumers). ----- */

export function formatDate(value: unknown, locale = "en-US"): string {
  if (isMissing(value)) return EMPTY;
  const date = value instanceof Date ? value : new Date(String(value));
  if (Number.isNaN(date.getTime())) return EMPTY;
  // Force UTC so a backend ISO date like "2026-05-17" doesn't slide
  // back to the 16th when the user's browser sits west of UTC. Date
  // columns in the workbench display dates only (no time component),
  // so the TZ shift would be a silent off-by-one in the table view.
  return date.toLocaleDateString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC",
  });
}

export function formatCurrency(
  value: unknown,
  currency: string = "USD",
  locale: string = "en-US",
): string {
  if (isMissing(value)) return EMPTY;
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return EMPTY;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

/**
 * Treats `value` as a ratio (0.1234 → "12.34%"). Pass `digits` for a
 * different precision; the default matches the workbench's "two-decimal
 * percentages everywhere" convention.
 */
export function formatPercent(value: unknown, digits = 2): string {
  if (isMissing(value)) return EMPTY;
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return EMPTY;
  return `${(num * 100).toFixed(digits)}%`;
}

/** Renders a raw basis-points value (e.g. 12.5 → "12.5 bps"). */
export function formatBasisPoints(value: unknown, digits = 1): string {
  if (isMissing(value)) return EMPTY;
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return EMPTY;
  return `${num.toFixed(digits)} bps`;
}

/**
 * Allocation weight: same numeric content as `formatPercent` but
 * tightens precision to match the recommendation card's "AA target
 * 25.0%" reading (vs "25.00%", which crowds the column).
 */
export function formatWeight(value: unknown, digits = 1): string {
  return formatPercent(value, digits);
}

/* ----- ColDef helpers. ----- */

interface BaseOpts<T> {
  field: ColDefField<T>;
  headerName?: string;
  width?: number;
  flex?: number;
}

function headerLabel<T>(opts: BaseOpts<T>): string {
  return opts.headerName ?? String(opts.field);
}

export function dateColumn<T>(opts: BaseOpts<T> & { locale?: string }): ColDef<T> {
  return {
    field: opts.field,
    headerName: headerLabel(opts),
    width: opts.width,
    flex: opts.flex,
    cellClass: RIGHT_ALIGN_CLASS,
    headerClass: NUMERIC_HEADER_CLASS,
    valueFormatter: (params) => formatDate(params.value, opts.locale),
  };
}

export function currencyColumn<T>(
  opts: BaseOpts<T> & { currency?: string; locale?: string },
): ColDef<T> {
  return {
    field: opts.field,
    headerName: headerLabel(opts),
    width: opts.width,
    flex: opts.flex,
    cellClass: RIGHT_ALIGN_CLASS,
    headerClass: NUMERIC_HEADER_CLASS,
    valueFormatter: (params) =>
      formatCurrency(params.value, opts.currency ?? "USD", opts.locale),
  };
}

export function percentColumn<T>(opts: BaseOpts<T> & { digits?: number }): ColDef<T> {
  return {
    field: opts.field,
    headerName: headerLabel(opts),
    width: opts.width,
    flex: opts.flex,
    cellClass: RIGHT_ALIGN_CLASS,
    headerClass: NUMERIC_HEADER_CLASS,
    valueFormatter: (params) => formatPercent(params.value, opts.digits ?? 2),
  };
}

export function basisPointsColumn<T>(opts: BaseOpts<T> & { digits?: number }): ColDef<T> {
  return {
    field: opts.field,
    headerName: headerLabel(opts),
    width: opts.width,
    flex: opts.flex,
    cellClass: RIGHT_ALIGN_CLASS,
    headerClass: NUMERIC_HEADER_CLASS,
    valueFormatter: (params) => formatBasisPoints(params.value, opts.digits ?? 1),
  };
}

export function weightColumn<T>(opts: BaseOpts<T> & { digits?: number }): ColDef<T> {
  return {
    field: opts.field,
    headerName: headerLabel(opts),
    width: opts.width,
    flex: opts.flex,
    cellClass: RIGHT_ALIGN_CLASS,
    headerClass: NUMERIC_HEADER_CLASS,
    valueFormatter: (params) => formatWeight(params.value, opts.digits ?? 1),
  };
}
