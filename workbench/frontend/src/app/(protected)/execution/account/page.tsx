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

type AccountSnapshotPayload = components["schemas"]["AccountSnapshotPayload"];
type AccountUpdateRequest = components["schemas"]["AccountUpdateRequest"];
type PositionEntry = components["schemas"]["PositionEntry"];

const LATEST_URL = "/api/execution/account/latest";
const PUT_URL = "/api/execution/account";

interface PositionRow {
  symbol: string;
  shares: string;
  avg_cost: string;
}

const EMPTY_ROW: PositionRow = { symbol: "", shares: "", avg_cost: "" };

interface FormState {
  cash: string;
  base_currency: string;
  positions: PositionRow[];
}

function toFormState(snapshot: AccountSnapshotPayload | null): FormState {
  if (!snapshot) {
    return { cash: "0", base_currency: "USD", positions: [{ ...EMPTY_ROW }] };
  }
  return {
    cash: String(snapshot.cash ?? 0),
    base_currency: snapshot.base_currency ?? "USD",
    positions:
      (snapshot.positions ?? []).map((p) => ({
        symbol: p.symbol,
        shares: String(p.shares ?? 0),
        avg_cost: String(p.avg_cost ?? 0),
      })) ?? [],
  };
}

interface ValidationResult {
  ok: boolean;
  errors: Record<string, string>;
  payload: AccountUpdateRequest | null;
}

function validate(form: FormState): ValidationResult {
  const errors: Record<string, string> = {};

  const cash = Number(form.cash);
  if (!form.cash.trim() || Number.isNaN(cash)) {
    errors.cash = "Cash must be a number.";
  } else if (cash < 0) {
    errors.cash = "Cash cannot be negative.";
  }

  const base = form.base_currency.trim();
  if (base.length < 2) {
    errors.base_currency = "Base currency required (e.g. USD).";
  }

  const seenSymbols = new Set<string>();
  const positions: PositionEntry[] = [];
  form.positions.forEach((row, index) => {
    const symbol = row.symbol.trim().toUpperCase();
    const shares = Number(row.shares);
    const avgCost = Number(row.avg_cost);
    if (!symbol && !row.shares && !row.avg_cost) {
      return; // empty row, skipped
    }
    if (!symbol) {
      errors[`row-${index}-symbol`] = "Symbol required.";
      return;
    }
    if (seenSymbols.has(symbol)) {
      errors[`row-${index}-symbol`] = `Duplicate symbol: ${symbol}.`;
      return;
    }
    seenSymbols.add(symbol);
    if (Number.isNaN(shares) || shares < 0) {
      errors[`row-${index}-shares`] = "Shares must be ≥ 0.";
      return;
    }
    if (Number.isNaN(avgCost) || avgCost < 0) {
      errors[`row-${index}-avg_cost`] = "Avg cost must be ≥ 0.";
      return;
    }
    positions.push({ symbol, shares, avg_cost: avgCost });
  });

  // Weight-sum check per F002 acceptance: weights ≤ 1.0. Compute notional
  // weight per row against the total notional + cash to surface a UI
  // warning when the user has more than 100% of the account allocated.
  const totalNotional = positions.reduce((acc, p) => acc + p.shares * p.avg_cost, 0);
  const totalEquity = totalNotional + (cash || 0);
  if (totalEquity > 0) {
    let cumulativeWeight = 0;
    positions.forEach((p) => {
      cumulativeWeight += (p.shares * p.avg_cost) / totalEquity;
    });
    if (cumulativeWeight > 1.0001) {
      errors.weights = "Positions notional exceeds total equity — weights must be ≤ 1.0.";
    }
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors, payload: null };
  }
  return {
    ok: true,
    errors,
    payload: { cash, base_currency: base.toUpperCase(), positions },
  };
}

export default function AccountEditPage() {
  const [form, setForm] = useState<FormState>(() => toFormState(null));
  const [latest, setLatest] = useState<AccountSnapshotPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async () => {
    try {
      const response = await fetch(LATEST_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as AccountSnapshotPayload | null;
      setLatest(data);
      setForm(toFormState(data));
      setLoadError(null);
    } catch (reason: unknown) {
      setLoadError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const updateRow = (index: number, patch: Partial<PositionRow>) => {
    setForm((prev) => ({
      ...prev,
      positions: prev.positions.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  const addRow = () => {
    setForm((prev) => ({ ...prev, positions: [...prev.positions, { ...EMPTY_ROW }] }));
  };
  const removeRow = (index: number) => {
    setForm((prev) => ({
      ...prev,
      positions: prev.positions.filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validation = validate(form);
    setErrors(validation.errors);
    if (!validation.ok || validation.payload == null) {
      toast.error("Form has errors — fix them before saving.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await fetch(PUT_URL, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(validation.payload),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      const saved = (await response.json()) as AccountSnapshotPayload;
      setLatest(saved);
      setForm(toFormState(saved));
      toast.success(`Snapshot saved (id ${saved.id ?? "?"}).`);
    } catch (reason: unknown) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section data-testid="page-account-edit" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Account state</h1>
          <p className="text-xs text-muted-foreground">
            Edit cash + positions. Every save inserts a new snapshot (source = ui_edit) — old
            snapshots stay on file for reconciliation history.
          </p>
        </div>
        <span data-testid="account-latest-state" className="text-xs text-muted-foreground">
          {loadError
            ? `unreachable: ${loadError}`
            : latest
              ? `latest snapshot ${latest.id ?? ""} (${latest.source ?? ""})`
              : "no snapshot yet"}
        </span>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6" data-testid="account-edit-form">
        <Card>
          <CardHeader>
            <CardTitle>Cash</CardTitle>
            <CardDescription>Settled cash in the base currency.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="cash">
                Cash balance
              </label>
              <Input
                id="cash"
                data-testid="account-cash-input"
                value={form.cash}
                inputMode="decimal"
                onChange={(e) => setForm((p) => ({ ...p, cash: e.target.value }))}
              />
              {errors.cash ? (
                <p data-testid="account-cash-error" className="text-xs text-destructive">
                  {errors.cash}
                </p>
              ) : null}
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="base-currency">
                Base currency
              </label>
              <Input
                id="base-currency"
                data-testid="account-currency-input"
                value={form.base_currency}
                onChange={(e) => setForm((p) => ({ ...p, base_currency: e.target.value }))}
              />
              {errors.base_currency ? (
                <p className="text-xs text-destructive">{errors.base_currency}</p>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Positions</CardTitle>
              <CardDescription>
                One row per held symbol; shares × avg cost contributes to equity.
              </CardDescription>
            </div>
            <Button type="button" variant="secondary" onClick={addRow} data-testid="account-add-row">
              Add row
            </Button>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">Symbol</TableHead>
                  <TableHead className="w-32 text-right">Shares</TableHead>
                  <TableHead className="w-40 text-right">Avg cost</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {form.positions.map((row, index) => (
                  <TableRow key={index} data-testid={`account-position-row-${index}`}>
                    <TableCell>
                      <Input
                        value={row.symbol}
                        data-testid={`account-symbol-${index}`}
                        onChange={(e) => updateRow(index, { symbol: e.target.value })}
                      />
                      {errors[`row-${index}-symbol`] ? (
                        <p className="text-xs text-destructive">{errors[`row-${index}-symbol`]}</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right">
                      <Input
                        value={row.shares}
                        inputMode="decimal"
                        data-testid={`account-shares-${index}`}
                        onChange={(e) => updateRow(index, { shares: e.target.value })}
                      />
                      {errors[`row-${index}-shares`] ? (
                        <p className="text-xs text-destructive">{errors[`row-${index}-shares`]}</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right">
                      <Input
                        value={row.avg_cost}
                        inputMode="decimal"
                        data-testid={`account-avgcost-${index}`}
                        onChange={(e) => updateRow(index, { avg_cost: e.target.value })}
                      />
                      {errors[`row-${index}-avg_cost`] ? (
                        <p className="text-xs text-destructive">
                          {errors[`row-${index}-avg_cost`]}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        data-testid={`account-remove-${index}`}
                        onClick={() => removeRow(index)}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {errors.weights ? (
              <p data-testid="account-weight-error" className="mt-3 text-sm text-destructive">
                {errors.weights}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <div className="flex items-center gap-3">
          <Button type="submit" data-testid="account-save" disabled={submitting}>
            {submitting ? "Saving…" : "Save snapshot"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setForm(toFormState(latest));
              setErrors({});
            }}
            disabled={submitting}
          >
            Reset
          </Button>
        </div>
      </form>

      <Toaster />
    </section>
  );
}
