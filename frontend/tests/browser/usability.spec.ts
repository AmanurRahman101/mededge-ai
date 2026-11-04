import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function session(context: BrowserContext, role: "patient" | "doctor") {
  await context.addCookies([{ name: "mededge_session", value: `ui-${role}`, url: "http://127.0.0.1:8023" }]);
}
async function bounds(page: Page) {
  const overflow = await page.evaluate(() => ({width: innerWidth, document: document.documentElement.scrollWidth, elements: [...document.querySelectorAll("main *, header *")].filter(node => { const box = node.getBoundingClientRect(); return box.width > 1 && (box.left < -1 || box.right > innerWidth + 1); }).map(node => `${node.tagName}.${node.className}: ${node.textContent?.slice(0, 60)}`)}));
  expect(overflow.document <= overflow.width + 1, JSON.stringify(overflow)).toBe(true);
  expect(await page.locator("button, input:not([type=file]), textarea, select, summary").evaluateAll(nodes => nodes.filter(node => {
    const rect = node.getBoundingClientRect(); return node.getClientRects().length && rect.width > 1 && (rect.left < -1 || rect.right > innerWidth + 1);
  }).map(node => node.textContent || node.tagName))).toEqual([]);
}

test("patient language covers medicines, consent, upload and persists without clinical translation", async ({ page, context }) => {
  await session(context, "patient");
  await page.goto("/patient?tab=summary");
  await page.getByRole("button", { name: "বাংলা", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { name: "আপনার স্বাস্থ্যের সারাংশ" })).toBeVisible();
  await page.getByRole("button", { name: "ওষুধ যোগ করুন", exact: true }).click();
  const name = page.getByLabel("ওষুধের নাম ও শক্তি");
  await name.fill("Fictional medicine 5 mg");
  await expect(page.getByLabel("বাংলাদেশের ওষুধ খুঁজুন")).toBeHidden();
  await page.getByRole("button", { name: "বাংলা", exact: true }).click();
  await expect(name).toHaveValue("Fictional medicine 5 mg");
  await page.getByRole("button", { name: "বাতিল", exact: true }).click();
  await page.route("**/api/chart/connections", async route => {
    const response = await route.fetch(); const data = await response.json();
    data.connections[0].status = "pending";
    await route.fulfill({ json: data });
  });
  await page.reload();
  await page.getByRole("button", { name: /^আমার ডাক্তার/ }).click();
  await expect(page.locator(".consent-details")).toContainText("ডাউনলোড করা তথ্য ফেরত নেওয়া যায় না");
  await expect(page.locator(".consent-details")).toContainText("Meta");
  await expect(page.getByRole("button", { name: "এই ডাক্তারকে অনুমতি দিন" })).toBeDisabled();
  await page.getByRole("button", { name: "রিপোর্ট যোগ করুন", exact: true }).click();
  await expect(page.getByText("ছবি বেছে নিন", { exact: true })).toBeVisible();
  await expect(page.getByLabel("রিপোর্টের ছবি")).toHaveAttribute("type", "file");
  await expect(page.locator(".upload-module")).toContainText("ব্যক্তিগত তথ্য");
  for (const theme of ["dark", "light"]) {
    await page.evaluate(t => document.documentElement.classList.toggle("dark", t === "dark"), theme);
    for (const width of [320, 375, 390, 768, 1280, 1440, 1920]) { await page.setViewportSize({ width, height: 900 }); await bounds(page); }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../scripts/out/ui/usability-patient-bn.png", fullPage: true });
});

test("filtered empty reports recover through visible clear action; open menus stay in bounds", async ({ page, context }) => {
  await session(context, "patient"); await page.goto("/patient");
  await page.getByLabel("Find a report", { exact: true }).fill("No such fictional report");
  await expect(page.getByText("No records found", { exact: true })).toBeVisible();
  await expect(page.locator(".active-filters")).toContainText("No such fictional report");
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.locator(".record-row").first()).toBeVisible();
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const menu = page.locator(".record-manage").first();
    await menu.locator("summary").click(); await bounds(page);
    await page.keyboard.press("Escape"); await expect(menu).not.toHaveAttribute("open", "");
    await expect(menu.locator("summary")).toBeFocused();
    await menu.locator("summary").click(); await page.getByRole("heading", { name: "My health", exact: true }).click();
    await expect(menu).not.toHaveAttribute("open", "");
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.evaluate(() => { document.body.style.zoom = "2"; });
  await bounds(page);
});

test("SPA navigation announces its destination and returns keyboard focus", async ({ page }) => {
  await page.goto("/signin");
  await page.getByRole("button", { name: "Create an account", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Create account", exact: true })).toBeFocused();
  await expect(page).toHaveTitle("Create account · MedEdge AI");
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeFocused();
});

test("prescription review has actionable checks, saved state, and explicit row collapse", async ({ page, context }) => {
  await session(context, "doctor"); await page.goto("/doctor?patient=ui-patient&section=add");
  await page.getByRole("button", { name: "New prescription", exact: true }).click();
  await page.getByRole("button", { name: "Write manually", exact: true }).click();
  await page.getByRole("button", { name: "Start manual prescription", exact: true }).click();
  await page.getByRole("button", { name: "Add medicine manually", exact: true }).click();
  const row = page.getByRole("article", { name: "Medicine 1", exact: true });
  await expect(page.locator(".draft-status")).toHaveText("Unsaved changes");
  await page.getByRole("button", { name: "Unnamed medicine: check name, strength and instructions" }).click();
  await expect(row.getByLabel("Medicine name", { exact: true })).toBeFocused();
  await row.getByLabel("Medicine name", { exact: true }).fill("Fictional checked medicine");
  await row.getByRole("checkbox").check();
  await expect(page.getByText("1 of 1 checked", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Collapse checked medicine" }).click();
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveCount(0);
  await row.getByRole("button", { name: "Edit medicine 1" }).click();
  await expect(row.getByRole("checkbox")).toBeChecked();
  await page.locator("#assessment-bn").fill("");
  await page.getByRole("button", { name: "Add the Bangla assessment" }).click();
  await expect(page.locator("#assessment-bn")).toBeFocused();
  await page.locator("#assessment-bn").fill("কাল্পনিক মূল্যায়ন।");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".draft-status")).toHaveText("Saved");
  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(await page.locator("#assessment-en").evaluate(el => el.getBoundingClientRect().top)).toBe(await page.locator("#assessment-bn").evaluate(el => el.getBoundingClientRect().top));
  await page.screenshot({ path: "../scripts/out/ui/usability-prescription.png", fullPage: true });
  const axe = await new AxeBuilder({ page }).analyze(); expect(axe.violations).toEqual([]);
  await page.getByRole("button", { name: "Back to patient chart", exact: true }).click();
  await expect(page).toHaveURL(/patient=ui-patient.*section=history/);
});

test("saved prescription loading and failure never masquerade as an empty prescription", async ({ page, context }) => {
  await session(context, "doctor");
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/chart/records/loading-prescription/summaries", async route => { await gate; await route.fulfill({ status: 503, json: { detail: "Fictional interrupted connection" } }); });
  await page.route("**/api/runs/loading-prescription", route => route.fulfill({ json: { run_id: "loading-prescription", patient_id: "ui-patient", patient_name: "Nadia (fictional)", input_mode: "manual_prescription", status: "reviewing", trace: [] } }));
  await page.goto("/doctor/records/loading-prescription");
  await expect(page.getByText("Loading the saved prescription…", { exact: true })).toBeVisible();
  await expect(page.getByText("The author has not published this prescription yet.")).toHaveCount(0);
  release();
  await expect(page.getByRole("button", { name: "Try loading again" })).toBeVisible();
  await expect(page.getByText("The author has not published this prescription yet.")).toHaveCount(0);
});
