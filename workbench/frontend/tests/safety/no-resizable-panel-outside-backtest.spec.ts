/**
 * B022 F008 hard boundary: the ResizablePanel layout primitive is
 * permitted on exactly **one** page — the Backtest viewer — and
 * forbidden everywhere else under `src/app/(protected)/`. The spec
 * (and ADR §"Out Of Scope") explicitly rejects the dockable-multi-panel
 * Phase 3+ pattern; this regression guard prevents a future feature
 * from accidentally re-introducing it via a different route.
 *
 * The check is a literal-import scan because that's the only realistic
 * way a future page could pull the primitive in. ResizablePanel /
 * ResizableHandle / ResizablePanelGroup live under
 * `src/components/ui/resizable.tsx`; allowed import paths therefore
 * end with `/components/ui/resizable` or `@/components/ui/resizable`.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const PROTECTED_ROOT = join(FRONTEND_ROOT, "src", "app", "(protected)");
const ALLOWED_FILE = join(PROTECTED_ROOT, "backtest", "page.tsx");

const RESIZABLE_IMPORT_RE = /from\s+["'](?:@\/components\/ui\/resizable|.+\/components\/ui\/resizable)["']/;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      out.push(...walk(full));
      continue;
    }
    if (stat.isFile() && /\.(ts|tsx|js|jsx)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe("ResizablePanel use is confined to the backtest page", () => {
  it("no file under src/app/(protected)/ imports resizable except backtest/page.tsx", () => {
    const offenders: string[] = [];
    for (const file of walk(PROTECTED_ROOT)) {
      if (resolve(file) === resolve(ALLOWED_FILE)) continue;
      const text = readFileSync(file, "utf-8");
      if (RESIZABLE_IMPORT_RE.test(text)) {
        offenders.push(file.replace(`${FRONTEND_ROOT}/`, ""));
      }
    }
    expect(offenders).toEqual([]);
  });
});
