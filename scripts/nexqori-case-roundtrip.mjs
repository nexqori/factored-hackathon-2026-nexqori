// Isolated customer → admin → customer journey; no live providers or manual accounts.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin = 'http://127.0.0.1:5192';
const folder = await fs.mkdtemp(path.resolve('.local/verification/case-roundtrip-'));
assert.equal(await fetch(origin + '/api/health').then(() => true).catch(() => false), false, 'Port 5192 must be free');
const python = process.env.NEXQORI_BANK_PYTHON || path.resolve(process.platform === 'win32' ? '.venv-app/Scripts/python.exe' : '.venv-app/bin/python');
const server = spawn(python, ['-m', 'backend.tests.attention_ui_server'], { env: { ...process.env, BANK_VOICE_ENABLED: 'false', NEXQORI_CHAT_UI_CHECK: '1', NEXQORI_CHAT_UI_DATA: folder }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let diagnostics = '', browser, page;
server.stderr.on('data', chunk => diagnostics += chunk.toString());
const report = { checks: [], accessibility: [], errors: [] };
async function login(person) {
  const context = await browser.newContext({ viewport: process.env.NEXQORI_ADMIN_MOBILE === '1' ? { width: 390, height: 844 } : { width: 1512, height: 1050 } });
  const response = await context.request.post(origin + '/api/auth/login', { headers: { Origin: origin }, data: { identifier: person.email, password: person.password } });
  assert.equal(response.status(), 200);
  return { context, headers: { Origin: origin, 'X-CSRF-Token': (await response.json()).csrfToken } };
}
async function checkAxe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  report.accessibility.push({ name, violations: result.violations.map(value => value.id) });
  if (result.violations.length) await fs.writeFile(path.join(folder, 'axe-' + name + '.json'), JSON.stringify(result.violations, null, 2));
  assert.deepEqual(result.violations.map(value => value.id), []);
}
async function language(locale) {
  await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click();
}
try {
  for(let n=0;n<150;n++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error(diagnostics);await new Promise(r=>setTimeout(r,150));}
  const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
  const adminPerson=JSON.parse(await fs.readFile(path.join(folder,'admin.private.json'),'utf8'));
  browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
  const admin=await login(adminPerson);
  for(const locale of ['es','en','pt']){
    const copy=JSON.parse(await fs.readFile('src/locales/'+locale+'.json','utf8'));
    const person=people.find(p=>p.locale===locale&&p.intent==='unrecognized-charge');
    const customer=await login(person);page=await customer.context.newPage();const customerPage=page;
    page.on('pageerror',e=>report.errors.push(e.message));await page.goto(origin);await language(locale);
    const panel=page.locator('.assistant-panel');
    async function send(text){
      const response=customerPage.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
      await panel.locator('.paste-composer textarea').fill(text);await panel.locator('.paste-entry button').click();
      const result=await response;assert.equal(result.status(),200);const data=await result.json();
      await expect(panel.locator('.chat-bubble.assistant').last()).toHaveText(data.text);return data;
    }
    const first=await send({es:'No reconozco el cobro del teléfono [CASE-1]',en:'I do not recognize the phone charge [CASE-1]',pt:'Não reconheço a cobrança do telefone [CASE-1]'}[locale]);
    assert.equal(first.flow.suggestedTransaction.id,person.transactionId);
    await panel.getByRole('button',{name:copy['chatSending.confirm'],exact:true}).click();
    await expect(panel.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true})).toBeVisible();
    await panel.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();
    await page.locator('.chat-details-dialog').getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();
    const review=page.locator('.chat-claim-review');await expect(review.locator('.chat-claim-summary')).not.toHaveText('');
    await expect(review.getByRole('checkbox')).toHaveCount(0);
    const registered=page.waitForResponse(r=>r.url().endsWith('/'+first.conversation.id+'/claim')&&r.request().method()==='POST');
    await review.getByRole('button',{name:copy['chatClaim.register'],exact:true}).click();
    const registration=await registered;assert.equal(registration.status(),200);const claim=await registration.json();
    await expect(page).toHaveURL(new RegExp('/complaints\\?case='+claim.id));
    const followText={es:'¿Cómo va mi caso? ¿Ya se realizó el reembolso?',en:'What is the status of my case? Has the refund been completed?',pt:'Como vai minha reclamação? O reembolso foi realizado?'}[locale];
    const pending=await send(followText);assert(pending.text.includes(claim.id));
    const before=await(await customer.context.request.get(origin+'/api/bootstrap')).json();
    await checkAxe('customer-registered-'+locale);
    page=await admin.context.newPage();await page.goto(origin+'/admin/complaints?case='+claim.id);await language(locale);
    await expect(page.locator('.claim-trace')).toHaveAttribute('data-trace-ready','true');
    await page.locator('[data-trace-tab=conversations]').click();
    await expect(page.locator('.trace-conversation')).toHaveCount(1);
    await page.locator('[data-trace-tab=decision]').click();const actions=page.locator('.admin-case-decision');
    for(const stage of ['delivered','in_review','approved']){
      if(stage==='approved')await actions.getByLabel(copy['claimStage.note'],{exact:true}).fill('Verificación del cargo y evidencia para resolver el reclamo.');
      await actions.getByLabel(copy['claimStage.confirm.'+stage],{exact:true}).check();
      await actions.getByRole('button',{name:copy['claimStage.action.'+stage],exact:true}).click();
      await expect(actions.locator('[aria-current=step]')).toContainText(copy['claimStage.'+stage]);
    }
    assert.deepEqual((await(await customer.context.request.get(origin+'/api/bootstrap')).json()).products,before.products);
    const approved=await send(followText);assert(approved.text.includes(claim.id));assert(!approved.text.includes('CR-'));
    const refund=actions.locator('.refund-panel');
    await refund.locator('select').selectOption('approve');
    await refund.getByLabel(copy.refundEvidence,{exact:true}).fill('Verificación: devolución del cargo no reconocido autorizada.');
    await refund.getByLabel(copy.password,{exact:true}).fill(adminPerson.password);
    await refund.getByLabel(copy.refundConfirmApprove,{exact:true}).check();
    await refund.getByRole('button',{name:copy.refundSaveDecision,exact:true}).click();
    await expect(actions.locator('[aria-current=step]')).toContainText(copy['claimStage.refunded']);
    await checkAxe('admin-refunded-'+locale);await page.screenshot({path:path.join(folder,'admin-'+locale+'.png'),fullPage:true});
    const after=await(await customer.context.request.get(origin+'/api/bootstrap')).json();const credits=after.transactions.filter(t=>t.category==='refund');assert.equal(credits.length,1);
    const fresh=await send(followText);assert(fresh.text.includes(credits[0].id));assert(fresh.text.includes(claim.id));
    assert.equal(fresh.flow.requestId,claim.id);assert.equal(fresh.conversation.id,first.conversation.id);
    assert.equal((await(await customer.context.request.get(origin+'/api/verification/summary')).json()).bankRecordsSentToModels,false);
    await page.close();page=customerPage;
    await page.locator('.claims-refresh button').click();
    await expect(page.locator('.trace-current')).toContainText(copy['trace.outcome.refund_approved']);
    await page.getByRole('button',{name:copy['caseDecision.viewCredit'],exact:true}).click();
    await expect(page).toHaveURL(/\/movements\?transaction=CR-/);
    await expect(page.locator('.transaction-panel .transaction-row')).toHaveCount(1);
    await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(credits[0].id);
    await checkAxe('customer-credit-'+locale);
    await page.screenshot({path:path.join(folder,'customer-'+locale+'.png'),fullPage:true});
    report.checks.push({locale,caseId:claim.id,conversationPreserved:true,credit:credits[0].id,registeredThroughChat:true,adminDecisionThroughUI:true,freshChatStatus:true});
    await customer.context.close();
  }
  assert.deepEqual(report.errors,[]);await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({folder,...report},null,2));
} catch(error){if(page&&!page.isClosed())await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true});throw error;}
finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
