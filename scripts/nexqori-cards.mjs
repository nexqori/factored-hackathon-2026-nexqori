// Local PostgreSQL acceptance using a dedicated verification customer.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { strict as assert } from 'node:assert';
import { verificationUser } from './verification-user.mjs';
const person=verificationUser(), origin='http://localhost:5180';
const folder='.local/verification/cards-'+person.packId;mkdirSync(folder,{recursive:true});
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1512,height:1050}});const page=await context.newPage();
const report={checks:[],accessibility:[],errors:[]};page.on('pageerror',e=>report.errors.push(e.message));
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.equal(r.violations.length,0,JSON.stringify(r.violations.map(v=>v.id)));report.accessibility.push(name);}
async function send(text){const panel=page.locator('.assistant-panel');await panel.locator('textarea').fill(text);await panel.locator('.paste-entry button').click();await expect(page.locator('dialog')).toBeVisible();}
try{
 const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
 await page.goto(origin+'/cards');await expect(page.locator('.bank-card')).toBeVisible();
 const cards=(await(await context.request.get(origin+'/api/cards')).json()).cards;assert.equal(cards.length,1);assert(cards[0].canReveal);
 const card=cards[0];let reveals=0,refreshes=0;
 page.on('request',r=>{if(r.url().endsWith('/reveal'))reveals++;if(r.url().endsWith('/cvv'))refreshes++;});
 for(const lang of ['es','en','pt']){
  const copy=JSON.parse(readFileSync('src/locales/'+lang+'.json','utf8'));
  await page.locator('.language-trigger').click();await page.locator('[data-locale="'+lang+'"]').click();
  await expect(page.getByTestId('card-cvv')).toHaveText('•••');await expect(page.getByTestId('card-expiry')).toHaveText('••/••');
  for(const width of [1512,390]){await page.setViewportSize({width,height:1050});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe(lang+'-'+width);await page.screenshot({path:folder+'/'+lang+'-'+width+'.png',fullPage:true});}
  await page.setViewportSize({width:1512,height:1050});
  const before=reveals;await send({es:'Ver datos de mi tarjeta',en:'Show details of my card',pt:'Mostre os dados do meu cartão'}[lang]);
  await expect(page).toHaveURL(origin+'/cards');assert.equal(reveals,before,'Chat only opens password prompt');
  const dialog=page.locator('dialog');await expect(dialog.getByLabel(copy.password,{exact:true})).toBeVisible();
  if(lang==='es'){await dialog.getByLabel(copy.password,{exact:true}).fill('incorrect-password');await dialog.getByRole('button',{name:copy.showCardDetails,exact:true}).click();await expect(dialog.getByRole('alert')).toBeVisible();await expect(page.getByTestId('card-expiry')).toHaveText('••/••');}
  if(lang==='pt'){
   await page.clock.install();
   await page.route('**/api/cards/*/reveal',async route=>{const r=await route.fetch();assert.equal(r.status(),200);const data=await r.json();await route.fulfill({response:r,json:{...data,cvv:'000',cvvExpiresAt:data.serverTime+2}});},{times:1});
   await page.route('**/api/cards/*/cvv',async route=>{const r=await route.fetch();assert.equal(r.status(),200);await route.fulfill({response:r,json:{...await r.json(),cvv:'111'}});},{times:1});
  }
  await dialog.getByLabel(copy.password,{exact:true}).fill(person.password);await dialog.getByRole('button',{name:copy.showCardDetails,exact:true}).click();
  await expect(page.getByTestId('card-cvv')).toHaveText(/^\d{3}$/);await expect(page.getByTestId('card-expiry')).toHaveText(/^\d{2}\/\d{2}$/);
  assert((await page.locator('.card-number').innerText()).replaceAll(' ','').endsWith(card.last4));
  await expect(page.getByTestId('card-cvv-renewal')).toContainText(/\d+:\d{2}/);await expect(page.getByTestId('card-hide-timer')).toBeVisible();
  if(lang==='pt'){await page.clock.runFor(2500);await expect(page.getByTestId('card-cvv')).toHaveText('111');assert.equal(refreshes,1);await page.clock.runFor(59000);}
  else await page.evaluate(()=>window.dispatchEvent(new Event('blur')));
  await expect(page.getByTestId('card-cvv')).toHaveText('•••');await expect(page.getByTestId('card-expiry')).toHaveText('••/••');
  await send({es:'Bloquea mi tarjeta',en:'Block my card',pt:'Bloqueie meu cartão'}[lang]);
  assert.equal((await(await context.request.get(origin+'/api/cards')).json()).cards[0].status,'active');
  if(card.blockRequiresEmail){
   // This PostgreSQL check must not send real mail. The isolated notifications
   // suite completes the email-code flow, including wrong codes and retries.
   await expect(dialog).toContainText(copy['notifications.blockIntro']);
   await expect(dialog.getByRole('button',{name:copy.confirmBlockCard,exact:true})).toHaveCount(0);
   await dialog.getByRole('button',{name:copy.close,exact:true}).click();
  }else{
   await expect(dialog.getByLabel(copy.password,{exact:true})).toBeVisible();await expect(dialog.getByRole('checkbox')).not.toBeChecked();
   if(lang==='pt'){
    await dialog.getByLabel(copy.password,{exact:true}).fill(person.password);await dialog.getByRole('checkbox').check();await dialog.getByRole('button',{name:copy.confirmBlockCard,exact:true}).click();
    await expect(page.locator('.card-blocked-label')).toBeVisible();await expect(page.getByRole('button',{name:copy.showCardDetails,exact:true})).toBeDisabled();
   }else await dialog.getByRole('button',{name:copy.close,exact:true}).click();
  }
  report.checks.push({lang,passwordRequired:true,chatOnlyPrepares:true,hiddenByDefault:true});
 }
 assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage)),['nexqori-language']);assert.deepEqual(report.errors,[]);
 writeFileSync(folder+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify({folder,...report}));
}finally{await browser.close();}
