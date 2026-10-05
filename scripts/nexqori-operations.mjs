// Uses only persistent records marked Verificación; credentials remain private.
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { parseEnv } from 'node:util';
import assert from 'node:assert/strict';

const fixture = JSON.parse(readFileSync('.local/verification/operations-private.json', 'utf8').replace(/^\uFEFF/, ''));
const credentials = parseEnv(readFileSync('.env', 'utf8'));
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const errors = [], checks = [];
const customer = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
const operator = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
const page = await customer.newPage(), admin = await operator.newPage();
for (const tab of [page, admin]) tab.on('pageerror', e => errors.push(e.message));
const base = 'http://localhost:5180';
mkdirSync('.local/verification', { recursive: true });
async function login(tab, email, password) {
  await tab.goto(base); if (!email.includes('@')) await tab.locator('input[name="loginMethod"][value="identity"]').check();
  await tab.locator('input[autocomplete="username"]').fill(email);
  await tab.getByLabel('Contraseña', { exact: true }).fill(password);
  await tab.getByRole('button', { name: 'Entrar a mi espacio' }).click();
  await tab.locator('.workspace').waitFor();
}
async function language(tab, lang) {
  await tab.locator('.language-trigger').click(); await tab.locator('[data-locale="'+lang+'"]').click();
  await tab.waitForFunction(lang => document.documentElement.lang === lang, lang);
}
async function inspect(tab, name) {
  const a = await new AxeBuilder({ page: tab }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  checks.push({ name, violations: a.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => ({ target:n.target, summary:n.failureSummary })) })) });
  assert.ok(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
  await tab.screenshot({ path: '.local/verification/operations-'+name+'.png', fullPage: true });
}
async function openCase(tab) { await tab.locator('.case-card').filter({ hasText: fixture.uiCaseId }).click(); await tab.locator('.refund-panel .refund-summary').waitFor(); }
try {
  await login(page, fixture.email, fixture.password);
  await page.goto(base+'/cards'); await page.locator('.bank-card').waitFor();
  for (const lang of ['es','en','pt']) {
    await language(page, lang);
    await page.setViewportSize({ width: lang === 'en' ? 390 : 1512, height: 1050 });
    await inspect(page, 'cards-'+lang);
  }
  await language(page, 'es'); await page.setViewportSize({ width:1512, height:1050 });
  await page.getByRole('button', { name:'Bloquear tarjeta', exact:true }).click();
  await inspect(page, 'block-confirm');
  await page.getByRole('dialog').getByLabel('Contraseña', { exact:true }).fill(fixture.password);
  await page.getByLabel('Confirmo el bloqueo de mi tarjeta.').check();
  await page.getByRole('button', { name:'Confirmar bloqueo', exact:true }).click();
  await page.locator('.card-blocked-label').waitFor();
  await page.getByRole('link', {name:'Mis productos',exact:true}).click();
  await page.locator('.product-kind-card .status-blocked').waitFor();
  await page.getByRole('link', {name:'Tarjetas',exact:true}).click();
  await page.reload(); await page.locator('.card-blocked-label').waitFor();
  assert.equal(await page.getByRole('button', { name:'Ver datos de la tarjeta', exact:true }).isDisabled(), true);
  await inspect(page, 'blocked-persisted');
  for (const lang of ['es','en','pt']) {
    await page.goto(base+'/requests'); await page.locator('.case-card').first().waitFor(); await language(page, lang);
    await page.setViewportSize({ width:lang === 'pt' ? 390 : 1512, height:1050 });
    await openCase(page); await inspect(page, 'refund-request-'+lang);
  }
  // Reload closes the previous dialog and restores the normal language control.
  await page.goto(base+'/requests'); await page.locator('.case-card').first().waitFor(); await language(page, 'es');
  await page.setViewportSize({ width:1512, height:1050 }); await openCase(page);
  await page.getByLabel('Solicito la revisión de este cargo para una devolución.').check();
  await page.getByRole('button', { name:'Solicitar devolución', exact:true }).click();
  await page.locator('.refund-panel').getByText('Devolución pendiente de aprobación', { exact:true }).waitFor();
  let data = await (await page.request.get(base+'/api/bootstrap')).json();
  const operationId = data.requests.find(r=>r.id===fixture.uiCaseId).refund.id;
  assert.ok(operationId.startsWith('RF-'));
  await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
  await page.getByRole('searchbox',{name:'Buscar una solicitud'}).fill(operationId);
  const pendingCard=page.locator('.case-card');
  assert.equal(await pendingCard.count(),1);
  assert.ok((await pendingCard.innerText()).includes('Devolución pendiente de aprobación'));
  await inspect(page,'pending-operation-id');
  assert.equal(data.products.find(p => p.id === fixture.accountId).balanceMinor, fixture.balanceBeforeUi);
  assert.equal(data.products.find(p => p.id === fixture.cardId).status, 'blocked');
  await login(admin, '00000002', credentials.ADMIN_PASSWORD);
  await admin.getByRole('searchbox',{name:'Buscar una solicitud'}).fill(operationId);
  assert.equal(await admin.locator('.case-card').count(),1);
  await openCase(admin);
  for (const width of [1512,390]) { await admin.setViewportSize({width,height:1050}); await inspect(admin, 'admin-review-'+width); }
  await admin.getByLabel('Evidencia revisada y motivo de la decisión').fill('Verificación UI: comprobante ficticio y titularidad revisados.');
  await admin.getByRole('dialog').getByLabel('Contraseña', {exact:true}).fill(credentials.ADMIN_PASSWORD);
  await admin.getByLabel('Revisé la evidencia y confirmo el abono a esta cuenta.').check();
  await admin.getByRole('button',{name:'Confirmar decisión',exact:true}).click();
  await admin.locator('.refund-panel').getByText('Devolución aprobada · abono registrado',{exact:true}).waitFor();
  await inspect(admin,'admin-approved');
  await page.reload(); await page.locator('.case-card').first().waitFor(); await openCase(page);
  await page.locator('.refund-panel').getByText('Devolución aprobada · abono registrado',{exact:true}).waitFor();
  await inspect(page, 'customer-approved');
  data=await (await page.request.get(base+'/api/bootstrap')).json();
  assert.equal(data.products.find(p=>p.id===fixture.accountId).balanceMinor,fixture.balanceBeforeUi+fixture.uiRefundAmount);
  assert.equal(data.transactions.filter(t=>t.category==='refund').length,4);
  const finalCase=data.requests.find(r=>r.id===fixture.uiCaseId);
  assert.equal(finalCase.refund.id,operationId); assert.equal(finalCase.refund.status,'approved');
  assert.ok(finalCase.refund.creditTransactionId.startsWith('CR-'));
  await admin.goto(base+'/admin');
  await admin.getByRole('searchbox',{name:'Buscar una solicitud'}).fill(finalCase.refund.creditTransactionId);
  assert.equal(await admin.locator('.case-card').count(),1);
  assert.ok((await admin.locator('.case-card').innerText()).includes('Devolución aprobada · abono registrado'));
  for (const lang of ['es','en','pt']) {
    await page.goto(base+'/movements'); await page.locator('.transaction-row').first().waitFor(); await language(page,lang);
    await page.setViewportSize({width:lang==='pt'?390:1512,height:1050});
    await page.locator('[data-transaction-id="'+finalCase.transactionId+'"]').click();
    await page.getByRole('button',{name:({es:'Preguntar por este movimiento',en:'Ask about this transaction',pt:'Perguntar sobre esta movimentação'})[lang],exact:true}).click();
    await page.locator('.transaction-context code').waitFor();
    assert.equal(await page.locator('.transaction-context code').textContent(),finalCase.transactionId);
    assert.ok((await page.locator('.chat-bubble.assistant').last().innerText()).includes(operationId));
    assert.ok((await page.locator('.chat-bubble.assistant').last().innerText()).includes(finalCase.refund.creditTransactionId));
    await inspect(page,'transaction-context-'+lang);
  }
  // Reopen the persisted context: the server derives the same movement on the next turn.
  await language(page,'es'); await page.reload(); await page.locator('.assistant-panel').waitFor();
  await page.getByRole('button',{name:'Conversaciones',exact:true}).click();
  await page.locator('.conversation-list button').first().click();
  assert.equal(await page.locator('.transaction-context code').textContent(),finalCase.transactionId);
  const audit=await (await admin.request.get(base+'/api/admin/audit?userId='+fixture.userId)).json();
  assert.ok(audit.events.some(e=>e.action==='card_blocked'&&e.actorId===fixture.userId&&e.productId===fixture.cardId));
  assert.ok(audit.events.some(e=>e.action==='refund_approved'&&e.actorId==='nora'&&e.userId===fixture.userId&&e.requestId===fixture.uiCaseId));
  assert.ok(audit.events.some(e=>e.action==='transaction_context_viewed'&&e.transactionId===finalCase.transactionId&&e.conversationId));
  assert.deepEqual(errors,[]);
  writeFileSync('.local/verification/operations-ui.json',JSON.stringify({checks,errors,verified:['persistent card block','customer request without credit','admin approved credit','same-owner balance and audit','pending and approved list state','admin searches operation and credit IDs','transaction chat ES/EN/PT and resumed context']},null,2));
  assert.equal(checks.flatMap(c=>c.violations).length,0,JSON.stringify(checks));
  console.log(JSON.stringify({passed:true,checks:checks.length,violations:0,errors:0}));
} finally { await browser.close(); }
