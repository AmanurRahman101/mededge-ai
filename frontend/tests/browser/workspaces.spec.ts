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
  const clipped = await page.locator("button, input:not([type=file]), select, summary").evaluateAll(elements => elements.filter(element => {
    const rect = element.getBoundingClientRect();
    return element.getClientRects().length > 0 && rect.width > 2 && (rect.left < -1 || rect.right > window.innerWidth + 1);
  }).map(element => element.textContent?.trim() || element.getAttribute("aria-label") || element.tagName));
  expect(clipped).toEqual([]);
}

test("doctor workspace: modular desktop/mobile, both themes, source and editable note", async ({
  page,
  context,
}) => {
  await session(context, "doctor");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/doctor");
  await page.getByRole("button", { name: /Nadia \(fictional\)/ }).click();
  await expect(
    page.getByRole("heading", { name: "Verified history at a glance" }),
  ).toBeVisible();
  await expect(page.locator(".digest-sections")).toContainText(
    "No fever reported",
  );
  await expect(page.getByText("Superseded note", { exact: true })).toHaveCount(
    0,
  );
  expect(
    await page
      .locator(".workspace-grid")
      .evaluate((el) => el.getBoundingClientRect().width),
  ).toBeLessThanOrEqual(1200);
  await expect(page.locator(".current-medicines .empty-inline")).toBeVisible();
  await page.route("**/api/chart/patients/ui-patient/medicines", route => route.fulfill({
    json: { medicines: [{id:"fictional", name:"Newly reported fictional medicine", instructions:"As prescribed", confirmed_at:"2026-11-04T00:00:00Z"}] }
  }));
  await page.locator(".patient-overview > .module-heading").getByRole("button", {name:"Refresh", exact:true}).click();
  await expect(page.locator(".current-medicine-list")).toContainText("Newly reported fictional medicine");
  await expect(page.locator(".current-medicine-list")).toContainText("Reported by patient");
  await page.unroute("**/api/chart/patients/ui-patient/medicines");
  await page.locator(".patient-overview > .module-heading").getByRole("button", {name:"Refresh", exact:true}).click();
  await expect(page.locator(".current-medicines .empty-inline")).toBeVisible();
  await mkdir("../scripts/out/ui", { recursive: true });
  for (const theme of ["dark", "light"]) {
    await page.evaluate(
      (t) => document.documentElement.classList.toggle("dark", t === "dark"),
      theme,
    );
    for (const [width, height, label] of [
      [1440, 1000, "desktop"],
      [390, 844, "mobile"],
    ] as const) {
      await page.setViewportSize({ width, height });
      await noOverflow(page);
      await page.screenshot({
        path: `../scripts/out/ui/doctor-${label}-${theme}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Reports & history", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Today's visit/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Add report & note", exact: true })
    .click();
  await expect(page.getByLabel("Choose an image")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue to privacy review" }),
  ).toBeDisabled();
  await page.goto("/doctor/records/ui-report");
  await expect(
    page.getByRole("heading", { name: "Published note", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Report reading", exact: true })
    .click();
  await expect(page.getByText("CRP", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Image & recording", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: /Report with private/ }),
  ).toBeVisible();
  await page.goto("/doctor/records/ui-draft");
  await expect(page.getByLabel("Voice transcript")).toBeVisible();
  await page
    .getByLabel("English version")
    .fill("Fictional new history: symptoms resolved.");
  await page
    .getByLabel("বাংলা সংস্করণ")
    .fill("কাল্পনিক নতুন ইতিহাস: উপসর্গ সেরে গেছে।");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("Draft saved.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("English version")).toHaveValue(
    "Fictional new history: symptoms resolved.",
  );
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Verify and publish", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Published note", exact: true }),
  ).toBeVisible();
  await page.goto("/doctor");
  await page.getByRole("button", { name: /Nadia \(fictional\)/ }).click();
  await expect(page.locator(".digest-sections")).toContainText(
    "symptoms resolved",
  );
  await expect(
    page.getByRole("button", { name: /FHIR|How this record/ }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("patient: manage dropdown closes, summary and record tabs in both themes", async ({
  page,
  context,
}) => {
  await session(context, "patient");
  await page.goto("/patient");
  await expect(page.getByRole("searchbox")).toBeVisible();
  for (const width of [320, 375, 390, 768, 831, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator(".patient-tools > summary").click();
    await expect(page.getByRole("combobox", { name: "Type", exact: true })).toBeVisible();
    await noOverflow(page);
    await page.locator(".patient-tools > summary").click();
  }

  await expect(page.getByText("See recent changes", { exact: true })).toHaveCount(0);
  const manage = page.locator(".record-manage").first();
  await manage.locator("summary").click();
  await expect(
    manage.getByRole("button", { name: "Rename", exact: true }),
  ).toBeVisible();
  await manage.locator("summary").click();
  await expect(
    manage.getByRole("button", { name: "Rename", exact: true }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "My summary", exact: true }).click();
  await expect(page.locator(".health-narrative")).toContainText(
    "No fever reported",
  );
  for (const theme of ["dark", "light"]) {
    await page.evaluate(
      (t) => document.documentElement.classList.toggle("dark", t === "dark"),
      theme,
    );
    for (const [width, height, label] of [
      [1440, 1000, "desktop"],
      [390, 844, "mobile"],
    ] as const) {
      await page.setViewportSize({ width, height });
      await noOverflow(page);
      await page.screenshot({
        path: `../scripts/out/ui/patient-${label}-${theme}.png`,
        fullPage: true,
      });
    }
  }
  await expect(page.locator(".source-links")).toHaveCount(0);
  await expect(page.getByText("What your doctor shared", { exact: true })).toHaveCount(0);
  await expect(page.locator(".overview-clinical")).toHaveCount(0);
  await page.getByRole("button", { name: "Add a medicine", exact: true }).click();
  await page.getByLabel("Medicine name and strength").fill("Fictional medicine 5 mg");
  await page.getByLabel("How you take it").fill("Only as prescribed");
  await page.getByRole("button", { name: "I take this medicine", exact: true }).click();
  await expect(page.locator(".current-medicine-list")).toContainText("Fictional medicine 5 mg");
  await page.reload();
  await expect(page.locator(".health-narrative")).toContainText("No fever reported");
  await expect(page.locator(".current-medicine-list")).toContainText("Fictional medicine 5 mg");
  await page.getByRole("button",{name:"Edit Fictional medicine 5 mg",exact:true}).click();
  await page.getByLabel("How you take it").fill("Updated manually by patient");
  await page.getByRole("button",{name:"Save medicine changes",exact:true}).click();
  await expect(page.locator(".current-medicine-list")).toContainText("Updated manually by patient");
  await page.reload();
  await expect(page.locator(".current-medicine-list")).toContainText("Updated manually by patient");
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "Remove Fictional medicine 5 mg from my list", exact: true }).click();
  await expect(page.locator(".current-medicine-list")).toContainText("Fictional medicine 5 mg");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Remove Fictional medicine 5 mg from my list", exact: true }).click();
  await expect(page.locator(".current-medicine-list")).toHaveCount(0);
  await page.getByRole("button", { name: "Detailed history", exact: true }).click();
  await expect(page).toHaveURL(/tab=history/);
  await expect(page.locator(".overview-clinical")).toBeVisible();
  await expect(page.locator(".health-narrative")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Detailed history", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Back to my summary", exact: true }).click();
  await expect(page.locator(".health-narrative")).toBeVisible();
  await page.goto("/patient/records/ui-report");
  await expect(
    page.getByRole("heading", { name: "Your doctor's notes", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Report reading", exact: true })
    .click();
  await expect(page.getByText("CRP", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Image & recording", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "Redacted report", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /FHIR|How this record/ }),
  ).toHaveCount(0);
  await noOverflow(page);
});


test("published notes print with light contrast and stale account tabs pause", async ({page,context}) => {
  await session(context,"patient");
  await page.goto("/patient/records/ui-report");
  await expect(page.locator(".published-note")).toBeVisible();
  await page.emulateMedia({media:"print"});
  const colors = await page.locator(".published-note").evaluate(el => ({bg:getComputedStyle(el).backgroundColor,color:getComputedStyle(el).color}));
  expect(colors.bg).toBe("rgb(255, 255, 255)");
  expect(colors.color).toBe("rgb(17, 17, 17)");
  await page.pdf({path:"../scripts/out/ui/published-note.pdf",printBackground:true});
  await page.emulateMedia({media:"screen"});
  await context.addCookies([{name:"mededge_session",value:"ui-doctor",url:"http://127.0.0.1:8023"}]);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("heading",{name:"Account changed",exact:true})).toBeVisible();
  await expect(page.locator("main")).not.toBeVisible();
});
