import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Workbench (research-only)",
  description: "Research workbench for backtests and recommendations. Never authorizes trades.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen flex-col bg-neutral-950 text-neutral-200">{children}</body>
    </html>
  );
}
