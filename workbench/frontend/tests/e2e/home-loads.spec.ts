import { expect, test } from "@playwright/test";

test.describe("workbench home page", () => {
  test("loads the placeholder card and disclaimer", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("workbench-home")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workbench scaffold OK" })).toBeVisible();

    const disclaimer = page.getByTestId("workbench-disclaimer");
    await expect(disclaimer).toBeVisible();
    await expect(disclaimer).toContainText(/research-only/i);
  });
});
