import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: [
      "tests/unit/**/*.{spec,test}.ts",
      "tests/safety/no-broker-sdk-imports.spec.ts",
      "tests/safety/production-callback-url.spec.ts",
    ],
    exclude: [
      "tests/e2e/**",
      "tests/safety/disclaimer-present.spec.ts",
      "node_modules/**",
      ".next/**",
    ],
  },
});
