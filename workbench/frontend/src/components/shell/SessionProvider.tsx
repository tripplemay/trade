"use client";

/**
 * `next-auth/react`'s SessionProvider is a client component but server
 * components can't import it directly. This thin re-export lives at a
 * "use client" boundary so the server-side `(protected)/layout.tsx`
 * can render the provider in its tree while keeping the gate itself
 * (auth() check + redirect) on the server.
 *
 * Pass the initial session from the server via the `session` prop so
 * the first render does not flash a "loading" state on the client.
 */
export { SessionProvider } from "next-auth/react";
