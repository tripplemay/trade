/**
 * B023 F003 acceptance #4 + B024 F003 — Frontend regression: any button
 * labelled "execute" / "place order" / "send to broker" (English) OR
 * 「执行 / 下单 / 发送券商 / 立即买入 / 实盘 / 真实交易 / 自动交易 /
 * 一键交易」 (Chinese) is forbidden.
 *
 * The workbench is research-only (B023 §Hard boundaries). The execution
 * pages generate Markdown checklists for the user to act on manually
 * in their broker app; the workbench never sends an order. This guard
 * grep-scans every `(protected)/execution/**` page for the forbidden
 * labels so a future refactor (in either language) can't quietly add a
 * button that suggests the workbench performs execution.
 *
 * Why also scan messages/zh-CN.json:
 *   - B024 F003 moves user-facing copy into the i18n bundle. A forbidden
 *     phrase could land inside the bundle even if no JSX text node
 *     contains it literally. We scan the bundle for the exact button-
 *     label keys (and require that no value matches a banned phrase).
 *
 * String literals that legitimately mention the phrase in user-facing
 * disclaimer copy ("the workbench does NOT place orders" / 「工作台从不
 * 下单」) are kept out of the offending list by anchoring the regex to
 * a JSX text-node or button-label assignment shape — disclaimers in
 * comments / paragraphs / aria copy are fine.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const EXECUTION_DIR = join(FRONTEND_ROOT, "src", "app", "(protected)", "execution");
// B037 F002/F003 — the restructured Home is a no-execution surface too
// (no order/execute buttons; read-only NAV + Day P&L + sleeve breakdown).
// Scan it alongside the execution pages so a future Home edit can't add
// an execution affordance in either language.
const HOME_PAGE = join(FRONTEND_ROOT, "src", "app", "(protected)", "page.tsx");
// B038 F002 — the Home "Today's market news" panel is part of the same
// no-execution Home surface; scan it so a future edit can't add an
// order/execute affordance (in either language) to the news element.
const HOME_NEWS_PANEL = join(FRONTEND_ROOT, "src", "components", "home", "HomeNewsPanel.tsx");
// B039 F001 — the Home AI Advisor section (with its research disclaimer) is
// part of the same no-execution Home surface; scan it so a future edit can't
// add an order/execute affordance (in either language) to the advisor element.
const ADVISOR_SECTION = join(FRONTEND_ROOT, "src", "components", "advisor", "AdvisorSection.tsx");
// B040 F002 — the shared Robinhood metrics display (used by /backtest and
// /reports) is a read-only surface; scan it so a future edit can't add an
// order/execute affordance to the metrics card in either language.
const METRICS_DISPLAY = join(FRONTEND_ROOT, "src", "components", "metrics", "MetricsDisplay.tsx");
// B041 F001 — the simplified target-positions card view is a read-only surface
// (target/current/delta weights, no order affordance); scan it so a future edit
// can't add an execute/order button in either language.
const POSITION_CARDS = join(
  FRONTEND_ROOT,
  "src",
  "components",
  "recommendations",
  "PositionCards.tsx",
);
// B059 F002 — the symbol-lookup page + its price chart are a research-only
// read-only surface (EOD price/stats; no order affordance). Scan them so a
// future edit can't add a buy/sell/execute button in either language.
const SYMBOLS_PAGE = join(FRONTEND_ROOT, "src", "app", "(protected)", "symbols", "page.tsx");
const PRICE_CHART = join(FRONTEND_ROOT, "src", "components", "chart", "PriceChart.tsx");
// B060 F001 — the shared SymbolLink wires every displayed ticker site-wide to
// a click-through to the read-only /symbols detail page. It is research-only
// navigation (NOT an order/execute affordance); scan it so a future edit can't
// turn the clickable symbol into a buy/sell button in either language.
const SYMBOL_LINK = join(FRONTEND_ROOT, "src", "components", "symbol", "SymbolLink.tsx");
// B067 F003 — the cn_attack out-of-sample honesty disclosure is a research-only
// advisory banner (it renders the negative-OOS caveat; no order/execute
// affordance). Scan it so a future edit can't add a buy/sell/execute button in
// either language to the A-share attack advisory surface.
const CN_ATTACK_OOS_DISCLOSURE = join(
  FRONTEND_ROOT,
  "src",
  "components",
  "recommendations",
  "CnAttackOosDisclosure.tsx",
);
const MESSAGES_DIR = join(FRONTEND_ROOT, "messages");

const EN_BANNED = ["execute", "place order", "send to broker"] as const;

// B024 F003 banned Chinese phrases — the workbench surface must never
// describe a manual-checklist button as if it performs the trade.
const ZH_BANNED = [
  "执行",
  "下单",
  "发送券商",
  "立即买入",
  "实盘",
  "真实交易",
  "自动交易",
  "一键交易",
] as const;

const EN_FORBIDDEN_JSX = /(?:>\s*)(execute|place\s+order|send\s+to\s+broker)(?:\s*<)/i;
const ZH_FORBIDDEN_JSX = new RegExp(`(?:>\\s*)(?:${ZH_BANNED.join("|")})(?:\\s*<)`);

// `children: "Execute"` / `aria-label="Execute"` shapes.
const EN_FORBIDDEN_ASSIGN =
  /(?:children|label|title|aria-label)\s*[:=]\s*"(?:execute|place\s+order|send\s+to\s+broker)/i;
const ZH_FORBIDDEN_ASSIGN = new RegExp(
  `(?:children|label|title|aria-label)\\s*[:=]\\s*"(?:${ZH_BANNED.join("|")})`,
);

function collectPageFiles(root: string): string[] {
  const out: string[] = [];
  function walk(dir: string): void {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.tsx?$/.test(entry)) continue;
      out.push(full);
    }
  }
  walk(root);
  return out;
}

describe("no execution buttons under (protected)/execution/** + Home", () => {
  const files = [
    ...collectPageFiles(EXECUTION_DIR),
    HOME_PAGE,
    HOME_NEWS_PANEL,
    ADVISOR_SECTION,
    METRICS_DISPLAY,
    POSITION_CARDS,
    SYMBOLS_PAGE,
    PRICE_CHART,
    SYMBOL_LINK,
    CN_ATTACK_OOS_DISCLOSURE,
  ];

  it(`covers the Home page`, () => {
    expect(files).toContain(HOME_PAGE);
  });

  it(`covers the symbol-lookup page + price chart`, () => {
    expect(files).toContain(SYMBOLS_PAGE);
    expect(files).toContain(PRICE_CHART);
  });

  it(`covers the shared SymbolLink component`, () => {
    expect(files).toContain(SYMBOL_LINK);
  });

  it(`covers the recommendations position cards`, () => {
    expect(files).toContain(POSITION_CARDS);
  });

  it(`covers the cn_attack OOS disclosure`, () => {
    expect(files).toContain(CN_ATTACK_OOS_DISCLOSURE);
  });

  it(`covers the Home news panel`, () => {
    expect(files).toContain(HOME_NEWS_PANEL);
  });

  it(`covers the Home advisor section`, () => {
    expect(files).toContain(ADVISOR_SECTION);
  });

  it(`covers the shared metrics display`, () => {
    expect(files).toContain(METRICS_DISPLAY);
  });

  it(`covers at least the 5 execution pages`, () => {
    // B023 ships position-diff + ticket + ticket/[id] + fills +
    // journal-history + account. Floor at 5 to guard against tree
    // pruning.
    expect(files.length).toBeGreaterThanOrEqual(5);
  });

  for (const file of files) {
    const relative = file.slice(FRONTEND_ROOT.length + sep.length);
    it(`${relative} contains no English execute/place-order/send-to-broker button label`, () => {
      const body = readFileSync(file, "utf-8");
      const jsxMatch = body.match(EN_FORBIDDEN_JSX);
      if (jsxMatch) {
        throw new Error(`forbidden English button label detected in ${relative}: ${jsxMatch[0]}`);
      }
      const assignMatch = body.match(EN_FORBIDDEN_ASSIGN);
      if (assignMatch) {
        throw new Error(
          `forbidden English button label assignment in ${relative}: ${assignMatch[0]}`,
        );
      }
    });

    it(`${relative} contains no Chinese 执行/下单/实盘/etc button label`, () => {
      const body = readFileSync(file, "utf-8");
      const jsxMatch = body.match(ZH_FORBIDDEN_JSX);
      if (jsxMatch) {
        throw new Error(`forbidden Chinese button label detected in ${relative}: ${jsxMatch[0]}`);
      }
      const assignMatch = body.match(ZH_FORBIDDEN_ASSIGN);
      if (assignMatch) {
        throw new Error(
          `forbidden Chinese button label assignment in ${relative}: ${assignMatch[0]}`,
        );
      }
    });
  }
});

describe("no forbidden button labels in messages bundle", () => {
  // Banned phrases are only forbidden when used AS a button label key.
  // Disclaimer / description / toast prose may legitimately reference
  // "下单" inside copy like 「工作台从不下单」. Keys with these suffixes
  // are interpreted as button labels:
  const BUTTON_LABEL_KEY_PATTERN =
    /(button|generate|void|save|submit|upload|run|export|reset|delete|edit|create|signIn|signOut|addRow|action|cta)/i;

  for (const locale of ["en", "zh-CN"] as const) {
    it(`${locale}.json: no value at a button-label key contains a banned phrase`, () => {
      const filePath = join(MESSAGES_DIR, `${locale}.json`);
      const bundle = JSON.parse(readFileSync(filePath, "utf-8"));
      const offending: { path: string; value: string }[] = [];

      const walk = (node: unknown, path: string[]): void => {
        if (node === null || node === undefined) return;
        if (typeof node === "string") {
          const finalKey = path[path.length - 1] ?? "";
          if (!BUTTON_LABEL_KEY_PATTERN.test(finalKey)) return;
          for (const phrase of locale === "en" ? EN_BANNED : ZH_BANNED) {
            if (node.toLowerCase().includes(phrase.toLowerCase())) {
              offending.push({ path: path.join("."), value: node });
            }
          }
          return;
        }
        if (typeof node === "object") {
          for (const [k, v] of Object.entries(node)) {
            walk(v, [...path, k]);
          }
        }
      };

      walk(bundle, []);
      if (offending.length > 0) {
        const list = offending.map((o) => `  ${o.path} = ${JSON.stringify(o.value)}`).join("\n");
        throw new Error(`forbidden button-label phrases in ${locale}.json:\n${list}`);
      }
    });
  }
});
