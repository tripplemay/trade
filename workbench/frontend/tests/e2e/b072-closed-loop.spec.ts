import { expect, test, type Page } from "@playwright/test";

// B072 F002 — automate BL-B023-S1: the recommend → diff → ticket → fills →
// reconcile → journal trading loop Codex used to smoke by hand. The full stack
// is seeded with the golden fixture (B072 F001 scripts/seed_golden_e2e.py), so
// /recommendations + /execution/position-diff show a real, marked Master target
// and a non-empty diff against the seeded closed-loop account.
//
// Compliance: the workbench is research-only. This loop generates a Markdown
// review checklist, records broker fills (CSV), and reconciles them into a new
// account snapshot — it never places an order. Reconcile has no UI control (it
// is a backend endpoint); the test drives it through the authenticated request
// context, exactly as the manual smoke does.

// Inlined broker fills CSV (generic adapter columns) — a single small SGOV buy
// the seeded account's ample cash covers, so reconcile never overdraws. Kept
// in-spec (not a fixture file) since *.csv is gitignored outside data/fixtures/.
const FILLS_CSV =
  "order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at\n" +
  "1,SGOV,buy,1,100.27,0,0,USD,2026-06-22T15:30:00Z\n";

async function setEnLocale(page: Page): Promise<void> {
  const { hostname } = new URL(test.info().project.use.baseURL ?? "http://127.0.0.1:3000");
  await page.context().addCookies([
    {
      name: "NEXT_LOCALE",
      value: "en",
      domain: hostname,
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
      expires: Math.floor(Date.now() / 1000) + 3600,
    },
  ]);
}

test.describe("B072 F002 — e2e trading loop (recommend → diff → ticket → fills → reconcile → journal)", () => {
  test("drives the golden closed loop end to end and the journal records the reconciled ticket", async ({
    page,
  }) => {
    await setEnLocale(page);

    // 1. RECOMMEND — the golden Master target renders with the research-only
    //    disclaimer (account_present → positions card, not the empty state).
    await page.goto("/recommendations");
    await expect(page.getByTestId("page-recommendations")).toBeVisible();
    await expect(page.getByTestId("recommendations-positions-card")).toBeVisible();
    await expect(page.getByTestId("recommendations-disclaimer-card")).toContainText(
      /research-only/i,
    );

    // 2. DIFF — buy/sell deltas against the seeded closed-loop account. Rows are
    //    present (golden marks resolve every target) → the CSV export is enabled
    //    (it is disabled only when there is nothing to rebalance).
    await page.goto("/execution/position-diff");
    await expect(page.getByTestId("page-position-diff")).toBeVisible();
    await expect(page.getByTestId("position-diff-state")).toBeVisible();
    await expect(page.getByTestId("position-diff-export-csv")).toBeEnabled();
    await expect(page.getByTestId("position-diff-empty")).toHaveCount(0);

    // 3. TICKET — generate the Markdown rebalance checklist.
    await page.goto("/execution/ticket");
    await expect(page.getByTestId("page-ticket")).toBeVisible();
    await page.getByTestId("ticket-generate").click();
    await expect(page.getByTestId("ticket-preview-card")).toBeVisible();
    // The per-row id is the only place the ticket id surfaces; resolve it from
    // the list endpoint (newest first) and confirm it lands in the history.
    const ticketsRes = await page.request.get("/api/execution/tickets?limit=1");
    expect(ticketsRes.ok()).toBeTruthy();
    const ticketId = ((await ticketsRes.json()).items[0]?.id ?? "") as string;
    expect(ticketId).toMatch(/^tkt-/);
    await expect(page.getByTestId(`ticket-history-row-${ticketId}`)).toBeVisible();

    // 4. FILLS — upload the broker CSV against the generated ticket.
    await page.goto("/execution/fills");
    await expect(page.getByTestId("page-fills")).toBeVisible();
    await page.getByTestId("fills-ticket-select").selectOption(ticketId);
    await page.getByTestId("fills-allow-unmatched").check();
    await page.getByTestId("fills-csv-input").setInputFiles({
      name: "b072-fills.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(FILLS_CSV, "utf-8"),
    });
    await page.getByTestId("fills-csv-submit").click();
    await expect(page.getByTestId("fills-preview-card")).toBeVisible();
    await expect(page.getByTestId("fills-history-card")).toBeVisible();
    await expect(page.getByTestId("fills-row-errors-card")).toHaveCount(0);

    // 5. RECONCILE — backend-only endpoint; drive it through the authenticated
    //    request context (the browser storageState cookie rides along).
    const reconcileRes = await page.request.post(`/api/execution/reconcile/${ticketId}`);
    expect(reconcileRes.ok()).toBeTruthy();
    const reconcile = await reconcileRes.json();
    expect(reconcile.already_reconciled).toBe(false);
    expect(reconcile.snapshot_id).toBeTruthy();

    // 6. JOURNAL — the reconciled ticket is recorded (loop closed).
    await page.goto("/execution/journal-history");
    await expect(page.getByTestId("page-journal-history")).toBeVisible();
    await expect(page.getByTestId("journal-history-table-card")).toBeVisible();
    await expect(page.getByTestId(`journal-history-link-${ticketId}`)).toBeVisible();
    await expect(page.getByTestId("journal-history-empty")).toHaveCount(0);
  });
});
