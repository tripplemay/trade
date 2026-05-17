/**
 * No source file under `src/` may hardcode a loopback / localhost URL
 * targeting the workbench backend.
 *
 * Background: B021 F006 reverify 2026-05-17 caught
 * `src/app/(protected)/page.tsx` defaulting the browser health probe to
 * `http://127.0.0.1:8723/api/health`. In production that URL points at
 * the *user's* machine, not the VM — the post-login home page rendered
 * "Backend unreachable: Failed to fetch" even though the backend was
 * healthy. The fix uses a same-origin `/api/health` and a dev-only
 * Next.js rewrite (next.config.mjs); this regression guard prevents a
 * future commit from reintroducing the hardcoded host inside any
 * client / server component the bundler ships to the browser.
 *
 * Allowlisted: `next.config.mjs` (lives outside `src/`, defines the dev
 * proxy itself) + test files (this one references the forbidden
 * pattern literally).
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const SRC_ROOT = join(FRONTEND_ROOT, "src");
const SELF_PATH = fileURLToPath(import.meta.url);

const FORBIDDEN_PATTERNS: readonly RegExp[] = [
  /http:\/\/127\.0\.0\.1:872\d/,
  /http:\/\/localhost:872\d/,
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

describe("no hardcoded backend host in src/", () => {
  it("src/ contains no http://127.0.0.1:872X or http://localhost:872X URLs", () => {
    const offenders: { file: string; pattern: string; line: number; text: string }[] = [];
    for (const file of walk(SRC_ROOT)) {
      if (resolve(file) === SELF_PATH) continue;
      const lines = readFileSync(file, "utf-8").split("\n");
      for (const pattern of FORBIDDEN_PATTERNS) {
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (line === undefined) continue;
          if (pattern.test(line)) {
            offenders.push({
              file: file.replace(`${FRONTEND_ROOT}/`, ""),
              pattern: pattern.source,
              line: i + 1,
              text: line.trim(),
            });
          }
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
