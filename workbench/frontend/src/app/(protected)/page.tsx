"use client";

import { useEffect, useState } from "react";

import type { components } from "@/types/api";

type HealthResponse = components["schemas"]["HealthResponse"];

// Same-origin probe. In production nginx routes `/api/*` to the FastAPI
// backend before the request reaches the Next.js standalone server (see
// workbench/deploy/nginx/trade.guangai.ai.conf). In dev, `next.config.mjs`
// rewrites this path to the backend loopback so the browser keeps
// fetching same-origin against the Next.js dev server. A loopback URL
// baked into the client bundle would target the USER's machine in
// production — exactly the gap B021 F006 reverify 2026-05-17 surfaced.
const HEALTH_URL = "/api/health";

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
    <section data-testid="workbench-home" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Home</h1>
      <div className="max-w-xl rounded-lg border border-border bg-card p-6 text-card-foreground shadow-sm">
        <p className="text-sm text-muted-foreground">
          Dashboard cards (NAV / drawdown / next rebalance / recent reports) land in B022 F006.
          The shell is in place; the safety footer is rendered by the protected layout.
        </p>
        <p data-testid="workbench-health" className="mt-4 text-xs text-muted-foreground">
          {health
            ? `Backend: ${health.status} (build ${health.version})`
            : error
              ? `Backend unreachable: ${error}`
              : "Probing backend…"}
        </p>
      </div>
    </section>
  );
}
