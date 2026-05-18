"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { components } from "@/types/api";

type TicketDetail = components["schemas"]["TicketDetail"];

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

export default function TicketDetailPage() {
  const params = useParams<{ ticket_id: string }>();
  const ticketId = params?.ticket_id ?? "";
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticketId) return;
    let cancelled = false;
    fetch(`/api/execution/tickets/${encodeURIComponent(ticketId)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = (await response.json()) as TicketDetail;
        if (!cancelled) setDetail(payload);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  const handleDownload = () => {
    if (!detail) return;
    downloadMarkdown(`order-ticket-${detail.id}.md`, detail.markdown_body);
  };

  return (
    <section data-testid="page-ticket-detail" className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Ticket <span className="font-mono text-base">{ticketId}</span>
          </h1>
          <p className="text-xs text-muted-foreground">
            Read-only archive. Open <Link href="/execution/ticket" className="underline">the
            ticket page</Link> to generate a new ticket from the current diff.
          </p>
        </div>
        <span data-testid="ticket-detail-state" className="text-xs text-muted-foreground">
          {error
            ? `unreachable: ${error}`
            : detail
              ? `${detail.status} · ticket_date ${detail.ticket_date}`
              : "loading…"}
        </span>
      </header>

      {detail ? (
        <>
          <Card data-testid="ticket-detail-meta-card">
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
              <CardDescription>
                Markdown source: <code>{detail.markdown_path}</code>
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <span className="text-muted-foreground">Status:</span>{" "}
                <span className="font-mono">{detail.status}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Snapshot id:</span>{" "}
                <span className="font-mono">{detail.snapshot_id}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Target positions id:</span>{" "}
                <span className="font-mono">{detail.target_positions_id}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Created:</span>{" "}
                {new Date(detail.created_at).toLocaleString()}
              </div>
              {detail.executed_at ? (
                <div>
                  <span className="text-muted-foreground">Executed:</span>{" "}
                  {new Date(detail.executed_at).toLocaleString()}
                </div>
              ) : null}
              <div className="sm:col-span-2">
                <Button
                  data-testid="ticket-detail-download"
                  variant="secondary"
                  onClick={handleDownload}
                >
                  Download Markdown
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card data-testid="ticket-detail-body-card">
            <CardHeader>
              <CardTitle>Checklist</CardTitle>
              <CardDescription>
                Research-only. The workbench did not place these orders.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MarkdownRenderer body={detail.markdown_body} />
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  );
}
