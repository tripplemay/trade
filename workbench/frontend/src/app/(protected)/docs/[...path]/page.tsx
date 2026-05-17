"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type DocsResponse = components["schemas"]["DocsResponse"];

export default function DocsViewerPage() {
  const params = useParams<{ path: string | string[] }>();
  const segments = params?.path ?? [];
  const filePath = Array.isArray(segments) ? segments.join("/") : segments;

  const [doc, setDoc] = useState<DocsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!filePath) return;
    let cancelled = false;
    fetch(`/api/docs/${filePath}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as DocsResponse;
        if (!cancelled) setDoc(data);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [filePath]);

  return (
    <section data-testid="page-docs-viewer" className="space-y-4">
      <header className="flex items-baseline justify-between">
        <h1 className="truncate text-xl font-semibold tracking-tight text-foreground">
          {filePath || "—"}
        </h1>
        <span data-testid="docs-viewer-state" className="text-xs text-muted-foreground">
          {error ? `unreachable: ${error}` : doc ? doc.content_type : "loading…"}
        </span>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{filePath}</CardTitle>
          <CardDescription>Repo-relative file rendered via the workbench docs viewer.</CardDescription>
        </CardHeader>
        <CardContent>
          {doc ? (
            doc.content_type === "markdown" ? (
              <MarkdownRenderer body={doc.body} />
            ) : (
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
                {doc.body}
              </pre>
            )
          ) : (
            <p data-testid="docs-viewer-loading" className="text-sm text-muted-foreground">
              Loading…
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
