/**
 * B024 F001 / F002 — translation key parity guard.
 *
 * `messages/zh-CN.json` is the authoritative schema (the TypeScript
 * IntlMessages augmentation in src/types/intl.d.ts imports it). Every
 * other locale's bundle must mirror the key set bit-for-bit, otherwise
 * `t('foo.bar')` in en may render `foo.bar` literally and ship to
 * users. The CI parity check in F002 acceptance is a `jq` diff; this
 * spec is the in-process Vitest twin so the breakage is caught at
 * unit-test time (before lint / typecheck / build).
 *
 * Also verifies the starter bundle has at least 10 keys (F001
 * acceptance: common namespace + nav ≥10 keys).
 */
import { describe, expect, it } from "vitest";

import enMessages from "../../messages/en.json";
import zhCNMessages from "../../messages/zh-CN.json";

function collectKeys(node: unknown, prefix = ""): string[] {
  if (node === null || typeof node !== "object") return [];
  const keys: string[] = [];
  for (const [k, v] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      keys.push(...collectKeys(v, path));
    } else {
      keys.push(path);
    }
  }
  return keys.sort();
}

describe("messages bundle parity", () => {
  it("zh-CN and en share the exact same recursive key set", () => {
    const zhKeys = collectKeys(zhCNMessages);
    const enKeys = collectKeys(enMessages);
    // Diff in both directions surfaces missing AND extra keys.
    const zhMinusEn = zhKeys.filter((k) => !enKeys.includes(k));
    const enMinusZh = enKeys.filter((k) => !zhKeys.includes(k));
    expect(zhMinusEn).toEqual([]);
    expect(enMinusZh).toEqual([]);
    expect(zhKeys).toEqual(enKeys);
  });

  it("starter bundles ship at least 10 leaf keys (spec F001 acceptance)", () => {
    expect(collectKeys(zhCNMessages).length).toBeGreaterThanOrEqual(10);
    expect(collectKeys(enMessages).length).toBeGreaterThanOrEqual(10);
  });

  it("advisor research disclaimer is present + non-empty in both locales (B039 永存)", () => {
    // i18n-disclaimer 永存守门 (v0.9.26 family): the Home AI Advisor section's
    // ⚠️ research disclaimer must exist AND be non-empty in zh-CN + en — drop
    // one side and this fails (key parity above already bans a one-sided key;
    // this also bans an accidentally-emptied disclaimer value).
    for (const bundle of [zhCNMessages, enMessages] as const) {
      const home = (
        bundle as unknown as {
          home?: { advisor?: { disclaimer?: string } };
        }
      ).home;
      const value = home?.advisor?.disclaimer;
      expect(typeof value).toBe("string");
      expect((value ?? "").trim().length).toBeGreaterThan(0);
    }
  });

  it("every leaf value is a string in both bundles", () => {
    // Empty-string leaves are intentional in some namespaces (e.g.
    // ternary "override marker" suffixes that may render as no-op);
    // the parity contract is type + key-set, not non-empty content.
    const inspect = (bundle: unknown): void => {
      if (bundle === null || typeof bundle !== "object") return;
      for (const v of Object.values(bundle)) {
        if (v !== null && typeof v === "object" && !Array.isArray(v)) {
          inspect(v);
        } else {
          expect(typeof v).toBe("string");
        }
      }
    };
    inspect(zhCNMessages);
    inspect(enMessages);
  });
});
