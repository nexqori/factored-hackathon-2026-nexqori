// Local persistent verification customers. No provider calls or external payments.
// This script does not reset any customer's bills, balances or conversations.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';

const origin = 'http://localhost:5180';
const output = '.local/verification/deferred-payments';
mkdirSync(output, { recursive: true });
const definitions = JSON.parse(readFileSync('tests/scenarios/banking-cases.json', 'utf8')).cases;
const prepared = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1',
  '-e', 'NEXQORI_CASES_INPUT=' + Buffer.from(JSON.stringify({ mode:'prepare', languages:['es'], definitions, phoneBills:true })).toString('base64'),
  'api', 'python', '-'], { input:readFileSync('scripts/banking-cases-fixtures.py','utf8'), encoding:'utf8', windowsHide:true, timeout:120000 });
assert.equal(prepared.status, 0, 'Fixture creation failed; private output suppressed.');
const pack = JSON.parse(prepared.stdout); const folder = output + '/' + pack.runId;
mkdirSync(folder, { recursive:true });
writeFileSync(folder + '/credentials.private.json', JSON.stringify(pack,null,2), { mode:0o600 });
const report = { runId:pack.runId, status:'running', cases:[], accessibility:[], errors:[], modelRequests:0 };
const browser = await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
let page;
async function axe(name) {
  const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  const violations = result.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}));
  report.accessibility.push({name,violations}); assert.deepEqual(violations,[],name);
}
async function json(response) {assert.equal(response.status(),200,response.url());return response.json();}
async function login(context, person) {
  const session = await json(await context.request.post(origin+'/api/auth/login',{
    headers:{Origin:origin},data:{identifier:person.email,password:person.password},
  }));
  return {Origin:origin,'X-CSRF-Token':session.csrfToken};
}
try {
  const admin = await browser.newContext(); await login(admin,pack.admin);
  for (const [index,locale] of ['es','en','pt'].entries()) {
    const person=pack.cases[index], reference='550000000'+(index+1);
    const copy=JSON.parse(readFileSync('src/locales/'+locale+'.json','utf8'));
    const context=await browser.newContext({viewport:{width:1512,height:1050}});
    page=await context.newPage(); page.on('pageerror',error=>report.errors.push(error.message));
    // Exercise the existing authenticated transaction reader, not a mocked bank
    // reply. This keeps the acceptance reproducible without Jev/LLM consumption.
    await page.route('**/api/assistant/capabilities',route=>route.fulfill({json:{connected:false,providers:{}}}));
    await page.route('**/api/assistant/flow',route=>{report.modelRequests++;return route.abort('blockedbyclient');});
    const headers=await login(context,person);
    await json(await context.request.patch(origin+'/api/profile/locale',{headers,data:{locale}}));
    const before=await json(await context.request.get(origin+'/api/bootstrap'));
    await page.goto(origin+'/services/catalog/phone-bill');
    await page.getByRole('textbox',{name:copy.catalogReference_phone,exact:true}).fill(reference);
    await page.getByRole('button',{name:copy['bills.lookup'],exact:true}).click();
    await expect(page.getByRole('radio',{name:copy['pay.immediate'],exact:true})).toBeChecked();
    await page.getByRole('radio',{name:copy['pay.deferred'],exact:true}).check();
    await expect(page.getByText(copy['pay.deferredHint'],{exact:true})).toBeVisible();
    await axe('deferred-choice-'+locale);
    await page.getByRole('button',{name:copy['pay.review'],exact:true}).click();
    await expect(page.getByRole('button',{name:copy['pay.deferredConfirm'],exact:true})).toBeDisabled();
    await page.getByRole('checkbox',{name:copy['pay.deferredConfirmCheck'],exact:true}).check();
    let originalKey;
    if(index===0) await page.route('**/api/service-bills/*/pay',async route=>{
      originalKey=route.request().postDataJSON().requestKey;
      const response=await route.fetch();assert.equal(response.status(),200);await route.abort('failed');
    },{times:1});
    await page.getByRole('button',{name:copy['pay.deferredConfirm'],exact:true}).click();
    if(index===0) {
      await expect(page.getByRole('alert')).toContainText(copy['error.network']);
      const repeat=page.waitForRequest(request=>request.url().includes('/api/service-bills/')&&request.method()==='POST');
      await page.getByRole('button',{name:copy['pay.deferredConfirm'],exact:true}).click();
      assert.equal((await repeat).postDataJSON().requestKey,originalKey);
    }
    await expect(page.getByRole('heading',{name:copy['pay.pendingTitle'],exact:true})).toBeVisible();
    await expect(page.getByRole('heading',{name:copy['pay.done'],exact:true})).toHaveCount(0);
    const receiptElement=page.locator('[data-payment-id]');
    await expect(receiptElement).toHaveAttribute('data-payment-status','pending');
    const paymentId=await receiptElement.getAttribute('data-payment-id');
    await expect(receiptElement).toContainText(reference);
    await expect(receiptElement).toContainText(copy['pay.pendingHint']);
    await axe('pending-receipt-'+locale);
    await page.reload();await expect(page.locator('[data-payment-id]')).toHaveAttribute('data-payment-status','pending');
    const receipt=await json(await context.request.get(origin+'/api/payments/'+paymentId));
    assert.equal(receipt.status,'pending');assert.equal(receipt.amountMinor,29900);assert.equal(receipt.reference,reference);
    const after=await json(await context.request.get(origin+'/api/bootstrap'));
    const account=rows=>rows.products.find(p=>p.id===person.accountId);
    assert.equal(account(after).balanceMinor,account(before).balanceMinor-29900);
    assert.equal(after.transactions.length,before.transactions.length+1);assert.deepEqual(after.requests,before.requests);
    const transaction=after.transactions.find(tx=>tx.paymentId===paymentId);
    assert.equal(transaction.status,'pending');assert.equal(transaction.id,receipt.transactionId);assert.equal(transaction.amountMinor,-29900);
    const attempt=await context.request.post(origin+'/api/service-bills/'+person.billId+'/pay',{
      headers,data:{accountId:person.accountId,confirmed:true,mode:'total',processingMode:'pending',expectedOutstandingMinor:29900,requestKey:crypto.randomUUID()},
    });
    assert.equal(attempt.status(),409);assert.equal((await attempt.json()).error,'bill_in_processing');
    const found=await json(await context.request.post(origin+'/api/service-bills/lookup',{headers,data:{serviceId:'phone-bill',reference}}));
    const bill=found.bills.find(b=>b.id===person.billId);
    assert.equal(bill.paymentStatus,'pending');assert.equal(bill.pendingMinor,29900);assert.equal(bill.paidMinor,0);
    assert.equal(bill.outstandingMinor,0);assert.equal(bill.pendingPaymentId,paymentId);
    await page.getByRole('link',{name:copy['bills.another'],exact:true}).click();
    await page.getByRole('textbox',{name:copy.catalogReference_phone,exact:true}).fill(reference);
    await page.getByRole('button',{name:copy['bills.lookup'],exact:true}).click();
    await expect(page.locator('.bill-total')).toContainText(copy['pay.pendingTitle']);
    await expect(page.locator('.bill-total')).not.toContainText(copy['pay.paid']);
    await expect(page.getByRole('button',{name:copy['pay.review'],exact:true})).toHaveCount(0);
    await page.getByRole('link',{name:copy['pay.pendingReceipt'],exact:true}).click();
    await expect(page.locator('[data-payment-id]')).toHaveAttribute('data-payment-id',paymentId);
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await axe('pending-mobile-'+locale);await page.screenshot({path:folder+'/pending-mobile-'+locale+'.png',fullPage:true});
    await page.setViewportSize({width:1512,height:1050});
    await page.getByRole('link',{name:copy.seeMovements,exact:true}).click();
    await page.locator('[data-transaction-id="'+transaction.id+'"]').click();
    await expect(page.locator('dialog [data-payment-id]')).toHaveAttribute('data-payment-status','pending');
    await expect(page.locator('dialog')).toContainText(reference);await expect(page.locator('dialog')).toContainText(paymentId);
    await axe('pending-movement-'+locale);
    const answerPromise=page.waitForResponse(response=>response.url()===origin+'/api/assistant'&&response.request().method()==='POST');
    await page.getByRole('button',{name:copy.askTransaction,exact:true}).click();
    const answer=await json(await answerPromise);
    assert.equal(answer.conversation.transactionId,transaction.id);
    assert.equal(answer.evidence.transaction.status,'pending');assert.equal(answer.evidence.transaction.id,transaction.id);
    assert.equal(answer.evidence.externalProcessorLogs,false);
    const reply=page.locator('.assistant-panel .chat-bubble.assistant').last();
    await expect(reply).toContainText(transaction.id);await expect(reply).toHaveAttribute('lang',locale);
    await expect(reply).toContainText({es:'pendiente',en:'pending',pt:'pendente'}[locale]);
    await page.reload();await page.getByRole('button',{name:copy.conversations,exact:true}).click();
    await page.locator('.conversation-list button').first().click();
    await expect(page.locator('.assistant-panel .chat-bubble.assistant').last()).toContainText(transaction.id);
    const stored=await json(await context.request.get(origin+'/api/conversations/'+answer.conversation.id));
    assert.equal(stored.conversation.transactionId,transaction.id);
    const audit=await json(await admin.request.get(origin+'/api/admin/audit?userId='+encodeURIComponent(person.userId)));
    assert.equal(audit.events.filter(e=>e.action==='phone_bill_pending').length,1);
    assert(audit.events.some(e=>e.action==='transaction_context_viewed'&&e.transactionId===transaction.id));
    const final=await json(await context.request.get(origin+'/api/bootstrap'));
    assert.deepEqual(final.products,after.products);assert.deepEqual(final.transactions,after.transactions);assert.deepEqual(final.requests,before.requests);
    report.cases.push({locale,userId:person.userId,paymentId,transactionId:transaction.id,conversationId:answer.conversation.id,
      status:'pending',debitedMinor:29900,singleDebit:true,requestsUnchanged:true,bankEvidenceRead:true});
    await context.close();
  }
  await admin.close();assert.deepEqual(report.errors,[]);assert.equal(report.modelRequests,0);report.status='passed';
} catch(error) {
  report.status='failed';report.failure=String(error);
  if(page&&!page.isClosed())await page.screenshot({path:folder+'/failure.png',fullPage:true}).catch(()=>{});
  throw error;
} finally {
  writeFileSync(folder+'/report.json',JSON.stringify(report,null,2));
  writeFileSync(output+'/latest.json',JSON.stringify({folder,runId:pack.runId,status:report.status}));
  await browser.close();
  console.log(JSON.stringify({runId:pack.runId,status:report.status,cases:report.cases.length,accessibilityChecks:report.accessibility.length,
    modelRequests:report.modelRequests,report:folder+'/report.json'},null,2));
}
