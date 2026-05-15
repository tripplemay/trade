/**
 * Unit tests for `lib/auth.ts` — the Auth.js v5 configuration.
 *
 * We import the raw `authConfig` (not the `NextAuth()` factory output) so
 * Vitest can exercise the callbacks without touching Next.js runtime
 * internals.
 *
 * Coverage targets the F001 acceptance contract:
 *
 *  - `signIn` callback admits only the allowlisted email.
 *  - `signIn` callback denies when the allowlist env var is unset (fail
 *    closed; never silently accept everyone).
 *  - `jwt.encode` produces HS256 JWS, `jwt.decode` round-trips it, and
 *    a different secret rejects the token (interop guarantee with the
 *    backend's python-jose validator).
 *  - The `pages` block points sign-in and error to `/login` so Auth.js
 *    surfaces the spec's "AccessDenied" copy on the configured page.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authConfig } from "@/lib/auth-config";

const ALLOWED_EMAIL = "owner@example.com";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env.ALLOWED_USER_EMAIL = ALLOWED_EMAIL;
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  for (const [key, value] of Object.entries(ORIGINAL_ENV)) {
    process.env[key] = value;
  }
  vi.restoreAllMocks();
});

type SignInCallback = NonNullable<NonNullable<typeof authConfig.callbacks>["signIn"]>;

function callSignIn(profile: { email?: string | null } | null): ReturnType<SignInCallback> {
  const callback = authConfig.callbacks?.signIn;
  if (!callback) throw new Error("authConfig.callbacks.signIn is required");
  // Auth.js passes a heavier object; we satisfy the field the workbench
  // checks (profile.email) and rely on TypeScript widening for the rest.
  return callback({ profile } as unknown as Parameters<SignInCallback>[0]);
}

describe("signIn allowlist callback", () => {
  it("admits the allowlisted email", async () => {
    await expect(callSignIn({ email: ALLOWED_EMAIL })).resolves.toBe(true);
  });

  it("admits the allowlisted email case-insensitively", async () => {
    await expect(callSignIn({ email: "Owner@Example.COM" })).resolves.toBe(true);
  });

  it("rejects any other email", async () => {
    await expect(callSignIn({ email: "stranger@example.com" })).resolves.toBe(false);
  });

  it("rejects when the profile carries no email at all", async () => {
    await expect(callSignIn({})).resolves.toBe(false);
    await expect(callSignIn(null)).resolves.toBe(false);
  });

  it("fails closed when ALLOWED_USER_EMAIL is unset", async () => {
    delete process.env.ALLOWED_USER_EMAIL;
    await expect(callSignIn({ email: ALLOWED_EMAIL })).resolves.toBe(false);
  });
});

describe("jwt encode / decode override (HS256 JWS)", () => {
  const SECRET = "test-secret-do-not-use-in-prod";

  it("round-trips a payload with the same secret", async () => {
    const encode = authConfig.jwt?.encode;
    const decode = authConfig.jwt?.decode;
    if (!encode || !decode) throw new Error("jwt.encode / jwt.decode must be configured");

    const token = await encode({
      token: { email: ALLOWED_EMAIL, sub: "user-id-1" },
      secret: SECRET,
      maxAge: 3600,
      salt: "authjs.session-token",
    });
    expect(typeof token).toBe("string");
    expect(token.length).toBeGreaterThan(0);

    const decoded = await decode({ token, secret: SECRET, salt: "authjs.session-token" });
    expect(decoded?.email).toBe(ALLOWED_EMAIL);
    expect(decoded?.sub).toBe("user-id-1");
  });

  it("emits a three-segment JWS with alg=HS256 in the header", async () => {
    const encode = authConfig.jwt?.encode;
    if (!encode) throw new Error("jwt.encode must be configured");
    const token = await encode({
      token: { email: ALLOWED_EMAIL },
      secret: SECRET,
      maxAge: 60,
      salt: "authjs.session-token",
    });
    const segments = token.split(".");
    expect(segments).toHaveLength(3);
    const headerSegment = segments[0];
    if (!headerSegment) throw new Error("expected JWS header segment");
    const header = JSON.parse(Buffer.from(headerSegment, "base64url").toString("utf-8"));
    expect(header).toMatchObject({ alg: "HS256", typ: "JWT" });
  });

  it("rejects a token signed with a different secret", async () => {
    const encode = authConfig.jwt?.encode;
    const decode = authConfig.jwt?.decode;
    if (!encode || !decode) throw new Error("jwt.encode / jwt.decode must be configured");
    const token = await encode({
      token: { email: ALLOWED_EMAIL },
      secret: SECRET,
      maxAge: 60,
      salt: "authjs.session-token",
    });
    const result = await decode({
      token,
      secret: "different-secret",
      salt: "authjs.session-token",
    });
    expect(result).toBeNull();
  });

  it("returns null for an empty token without throwing", async () => {
    const decode = authConfig.jwt?.decode;
    if (!decode) throw new Error("jwt.decode must be configured");
    const result = await decode({ token: "", secret: SECRET, salt: "authjs.session-token" });
    expect(result).toBeNull();
  });
});

describe("pages configuration", () => {
  it("redirects sign-in and OAuth errors to /login", () => {
    expect(authConfig.pages?.signIn).toBe("/login");
    expect(authConfig.pages?.error).toBe("/login");
  });
});
