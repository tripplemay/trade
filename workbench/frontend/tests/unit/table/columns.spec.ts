/**
 * Snapshot the 5 reusable formatters on a fixed sample so a future
 * format drift (currency symbol changes / decimal precision changes /
 * locale tweaks) surfaces as a deliberate snapshot update rather than
 * a silent visual regression on every workbench table.
 */
import { describe, expect, it } from "vitest";

import {
  basisPointsColumn,
  currencyColumn,
  dateColumn,
  formatBasisPoints,
  formatCurrency,
  formatDate,
  formatPercent,
  formatWeight,
  percentColumn,
  weightColumn,
} from "@/components/table/columns";

const DATE_SAMPLES: Array<unknown> = [
  "2026-05-17",
  new Date("2025-12-31T00:00:00Z"),
  null,
  "not-a-date",
];

const NUMERIC_SAMPLES: Array<unknown> = [0, 1.5, -2.345, 1234.5, null, "1.5", Number.NaN, ""];

describe("formatDate", () => {
  it("matches snapshot on a fixed sample", () => {
    expect(DATE_SAMPLES.map((v) => formatDate(v, "en-US"))).toMatchInlineSnapshot(`
      [
        "05/17/2026",
        "12/31/2025",
        "—",
        "—",
      ]
    `);
  });
});

describe("formatCurrency", () => {
  it("matches snapshot on a fixed sample", () => {
    expect(NUMERIC_SAMPLES.map((v) => formatCurrency(v, "USD", "en-US"))).toMatchInlineSnapshot(`
      [
        "$0.00",
        "$1.50",
        "-$2.35",
        "$1,234.50",
        "—",
        "$1.50",
        "—",
        "—",
      ]
    `);
  });
});

describe("formatPercent", () => {
  it("matches snapshot on a fixed sample", () => {
    expect(NUMERIC_SAMPLES.map((v) => formatPercent(v))).toMatchInlineSnapshot(`
      [
        "0.00%",
        "150.00%",
        "-234.50%",
        "123450.00%",
        "—",
        "150.00%",
        "—",
        "—",
      ]
    `);
  });
});

describe("formatBasisPoints", () => {
  it("matches snapshot on a fixed sample", () => {
    expect(NUMERIC_SAMPLES.map((v) => formatBasisPoints(v))).toMatchInlineSnapshot(`
      [
        "0.0 bps",
        "1.5 bps",
        "-2.3 bps",
        "1234.5 bps",
        "—",
        "1.5 bps",
        "—",
        "—",
      ]
    `);
  });
});

describe("formatWeight", () => {
  it("matches snapshot on a fixed sample", () => {
    expect(NUMERIC_SAMPLES.map((v) => formatWeight(v))).toMatchInlineSnapshot(`
      [
        "0.0%",
        "150.0%",
        "-234.5%",
        "123450.0%",
        "—",
        "150.0%",
        "—",
        "—",
      ]
    `);
  });
});

describe("column helpers", () => {
  interface Row {
    date: string;
    amount: number;
    pct: number;
    bps: number;
    weight: number;
  }

  it("dateColumn wires field + right-align numeric class", () => {
    const col = dateColumn<Row>({ field: "date" });
    expect(col.field).toBe("date");
    expect(col.cellClass).toContain("ag-right-aligned-cell");
    expect(col.cellClass).toContain("numeric");
    expect(col.headerClass).toBe("ag-right-aligned-header");
    expect(typeof col.valueFormatter).toBe("function");
  });

  it("currencyColumn formatter uses the supplied currency", () => {
    const col = currencyColumn<Row>({ field: "amount", currency: "EUR" });
    const fmt = col.valueFormatter;
    if (typeof fmt !== "function") throw new Error("valueFormatter missing");
    expect(fmt({ value: 12.5 } as never)).toMatch(/€|EUR/);
  });

  it("percentColumn respects the digits override", () => {
    const col = percentColumn<Row>({ field: "pct", digits: 4 });
    const fmt = col.valueFormatter;
    if (typeof fmt !== "function") throw new Error("valueFormatter missing");
    expect(fmt({ value: 0.123456 } as never)).toBe("12.3456%");
  });

  it("basisPointsColumn renders 'bps' suffix at default precision", () => {
    const col = basisPointsColumn<Row>({ field: "bps" });
    const fmt = col.valueFormatter;
    if (typeof fmt !== "function") throw new Error("valueFormatter missing");
    expect(fmt({ value: 7.25 } as never)).toBe("7.3 bps");
  });

  it("weightColumn defaults to 1 fractional digit", () => {
    const col = weightColumn<Row>({ field: "weight" });
    const fmt = col.valueFormatter;
    if (typeof fmt !== "function") throw new Error("valueFormatter missing");
    expect(fmt({ value: 0.255 } as never)).toBe("25.5%");
  });
});
