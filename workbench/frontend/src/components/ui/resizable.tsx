"use client";

/**
 * shadcn-style wrapper around `react-resizable-panels` v4.
 *
 * B022 §F008 acceptance: the Backtest page is the *only* surface
 * authorised to use a resizable split layout in Phase 1 (the
 * regression spec `tests/safety/no-resizable-panel-outside-backtest.spec.ts`
 * enforces that boundary). The wrapper is thin so that page-level uses
 * stay declarative and the page does not need to import directly from
 * the underlying lib.
 *
 * v4 renamed the API from v3 (`PanelGroup` → `Group`, `PanelResizeHandle`
 * → `Separator`); the shadcn names below match what F008 expects.
 */

import { GripVertical } from "lucide-react";
import { Group, Panel, Separator } from "react-resizable-panels";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function ResizablePanelGroup({
  className,
  ...props
}: ComponentProps<typeof Group>) {
  return (
    <Group
      className={cn(
        "flex h-full w-full data-[orientation=vertical]:flex-col",
        className,
      )}
      {...props}
    />
  );
}

export const ResizablePanel = Panel;

export function ResizableHandle({
  withHandle = false,
  className,
  ...props
}: ComponentProps<typeof Separator> & { withHandle?: boolean }) {
  return (
    <Separator
      className={cn(
        "relative flex w-px items-center justify-center bg-border transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring data-[orientation=vertical]:h-px data-[orientation=vertical]:w-full",
        className,
      )}
      {...props}
    >
      {withHandle ? (
        <span className="z-10 flex h-4 w-3 items-center justify-center rounded-sm border border-border bg-background">
          <GripVertical className="h-2.5 w-2.5 text-muted-foreground" />
        </span>
      ) : null}
    </Separator>
  );
}
