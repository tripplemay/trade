"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { NAV_ITEMS } from "@/components/shell/nav-items";
import { cn } from "@/lib/utils";

function isActive(currentPath: string, href: string): boolean {
  // Home is the only exact-match route; all others highlight on prefix
  // so deep links (e.g. /reports/B019-retune) still light the parent nav.
  if (href === "/") return currentPath === "/";
  return currentPath === href || currentPath.startsWith(`${href}/`);
}

export default function SideNav() {
  const pathname = usePathname() ?? "/";
  const t = useTranslations("nav");
  const tBar = useTranslations("topbar");

  return (
    <nav
      data-testid="workbench-sidenav"
      aria-label={tBar("primaryNavAria")}
      className="hidden w-56 shrink-0 border-r border-border bg-card/40 px-2 py-4 md:block"
    >
      <ul className="space-y-1">
        {NAV_ITEMS.map(({ href, labelKey, icon: Icon, testId }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link
                href={href}
                data-testid={testId}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-accent-foreground",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
                <span>{t(labelKey)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
