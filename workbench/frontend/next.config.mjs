/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // B021 F003 systemd unit runs `.next/standalone/server.js` directly so
  // we ship a minimal self-contained Node bundle. Without this, `next start`
  // is the only supported entry point, which would force the systemd unit
  // to invoke `npm` and drag the dev dependencies into prod.
  output: "standalone",
};

export default nextConfig;
