/**
 * Broker SDK imports are forbidden anywhere in the workbench frontend.
 *
 * The test walks `src/**` for any reference to known broker SDK package names
 * and also inspects `package.json` (dependencies + devDependencies) for the
 * same. The two forms together prevent both source-level usage and silent
 * dependency installation. A red test here is a boundary breach.
 */

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const SRC_ROOT = join(FRONTEND_ROOT, "src");
const PACKAGE_JSON = join(FRONTEND_ROOT, "package.json");
const SELF_PATH = fileURLToPath(import.meta.url);

const FORBIDDEN_PACKAGE_FRAGMENTS: readonly string[] = [
  "@alpaca/",
  "ib-insync",
  "futu-api",
  "tiger-securities",
];

const SCAN_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      if (entry === "node_modules" || entry.startsWith(".")) continue;
      out.push(...walk(full));
      continue;
    }
    if (!stat.isFile()) continue;
    const lastDot = full.lastIndexOf(".");
    const ext = lastDot >= 0 ? full.slice(lastDot) : "";
    if (!SCAN_EXTENSIONS.has(ext)) continue;
    out.push(full);
  }
  return out;
}

describe("frontend broker-SDK absence guard", () => {
  it("contains no broker SDK reference under src/", () => {
    const offenders: { file: string; pattern: string }[] = [];
    for (const file of walk(SRC_ROOT)) {
      if (resolve(file) === SELF_PATH) continue;
      const text = readFileSync(file, "utf-8");
      for (const fragment of FORBIDDEN_PACKAGE_FRAGMENTS) {
        if (text.includes(fragment)) {
          offenders.push({ file: file.replace(`${FRONTEND_ROOT}/`, ""), pattern: fragment });
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("declares no broker SDK in package.json (deps + devDeps)", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON, "utf-8")) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    const declared = new Set<string>([
      ...Object.keys(pkg.dependencies ?? {}),
      ...Object.keys(pkg.devDependencies ?? {}),
    ]);
    const offenders: string[] = [];
    for (const name of declared) {
      for (const fragment of FORBIDDEN_PACKAGE_FRAGMENTS) {
        if (name.includes(fragment)) {
          offenders.push(name);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
