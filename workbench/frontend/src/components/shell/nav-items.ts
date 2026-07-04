import {
  Activity,
  BookOpen,
  ClipboardList,
  Compass,
  DatabaseBackup,
  FileText,
  FlaskConical,
  History,
  LayoutDashboard,
  LineChart,
  ListTodo,
  Receipt,
  Search,
  ShieldAlert,
  Upload,
  Wallet,
  type LucideIcon,
} from "lucide-react";

/**
 * Keys must mirror namespace `nav` in messages/{zh-CN,en}.json. Adding
 * an entry here without the corresponding translation key trips the
 * messages-key-parity unit test.
 */
export type NavKey =
  | "home"
  | "strategies"
  | "backtest"
  | "reports"
  | "symbols"
  | "recommendations"
  | "risk"
  | "paper"
  | "monitoring"
  | "positionDiff"
  | "ticket"
  | "fills"
  | "journal"
  | "account"
  | "snapshots"
  | "backlog";

export interface NavItem {
  href: string;
  /** i18n key under the `nav` namespace; rendered through next-intl. */
  labelKey: NavKey;
  icon: LucideIcon;
  testId: string;
}

/**
 * Single source of truth for the workbench nav. TopBar and SideNav both
 * render from this array. B023 Phase 2 (F002+) grows the original 7-page
 * Phase 1 nav by the execution-workflow surface; B024 F002 swapped the
 * hardcoded labels for translation keys.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", labelKey: "home", icon: LayoutDashboard, testId: "nav-home" },
  { href: "/strategies", labelKey: "strategies", icon: BookOpen, testId: "nav-strategies" },
  { href: "/backtest", labelKey: "backtest", icon: LineChart, testId: "nav-backtest" },
  { href: "/reports", labelKey: "reports", icon: FileText, testId: "nav-reports" },
  { href: "/symbols", labelKey: "symbols", icon: Search, testId: "nav-symbols" },
  {
    href: "/recommendations",
    labelKey: "recommendations",
    icon: Compass,
    testId: "nav-recommendations",
  },
  { href: "/risk", labelKey: "risk", icon: ShieldAlert, testId: "nav-risk" },
  { href: "/paper", labelKey: "paper", icon: FlaskConical, testId: "nav-paper" },
  { href: "/monitoring", labelKey: "monitoring", icon: Activity, testId: "nav-monitoring" },
  {
    href: "/execution/position-diff",
    labelKey: "positionDiff",
    icon: ClipboardList,
    testId: "nav-position-diff",
  },
  {
    href: "/execution/ticket",
    labelKey: "ticket",
    icon: Receipt,
    testId: "nav-ticket",
  },
  {
    href: "/execution/fills",
    labelKey: "fills",
    icon: Upload,
    testId: "nav-fills",
  },
  {
    href: "/execution/journal-history",
    labelKey: "journal",
    icon: History,
    testId: "nav-journal",
  },
  {
    href: "/execution/account",
    labelKey: "account",
    icon: Wallet,
    testId: "nav-account",
  },
  { href: "/snapshots", labelKey: "snapshots", icon: DatabaseBackup, testId: "nav-snapshots" },
  { href: "/backlog", labelKey: "backlog", icon: ListTodo, testId: "nav-backlog" },
];
