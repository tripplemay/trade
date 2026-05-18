import {
  BookOpen,
  ClipboardList,
  Compass,
  DatabaseBackup,
  FileText,
  LayoutDashboard,
  LineChart,
  ListTodo,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  testId: string;
}

/**
 * Single source of truth for the workbench nav. TopBar and SideNav both
 * render from this array. B023 Phase 2 (F002+) grows the original 7-page
 * Phase 1 nav by the execution-workflow surface; F003/F004/F005 will
 * append `/execution/ticket`, `/execution/fills`, and
 * `/execution/journal-history` in their respective features.
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
  {
    href: "/execution/position-diff",
    label: "Position diff",
    icon: ClipboardList,
    testId: "nav-position-diff",
  },
  {
    href: "/execution/account",
    label: "Account",
    icon: Wallet,
    testId: "nav-account",
  },
  { href: "/snapshots", label: "Snapshots", icon: DatabaseBackup, testId: "nav-snapshots" },
  { href: "/backlog", label: "Backlog", icon: ListTodo, testId: "nav-backlog" },
];
