// Isolated SQLite + controlled mailbox; no real email, manual customer or provider.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const origin='http://127.0.0.1:5194';
await fs.mkdir('.local/verification',{recursive:true});
const folder=await fs.mkdtemp(path.resolve('.local/verification/notifications-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5194 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.notifications_ui_server'],{env:{...process.env,NEXQORI_NOTIFICATION_UI_CHECK:'1',NEXQORI_NOTIFICATION_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='',browser,page;server.stderr.on('data',b=>diagnostics+=b.toString());
const report={cases:[],accessibility:[],errors:[]};
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();const violations=r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}));report.accessibility.push({name,violations});assert.deepEqual(violations,[],name);}
try{
 for(let n=0;n<100;n++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error('Isolated server failed');await new Promise(r=>setTimeout(r,150));}
 const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const person of people){
  const t=JSON.parse(await fs.readFile('src/locales/'+person.locale+'.json','utf8'));
  const context=await browser.newContext({viewport:{width:1512,height:1050}});
  const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
  const before=await(await context.request.get(origin+'/api/bootstrap')).json();
  page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(origin+'/cards');await page.locator('.language-trigger').click();await page.locator('[data-locale="'+person.locale+'"]').click();
  await page.getByRole('button',{name:t.blockCard,exact:true}).click();
  await page.locator('dialog').getByLabel(t.password,{exact:true}).fill(person.password);
  await page.locator('dialog').getByRole('button',{name:t['notifications.sendCode'],exact:true}).click();
  await expect(page.locator('dialog [role=alert]')).toContainText(t['error.notification_email_required']);
  await page.locator('dialog').getByRole('link',{name:t['notifications.configure']}).click();
  await expect(page).toHaveURL(origin+'/settings');
  const settings=page.locator('.notification-settings');
  const destination='notifications-'+person.locale+'@example.com';
  await settings.getByLabel(t['notifications.email'],{exact:true}).fill(destination);
  await settings.getByLabel(t.password,{exact:true}).fill(person.password);
  await settings.getByRole('button',{name:t['notifications.verifyAddress'],exact:true}).click();
  await expect(settings.getByLabel(t['notifications.code'],{exact:true})).toBeVisible();
  const verification=await(await context.request.get(origin+'/api/verification/mailbox')).json();assert.equal(verification.purpose,'notification_email');
  await settings.getByLabel(t['notifications.code'],{exact:true}).fill(verification.code);
  await axe('verify-email-'+person.locale);
  await settings.getByRole('button',{name:t['notifications.confirmEmail'],exact:true}).click();
  await expect(settings).toContainText(t['notifications.saved']);
  assert.equal((await(await context.request.get(origin+'/api/session')).json()).user.email,person.email);
  await page.goto(origin+'/cards');await page.getByRole('button',{name:t.blockCard,exact:true}).click();
  await page.locator('dialog').getByLabel(t.password,{exact:true}).fill(person.password);
  await page.locator('dialog').getByRole('button',{name:t['notifications.sendCode'],exact:true}).click();
  await expect(page.locator('dialog').getByLabel(t['notifications.code'],{exact:true})).toBeVisible();
  const confirmation=await(await context.request.get(origin+'/api/verification/mailbox')).json();assert.equal(confirmation.purpose,'card_block');assert.equal(confirmation.last4,'9101');
  const wrong=String((Number(confirmation.code)+1)%1000000).padStart(6,'0');
  await page.locator('dialog').getByLabel(t['notifications.code'],{exact:true}).fill(wrong);
  await page.locator('dialog').getByRole('checkbox').check();
  await page.locator('dialog').getByRole('button',{name:t.confirmBlockCard,exact:true}).click();
  await expect(page.locator('dialog [role=alert]')).toContainText(t['error.email_code_invalid']);
  assert.equal((await(await context.request.get(origin+'/api/cards')).json()).cards[0].status,'active');
  await page.locator('dialog').getByLabel(t['notifications.code'],{exact:true}).fill(confirmation.code);
  await axe('confirm-block-'+person.locale);
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('confirm-block-mobile-'+person.locale);
  // Do not retain the temporary code in screenshots.
  await page.locator('dialog').getByLabel(t['notifications.code'],{exact:true}).fill('');
  await page.screenshot({path:path.join(folder,'block-'+person.locale+'.png'),fullPage:true});
  await page.locator('dialog').getByLabel(t['notifications.code'],{exact:true}).fill(confirmation.code);
  await page.locator('dialog').getByRole('button',{name:t.confirmBlockCard,exact:true}).click();
  await expect(page.locator('.card-blocked-label')).toBeVisible();await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.reload();await expect(page.locator('.card-blocked-label')).toBeVisible();
  const after=await(await context.request.get(origin+'/api/bootstrap')).json();
  assert.deepEqual(after.transactions,before.transactions);assert.deepEqual(after.requests,before.requests);
  assert.equal(after.audit.filter(a=>a.action==='card_blocked').length,1);
  report.cases.push({locale:person.locale,emailVerified:true,wrongCodeRejected:true,cardBlocked:true,singleAudit:true});
  await context.close();
 }
 assert.deepEqual(report.errors,[]);report.passed=true;
 console.log(JSON.stringify({passed:true,cases:report.cases.length,accessibility:report.accessibility.length,report:path.join(folder,'report.json')}));
}finally{
 await browser?.close();server.kill();await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);
}
