/**
 * Safety regression for B021 F001 acceptance §7.
 *
 * In production builds, NextAuth's callback URL must live under the
 * `trade.guangai.ai` apex. A wrong host would let a malicious Google OAuth
 * redirect land on someone else's domain and steal the session cookie. The
 * helper `assertProductionCallbackUrl` is invoked at module load so a
 * misconfigured deploy crashes before serving the first request; this test
 * pins the behaviour.
 */
import { describe, expect, it } from "vitest";

import { assertProductionCallbackUrl } from "@/lib/auth-config";

function envWith(extra: Record<string, string | undefined>): NodeJS.ProcessEnv {
  return { ...process.env, ...extra } as NodeJS.ProcessEnv;
}

describe("assertProductionCallbackUrl", () => {
  it("is a no-op in non-production environments", () => {
    expect(() =>
      assertProductionCallbackUrl(envWith({ NODE_ENV: "development", NEXTAUTH_URL: undefined })),
    ).not.toThrow();
    expect(() =>
      assertProductionCallbackUrl(envWith({ NODE_ENV: "test", NEXTAUTH_URL: "http://localhost" })),
    ).not.toThrow();
  });

  it("accepts a production NEXTAUTH_URL on trade.guangai.ai", () => {
    expect(() =>
      assertProductionCallbackUrl(
        envWith({ NODE_ENV: "production", NEXTAUTH_URL: "https://trade.guangai.ai" }),
      ),
    ).not.toThrow();
  });

  it("accepts a production AUTH_URL on trade.guangai.ai (Auth.js v5 alias)", () => {
    expect(() =>
      assertProductionCallbackUrl(
        envWith({
          NODE_ENV: "production",
          NEXTAUTH_URL: undefined,
          AUTH_URL: "https://trade.guangai.ai/api/auth",
        }),
      ),
    ).not.toThrow();
  });

  it("rejects a production deploy whose NEXTAUTH_URL points elsewhere", () => {
    expect(() =>
      assertProductionCallbackUrl(
        envWith({
          NODE_ENV: "production",
          NEXTAUTH_URL: "https://evil.example.com",
          AUTH_URL: undefined,
        }),
      ),
    ).toThrow(/trade\.guangai\.ai/);
  });

  it("rejects a production deploy that forgot to set NEXTAUTH_URL", () => {
    expect(() =>
      assertProductionCallbackUrl(
        envWith({ NODE_ENV: "production", NEXTAUTH_URL: undefined, AUTH_URL: undefined }),
      ),
    ).toThrow(/trade\.guangai\.ai/);
  });
});
