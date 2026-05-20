"use client";

import { CircleUser, Database, LogOut } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import { useTranslations } from "next-intl";

import LocaleSwitcher from "@/components/LocaleSwitcher";
import { Button } from "@/components/ui/button";

/**
 * The TopBar surfaces three things, in priority order:
 *
 * 1. Project identity — research-only "Workbench" wordmark so a glance at
 *    any page confirms which surface the user is on. The disclaimer rail
 *    in the Footer handles the safety claim itself.
 * 2. Snapshot freshness indicator — F011 wires the real status feed; F003
 *    ships the rail with a neutral placeholder so the surface is reserved.
 * 3. Authenticated user identity + sign-out — useSession (next-auth/react)
 *    gives us the user without an extra prop-drill from the layout.
 */
export default function TopBar() {
  const { data: session, status } = useSession();
  const email = session?.user?.email ?? null;
  const t = useTranslations("common");
  const tBar = useTranslations("topbar");

  return (
    <header
      data-testid="workbench-topbar"
      className="flex h-12 items-center justify-between border-b border-border bg-card/60 px-4"
    >
      <div className="flex items-center gap-4">
        <span className="text-sm font-semibold tracking-tight text-foreground">
          {t("appName")}
          <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
            {t("researchOnly")}
          </span>
        </span>
        <span
          data-testid="topbar-snapshot-indicator"
          className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex"
        >
          <Database className="h-3.5 w-3.5" aria-hidden />
          <span>{tBar("snapshotIndicator")}</span>
        </span>
      </div>

      <div className="flex items-center gap-2">
        <LocaleSwitcher />
        {status === "authenticated" && email ? (
          <span
            data-testid="topbar-user-email"
            className="hidden items-center gap-1.5 text-xs text-muted-foreground md:inline-flex"
          >
            <CircleUser className="h-3.5 w-3.5" aria-hidden />
            <span>{email}</span>
          </span>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          data-testid="topbar-signout"
          onClick={() => {
            void signOut({ callbackUrl: "/login" });
          }}
        >
          <LogOut className="h-3.5 w-3.5" aria-hidden />
          <span className="sr-only">{t("signOut")}</span>
        </Button>
      </div>
    </header>
  );
}
