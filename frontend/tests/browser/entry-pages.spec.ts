import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";

const demo = {enabled:true,patient_email:"fictional-patient@example.test",doctor_email:"fictional-doctor@example.test",password:"fictional-demo-password"};

for (const [path, name] of [["/","landing"],["/signin","signin"],["/signup","signup"]] as const) {
  test(`${name}: clear primary actions, responsive bounds and accessible themes`, async ({page}) => {
    await page.route("**/api/demo/accounts",route=>route.fulfill({json:demo}));
    await page.goto(path);
    await expect(page.locator("main h1")).toHaveCount(1);
    await expect(page.locator(".auth-aside")).toHaveCount(0);
    if(path==="/signin") {
      await expect(page.getByRole("button",{name:"Sign in",exact:true})).toHaveCount(1);
      await expect(page.getByRole("button",{name:"Use demo patient",exact:true})).not.toBeVisible();
    }
    if(path==="/") {
      await expect(page.getByRole("heading",{name:"Patient portal",exact:true})).toBeVisible();
      await expect(page.getByRole("heading",{name:"Doctor workspace",exact:true})).toBeVisible();
    }
    await mkdir("../scripts/out/ui",{recursive:true});
    for(const theme of ["light","dark"]) {
      await page.evaluate(t=>document.documentElement.classList.toggle("dark",t==="dark"),theme);
      for(const width of [320,375,390,768,1280,1440,1920]) {
        await page.setViewportSize({width,height:900});
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
        const clipped=await page.locator("button,input,summary,label").evaluateAll(nodes=>nodes.filter(node=>{
          const r=node.getBoundingClientRect();
          return node.getClientRects().length>0 && r.width>2 && (r.left < -1 || r.right > innerWidth+1);
        }).map(node=>node.textContent||node.getAttribute("aria-label")));
        expect(clipped).toEqual([]);
        if(width===375||width===1440) {
          await page.evaluate(()=>document.fonts.ready);
          await page.screenshot({path:`../scripts/out/ui/entry-${name}-${width}-${theme}.png`,fullPage:true});
          const result=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
          expect(result.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))).toEqual([]);
        }
      }
    }
  });
}

test("sign-up keeps role selection, password validation, verification cooldown and visible resend errors",async({page})=>{
  await page.clock.install({time:new Date("2030-01-01T00:00:00Z")});
  await page.clock.pauseAt(new Date("2030-01-01T00:00:01Z"));
  await page.route("**/api/auth/register",route=>{
    expect(route.request().postDataJSON()).toMatchObject({role:"doctor",password:"Terabaap*101"});
    return route.fulfill({status:202,json:{message:"Check your email"}});
  });
  await page.route("**/api/auth/resend-verification",route=>route.fulfill({status:503,json:{detail:"Email delivery is temporarily unavailable. Please retry."}}));
  await page.goto("/signup?role=doctor");
  await expect(page.getByRole("radio",{name:"Doctor",exact:true})).toBeChecked();
  await expect(page.getByText(/Doctor credentials are self-declared/)).toBeVisible();
  await page.getByLabel("Full name",{exact:true}).fill("Fictional Doctor");
  await page.getByLabel("Email address",{exact:true}).fill("fictional@example.test");
  await page.getByLabel("Password",{exact:true}).fill("Terabaap*101");
  await page.getByLabel("Confirm password",{exact:true}).fill("Different-password");
  await page.getByRole("button",{name:"Create account",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("passwords don’t match");
  await page.getByLabel("Confirm password",{exact:true}).fill("Terabaap*101");
  await page.getByRole("button",{name:"Create account",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Check your email",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:/Resend in/})).toBeDisabled();
  for(let remaining=59;remaining>=0;remaining--) {
    await page.clock.runFor(1000);
    await expect(page.locator(".auth-success > button.secondary")).toHaveText(remaining ? `Resend in ${remaining}s` : "Resend verification email");
  }
  await page.getByRole("button",{name:"Resend verification email",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Email delivery is temporarily unavailable");
});

test("sign-in keeps demo, password visibility, recovery and verification discoverable",async({page})=>{
  await page.route("**/api/demo/accounts",route=>route.fulfill({json:demo}));
  await page.goto("/signin?role=doctor");
  await page.getByText("Try a demo account",{exact:true}).click();
  await page.getByRole("button",{name:"Use demo doctor",exact:true}).click();
  await expect(page.getByLabel("Email address",{exact:true})).toHaveValue(demo.doctor_email);
  await page.getByRole("button",{name:"Show password",exact:true}).click();
  await expect(page.getByLabel("Password",{exact:true})).toHaveAttribute("type","text");
  await page.getByText("Trouble signing in?",{exact:true}).click();
  await page.getByRole("button",{name:"Resend verification email",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Resend verification email",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Back to sign in",exact:true}).first().click();
  await page.getByRole("button",{name:"Forgot password?",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Reset your password",exact:true})).toBeVisible();
});
