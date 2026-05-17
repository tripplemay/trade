import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  // React 17+ automatic JSX runtime so component spec files don't have to
  // `import React` just to satisfy the classic transform. tsconfig keeps
  // jsx: "preserve" for Next.js's own pipeline; this only affects vitest.
  esbuild: {
    jsx: "automatic",
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // Default environment is node — fast and adequate for safety scans
    // and pure-Node unit tests. Component tests opt into happy-dom via
    // a per-file `// @vitest-environment happy-dom` directive at the
    // top of the .spec.tsx files; that avoids paying the DOM init cost
    // on every node-only test.
    environment: "node",
    setupFiles: ["tests/setup.ts"],
    include: [
      "tests/unit/**/*.{spec,test}.{ts,tsx}",
      "tests/safety/no-broker-sdk-imports.spec.ts",
      "tests/safety/no-hardcoded-backend-host.spec.ts",
      "tests/safety/no-resizable-panel-outside-backtest.spec.ts",
      "tests/safety/dev-rewrites-cover-backend-api.spec.ts",
      "tests/safety/production-callback-url.spec.ts",
    ],
    exclude: [
      // disclaimer-present runs in Playwright (anon project) only.
      "tests/e2e/**",
      "tests/safety/disclaimer-present.spec.ts",
      "node_modules/**",
      ".next/**",
    ],
  },
});
