import { test, expect, type Page, type BrowserContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({launchOptions:{args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream"]},permissions:["microphone"]});

async function doctor(page: Page, context: BrowserContext) {
  await context.addCookies([{name:"mededge_session",value:"ui-doctor",url:"http://127.0.0.1:8023"}]);
  await page.goto("/doctor");
  await page.getByRole("button",{name:/Nadia \(fictional\)/}).click();
}
async function draft(page: Page, context: BrowserContext) {
  await doctor(page,context);
  await page.getByRole("button",{name:"Start visit",exact:true}).click();
  await page.getByRole("button",{name:"New prescription",exact:true}).click();
  await page.getByRole("button",{name:"Write manually",exact:true}).click();
  await page.getByRole("button",{name:"Start manual prescription",exact:true}).click();
  await page.getByRole("button",{name:"Add medicine manually",exact:true}).click();
  const input = page.getByRole("article",{name:"Medicine 1",exact:true}).getByLabel("Medicine name",{exact:true});
  await input.fill("Unsaved fictional audit medicine");
  return input;
}

test("sign-out cancellation keeps the session and unsaved prescription",async({page,context}) => {
  const input = await draft(page,context);
  let logoutRequests=0;
  page.on("request",r=>{if(r.url().endsWith("/api/auth/logout"))logoutRequests++;});
  let decisions=0;
  page.once("dialog",async dialog=>{decisions++; await dialog.dismiss();});
  await page.getByRole("button",{name:"Sign out",exact:true}).click();
  expect(decisions).toBe(1);
  expect(logoutRequests).toBe(0);
  await expect(input).toHaveValue("Unsaved fictional audit medicine");
  await expect(page.getByRole("button",{name:"Sign out",exact:true})).toBeVisible();
});

test("native browser Back cancellation keeps an unsaved prescription",async({page,context})=>{
  const input=await draft(page,context);
  const url=page.url();
  let decisions=0;
  page.once("dialog",async dialog=>{decisions++; await dialog.dismiss();});
  await page.goBack();
  await expect.poll(()=>decisions).toBe(1);
  await expect(page).toHaveURL(url);
  await expect(input).toHaveValue("Unsaved fictional audit medicine");
});

test("patient selection and visit routes survive reload and browser history",async({page,context})=>{
  await doctor(page,context);
  await expect(page).toHaveURL(/doctor\/patients\/ui-patient/);
  await page.getByRole("button",{name:"Start visit",exact:true}).click();
  await expect(page).toHaveURL(/doctor\/visits\/ui-visit$/);
  await page.reload();
  await expect(page.getByRole("heading",{name:"Follow-up consultation",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"New prescription",exact:true}).click();
  await page.goBack();
  await expect(page).toHaveURL(/doctor\/visits\/ui-visit$/);
});

test("a slow prescription save locks inputs until the saved revision is loaded",async({page,context})=>{
  const input=await draft(page,context);
  let release:()=>void=()=>{};
  let started:()=>void=()=>{};
  const gate=new Promise<void>(r=>{release=r;});
  const waiting=new Promise<void>(r=>{started=r;});
  await page.route("**/api/chart/records/*/summaries/*?publish=false",async route=>{
    started(); await gate; await route.continue();
  });
  try {
    await page.getByRole("button",{name:"Save draft",exact:true}).click();
    await waiting;
    await expect(input).toBeDisabled();
  } finally {release();}
  await expect(page.getByText("Prescription draft saved.",{exact:true})).toBeVisible();
  await expect(input).toBeEnabled();
});

test("session expiry and network failure preserve edits and recover with one session check",async({page,context})=>{
  const input=await draft(page,context);
  await page.route("**/api/auth/me",route=>route.fulfill({status:401,json:{detail:"Session expired"}}));
  await page.evaluate(()=>window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("heading",{name:"Please sign in again",exact:true})).toBeVisible();
  await expect(page.locator("main")).not.toBeVisible();
  await page.unroute("**/api/auth/me");
  await page.route("**/api/auth/me",route=>route.abort("failed"));
  await page.getByRole("button",{name:"Check account again",exact:true}).click();
  await expect(page.getByRole("heading",{name:"We couldn’t check your session",exact:true})).toBeVisible();
  await page.unroute("**/api/auth/me");
  let checks=0;
  page.on("request",r=>{if(r.url().endsWith("/api/auth/me"))checks++;});
  await page.getByRole("button",{name:"Check account again",exact:true}).click();
  await expect(input).toBeVisible();
  await expect(input).toHaveValue("Unsaved fictional audit medicine");
  expect(checks).toBe(1);
});

test("patient and doctor primary screens pass automated accessibility checks in both themes",async({page,context})=>{
  for(const role of ["patient","doctor"] as const){
    await context.addCookies([{name:"mededge_session",value:`ui-${role}`,url:"http://127.0.0.1:8023"}]);
    await page.goto(`/${role}`);
    await expect(page.getByRole("button",{name:"Account",exact:true})).toBeVisible();
    for(const theme of ["light","dark"]){
      await page.evaluate(t=>document.documentElement.classList.toggle("dark",t==="dark"),theme);
      for(const width of [320,1440]){
        await page.setViewportSize({width,height:1000});
        const results=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
        expect(results.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),`${role}/${theme}/${width}`).toEqual([]);
      }
    }
  }
});

test.describe("microphone privacy",()=>{
  test("pausing a changed account stops capture and retains the recording in memory",async({page,context})=>{
    await page.addInitScript(()=>{
      const state=window as Window & {auditCapturedSamples?:number};
      state.auditCapturedSamples=0;
      const NativeAudioNode=window.AudioWorkletNode;
      window.AudioWorkletNode=class extends NativeAudioNode {
        constructor(context:BaseAudioContext,name:string,options?:AudioWorkletNodeOptions) {
          super(context,name,options);
          this.port.addEventListener("message",event=>{state.auditCapturedSamples!+=event.data.length;});
          this.port.start();
        }
      };
    });
    await doctor(page,context);
    await page.getByRole("button",{name:"Start visit",exact:true}).click();
    await page.getByRole("button",{name:"New prescription",exact:true}).click();
    await page.getByRole("button",{name:"Start recording",exact:true}).click();
    await expect(page.getByRole("button",{name:"Stop recording",exact:true})).toBeVisible();
    // Wait for actual sample delivery, rather than microphone startup timing.
    await expect.poll(()=>page.evaluate(()=>(window as Window & {auditCapturedSamples?:number}).auditCapturedSamples||0)).toBeGreaterThan(2400);
    await context.addCookies([{name:"mededge_session",value:"ui-patient",url:"http://127.0.0.1:8023"}]);
    await page.evaluate(()=>window.dispatchEvent(new Event("focus")));
    await expect(page.getByRole("heading",{name:"Account changed",exact:true})).toBeVisible();
    await context.addCookies([{name:"mededge_session",value:"ui-doctor",url:"http://127.0.0.1:8023"}]);
    await page.getByRole("button",{name:"Check account again",exact:true}).click();
    await expect(page.getByRole("button",{name:"Record again",exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:"Stop recording",exact:true})).toHaveCount(0);
    await expect(page.locator("audio[aria-label='Prescription recording preview']")).toBeVisible();
  });
});
