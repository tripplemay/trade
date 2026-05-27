/**
 * B030 F004 fix-round 1 — synthetic-data-banner decommissioning guard.
 *
 * Codex F004 first-round verification found that even though the
 * SyntheticDataBanner component returned `null` correctly in
 * production (the `process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER`
 * inline got dead-code-eliminated to `return null`), the banner
 * surface was still observable from outside in two places:
 *
 *   1. The `syntheticBanner.headline` translation string still
 *      shipped in the next-intl messages JSON embedded in every
 *      authenticated page's RSC payload.
 *   2. The `SyntheticDataBanner` component name still appeared in
 *      the protected layout chunk because the layout still
 *      imported the component (even though the rendered JSX was
 *      dead-eliminated).
 *
 * Fix-round 1 removed both observables:
 *
 *   - `src/app/(protected)/layout.tsx` no longer imports the
 *     component nor renders `<SyntheticDataBanner />`.
 *   - `messages/zh-CN.json` + `messages/en.json` no longer contain
 *     the `syntheticBanner.*` namespace.
 *   - `src/components/SyntheticDataBanner.tsx` is preserved (with a
 *     decommissioning notice) so a future Layer 0 fallback batch can
 *     restore the banner without rebuilding the component.
 *
 * These guard tests fail loudly on any drift back to the pre-fix
 * state. The reactivation playbook lives in the component file's
 * top-of-file comment.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

import enMessages from "../../messages/en.json";
import zhCNMessages from "../../messages/zh-CN.json";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const PROTECTED_LAYOUT = path.join(FRONTEND_ROOT, "src", "app", "(protected)", "layout.tsx");
const COMPONENT_FILE = path.join(FRONTEND_ROOT, "src", "components", "SyntheticDataBanner.tsx");

function readFile(p: string): string {
  return fs.readFileSync(p, "utf-8");
}

describe("B030 F004 fix-round 1 — synthetic-data-banner decommissioned", () => {
  it("protected layout no longer imports SyntheticDataBanner", () => {
    const layout = readFile(PROTECTED_LAYOUT);
    // Strip line comments + block comments before matching so the
    // explanatory restore-playbook comment (which references the
    // import path) doesn't trip the guard.
    const stripped = layout.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    // The actual import declaration must start at column 0 of a
    // non-comment line; an anchored regex catches the canonical
    // statement and ignores docstring-mentioned paths.
    const importLine = /^\s*import\s+.*from\s+["']@\/components\/SyntheticDataBanner["']/m;
    expect(importLine.test(stripped)).toBe(false);
  });

  it("protected layout no longer renders <SyntheticDataBanner />", () => {
    const layout = readFile(PROTECTED_LAYOUT);
    // The JSX render call is the canonical signal. The comment
    // about reactivation steps may include the literal string
    // "<SyntheticDataBanner />" inside backticks — make the regex
    // exclude backtick-wrapped occurrences (i.e. JSX-position only).
    const jsxRender = /(?<!`)<SyntheticDataBanner\s*\/>(?!`)/;
    expect(jsxRender.test(layout)).toBe(false);
  });

  it("zh-CN messages bundle no longer contains a syntheticBanner namespace", () => {
    // Read the raw JSON instead of relying on the static import so
    // a future maintainer who adds the keys back trips this test
    // even if their TS types pass.
    const zhRaw = readFile(path.join(FRONTEND_ROOT, "messages", "zh-CN.json"));
    expect(zhRaw.includes("syntheticBanner")).toBe(false);
    expect(zhRaw.includes("研究原型 · 仅含合成数据 · 不构成投资决策依据")).toBe(false);
    // Belt-and-braces: also assert the parsed object has no key.
    expect("syntheticBanner" in (zhCNMessages as Record<string, unknown>)).toBe(false);
  });

  it("en messages bundle no longer contains a syntheticBanner namespace", () => {
    const enRaw = readFile(path.join(FRONTEND_ROOT, "messages", "en.json"));
    expect(enRaw.includes("syntheticBanner")).toBe(false);
    expect(
      enRaw.includes("Research prototype · Synthetic data only · Not for investment decisions"),
    ).toBe(false);
    expect("syntheticBanner" in (enMessages as Record<string, unknown>)).toBe(false);
  });

  it("SyntheticDataBanner component file is preserved for layer rollback", () => {
    // 永久边界 (k): the component must remain importable so a
    // future spec batch can restore the banner with a layout-level
    // edit alone (rather than rebuilding the component).
    expect(fs.existsSync(COMPONENT_FILE)).toBe(true);
    const component = readFile(COMPONENT_FILE);
    // The reactivation steps must be present so a maintainer knows
    // what to undo to bring the banner back.
    expect(component.includes("decommissioned")).toBe(true);
    // The component-side hardcoded headline must still match the
    // de-i18n strings (zh-CN canonical + en).
    expect(component.includes("研究原型 · 仅含合成数据 · 不构成投资决策依据")).toBe(true);
    expect(
      component.includes("Research prototype · Synthetic data only · Not for investment decisions"),
    ).toBe(true);
  });

  it("component still gates on NEXT_PUBLIC_SYNTHETIC_DATA_BANNER env flag", () => {
    // The env-gate is the kill-switch that protects production from
    // accidentally re-enabling the banner if someone reverts the
    // layout import without also flipping the env value. Catches the
    // failure mode "re-import shows banner on every deploy" before
    // the dual-fence guarantee disappears.
    const component = readFile(COMPONENT_FILE);
    expect(component.includes("process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER")).toBe(true);
    expect(component.includes('!== "false"')).toBe(true);
  });
});
