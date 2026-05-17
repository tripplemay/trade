"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  DataTable,
  type DataTableHandle,
  dateColumn,
} from "@/components/table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Toaster } from "@/components/ui/sonner";
import { streamSse, type SseEvent } from "@/lib/sse-stream";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type SnapshotSummary = components["schemas"]["SnapshotSummary"];
type SnapshotListResponse = components["schemas"]["SnapshotListResponse"];

const LIST_URL = "/api/snapshots";
const REFRESH_URL = "/api/snapshots/refresh";

const COLUMNS: ColDef<SnapshotSummary>[] = [
  { field: "id", headerName: "Snapshot id", flex: 1 },
  dateColumn<SnapshotSummary>({ field: "as_of_date", headerName: "As-of", width: 130 }),
  { field: "quality_status", headerName: "Quality", width: 120 },
  { field: "file_path", headerName: "Manifest", flex: 2 },
];

interface StageEvent {
  job_id?: string;
  stage?: string;
  detail?: string;
  ts?: string;
}

export default function SnapshotsPage() {
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [refreshOpen, setRefreshOpen] = useState(false);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const tableRef = useRef<DataTableHandle>(null);

  const loadList = useCallback(async () => {
    try {
      const response = await fetch(LIST_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as SnapshotListResponse;
      setSnapshots(data.snapshots);
      setListError(null);
    } catch (reason: unknown) {
      setListError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const handleRefresh = async () => {
    setEvents([]);
    setRefreshError(null);
    setRefreshing(true);
    setRefreshOpen(true);
    let sawComplete = false;
    try {
      await streamSse(REFRESH_URL, {}, (raw: SseEvent) => {
        const event = raw as StageEvent;
        setEvents((prev) => [...prev, event]);
        if (event.stage === "complete") sawComplete = true;
        if (event.stage === "error") {
          setRefreshError(event.detail ?? "unknown");
        }
      });
      if (sawComplete) {
        toast.success("Snapshot refreshed");
        await loadList();
      } else {
        toast.error("Refresh ended without a complete event");
      }
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : String(reason);
      setRefreshError(message);
      toast.error(`Refresh failed: ${message}`);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section data-testid="page-snapshots" className="space-y-6">
      <Toaster />
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Snapshots</h1>
        <div className="flex items-center gap-2">
          <span data-testid="snapshots-state" className="text-xs text-muted-foreground">
            {listError ? `unreachable: ${listError}` : `${snapshots.length} snapshots`}
          </span>
          <Button
            data-testid="snapshots-refresh"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh snapshot"}
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Public snapshot inventory</CardTitle>
          <CardDescription>
            Rows mirror the SnapshotMeta table; Refresh streams a synthetic 5-stage progress
            modal until the real <code>scripts/refresh_public_snapshot</code> subprocess wires
            in (B023).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<SnapshotSummary>
            ref={tableRef}
            rowData={snapshots}
            columnDefs={COLUMNS}
            height={420}
          />
        </CardContent>
      </Card>

      <Dialog open={refreshOpen} onOpenChange={setRefreshOpen}>
        <DialogContent data-testid="snapshots-refresh-modal">
          <DialogHeader>
            <DialogTitle>Refreshing snapshot…</DialogTitle>
            <DialogDescription>
              Stages stream via SSE; the modal stays open until you close it.
            </DialogDescription>
          </DialogHeader>
          <ul className="space-y-1 text-xs">
            {events.map((event, i) => (
              <li
                key={`${event.ts ?? ""}-${i}`}
                data-testid={`snapshot-event-${event.stage}`}
                className="flex items-start gap-2"
              >
                <span className="font-semibold uppercase">{event.stage}</span>
                <span className="text-muted-foreground">{event.detail}</span>
              </li>
            ))}
          </ul>
          {refreshError ? (
            <p data-testid="snapshots-refresh-error" className="text-xs text-destructive">
              {refreshError}
            </p>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}
