"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { DataTable, dateColumn } from "@/components/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  const t = useTranslations("backlog");
  const tTable = useTranslations("backlog.table");
  const tForm = useTranslations("backlog.form");
  const tToast = useTranslations("backlog.toast");
  const tCommon = useTranslations("common");

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
      toast.error(tToast("titleRequired"));
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
      toast.success(isUpdate ? tToast("updated") : tToast("created"));
      setEditing(null);
      await loadList();
    } catch (reason: unknown) {
      toast.error(
        `${tToast("submitFailedPrefix")} ${reason instanceof Error ? reason.message : String(reason)}`,
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm(tToast("confirmDelete", { id }))) return;
      try {
        const response = await fetch(`${LIST_URL}/${encodeURIComponent(id)}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          const body = await response.text();
          throw new Error(`HTTP ${response.status}: ${body || response.statusText}`);
        }
        toast.success(`${tToast("deletedPrefix")}${id}`);
        await loadList();
      } catch (reason: unknown) {
        toast.error(
          `${tToast("deleteFailedPrefix")} ${reason instanceof Error ? reason.message : String(reason)}`,
        );
      }
    },
    [loadList, tToast],
  );

  const columns: ColDef<BacklogEntry>[] = useMemo(
    () => [
      { field: "id", headerName: tTable("columnId"), width: 180 },
      { field: "title", headerName: tTable("columnTitle"), flex: 2 },
      { field: "priority", headerName: tTable("columnPriority"), width: 110 },
      dateColumn<BacklogEntry>({
        field: "updated_at",
        headerName: tTable("columnUpdated"),
        width: 160,
      }),
      {
        headerName: tTable("columnActions"),
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
                {t("edit")}
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-2 py-0.5 text-xs text-destructive hover:bg-destructive/10"
                onClick={() => void handleDelete(row.id)}
                data-testid={`backlog-delete-${row.id}`}
              >
                {t("delete")}
              </button>
            </div>
          );
        },
      },
    ],
    [handleDelete, t, tTable],
  );

  return (
    <section data-testid="page-backlog" className="space-y-6">
      <Toaster />
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <div className="flex items-center gap-2">
          <span data-testid="backlog-state" className="text-xs text-muted-foreground">
            {error
              ? tCommon("unreachableWithError", { error })
              : t("stateCount", { total: entries.length, visible: filtered.length })}
          </span>
          <Select
            value={priorityFilter}
            onValueChange={(value: string) => setPriorityFilter(value as "all" | Priority)}
          >
            <SelectTrigger className="w-36" data-testid="backlog-priority-filter">
              <SelectValue placeholder={tTable("columnPriority")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("allPriorities")}</SelectItem>
              {PRIORITIES.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button data-testid="backlog-add" onClick={() => setEditing({ ...EMPTY_FORM })}>
            {t("addEntry")}
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{tTable("title")}</CardTitle>
          <CardDescription>
            {tTable("descriptionPrefix")}
            <code>{tTable("descriptionFile")}</code>
            {tTable("descriptionMidA")}
            <code>{tTable("descriptionCmd")}</code>
            {tTable("descriptionMidB")}
            {tTable("descriptionSuffix")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable<BacklogEntry> rowData={filtered} columnDefs={columns} height={420} />
        </CardContent>
      </Card>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent data-testid="backlog-edit-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.id ? tForm("titleEdit") : tForm("titleAdd")}</DialogTitle>
            <DialogDescription>
              {tForm("descriptionPrefix")}
              <code>{tForm("descriptionCmd")}</code>
              {tForm("descriptionSuffix")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>{tForm("fieldTitle")}</span>
              <Input
                data-testid="backlog-form-title"
                value={editing?.title ?? ""}
                onChange={(e) =>
                  setEditing((prev) => (prev ? { ...prev, title: e.target.value } : prev))
                }
              />
            </label>
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>{tForm("fieldDescription")}</span>
              <textarea
                data-testid="backlog-form-description"
                value={editing?.description ?? ""}
                onChange={(e) =>
                  setEditing((prev) => (prev ? { ...prev, description: e.target.value } : prev))
                }
                className={cn(
                  "min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                )}
              />
            </label>
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>{tForm("fieldPriority")}</span>
              <Select
                value={editing?.priority ?? "medium"}
                onValueChange={(value) =>
                  setEditing((prev) => (prev ? { ...prev, priority: value as Priority } : prev))
                }
              >
                <SelectTrigger data-testid="backlog-form-priority">
                  <SelectValue placeholder={tTable("columnPriority")} />
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
            <Button variant="outline" onClick={() => setEditing(null)} disabled={submitting}>
              {t("cancel")}
            </Button>
            <Button
              data-testid="backlog-form-submit"
              onClick={() => void handleSubmit()}
              disabled={submitting}
            >
              {submitting ? t("saving") : editing?.id ? t("save") : t("create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
