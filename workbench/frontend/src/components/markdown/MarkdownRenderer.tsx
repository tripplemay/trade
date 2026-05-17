"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import type { ColDef } from "ag-grid-community";

import { DataTable } from "@/components/table";
import { cn } from "@/lib/utils";

const HEAVY_TABLE_ROW_THRESHOLD = 10;

export interface MarkdownRendererProps {
  body: string;
  className?: string;
}

/**
 * Shared markdown renderer used by /reports/[slug] and /docs/[...path].
 *
 * Customisations:
 * - `a`: rewrites repo-relative links (`docs/test-reports/X.md` →
 *   `/reports/X-slug`, anything else under `docs/` or `trade/` →
 *   `/docs/<original>`); external links open in a new tab.
 * - `code` (inline + fenced): adds the workbench monospace + muted
 *   surface so code blocks stand out without pulling in a syntax
 *   highlighter (deferred to a later batch).
 * - `table`: counts `tbody > tr` rows; ≥10 rows swaps the rendered
 *   HTML table for an AG Grid DataTable so the user gets sort + filter
 *   (the F009 acceptance calls this out for B019's sweep matrix).
 */
export default function MarkdownRenderer({ body, className }: MarkdownRendererProps) {
  return (
    <div className={cn("prose prose-invert max-w-none text-sm", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENT_OVERRIDES}>
        {body}
      </ReactMarkdown>
    </div>
  );
}

const COMPONENT_OVERRIDES: Components = {
  a({ href, children, ...rest }) {
    if (!href) return <a {...rest}>{children}</a>;
    const rewritten = rewriteRepoLink(href);
    if (rewritten.startsWith("/")) {
      return (
        <Link href={rewritten} className="text-foreground underline hover:no-underline">
          {children}
        </Link>
      );
    }
    return (
      <a
        href={rewritten}
        target={isExternal(rewritten) ? "_blank" : undefined}
        rel={isExternal(rewritten) ? "noreferrer noopener" : undefined}
        className="text-foreground underline hover:no-underline"
        {...rest}
      >
        {children}
      </a>
    );
  },
  code({ className: codeClass, children }) {
    return (
      <code
        className={cn(
          "rounded bg-muted px-1 py-0.5 text-xs text-foreground",
          codeClass,
        )}
      >
        {children}
      </code>
    );
  },
  pre({ children }) {
    return (
      <pre className="overflow-x-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
        {children}
      </pre>
    );
  },
  table({ children, ...rest }) {
    return <MarkdownTable {...rest}>{children}</MarkdownTable>;
  },
};

function MarkdownTable({ children, ...rest }: React.ComponentPropsWithoutRef<"table">) {
  const parsed = parseChildrenIntoTableRows(children);
  if (parsed && parsed.body.length >= HEAVY_TABLE_ROW_THRESHOLD) {
    return <MarkdownHeavyTable header={parsed.header} body={parsed.body} />;
  }
  return (
    <table {...rest} className="w-full border-collapse text-xs">
      {children}
    </table>
  );
}

interface ParsedTable {
  header: string[];
  body: string[][];
}

function parseChildrenIntoTableRows(children: React.ReactNode): ParsedTable | null {
  const header: string[] = [];
  const body: string[][] = [];
  const childArray = childrenToArray(children);
  for (const child of childArray) {
    if (!isReactElement(child)) continue;
    if (child.type === "thead") {
      for (const row of childrenToArray(child.props.children)) {
        if (!isReactElement(row) || row.type !== "tr") continue;
        for (const cell of childrenToArray(row.props.children)) {
          if (!isReactElement(cell)) continue;
          header.push(stringify(cell.props.children));
        }
      }
    } else if (child.type === "tbody") {
      for (const row of childrenToArray(child.props.children)) {
        if (!isReactElement(row) || row.type !== "tr") continue;
        const rowCells: string[] = [];
        for (const cell of childrenToArray(row.props.children)) {
          if (!isReactElement(cell)) continue;
          rowCells.push(stringify(cell.props.children));
        }
        body.push(rowCells);
      }
    }
  }
  if (header.length === 0 || body.length === 0) return null;
  return { header, body };
}

function MarkdownHeavyTable({ header, body }: ParsedTable) {
  type Row = Record<string, string>;
  const rows: Row[] = body.map((cells) => {
    const out: Row = {};
    header.forEach((col, i) => {
      out[col] = cells[i] ?? "";
    });
    return out;
  });
  const columnDefs: ColDef<Row>[] = header.map((col) => ({
    field: col,
    headerName: col,
    sortable: true,
    filter: true,
    resizable: true,
  }));
  return (
    <div data-testid="markdown-heavy-table" className="my-4">
      <DataTable<Row> rowData={rows} columnDefs={columnDefs} height={Math.min(500, 80 + rows.length * 30)} />
    </div>
  );
}

function childrenToArray(children: React.ReactNode): React.ReactNode[] {
  if (Array.isArray(children)) return children;
  if (children === null || children === undefined) return [];
  return [children];
}

function isReactElement(node: React.ReactNode): node is React.ReactElement<{ children?: React.ReactNode }> {
  return typeof node === "object" && node !== null && "type" in (node as object);
}

function stringify(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(stringify).join("");
  if (isReactElement(node)) return stringify(node.props.children);
  return "";
}

function isExternal(href: string): boolean {
  return /^(https?:|mailto:|tel:)/.test(href);
}

function rewriteRepoLink(href: string): string {
  if (isExternal(href) || href.startsWith("/") || href.startsWith("#")) return href;
  // docs/test-reports/B019-x-2026-05-15.md → /reports/B019-x
  const reportMatch = href.match(/^docs\/test-reports\/(.+?)(?:-\d{4}-\d{2}-\d{2})?\.md$/);
  if (reportMatch) {
    return `/reports/${reportMatch[1]}`;
  }
  // Anything else under docs/ or trade/ → /docs/<original>
  if (href.startsWith("docs/") || href.startsWith("trade/")) {
    return `/docs/${href}`;
  }
  return href;
}
