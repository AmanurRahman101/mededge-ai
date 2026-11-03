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
  await page.getByRole("button", { name: "Nadia (fictional)" }).click();
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
  ).toBeGreaterThan(1300);
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
  await page.getByRole("button", { name: "History", exact: true }).click();
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
  await page.getByRole("button", { name: "Nadia (fictional)" }).click();
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
  await expect(page.locator(".digest-sections")).toContainText(
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
