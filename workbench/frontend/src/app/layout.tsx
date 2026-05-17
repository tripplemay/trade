import type { Metadata } from "next";
import "@/styles/globals.css";

import { interSans, jetbrainsMono } from "@/lib/fonts";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Workbench (research-only)",
  description: "Research workbench for backtests and recommendations. Never authorizes trades.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // suppressHydrationWarning silences the classname-order delta between
  // SSR (this component's hard-coded "dark") and the client render
  // (next-themes ThemeProvider re-applies "dark" first). The classes
  // themselves match; only the order differs. This is the standard
  // next-themes integration pattern and is required by the new B022
  // F014 Playwright console-error guard which would otherwise fail
  // every authed test on the hydration warning.
  return (
    <html
      lang="en"
      className={cn("dark", interSans.variable, jetbrainsMono.variable)}
      suppressHydrationWarning
    >
      <body className="flex min-h-screen flex-col bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
