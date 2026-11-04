import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

async function login(context: BrowserContext, role = "doctor") {
  await context.addCookies([
    {
      name: "mededge_session",
      value: `ui-${role}`,
      url: "http://127.0.0.1:8023",
    },
  ]);
}
async function openEntry(page: Page) {
  await page.goto("/doctor");
  await page.getByRole("button", { name: /Nadia \(fictional\)/ }).click();
  await page.getByRole("button", { name: "Start visit", exact: true }).click();
  await page
    .getByRole("button", { name: "New prescription", exact: true })
    .click();
}
function wav() {
  const buffer = Buffer.alloc(44 + 4800);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(buffer.length - 8, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(24000, 24);
  buffer.writeUInt32LE(48000, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(4800, 40);
  return buffer;
}
async function bounds(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  const clipped = await page
    .locator("button, input:not([type=file]), select, textarea, summary")
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          return (
            element.getClientRects().length > 0 &&
            rect.width > 2 &&
            (rect.left < -1 || rect.right > innerWidth + 1)
          );
        })
        .map((element) => element.textContent),
    );
  expect(clipped).toEqual([]);
}

test("shared demo report entry offers fictional sources instead of a forbidden file upload", async ({
  page,
}) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "demo-doctor",
          role: "doctor",
          full_name: "Demo Doctor",
          email: "fictional@example.test",
          verified: true,
        },
        csrf_token: "fictional",
      },
    }),
  );
  await page.route("**/api/visits/demo-visit", (route) =>
    route.fulfill({
      json: {
        id: "demo-visit",
        patient_id: "demo-patient",
        patient_name: "Demo Patient",
        doctor_id: "demo-doctor",
        can_edit: true,
        status: "open",
        records: [],
      },
    }),
  );
  await page.goto("/doctor/visits/demo-visit/report");
  await expect(page.getByLabel("Choose an image")).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: "Choose a fictional sample report",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Shared demo: choose a fictional sample. File upload is unavailable.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.screenshot({
    path: "../scripts/out/ui/shared-demo-report.png",
    fullPage: true,
  });
});

test("manual prescription: registry lookup, editing, publication, patient view and print", async ({
  page,
  context,
  browser,
}) => {
  await login(context);
  await openEntry(page);
  await page
    .getByRole("button", { name: "Write manually", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Start manual prescription", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prescription", exact: true }),
  ).toBeVisible();
  const recordId = page.url().split("/").at(-1)!;
  await page
    .getByRole("button", { name: "Add medicine manually", exact: true })
    .click();
  const row = page.getByRole("article", { name: "Medicine 1", exact: true });
  await row
    .getByLabel("Medicine name", { exact: true })
    .fill("Fictional manual name");
  await row.getByLabel("Strength and unit").fill("5 mg");
  await row.getByLabel("Morning", { exact: true }).fill("½");
  await row.getByLabel("Noon", { exact: true }).fill("0");
  await row.getByLabel("Duration", { exact: true }).fill("চলবে");
  await row.locator(":scope > details > summary").click();
  await row.getByLabel("Find a Bangladesh medicine").fill("Napa");
  await row.getByRole("button", { name: "Search", exact: true }).click();
  await expect(row.locator(".medicine-search-results")).toContainText(
    "Fictional ingredient 5 mg",
  );
  await row
    .getByRole("button", { name: /Choose Fictional reference brand/ })
    .click();
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveValue(
    "Fictional reference brand",
  );
  await row.locator(":scope > details > summary").click();
  await row.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Prescription draft saved.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(row.getByLabel("Morning", { exact: true })).toHaveValue("½");
  await expect(row.getByLabel("Noon", { exact: true })).toHaveValue("0");
  await expect(row.getByLabel("Night", { exact: true })).toHaveValue("");
  await mkdir("../scripts/out/ui", { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate(
      (t) => document.documentElement.classList.toggle("dark", t === "dark"),
      theme,
    );
    for (const width of [320, 390, 831, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await bounds(page);
      if (width === 390 || width === 1440)
        await page.screenshot({
          path: `../scripts/out/ui/prescription-${width}-${theme}.png`,
          fullPage: true,
        });
    }
  }
  await page
    .getByRole("checkbox", { name: /I checked every medicine/ })
    .check();
  await page
    .getByRole("button", {
      name: "Verify and publish prescription",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Published prescription", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".prescription-table")).toContainText("চলবে");
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.emulateMedia({ media: "print" });
  await page.evaluate(() => document.fonts.ready);
  const overflow = await page
    .locator(".prescription-table th, .prescription-table td")
    .evaluateAll((cells) =>
      cells
        .filter((cell) => {
          const box = cell.getBoundingClientRect();
          const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            const range = document.createRange();
            range.selectNodeContents(walker.currentNode);
            if (
              [...range.getClientRects()].some(
                (rect) =>
                  rect.left < box.left - 1 || rect.right > box.right + 1,
              )
            )
              return true;
          }
          return false;
        })
        .map((cell) => cell.textContent),
    );
  expect(overflow).toEqual([]);
  await page.pdf({
    path: "../scripts/out/ui/prescription-print.pdf",
    printBackground: true,
    format: "A4",
  });
  await expect(page.locator(".prescription-audio")).toHaveCount(0);
  await expect(page.locator(".prescription-editor")).toHaveCount(0);
  await page.emulateMedia({ media: "screen" });
  const patient = await browser.newContext({
    baseURL: "http://127.0.0.1:8023",
  });
  try {
    await login(patient, "patient");
    const patientPage = await patient.newPage();
    await patientPage.goto(`/patient/records/${recordId}`);
    await expect(patientPage.locator(".prescription-table")).toContainText(
      "Fictional reference brand",
    );
    await expect(patientPage.locator(".prescription-table")).toContainText("½");
  } finally {
    await patient.close();
  }
  await page
    .getByRole("button", { name: "Create amendment", exact: true })
    .click();
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveValue(
    "Fictional reference brand",
  );
  await row.getByLabel("Strength and unit").fill("Corrected strength");
  await expect(row.getByRole("checkbox")).not.toBeChecked();
  await expect(
    page.locator(".published-note .prescription-table"),
  ).toContainText("5 mg");
});

test("voice-only prescription: no image, original audio, editable rows and saved corrections", async ({
  page,
  context,
}) => {
  await login(context);
  await openEntry(page);
  let submissions = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/prescriptions"))
      submissions++;
  });
  await page.getByLabel("Or upload a recording (WAV)").setInputFiles({
    name: "fictional.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page
    .getByRole("button", { name: "Create prescription draft", exact: true })
    .click();
  const row = page.getByRole("article", { name: "Medicine 1", exact: true });
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveValue(
    "Fictional medicine",
  );
  await expect(
    page.getByRole("heading", { name: "Original dictation", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: /report/i })).toHaveCount(0);
  await row
    .getByLabel("Medicine name", { exact: true })
    .fill("Doctor-corrected fictional medicine");
  await row.getByLabel("Night", { exact: true }).fill("");
  await page
    .getByRole("button", { name: "Add medicine manually", exact: true })
    .click();
  await expect(
    page.getByRole("article", { name: "Medicine 2", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Remove medicine 2", exact: true })
    .click();
  await row.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Prescription draft saved.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveValue(
    "Doctor-corrected fictional medicine",
  );
  expect(submissions).toBe(1);
});

test("handwritten prescription plus voice produces an editable evidence-backed medication table in its visit", async ({
  page,
  context,
  browser,
}) => {
  await login(context);
  await page.goto("/doctor/visits/ui-visit/prescription");
  await page
    .getByRole("button", { name: "Upload handwritten prescription", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Upload handwritten prescription", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Choose a prescription image", { exact: true })).toBeVisible();
  const image = await page.request.get(
    "/api/runs/ui-report/files/redacted.png",
  );
  expect(image.ok()).toBe(true);
  await page.getByLabel("Choose a prescription image").setInputFiles({
    name: "fictional.png",
    mimeType: "image/png",
    buffer: await image.body(),
  });
  await page.getByText("Use a recording file", { exact: true }).click();
  await page.getByLabel("WAV recording", { exact: true }).setInputFiles({
    name: "fictional.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page
    .getByRole("button", { name: "Check privacy preview", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm privacy & continue", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prescription", exact: true }),
  ).toBeVisible();
  const runId = page.url().split("/").at(-1)!;
  const row = page.getByRole("article", { name: "Medicine 1", exact: true });
  await expect(row.getByLabel("Medicine name", { exact: true })).toHaveValue(
    "Fictional medicine",
  );
  await expect(row.getByRole("checkbox")).not.toBeChecked();
  await row.locator(":scope > details > summary").click();
  await expect(row).toContainText("Fictional image medicine");
  await expect(row).toContainText("Fictional doctor voice");
  await row
    .getByLabel("Medicine name", { exact: true })
    .fill("Doctor corrected fictional medicine");
  await row.getByLabel("Strength and unit").fill("10 mg");
  await row.getByLabel("Morning", { exact: true }).fill("½");
  await row.getByLabel("Noon", { exact: true }).fill("0");
  await row.getByLabel("Duration", { exact: true }).fill("চলবে");
  await row.getByRole("checkbox").check();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator(".prescription-scan img")).toBeVisible();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(page.locator(".prescription-scan img")).toHaveAttribute(
    "style",
    /150%/,
  );
  await page.getByRole("button", { name: "Fit width", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(page.locator(".rx-mobile-views")).toBeHidden();
  const sourcePosition = await page.locator(".prescription-scan").boundingBox();
  const reviewPosition = await page
    .locator(".prescription-draft-fields")
    .boundingBox();
  expect(Math.abs(sourcePosition!.y - reviewPosition!.y)).toBeLessThan(90);
  await page.screenshot({
    path: "../scripts/out/ui/visit-medication-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 900 });
  await expect(page.locator(".prescription-scan")).toBeHidden();
  await page.getByRole("button", { name: "Source", exact: true }).click();
  await expect(page.locator(".prescription-scan img")).toBeVisible();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await bounds(page);
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Prescription draft saved.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(row.getByLabel("Strength and unit")).toHaveValue("10 mg");
  await page
    .getByRole("checkbox", { name: /I checked every medicine/ })
    .check();
  await page
    .getByRole("button", {
      name: "Verify and publish prescription",
      exact: true,
    })
    .click();
  await expect(
    page.locator(".published-note .prescription-table"),
  ).toContainText("Doctor corrected fictional medicine");
  const patient = await browser.newContext({
    baseURL: "http://127.0.0.1:8023",
  });
  try {
    await login(patient, "patient");
    const other = await patient.newPage();
    await other.goto(`/patient/records/${runId}`);
    await expect(other.locator(".prescription-table")).toContainText("10 mg");
    await expect(other.locator(".prescription-table")).toContainText("চলবে");
  } finally {
    await patient.close();
  }
});
