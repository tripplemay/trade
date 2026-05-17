import {
  BookOpen,
  Compass,
  DatabaseBackup,
  FileText,
  LayoutDashboard,
  LineChart,
  ListTodo,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  testId: string;
}

/**
 * Single source of truth for the workbench's 7-page nav. TopBar and
 * SideNav both render from this array; F006-F012 do not need to touch
 * the nav surface — adding the 8th page only happens when the spec
 * grows past Phase 1 (see B023 follow-up).
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Home", icon: LayoutDashboard, testId: "nav-home" },
  { href: "/strategies", label: "Strategies", icon: BookOpen, testId: "nav-strategies" },
  { href: "/backtest", label: "Backtest", icon: LineChart, testId: "nav-backtest" },
  { href: "/reports", label: "Reports", icon: FileText, testId: "nav-reports" },
  {
    href: "/recommendations",
    label: "Recommendations",
    icon: Compass,
    testId: "nav-recommendations",
  },
  { href: "/snapshots", label: "Snapshots", icon: DatabaseBackup, testId: "nav-snapshots" },
  { href: "/backlog", label: "Backlog", icon: ListTodo, testId: "nav-backlog" },
];
