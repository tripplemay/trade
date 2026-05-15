import { describe, expect, it } from "vitest";

import { DISCLAIMER_TEXT } from "@/lib/disclaimer";

describe("DISCLAIMER_TEXT", () => {
  it("is a non-empty string", () => {
    expect(typeof DISCLAIMER_TEXT).toBe("string");
    expect(DISCLAIMER_TEXT.length).toBeGreaterThan(0);
  });

  it("flags research-only intent (immutable contract)", () => {
    expect(DISCLAIMER_TEXT.toLowerCase()).toContain("research-only");
  });

  it("refuses to authorize trading (immutable contract)", () => {
    const lower = DISCLAIMER_TEXT.toLowerCase();
    expect(lower).toContain("never");
    expect(lower).toMatch(/paper or live trading/);
  });
});
