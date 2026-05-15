import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

/**
 * Auth gate for every authenticated workbench route.
 *
 * Middleware already redirects anonymous traffic to `/login`; this layout
 * is the second fence so a misconfigured matcher cannot accidentally
 * expose anything inside the `(protected)` route group.
 */
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  return <>{children}</>;
}
