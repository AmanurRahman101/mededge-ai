import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

async function session(context: BrowserContext, role: "doctor" | "patient") {
  await context.addCookies([
    {
      name: "mededge_session",
      value: `ui-${role}`,
      url: "http://127.0.0.1:8023",
    },
  ]);
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  const clipped = await page
    .locator("button, input:not([type=file]), select, summary")
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          return (
            element.getClientRects().length > 0 &&
            rect.width > 2 &&
            (rect.left < -1 || rect.right > window.innerWidth + 1)
          );
        })
        .map(
          (element) =>
            element.textContent?.trim() ||
            element.getAttribute("aria-label") ||
            element.tagName,
        ),
    );
  expect(clipped).toEqual([]);
}

test("visit-centered portals have uncluttered desktop and mobile navigation", async ({
  page,
  context,
}) => {
  await session(context, "doctor");
  await page.goto("/doctor");
  await expect(
    page.getByRole("heading", { name: "Patients", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Nadia \(fictional\)/ }).click();
  await expect(
    page.getByRole("heading", { name: "Nadia (fictional)", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Health summary", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".care-narrative")).toContainText(
    "No fever reported",
  );
  await expect(
    page.locator(".overview-provisional, .overview-clinical, .verified-digest"),
  ).toHaveCount(0);
  for (const theme of ["dark", "light"]) {
    await page.evaluate(
      (t) => document.documentElement.classList.toggle("dark", t === "dark"),
      theme,
    );
    for (const width of [320, 375, 390, 768, 1280, 1440, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      await noOverflow(page);
    }
    for (const [width, label] of [
      [1440, "desktop"],
      [390, "mobile"],
    ] as const) {
      await page.setViewportSize({ width, height: 900 });
      await page.screenshot({
        path: `../scripts/out/ui/visits-doctor-${label}-${theme}.png`,
        fullPage: true,
      });
    }
  }
  await page.getByRole("button", { name: "Start visit", exact: true }).click();
  await expect(page).toHaveURL(/doctor\/visits\/ui-visit$/);
  await expect(
    page.getByRole("heading", { name: "In this visit", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Report & voice", exact: true })
    .click();
  await expect(page.getByLabel("Choose an image")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Check privacy preview", exact: true }),
  ).toBeDisabled();
  await page.goto("/doctor/records/ui-report");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(
    page.getByRole("heading", { name: "Published note", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Report reading", exact: true })
    .click();
  await expect(page.locator(".reading-module")).toContainText("CRP");
  await expect(page.locator(".doctor-compare-source img")).toBeVisible();
});

test("patient visits, saved reports, medicine edits and consent remain easy to reach", async ({
  page,
  context,
}) => {
  await session(context, "patient");
  await page.goto("/patient");
  await expect(
    page.getByRole("heading", { name: "Nadia (fictional)", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Visits", exact: true }).click();
  await expect(page.locator(".care-visit-list")).toContainText(
    "Follow-up consultation",
  );
  await page.getByRole("button", { name: /Follow-up consultation/ }).click();
  await expect(
    page.getByRole("button", { name: "New prescription", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Complete visit", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const menu = page.locator(".record-manage").first();
  await menu.locator("summary").click();
  await expect(
    menu.getByRole("button", { name: "Rename", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).not.toHaveAttribute("open", "");
  await page.goto("/patient/health");
  await page
    .getByRole("button", { name: "Add a medicine", exact: true })
    .click();
  await page
    .getByLabel("Medicine name and strength")
    .fill("Fictional current medicine");
  await expect(page.getByLabel("Find a Bangladesh medicine")).toBeHidden();
  await page
    .getByRole("button", { name: "I take this medicine", exact: true })
    .click();
  await page.reload();
  await expect(page.locator(".current-medicine-list")).toContainText(
    "Fictional current medicine",
  );
  await page
    .getByRole("button", {
      name: "Edit Fictional current medicine",
      exact: true,
    })
    .click();
  await page.getByLabel("How you take it").fill("Fictional instructions");
  await page
    .getByRole("button", { name: "Save medicine changes", exact: true })
    .click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", {
      name: "Remove Fictional current medicine from my list",
      exact: true,
    })
    .click();
  await expect(page.locator(".current-medicine-list")).toHaveCount(0);
  await page.goto("/patient/visits");
  await expect(page.locator(".care-visit-list")).toContainText(
    "Follow-up consultation",
  );
  for (const theme of ["dark", "light"]) {
    await page.evaluate(
      (t) => document.documentElement.classList.toggle("dark", t === "dark"),
      theme,
    );
    for (const width of [320, 375, 390, 768, 1280, 1440, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      await noOverflow(page);
    }
    for (const [width, label] of [
      [1440, "desktop"],
      [390, "mobile"],
    ] as const) {
      await page.setViewportSize({ width, height: 900 });
      await page.screenshot({
        path: `../scripts/out/ui/visits-patient-${label}-${theme}.png`,
        fullPage: true,
      });
    }
  }
  await page.getByRole("button", { name: "Doctors", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Share with a doctor", exact: true }),
  ).toBeVisible();
});

test("a visit groups a published note, completion and patient readback", async ({
  page,
  context,
  browser,
}) => {
  await session(context, "doctor");
  await page.goto("/doctor/patients/ui-new-patient");
  await page.getByRole("button", { name: "Start visit", exact: true }).click();
  await expect(page).toHaveURL(/\/doctor\/visits\/[^/]+$/);
  const visitUrl = page.url();
  await page.getByRole("button", { name: "Write note", exact: true }).click();
  await page
    .getByLabel("English version")
    .fill("Fictional visit: symptoms improved. Follow up as discussed.");
  await page
    .getByLabel("বাংলা সংস্করণ")
    .fill("কাল্পনিক সাক্ষাৎ: উপসর্গ কমেছে।");
  await page
    .getByRole("checkbox", { name: /I reviewed the transcript/ })
    .check();
  await page
    .getByRole("button", { name: "Verify and publish", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Published note", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Back to patient chart/ }).click();
  await expect(page).toHaveURL(visitUrl);
  await expect(page.locator(".care-artifact-row")).toContainText(
    "Reviewed by doctor",
  );
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Complete visit", exact: true })
    .click();
  await expect(page.locator(".care-visit-heading")).toContainText("Completed");
  const patient = await browser.newContext({
    baseURL: "http://127.0.0.1:8023",
  });
  try {
    await patient.addCookies([
      {
        name: "mededge_session",
        value: "ui-new-patient",
        url: "http://127.0.0.1:8023",
      },
    ]);
    const other = await patient.newPage();
    await other.goto(visitUrl.replace("/doctor/", "/patient/"));
    await expect(other.locator(".care-artifact-row")).toContainText(
      "Visit note",
    );
    await other.getByRole("button", { name: /Visit note/ }).click();
    await expect(other.locator(".published-note")).toContainText(
      "Fictional visit: symptoms improved",
    );
  } finally {
    await patient.close();
  }
});

test("published notes print with light contrast and stale account tabs pause", async ({
  page,
  context,
}) => {
  await session(context, "patient");
  await page.goto("/patient/records/ui-report");
  await expect(page.locator(".published-note")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  const colors = await page.locator(".published-note").evaluate((el) => ({
    bg: getComputedStyle(el).backgroundColor,
    color: getComputedStyle(el).color,
  }));
  expect(colors.bg).toBe("rgb(255, 255, 255)");
  expect(colors.color).toBe("rgb(17, 17, 17)");
  await page.pdf({
    path: "../scripts/out/ui/published-note.pdf",
    printBackground: true,
  });
  await page.emulateMedia({ media: "screen" });
  await context.addCookies([
    {
      name: "mededge_session",
      value: "ui-doctor",
      url: "http://127.0.0.1:8023",
    },
  ]);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByRole("heading", { name: "Account changed", exact: true }),
  ).toBeVisible();
  await expect(page.locator("main")).not.toBeVisible();
});
