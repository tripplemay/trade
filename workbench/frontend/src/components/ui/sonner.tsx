"use client";

import { Toaster as SonnerToaster, type ToasterProps } from "sonner";

/**
 * Toast surface (sonner is the current shadcn-ui Toast default; the
 * legacy `<Toast>` component was retired upstream). Mount `<Toaster />`
 * once near the top of the route tree (added in F003 shell); fire toasts
 * from any client component via `import { toast } from "sonner"`.
 */
export function Toaster(props: ToasterProps) {
  return (
    <SonnerToaster
      theme="dark"
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
}
