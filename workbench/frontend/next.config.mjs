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
  // auth/[...nextauth]/route.ts).
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    const target = process.env.WORKBENCH_BACKEND_ORIGIN ?? "http://127.0.0.1:8723";
    return [
      { source: "/api/health", destination: `${target}/api/health` },
      { source: "/api/protected-test", destination: `${target}/api/protected-test` },
    ];
  },
};

export default nextConfig;
