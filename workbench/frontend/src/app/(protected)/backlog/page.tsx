"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { DataTable, dateColumn } from "@/components/table";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import type { ColDef } from "ag-grid-community";
import type { components } from "@/types/api";

type BacklogEntry = components["schemas"]["BacklogEntry"];
type BacklogListResponse = components["schemas"]["BacklogListResponse"];

const LIST_URL = "/api/backlog";

const PRIORITIES = ["high", "medium", "low"] as const;
type Priority = (typeof PRIORITIES)[number];

interface FormState {
  id?: string;
  title: string;
  description: string;
  priority: Priority;
}

const EMPTY_FORM: FormState = { title: "", description: "", priority: "medium" };

export default function BacklogPage() {
  const [entries, setEntries] = useState<BacklogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<"all" | Priority>("all");
  const [editing, setEditing] = useState<FormState | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const response = await fetch(LIST_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as BacklogListResponse;
      setEntries(data.entries);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const filtered = useMemo(
    () =>
      priorityFilter === "all"
        ? entries
        : entries.filter((entry) => entry.priority === priorityFilter),
    [entries, priorityFilter],
  );

  const handleSubmit = async () => {
    if (!editing) return;
    if (!editing.title.trim()) {
      toast.error("Title is required.");
      return;
    }
    setSubmitting(true);
    try {
      const isUpdate = Boolean(editing.id);
      const url = isUpdate ? `${LIST_URL}/${encodeURIComponent(editing.id!)}` : LIST_URL;
      const response = await fetch(url, {
        method: isUpdate ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: editing.title,
          description: editing.description,
          priority: editing.priority,
        }),
      });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(`HTTP ${response.status}: ${body || response.statusText}`);
      }
      toast.success(isUpdate ? "Backlog entry updated" : "Backlog entry created");
      setEditing(null);
      await loadList();
    } catch (reason: unknown) {
      toast.error(
        `Submit failed: ${reason instanceof Error ? reason.message : String(reason)}`,
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm(`Delete backlog entry ${id}?`)) return;
      try {
        const response = await fetch(`${LIST_URL}/${encodeURIComponent(id)}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          const body = await response.text();
          throw new Error(`HTTP ${response.status}: ${body || response.statusText}`);
        }
        toast.success(`Deleted ${id}`);
        await loadList();
      } catch (reason: unknown) {
        toast.error(
          `Delete failed: ${reason instanceof Error ? reason.message : String(reason)}`,
        );
      }
    },
    [loadList],
  );

  const columns: ColDef<BacklogEntry>[] = useMemo(
    () => [
      { field: "id", headerName: "ID", width: 180 },
      { field: "title", headerName: "Title", flex: 2 },
      { field: "priority", headerName: "Priority", width: 110 },
      { field: "status", headerName: "Status", width: 110 },
      dateColumn<BacklogEntry>({ field: "updated_at", headerName: "Updated", width: 160 }),
      {
        headerName: "Actions",
        width: 180,
        cellRenderer: (params: { data?: BacklogEntry }) => {
          const row = params.data;
          if (!row) return null;
          return (
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="rounded-md border border-border px-2 py-0.5 text-xs hover:bg-accent"
                onClick={() =>
                  setEditing({
                    id: row.id,
                    title: row.title,
                    description: row.description,
                    priority: row.priority as Priority,
                  })
                }
                data-testid={`backlog-edit-${row.id}`}
              >
                Edit
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-2 py-0.5 text-xs text-destructive hover:bg-destructive/10"
                onClick={() => void handleDelete(row.id)}
                data-testid={`backlog-delete-${row.id}`}
              >
                Delete
              </button>
            </div>
          );
        },
      },
    ],
    [handleDelete],
  );

  return (
    <section data-testid="page-backlog" className="space-y-6">
      <Toaster />
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Backlog</h1>
        <div className="flex items-center gap-2">
          <span data-testid="backlog-state" className="text-xs text-muted-foreground">
            {error ? `unreachable: ${error}` : `${entries.length} entries (showing ${filtered.length})`}
          </span>
          <Select
            value={priorityFilter}
            onValueChange={(value: string) => setPriorityFilter(value as "all" | Priority)}
          >
            <SelectTrigger className="w-36" data-testid="backlog-priority-filter">
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All priorities</SelectItem>
              {PRIORITIES.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button data-testid="backlog-add" onClick={() => setEditing({ ...EMPTY_FORM })}>
            Add entry
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Entries</CardTitle>
          <CardDescription>
            Mirrors <code>backlog.json</code>. Mutations <strong>auto-commit</strong> through
            <code>chore(backlog): add|edit|delete &lt;id&gt;</code> so the durable record on disk
            stays in lockstep with the workbench&apos;s run-time view.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<BacklogEntry>
            rowData={filtered}
            columnDefs={columns}
            height={420}
          />
        </CardContent>
      </Card>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent data-testid="backlog-edit-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.id ? "Edit backlog entry" : "Add backlog entry"}</DialogTitle>
            <DialogDescription>
              Saving runs <code>git add backlog.json && git commit</code> on the server.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Title</span>
              <Input
                data-testid="backlog-form-title"
                value={editing?.title ?? ""}
                onChange={(e) =>
                  setEditing((prev) => (prev ? { ...prev, title: e.target.value } : prev))
                }
              />
            </label>
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Description</span>
              <textarea
                data-testid="backlog-form-description"
                value={editing?.description ?? ""}
                onChange={(e) =>
                  setEditing((prev) =>
                    prev ? { ...prev, description: e.target.value } : prev,
                  )
                }
                className={cn(
                  "min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                )}
              />
            </label>
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Priority</span>
              <Select
                value={editing?.priority ?? "medium"}
                onValueChange={(value) =>
                  setEditing((prev) =>
                    prev ? { ...prev, priority: value as Priority } : prev,
                  )
                }
              >
                <SelectTrigger data-testid="backlog-form-priority">
                  <SelectValue placeholder="Priority" />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditing(null)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              data-testid="backlog-form-submit"
              onClick={() => void handleSubmit()}
              disabled={submitting}
            >
              {submitting ? "Saving…" : editing?.id ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
