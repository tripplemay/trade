"use client";

import { useEffect, useState } from "react";

import Footer from "@/components/shell/Footer";
import type { components } from "@/types/api";

type HealthResponse = components["schemas"]["HealthResponse"];

const HEALTH_URL =
  process.env.NEXT_PUBLIC_WORKBENCH_HEALTH_URL ?? "http://127.0.0.1:8723/health";

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(HEALTH_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as HealthResponse;
        if (!cancelled) setHealth(data);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <main
        data-testid="workbench-home"
        className="flex flex-1 flex-col items-center justify-center px-6 py-16"
      >
        <section className="w-full max-w-xl rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-lg">
          <h1 className="text-2xl font-semibold text-neutral-100">Workbench scaffold OK</h1>
          <p className="mt-3 text-sm text-neutral-400">
            B020 development infrastructure is online. Backend, frontend, lint, type-check and test
            tooling are wired. Strategy pages and broker integrations are intentionally absent —
            those land in later batches (B022 / B023).
          </p>
          <p data-testid="workbench-health" className="mt-4 text-xs text-neutral-500">
            {health
              ? `Backend: ${health.status} (build ${health.version})`
              : error
                ? `Backend unreachable: ${error}`
                : "Probing backend…"}
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
