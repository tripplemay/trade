/**
 * B023 F003 acceptance #4 — Frontend regression: any button labelled
 * "execute" / "place order" / "send to broker" is forbidden.
 *
 * The workbench is research-only (B023 §Hard boundaries). The execution
 * pages generate Markdown checklists for the user to act on manually
 * in their broker app; the workbench never sends an order. This guard
 * grep-scans every `(protected)/execution/**` page for the forbidden
 * labels so a future refactor can't quietly add a button that suggests
 * the workbench performs execution.
 *
 * String literals that legitimately mention the phrase in user-facing
 * disclaimer copy ("the workbench does NOT place orders") are kept out
 * of the offending list by anchoring the regex at the start of a quote
 * and requiring a button-context word ("Button", "label", "title", or
 * the JSX text node form `>label<`). Source code that talks ABOUT
 * execution in comments / disclaimers is fine; a rendered button
 * label is not.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const EXECUTION_DIR = join(
  FRONTEND_ROOT,
  "src",
  "app",
  "(protected)",
  "execution",
);

const FORBIDDEN_PATTERNS: RegExp[] = [
  // JSX text node form: `>Execute<`, `>Place order<`, `>Send to broker<`.
  // Inserted between a JSX opening and closing tag the button label
  // becomes literal `>label<` text — that's the shape we forbid.
  />\s*(?:execute|place\s+order|send\s+to\s+broker)\s*</im,
];

// More targeted scan: look for explicit button-label assignments.
const SCAN_REGEX =
  /(?:children|label|title|aria-label)\s*[:=]\s*"(?:execute|place\s+order|send\s+to\s+broker)/i;

function collectPageFiles(root: string): string[] {
  const out: string[] = [];
  function walk(dir: string): void {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.tsx?$/.test(entry)) continue;
      out.push(full);
    }
  }
  walk(root);
  return out;
}

describe("no execution buttons under (protected)/execution/**", () => {
  const files = collectPageFiles(EXECUTION_DIR);

  it(`covers at least the 4 F002+F003 pages`, () => {
    // F002 ships position-diff + account; F003 ships ticket page +
    // ticket detail subpage. F004+ append fills + journal-history.
    expect(files.length).toBeGreaterThanOrEqual(4);
  });

  for (const file of files) {
    const relative = file.slice(FRONTEND_ROOT.length + sep.length);
    it(`${relative} contains no execute/place-order/send-to-broker button label`, () => {
      const body = readFileSync(file, "utf-8");
      for (const pattern of FORBIDDEN_PATTERNS) {
        const match = body.match(pattern);
        if (match) {
          throw new Error(
            `forbidden button label detected in ${relative}: ${match[0]}`,
          );
        }
      }
      // Targeted label-assignment scan: any literal "Execute" /
      // "Place order" / "Send to broker" as a button label.
      // Render text in `<Button>Execute</Button>` is caught by the JSX
      // regex above; this regex catches the `children: "Execute"` and
      // `aria-label="Execute"` shapes that don't go through JSX text.
      const labelMatch = body.match(SCAN_REGEX);
      if (labelMatch) {
        throw new Error(
          `forbidden button label assignment in ${relative}: ${labelMatch[0]}`,
        );
      }
    });
  }
});
