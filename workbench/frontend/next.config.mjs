import createNextIntlPlugin from "next-intl/plugin";

// B024 F001: route next-intl's request-config loader (server-side
// message resolution + locale detection) through `src/i18n.ts`. The
// plugin wraps the Next config so we don't have to thread it through
// every dev/build entry point.
const withNextIntl = createNextIntlPlugin("./src/i18n.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // B021 F003 systemd unit runs `.next/standalone/server.js` directly so
  // we ship a minimal self-contained Node bundle. Without this, `next start`
  // is the only supported entry point, which would force the systemd unit
  // to invoke `npm` and drag the dev dependencies into prod.
  output: "standalone",

  // Dev-only proxy so the browser fetch from `localhost:3000` to the
  // FastAPI backend on `localhost:8723` stays same-origin. In production
  // nginx (workbench/deploy/nginx/trade.guangai.ai.conf) matches
  // `location /api/` and routes to 127.0.0.1:8723 before reaching the
  // Next.js standalone server, so the rewrite is a no-op there.
  //
  // `/api/auth/*` must NOT be rewritten — those are NextAuth route
  // handlers owned by this Next.js app (workbench/frontend/src/app/api/
  // auth/[...nextauth]/route.ts). The wildcard rewrite below uses an
  // explicit-prefix list so a future page that adds a new server route
  // under `/api/auth/...` cannot accidentally collide with the proxy.
  //
  // B022 F014 blocker fix: the prior rewrite list only covered F006's
  // /api/health + the F001 auth probe. Codex L1 saw the Next dev server
  // log 404s for every B022 page (`/api/dashboard`, `/api/strategies`,
  // `/api/backtests`, `/api/reports`, `/api/recommendations`,
  // `/api/snapshots`, `/api/backlog`, `/api/docs`) — Playwright passed
  // because the page tests only asserted shell/card presence. The list
  // below covers every backend route shipped through B022 F012 so dev
  // matches prod's nginx routing.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    const target = process.env.WORKBENCH_BACKEND_ORIGIN ?? "http://127.0.0.1:8723";
    // Every prefix below must NOT collide with /api/auth (NextAuth own).
    // B023 F002 added the `execution` prefix for the manual-execution
    // workflow surface (position-diff / account / tickets / fills /
    // reconcile). Keep the list alphabetised within each phase so the
    // safety test below stays a simple substring grep.
    const PROXIED_PREFIXES = [
      "health",
      "protected-test",
      "dashboard",
      "strategies",
      "backtests",
      "reports",
      "recommendations",
      "snapshots",
      "backlog",
      "docs",
      "execution",
      "market-context",
      "advisor",
      "home",
      "news",
      "paper",
      // B057 F005: the strategy-mode selector data source (GET /api/strategy-modes).
      "strategy-modes",
    ];
    return PROXIED_PREFIXES.flatMap((prefix) => [
      { source: `/api/${prefix}`, destination: `${target}/api/${prefix}` },
      { source: `/api/${prefix}/:path*`, destination: `${target}/api/${prefix}/:path*` },
    ]);
  },
};

export default withNextIntl(nextConfig);
