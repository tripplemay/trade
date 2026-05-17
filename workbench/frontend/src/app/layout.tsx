import type { Metadata } from "next";
import "@/styles/globals.css";

import { interSans, jetbrainsMono } from "@/lib/fonts";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Workbench (research-only)",
  description: "Research workbench for backtests and recommendations. Never authorizes trades.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("dark", interSans.variable, jetbrainsMono.variable)}>
      <body className="flex min-h-screen flex-col bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
