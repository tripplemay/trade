"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import { RiskBanner, useRiskPanel } from "@/components/risk/RiskBanner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Toaster } from "@/components/ui/sonner";
import { workbenchFetch } from "@/lib/api-fetch";
import type { components } from "@/types/api";

type TicketSummary = components["schemas"]["TicketSummary"];
type TicketListResponse = components["schemas"]["TicketListResponse"];
type GenerateTicketResponse = components["schemas"]["GenerateTicketResponse"];

type TicketMode = "normal" | "defensive";

const LIST_URL = "/api/execution/tickets";
const GENERATE_URL = "/api/execution/tickets";

const STATUS_STYLES: Record<TicketSummary["status"], string> = {
  generated: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  executed: "border-green-700/60 bg-green-950/30 text-green-200",
  voided: "border-zinc-700/60 bg-zinc-900/40 text-muted-foreground",
};

function downloadMarkdown(filename: string, body: string): void {
  const blob = new Blob([body], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function TicketPage() {
  const t = useTranslations("execution.ticket");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");

  const [list, setList] = useState<TicketSummary[]>([]);
  const [latest, setLatest] = useState<GenerateTicketResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mode, setMode] = useState<TicketMode>("normal");
  const { data: risk } = useRiskPanel();
  // Default to defensive when kill-switch is triggered so the user has to
  // explicitly opt back into the normal ticket. The state flips only on
  // the first risk-panel read so a later refetch can't quietly drop a
  // user's manual selection.
  const [riskAcknowledged, setRiskAcknowledged] = useState(false);
  useEffect(() => {
    if (!riskAcknowledged && risk?.state === "red") {
      setMode("defensive");
      setRiskAcknowledged(true);
    }
  }, [risk, riskAcknowledged]);

  const refresh = useCallback(async () => {
    try {
      const response = await workbenchFetch(LIST_URL);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()) as TicketListResponse;
      setList(payload.items);
      setLoadError(null);

      // If we don't have a cached "just generated" copy, load the most
      // recent ticket's detail so the preview pane has something to show.
      const top = payload.items[0];
      if (latest == null && top != null) {
        const detailResponse = await workbenchFetch(
          `${LIST_URL}/${encodeURIComponent(top.id)}`,
        );
        if (detailResponse.ok) {
          const detail = (await detailResponse.json()) as GenerateTicketResponse;
          setLatest(detail);
        }
      }
    } catch (reason: unknown) {
      setLoadError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [latest]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const response = await workbenchFetch(GENERATE_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ defensive: mode === "defensive" }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      const payload = (await response.json()) as GenerateTicketResponse;
      setLatest(payload);
      toast.success(
        mode === "defensive"
          ? tToast("ticketGeneratedDefensive", { id: payload.id })
          : tToast("ticketGeneratedNormal", { id: payload.id }),
      );
      await refresh();
    } catch (reason: unknown) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setGenerating(false);
    }
  };

  const handleVoid = async () => {
    if (!latest) return;
    setVoiding(true);
    try {
      const response = await workbenchFetch(
        `${LIST_URL}/${encodeURIComponent(latest.id)}/void`,
        { method: "POST" },
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      const summary = (await response.json()) as TicketSummary;
      setLatest({ ...latest, status: summary.status });
      toast.success(tToast("ticketVoided", { id: summary.id }));
      await refresh();
    } catch (reason: unknown) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setVoiding(false);
    }
  };

  const handleDownload = () => {
    if (!latest) return;
    downloadMarkdown(`order-ticket-${latest.id}.md`, latest.markdown_body);
  };

  const generateDisabled = generating;
  const voidDisabled = !latest || voiding || latest.status !== "generated";

  return (
    <section data-testid="page-ticket" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
          <p className="text-xs text-muted-foreground">{t("description")}</p>
        </div>
        <span data-testid="ticket-state" className="text-xs text-muted-foreground">
          {loadError
            ? tCommon("unreachableWithError", { error: loadError })
            : t("ticketsOnFile", { count: list.length })}
        </span>
      </header>

      <RiskBanner data={risk} noFetch />

      {risk?.state === "red" ? (
        <Card data-testid="ticket-mode-card" className="border-destructive/60">
          <CardHeader>
            <CardTitle>{t("modeCardTitle")}</CardTitle>
            <CardDescription>{t("modeCardDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="ticket-mode"
                value="normal"
                data-testid="ticket-mode-normal"
                checked={mode === "normal"}
                onChange={() => setMode("normal")}
              />
              <span>
                <strong>{t("modeNormalLabel")}</strong> {t("modeNormalBody")}
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="ticket-mode"
                value="defensive"
                data-testid="ticket-mode-defensive"
                checked={mode === "defensive"}
                onChange={() => setMode("defensive")}
              />
              <span>
                <strong>{t("modeDefensiveLabel")}</strong> {t("modeDefensivePrefix")}
                <code>
                  {risk.alternative_defensive_ticket?.target_positions[0]?.symbol ?? "SGOV"}
                </code>
                {t("modeDefensiveSuffix")}
              </span>
            </label>
          </CardContent>
        </Card>
      ) : null}

      <Card data-testid="ticket-actions-card">
        <CardHeader>
          <CardTitle>{t("latestCardTitle")}</CardTitle>
          <CardDescription>
            {latest
              ? t("latestCardSubtitleWithTicket", {
                  id: latest.id,
                  status: latest.status,
                  date: latest.ticket_date,
                })
              : t("latestCardSubtitleEmpty")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button
            data-testid="ticket-generate"
            onClick={handleGenerate}
            disabled={generateDisabled}
          >
            {generating
              ? tCommon("generating")
              : mode === "defensive"
                ? t("generateDefensive")
                : t("generateNew")}
          </Button>
          <Button
            data-testid="ticket-void"
            variant="ghost"
            onClick={handleVoid}
            disabled={voidDisabled}
          >
            {voiding ? tCommon("voiding") : t("voidLatest")}
          </Button>
          <Button
            data-testid="ticket-download"
            variant="secondary"
            onClick={handleDownload}
            disabled={!latest}
          >
            {t("downloadMarkdown")}
          </Button>
        </CardContent>
      </Card>

      {latest ? (
        <Card data-testid="ticket-preview-card">
          <CardHeader>
            <CardTitle>{t("previewCardTitle")}</CardTitle>
            <CardDescription>
              {t("previewCardDescriptionPrefix")}
              <code>{latest.markdown_path}</code>
              {t("previewCardDescriptionSuffix")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MarkdownRenderer body={latest.markdown_body} />
          </CardContent>
        </Card>
      ) : null}

      <Card data-testid="ticket-history-card">
        <CardHeader>
          <CardTitle>{t("historyCardTitle")}</CardTitle>
          <CardDescription>{t("historyCardDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {list.length === 0 ? (
            <p data-testid="ticket-history-empty" className="text-sm text-muted-foreground">
              {t("historyEmpty")}
            </p>
          ) : (
            <ul className="space-y-2">
              {list.map((row) => (
                <li
                  key={row.id}
                  data-testid={`ticket-history-row-${row.id}`}
                  className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-md border px-2 py-0.5 text-[10px] uppercase ${
                        STATUS_STYLES[row.status]
                      }`}
                    >
                      {row.status}
                    </span>
                    <Link
                      data-testid={`ticket-history-link-${row.id}`}
                      href={`/execution/ticket/${encodeURIComponent(row.id)}`}
                      className="font-mono text-xs underline-offset-2 hover:underline"
                    >
                      {row.id}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {t("historyRowMeta", {
                        date: row.ticket_date,
                        createdAt: new Date(row.created_at).toLocaleString(),
                      })}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Toaster />
    </section>
  );
}
