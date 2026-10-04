import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin='http://127.0.0.1:5195';
await fs.mkdir('.local/verification',{recursive:true});
const folder=await fs.mkdtemp(path.resolve('.local/verification/spending-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5195 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.spending_ui_server'],{env:{...process.env,NEXQORI_SPENDING_UI_CHECK:'1',NEXQORI_SPENDING_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='',browser,page;server.stderr.on('data',b=>diagnostics+=b.toString());
const report={cases:[],accessibility:[],errors:[]};
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();const violations=r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}));report.accessibility.push({name,violations});assert.deepEqual(violations,[],name);}
try{
 for(let n=0;n<100;n++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error('Isolated server failed');await new Promise(r=>setTimeout(r,150));}
 const person=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const locale of ['es','en','pt']){
  const t=JSON.parse(await fs.readFile('src/locales/'+locale+'.json','utf8'));const context=await browser.newContext({viewport:{width:1512,height:1050}});
  const logged=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.admin.email,password:person.admin.password}});assert.equal(logged.status(),200);
  const headers={Origin:origin,'X-CSRF-Token':(await logged.json()).csrfToken};
  assert.equal((await context.request.post(origin+'/api/admin/provider-updates/example',{headers,data:{preset:'usual',confirmed:true}})).status(),200);
  await context.request.post(origin+'/api/admin/provider-updates/refresh',{headers,data:{}});
  page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));await page.goto(origin+'/admin/providers');
  await page.locator('.language-trigger').click();await page.locator('[data-locale="'+locale+'"]').click();
  const panel=page.locator('[data-testid=provider-updates]');await expect(panel.locator('.provider-source-prices')).toContainText('299');
  await panel.getByLabel(t['providerUpdates.search'],{exact:true}).fill('Empresa Telefónica');await panel.getByRole('button',{name:t['providerUpdates.find'],exact:true}).click();
  await expect(panel.locator('.provider-source-card')).toHaveCount(1);
  await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:t['providerUpdates.publishIncrease'],exact:true}).click();
  await expect(panel.locator('.provider-source-state')).toHaveText(t['providerUpdates.pending']);
  assert.equal((await(await context.request.get(origin+'/api/provider-examples/phone-bill/telefono-esencial')).json()).priceMinor,45900);
  await panel.getByRole('button',{name:t['providerUpdates.check'],exact:true}).click();await expect(panel.locator('.provider-source-notice')).toHaveText(t['providerUpdates.changeDetected']);
  await axe('provider-admin-'+locale);await page.screenshot({path:path.join(folder,'provider-'+locale+'.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('provider-admin-mobile-'+locale);
  await panel.getByLabel(t['providerUpdates.search'],{exact:true}).fill('Empresa sin fuente');await panel.getByRole('button',{name:t['providerUpdates.find'],exact:true}).click();await expect(panel).toContainText(t['providerUpdates.empty']);
  report.cases.push({locale,providerPublishing:true,changeDetected:true,search:true});await context.close();
 }
 for(const locale of ['es','en','pt']){
  const t=JSON.parse(await fs.readFile('src/locales/'+locale+'.json','utf8'));const context=await browser.newContext({viewport:{width:1512,height:1050}});
  const logged=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(logged.status(),200);
  const before=await(await context.request.get(origin+'/api/bootstrap')).json();page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(origin+'/movements');await page.locator('.language-trigger').click();await page.locator('[data-locale="'+locale+'"]').click();
  await expect(page.locator('.spending-highlight')).toHaveCount(2);await axe('overview-'+locale);
  await page.getByLabel(t['spending.filter'],{exact:true}).selectOption('unusual');await expect(page.locator('.transaction-row')).toHaveCount(2);
  await page.getByRole('searchbox',{name:t.search,exact:true}).fill('Mercado del Barrio');await expect(page.locator('.transaction-row')).toHaveCount(1);
  await page.locator('.transaction-row').click();await expect(page.locator('.spending-detail')).toContainText('350');
  await page.locator('.spending-detail summary').click();await expect(page.locator('.spending-history li')).toHaveCount(5);await axe('detail-'+locale);
  await page.screenshot({path:path.join(folder,'detail-'+locale+'.png')});
  await page.getByRole('button',{name:t.close,exact:true}).click();
  await page.getByLabel(t['spending.filter'],{exact:true}).selectOption('comparable');await expect(page.locator('.transaction-row')).toHaveCount(2);
  await page.getByLabel(t['spending.filter'],{exact:true}).selectOption('all');await expect(page.locator('.transaction-row')).toHaveCount(6);
  await page.getByRole('searchbox',{name:t.search,exact:true}).fill('Empresa Telefónica');await page.getByLabel(t.status,{exact:true}).selectOption('pending');
  await expect(page.locator('.transaction-row')).toHaveCount(1);await page.reload();await expect(page.locator('.transaction-row')).toHaveCount(1);await page.locator('.transaction-row').click();
  await expect(page.locator('.spending-detail')).toContainText(locale==='es'||locale==='pt'?'53,5':'53.5');await expect(page.locator('dialog')).toContainText(person.scenarios.reference);
  await expect(page.locator('.spending-source')).toContainText('Teléfono Esencial');await expect(page.locator('.spending-source')).toContainText('459');
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('mobile-'+locale);
  await page.screenshot({path:path.join(folder,'mobile-'+locale+'.png'),fullPage:true});
  assert.deepEqual(await(await context.request.get(origin+'/api/bootstrap')).json(),before);
  report.cases.push({locale,filters:true,history:true,receipt:true,readOnly:true});await context.close();
 }
 assert.deepEqual(report.errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,cases:report.cases.length,accessibility:report.accessibility.length,report:path.join(folder,'report.json')}));
}catch(e){if(page&&!page.isClosed()){await page.screenshot({path:path.join(folder,'failure.png')});await fs.writeFile(path.join(folder,'failure.html'),await page.content());}throw e;}finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
