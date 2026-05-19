"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toaster } from "@/components/ui/sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { components } from "@/types/api";

type TicketListResponse = components["schemas"]["TicketListResponse"];
type FillSubmitResponse = components["schemas"]["FillSubmitResponse"];
type FillsListResponse = components["schemas"]["FillsListResponse"];
type FillRowIn = components["schemas"]["FillRowIn"];

const TICKETS_URL = "/api/execution/tickets";
const FILLS_URL = "/api/execution/fills";
const FILLS_CSV_URL = "/api/execution/fills/csv";

interface ManualRow {
  order_seq: string;
  symbol: string;
  side: "buy" | "sell";
  shares: string;
  fill_price: string;
  commission: string;
  fees: string;
  currency: string;
  filled_at: string;
  notes: string;
}

const EMPTY_MANUAL_ROW: ManualRow = {
  order_seq: "",
  symbol: "",
  side: "buy",
  shares: "",
  fill_price: "",
  commission: "0",
  fees: "0",
  currency: "USD",
  filled_at: "",
  notes: "",
};

type RowError = { row: number; error: string };

function manualRowToFill(row: ManualRow, index: number): { fill: FillRowIn | null; error?: RowError } {
  const errors: string[] = [];
  if (!row.symbol.trim()) errors.push("symbol required");
  const sharesNum = Number(row.shares);
  if (!Number.isFinite(sharesNum) || sharesNum <= 0) errors.push("shares must be > 0");
  const priceNum = Number(row.fill_price);
  if (!Number.isFinite(priceNum) || priceNum <= 0) errors.push("fill_price must be > 0");
  if (!row.filled_at.trim()) errors.push("filled_at required (ISO date-time)");
  if (errors.length > 0) {
    return { fill: null, error: { row: index, error: errors.join("; ") } };
  }
  const order_seq = row.order_seq.trim() ? Number(row.order_seq) : null;
  return {
    fill: {
      order_seq: order_seq != null && Number.isFinite(order_seq) ? order_seq : null,
      symbol: row.symbol.trim().toUpperCase(),
      side: row.side,
      shares: sharesNum,
      fill_price: priceNum,
      commission: Number(row.commission) || 0,
      fees: Number(row.fees) || 0,
      currency: row.currency.trim().toUpperCase() || "USD",
      filled_at: row.filled_at,
      notes: row.notes.trim() || null,
    },
  };
}

export default function FillsPage() {
  const [ticketId, setTicketId] = useState("");
  const [tickets, setTickets] = useState<TicketListResponse["items"]>([]);
  const [fills, setFills] = useState<FillsListResponse["items"]>([]);
  const [manualRows, setManualRows] = useState<ManualRow[]>([{ ...EMPTY_MANUAL_ROW }]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [allowUnmatched, setAllowUnmatched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [preview, setPreview] = useState<FillSubmitResponse | null>(null);
  const [rowErrors, setRowErrors] = useState<RowError[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshTickets = useCallback(async () => {
    try {
      const response = await fetch(TICKETS_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()) as TicketListResponse;
      setTickets(payload.items);
      const firstActive =
        payload.items.find((t) => t.status === "generated") ?? payload.items[0];
      if (firstActive && !ticketId) setTicketId(firstActive.id);
      setLoadError(null);
    } catch (reason: unknown) {
      setLoadError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [ticketId]);

  useEffect(() => {
    void refreshTickets();
  }, [refreshTickets]);

  const refreshFills = useCallback(async (id: string) => {
    if (!id) {
      setFills([]);
      return;
    }
    try {
      const response = await fetch(
        `${FILLS_URL}?ticket_id=${encodeURIComponent(id)}`,
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()) as FillsListResponse;
      setFills(payload.items);
    } catch (reason: unknown) {
      setFills([]);
      setLoadError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    if (ticketId) void refreshFills(ticketId);
  }, [ticketId, refreshFills]);

  const handleManualSubmit = async () => {
    if (!ticketId) {
      toast.error("Pick a ticket first.");
      return;
    }
    const collected: FillRowIn[] = [];
    const errors: RowError[] = [];
    manualRows.forEach((row, index) => {
      if (
        !row.symbol &&
        !row.shares &&
        !row.fill_price &&
        !row.filled_at
      ) {
        return; // blank row, skipped
      }
      const result = manualRowToFill(row, index);
      if (result.fill) collected.push(result.fill);
      else if (result.error) errors.push(result.error);
    });
    setRowErrors(errors);
    if (errors.length > 0) {
      toast.error(`${errors.length} row(s) have errors`);
      return;
    }
    if (collected.length === 0) {
      toast.error("Add at least one fill row.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await fetch(FILLS_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          ticket_id: ticketId,
          fills: collected,
          allow_unmatched: allowUnmatched,
        }),
      });
      if (!response.ok) {
        const detail = await response.json();
        if (detail?.detail?.errors) {
          setRowErrors(detail.detail.errors);
          toast.error(`${detail.detail.errors.length} row(s) rejected by server`);
        } else {
          throw new Error(`HTTP ${response.status}: ${JSON.stringify(detail)}`);
        }
        return;
      }
      const payload = (await response.json()) as FillSubmitResponse;
      setPreview(payload);
      toast.success(
        `Inserted ${payload.inserted.length} fill(s); ${payload.unmatched_count} unmatched`,
      );
      setManualRows([{ ...EMPTY_MANUAL_ROW }]);
      await refreshFills(ticketId);
    } catch (reason: unknown) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCsvSubmit = async () => {
    if (!ticketId) {
      toast.error("Pick a ticket first.");
      return;
    }
    if (!csvFile) {
      toast.error("Select a CSV file first.");
      return;
    }
    setSubmitting(true);
    try {
      const form = new FormData();
      form.append("ticket_id", ticketId);
      form.append("allow_unmatched", String(allowUnmatched));
      form.append("csv_file", csvFile);
      const response = await fetch(FILLS_CSV_URL, { method: "POST", body: form });
      if (!response.ok) {
        const detail = await response.json();
        if (detail?.detail?.errors) {
          setRowErrors(detail.detail.errors);
          toast.error(`CSV has ${detail.detail.errors.length} bad row(s)`);
        } else {
          throw new Error(`HTTP ${response.status}: ${JSON.stringify(detail)}`);
        }
        return;
      }
      const payload = (await response.json()) as FillSubmitResponse;
      setPreview(payload);
      toast.success(
        `Inserted ${payload.inserted.length} fill(s); ${payload.unmatched_count} unmatched`,
      );
      setCsvFile(null);
      await refreshFills(ticketId);
    } catch (reason: unknown) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  };

  const updateManualRow = (index: number, patch: Partial<ManualRow>) => {
    setManualRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  };
  const addManualRow = () => setManualRows((prev) => [...prev, { ...EMPTY_MANUAL_ROW }]);
  const removeManualRow = (index: number) =>
    setManualRows((prev) => prev.filter((_, i) => i !== index));

  return (
    <section data-testid="page-fills" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Fill journal
          </h1>
          <p className="text-xs text-muted-foreground">
            Upload broker CSV or enter fills manually. The workbench records
            what you executed; it does not place orders.
          </p>
        </div>
        <span data-testid="fills-state" className="text-xs text-muted-foreground">
          {loadError ? `unreachable: ${loadError}` : `${fills.length} fill(s) on this ticket`}
        </span>
      </header>

      <Card data-testid="fills-ticket-card">
        <CardHeader>
          <CardTitle>Ticket</CardTitle>
          <CardDescription>
            Pick the ticket these fills belong to. Voided / executed tickets are read-only.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <select
            data-testid="fills-ticket-select"
            value={ticketId}
            onChange={(e) => setTicketId(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">— pick a ticket —</option>
            {tickets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.id} ({t.status} · {t.ticket_date})
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      <Card data-testid="fills-csv-card">
        <CardHeader>
          <CardTitle>CSV upload</CardTitle>
          <CardDescription>
            Generic / Schwab / IBKR formats auto-detected. Errors return per-row;
            the rest of the file is preserved for re-upload.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            type="file"
            accept=".csv,text/csv"
            data-testid="fills-csv-input"
            onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              data-testid="fills-allow-unmatched"
              checked={allowUnmatched}
              onChange={(e) => setAllowUnmatched(e.target.checked)}
            />
            Accept unmatched fills (order_seq missing)
          </label>
          <Button
            data-testid="fills-csv-submit"
            onClick={handleCsvSubmit}
            disabled={!csvFile || submitting}
          >
            {submitting ? "Uploading…" : "Upload CSV"}
          </Button>
        </CardContent>
      </Card>

      <Card data-testid="fills-manual-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Manual entry</CardTitle>
            <CardDescription>One row per fill. Validated client-side first.</CardDescription>
          </div>
          <Button
            type="button"
            variant="secondary"
            data-testid="fills-manual-add"
            onClick={addManualRow}
          >
            Add row
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">Seq</TableHead>
                <TableHead className="w-28">Symbol</TableHead>
                <TableHead className="w-20">Side</TableHead>
                <TableHead className="w-24 text-right">Shares</TableHead>
                <TableHead className="w-28 text-right">Price</TableHead>
                <TableHead className="w-48">Filled at (ISO)</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {manualRows.map((row, index) => (
                <TableRow key={index} data-testid={`fills-manual-row-${index}`}>
                  <TableCell>
                    <Input
                      data-testid={`fills-manual-seq-${index}`}
                      value={row.order_seq}
                      inputMode="numeric"
                      onChange={(e) => updateManualRow(index, { order_seq: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      data-testid={`fills-manual-symbol-${index}`}
                      value={row.symbol}
                      onChange={(e) => updateManualRow(index, { symbol: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <select
                      data-testid={`fills-manual-side-${index}`}
                      value={row.side}
                      onChange={(e) =>
                        updateManualRow(index, { side: e.target.value as "buy" | "sell" })
                      }
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    >
                      <option value="buy">buy</option>
                      <option value="sell">sell</option>
                    </select>
                  </TableCell>
                  <TableCell>
                    <Input
                      data-testid={`fills-manual-shares-${index}`}
                      value={row.shares}
                      inputMode="decimal"
                      onChange={(e) => updateManualRow(index, { shares: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      data-testid={`fills-manual-price-${index}`}
                      value={row.fill_price}
                      inputMode="decimal"
                      onChange={(e) => updateManualRow(index, { fill_price: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      data-testid={`fills-manual-filled-at-${index}`}
                      value={row.filled_at}
                      placeholder="2026-05-30T13:31:42"
                      onChange={(e) => updateManualRow(index, { filled_at: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      data-testid={`fills-manual-remove-${index}`}
                      onClick={() => removeManualRow(index)}
                    >
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Button
            data-testid="fills-manual-submit"
            onClick={handleManualSubmit}
            disabled={submitting}
          >
            {submitting ? "Saving…" : "Save fills"}
          </Button>
        </CardContent>
      </Card>

      {rowErrors.length > 0 ? (
        <Card data-testid="fills-row-errors-card" className="border-destructive/60">
          <CardHeader>
            <CardTitle>Row-level errors</CardTitle>
            <CardDescription>
              Fix the listed rows and resubmit. The other rows are preserved.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {rowErrors.map((e, i) => (
                <li
                  key={`${e.row}-${i}`}
                  data-testid={`fills-row-error-${e.row}`}
                  className="rounded-md border border-destructive/40 px-2 py-1"
                >
                  <strong>row {e.row}:</strong> {e.error}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {preview ? (
        <Card data-testid="fills-preview-card">
          <CardHeader>
            <CardTitle>Last insert</CardTitle>
            <CardDescription>
              {preview.inserted.length} row(s) accepted; {preview.unmatched_count} flagged
              as unmatched
              {preview.accepted_under_allow_unmatched ? " (override on)" : ""}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {preview.inserted.map((row) => (
                <li
                  key={row.id}
                  data-testid={`fills-preview-row-${row.id}`}
                  className="rounded-md border border-border/60 px-2 py-1 font-mono text-xs"
                >
                  {row.symbol} {row.side} {row.shares} @ {row.fill_price} ·{" "}
                  {row.matched ? "matched" : "unmatched"}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <Card data-testid="fills-history-card">
        <CardHeader>
          <CardTitle>Fills on this ticket</CardTitle>
          <CardDescription>
            Persisted journal rows. Reconcile in the journal-history view (F005).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {fills.length === 0 ? (
            <p data-testid="fills-history-empty" className="text-sm text-muted-foreground">
              No fills recorded for this ticket yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Seq</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead className="text-right">Shares</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Filled at</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {fills.map((row) => (
                  <TableRow key={row.id} data-testid={`fills-history-row-${row.id}`}>
                    <TableCell>{row.order_seq ?? "—"}</TableCell>
                    <TableCell className="font-mono">{row.symbol}</TableCell>
                    <TableCell>{row.side}</TableCell>
                    <TableCell className="text-right">{row.shares}</TableCell>
                    <TableCell className="text-right">{row.fill_price}</TableCell>
                    <TableCell>{row.source}</TableCell>
                    <TableCell>{new Date(row.filled_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Toaster />
    </section>
  );
}
