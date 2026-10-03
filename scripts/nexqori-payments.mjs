// Persistent, fictional PostgreSQL fixtures. No models or external payments.
import {chromium, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawnSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const origin='http://localhost:5180', output='.local/verification/payments';mkdirSync(output,{recursive:true});
const definitions=JSON.parse(readFileSync('tests/scenarios/banking-cases.json','utf8')).cases;
const fixture=spawnSync('docker',['compose','exec','-T','-e','NEXQORI_LOCAL_VERIFY=1','-e','NEXQORI_CASES_INPUT='+Buffer.from(JSON.stringify({mode:'prepare',languages:['es'],definitions,phoneBills:true})).toString('base64'),'api','python','-'],{input:readFileSync('scripts/banking-cases-fixtures.py','utf8'),encoding:'utf8',windowsHide:true,timeout:120000});
assert.equal(fixture.status,0,'Fixture creation failed (private output suppressed)');
const pack=JSON.parse(fixture.stdout),folder=output+'/'+pack.runId;mkdirSync(folder,{recursive:true});
writeFileSync(folder+'/credentials.private.json',JSON.stringify(pack,null,2),{mode:0o600});
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const report={runId:pack.runId,cases:[],accessibility:[],errors:[]};let page;
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();report.accessibility.push({name,violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))});}
try{
for(const [i,locale] of ['es','en','pt'].entries()){
 const person=pack.cases[i],copy=JSON.parse(readFileSync('src/locales/'+locale+'.json','utf8'));
 const context=await browser.newContext({viewport:{width:1512,height:1050}});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
 const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
 const session=await login.json(),headers={Origin:origin,'X-CSRF-Token':session.csrfToken};
 await context.request.patch(origin+'/api/profile/locale',{headers,data:{locale}});
 await page.goto(origin+'/services/catalog/phone-bill');await page.locator('.language-trigger').click();await page.locator('[data-locale="'+locale+'"]').click();
 await page.getByRole('textbox',{name:copy.catalogReference_phone,exact:true}).fill('550000000'+(i+1));
 await page.getByRole('button',{name:copy['bills.lookup'],exact:true}).click();
 await expect(page.locator('.bill-total')).toContainText(/299[.,]00/);assert.equal(await page.locator('.bill-result input[inputmode=decimal]').count(),0);
 const before=await(await context.request.get(origin+'/api/bootstrap')).json();
 await axe('bill-'+locale);await page.getByRole('button',{name:copy['pay.review'],exact:true}).click();await page.getByRole('checkbox').check();
 await axe('review-'+locale);
 // Lose the first response only after the server has committed it. Retry keeps
 // the same UI idempotency key, and must recover the original payment receipt.
 if(i===0){await page.route('**/api/service-bills/*/pay',async route=>{await route.fetch();await route.abort('failed');},{times:1});}
 if(i===2){await page.route('**/api/service-bills/*/pay',async route=>{const responses=await Promise.all([route.fetch(),route.fetch()]);assert.deepEqual(await responses[0].json(),await responses[1].json());await route.fulfill({response:responses[0]});},{times:1});}
 await page.getByRole('button',{name:copy['pay.confirm'],exact:true}).click();
 if(i===0){await page.getByRole('alert').waitFor();await page.getByRole('button',{name:copy['pay.confirm'],exact:true}).click();}
 await page.getByRole('heading',{name:copy['pay.done'],exact:true}).waitFor();
 const paymentId=await page.locator('[data-payment-id]').getAttribute('data-payment-id');
 await axe('receipt-'+locale);await page.screenshot({path:folder+'/receipt-'+locale+'.png',fullPage:true});
 await page.reload();await expect(page.locator('[data-payment-id]')).toHaveAttribute('data-payment-id',paymentId);
 const after=await(await context.request.get(origin+'/api/bootstrap')).json();assert.deepEqual(after.requests,before.requests);
 assert.equal(after.transactions.length,before.transactions.length+1);
 const balance=rows=>rows.products.find(p=>p.id===person.accountId).balanceMinor;assert.equal(balance(after),balance(before)-29900);
 const tx=after.transactions.find(t=>t.paymentId===paymentId);assert.equal(tx.amountMinor,-29900);
 // Concurrent retries with different keys still reference one paid invoice.
 const repeats=await Promise.all([1,2].map(()=>context.request.post(origin+'/api/phone-bills/'+person.billId+'/pay',{headers,data:{confirmed:true,accountId:person.accountId,requestKey:crypto.randomUUID()}})));
 for(const r of repeats){assert.equal(r.status(),200);assert.equal((await r.json()).id,paymentId);}
 await page.goto(origin+'/movements');await page.getByRole('button').filter({hasText:'Empresa Telefónica'}).click();
 await expect(page.locator('dialog')).toContainText(paymentId);await expect(page.locator('dialog')).toContainText(person.billId.includes('verify')?'550000000'+(i+1):'');await axe('movement-'+locale);
 await page.getByRole('button',{name:copy.close,exact:true}).click();await page.goto(origin+'/requests');await expect(page.locator('.case-card')).toHaveCount(0);
 await page.goto(origin+'/complaints');await expect(page.getByRole('heading',{name:copy.myClaims,exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.goto(origin+'/payments/'+paymentId);await page.locator('[data-payment-id]').waitFor();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('receipt-mobile-'+locale);
 report.cases.push({locale,userId:person.userId,billId:person.billId,paymentId,transactionId:tx.id,debitedMinor:29900,requestsUnchanged:true});await context.close();
}
assert.deepEqual(report.errors,[]);assert(report.accessibility.every(r=>!r.violations.length),JSON.stringify(report.accessibility));
writeFileSync(folder+'/report.json',JSON.stringify(report,null,2));writeFileSync(output+'/latest.json',JSON.stringify({folder,runId:pack.runId}));console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
