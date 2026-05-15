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
    include: ["tests/unit/**/*.{spec,test}.ts"],
    exclude: ["tests/e2e/**", "tests/safety/**", "node_modules/**", ".next/**"],
  },
});
