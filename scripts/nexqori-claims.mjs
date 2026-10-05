// Fresh PostgreSQL fixtures, then real UI/read-only trace checks. No LLM calls.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const origin = 'http://localhost:5180';
const output = '.local/verification/claims';
mkdirSync(output, { recursive: true });
const definitions = JSON.parse(readFileSync('tests/scenarios/banking-cases.json', 'utf8')).cases;
const input = { mode: 'prepare', languages: ['es'], definitions, integratedBanking: true };
const fixture = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1', '-e',
  'NEXQORI_CASES_INPUT=' + Buffer.from(JSON.stringify(input)).toString('base64'), 'api', 'python', '-'], {
  input: readFileSync('scripts/banking-cases-fixtures.py', 'utf8'), encoding: 'utf8', windowsHide: true, timeout: 120000,
});
if (fixture.status !== 0 || fixture.error) {
  writeFileSync(output + '/fixture-error.private.log', fixture.stderr || String(fixture.error), { mode: 0o600 });
  throw new Error('Fixture creation failed. Check the private diagnostic file.');
}
let pack;
try { pack = JSON.parse(fixture.stdout); } catch { throw new Error('Invalid fixture response; private stdout suppressed.'); }
const runDir = output + '/' + pack.runId;
mkdirSync(runDir, { recursive: true });
writeFileSync(runDir + '/credentials.private.json', JSON.stringify(pack, null, 2), { mode: 0o600 });
const copy = Object.fromEntries(['es', 'en', 'pt'].map(l => [l, JSON.parse(readFileSync('src/locales/' + l + '.json', 'utf8'))]));
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const report = { runId: pack.runId, cases: [], accessibility: [], errors: [], bankingDataUnchangedByReads: false };
const customerContexts = [];
let page;
async function authenticated(person) {
  const context = await browser.newContext({ viewport: { width: 1512, height: 1050 }, locale: 'es-MX' });
  const login = await context.request.post(origin + '/api/auth/login', { headers: { Origin: origin }, data: { identifier: person.email, password: person.password } });
  assert.equal(login.status(), 200, 'Fixture login must succeed');
  const { csrfToken } = await login.json();
  return { context, headers: { Origin: origin, 'X-CSRF-Token': csrfToken } };
}
async function mutate(auth, path, data) {
  const result = await auth.context.request.post(origin + '/api' + path, { headers: auth.headers, data });
  assert([200, 201].includes(result.status()), 'Expected fixture operation success: ' + path);
  return result.json();
}
async function bankData(context) {
  const { products, transactions, requests } = await (await context.request.get(origin + '/api/bootstrap')).json();
  return { products, transactions, requests };
}
async function axe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  report.accessibility.push({ name, violations: result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })) });
}
try {
  const admin = await authenticated(pack.admin);
  for (const [index, record] of pack.cases.entries()) {
    const customer = await authenticated(record); customerContexts.push(customer);
    const request = await mutate(customer, '/requests', { transactionId: record.transactionId, requestKey: randomUUID(), service: 'cards', reason: ['unknown', 'amount', 'payment'][index], details: 'Verificación de trazabilidad. ' + record.messages.es, confirmed: true });
    const chat = await mutate(customer, '/assistant', { transactionId: record.transactionId, message: record.messages.es, locale: 'es' });
    await mutate(customer, '/assistant/tools/read', { intent: record.intent, tool: 'read-transaction-evidence', referenceId: record.transactionId });
    if (index < 2) {
      const refund = await mutate(customer, '/requests/' + request.id + '/refund', { confirmed: true, requestKey: randomUUID() });
      if (index === 1) for (const stage of ['delivered', 'in_review', 'approved']) await mutate(admin, '/admin/requests/' + request.id + '/stage', { confirmed: true, stage, note: stage === 'approved' ? 'Verificación: evidencia del cargo revisada.' : '' });
      if (index === 1) await mutate(admin, '/admin/refunds/' + refund.id + '/decision', { confirmed: true, requestKey: randomUUID(), decision: 'approve', note: 'Verificación: revisión de importe, titular y cuenta de abono en el panel de reclamos.', password: pack.admin.password });
    } else await mutate(customer, '/requests/' + request.id + '/handoff', { confirmed: true });
    const document = (await mutate(customer, '/conversations/' + record.conversationId + '/documents', { kind: 'claims_summary', scope: 'selected', requestId: request.id, locale: 'es', requestKey: randomUUID() })).document;
    report.cases.push({ documentId: document.id, id: record.id, userId: record.userId, requestId: request.id, conversationId: chat.conversation.id, url: origin + '/admin/complaints?user=' + record.userId + '&case=' + request.id });
  }
  const baselines = await Promise.all(customerContexts.map(c => bankData(c.context)));
  page = await admin.context.newPage(); page.setDefaultTimeout(20000); page.on('pageerror', e => report.errors.push(e.message));
  await page.goto(origin + '/admin');
  const userRow = page.locator('.admin-users tr').filter({ hasText: pack.cases[0].email });
  await userRow.getByRole('button', { name: copy.es['claims.viewUser'], exact: true }).click();
  await expect(page).toHaveURL(new RegExp('user=' + pack.cases[0].userId));
  await expect(page.locator('.claim-choice')).toHaveCount(1);
  await page.locator('.claim-choice').click();
  await page.locator('[data-trace-ready=true]').waitFor();
  await expect(page.locator('.trace-current')).toContainText(copy.es['trace.outcome.refund_pending']);
  await page.locator('[data-trace-tab=decision]').click();
  await expect(page.locator('.admin-case-decision')).toBeVisible();
  await expect(page.locator('.admin-case-decision').getByRole('button', { name: copy.es['claimStage.action.delivered'], exact: true })).toBeDisabled();
  await expect(page.locator('.admin-case-decision .refund-panel select')).toHaveCount(0);
  await expect(page.locator('.admin-case-decision .refund-panel')).toContainText(copy.es['claimStage.approvalRequired']);
  await page.reload(); await page.locator('[data-trace-ready=true]').waitFor();
  await expect(page.locator('.trace-current')).toContainText(copy.es['trace.outcome.refund_pending']);
  const dossier = await (await admin.context.request.get(origin + '/api/admin/users/' + pack.cases[0].userId + '/requests/' + report.cases[0].requestId + '/trace')).json();
  assert(dossier.events.some(e => e.action === 'tool_transaction_evidence'));
  assert.equal(dossier.conversations[0].id, report.cases[0].conversationId);
  const wrongOwner = await admin.context.request.get(origin + '/api/admin/users/' + pack.cases[1].userId + '/requests/' + report.cases[0].requestId + '/trace');
  assert.equal(wrongOwner.status(), 404);
  for (const locale of ['es', 'en', 'pt']) {
    await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click();
    await page.waitForFunction(l => document.documentElement.lang === l, locale);
    const t = copy[locale];
    await expect(page.getByRole('heading', { name: t['claims.title'], exact: true })).toBeVisible();
    for (const [index, result] of report.cases.entries()) {
      await page.goto(result.url); await page.locator('[data-trace-ready=true]').waitFor();
      await expect(page.locator('.trace-current')).toContainText(t['trace.outcome.' + ['refund_pending', 'refund_approved', 'handed_off'][index]]);
      await expect(page.locator('.trace-facts').first()).toContainText(result.requestId);
      await page.getByRole('button', { name: new RegExp('^' + t['caseAdmin.conversations']) }).click();
      await page.locator('.trace-conversation').first().click();
      await expect(page.locator('.trace-transcript')).toContainText(pack.cases[index].messages.es);
      if (index === 0) await axe(locale + '-transcript');
      await page.locator('.trace-transcript').getByRole('button', { name: t.close, exact: true }).click();
      await page.getByRole('button', { name: new RegExp('^' + t['caseAdmin.documents']) }).click();
      const card = page.locator('[data-case-document="' + result.documentId + '"]');
      await expect(card).toBeVisible();
      const link = card.getByRole('link', { name: new RegExp('^' + t['caseAdmin.openPdf']) });
      await expect(link).toHaveAttribute('target', '_blank');
      const fileUrl = await link.getAttribute('href');
      const opened = await admin.context.request.get(origin + fileUrl);
      assert.equal(opened.status(), 200); assert.equal((await opened.body()).subarray(0, 5).toString(), '%PDF-');
      assert(opened.headers()['content-disposition'].startsWith('inline'));
      const download = page.waitForEvent('download');
      await card.getByRole('link', { name: new RegExp('^' + t['documents.download']) }).click();
      await (await download).saveAs(runDir + '/case-' + index + '-' + locale + '.pdf');
      if (index === 0) { await axe(locale + '-documents'); await page.screenshot({path: runDir + '/documents-' + locale + '.png', fullPage: true}); }
      await page.getByRole('button', { name: t['caseAdmin.activity'], exact: true }).click();
      await page.locator('.claim-trace').getByRole('button', {name: t.auditRefresh, exact: true}).click();
      await page.locator('[data-trace-ready=true]').waitFor();
      await expect(page.locator('.trace-events')).toContainText(t['auditActions.case_document_opened']);
      await expect(page.locator('.trace-events')).toContainText(t['auditActions.case_document_downloaded']);
      await page.getByRole('button', { name: t['inbox.technical'], exact: true }).click();
      const json = JSON.parse(await page.locator('.trace-json').innerText());
      assert.equal(json.request.userId, result.userId); assert.equal(json.externalProcessorLogs, false);
      await page.getByRole('button', { name: t['trace.simple'], exact: true }).click();
      await axe(locale + '-' + result.id);
      if (locale === 'es') await page.screenshot({ path: runDir + '/' + result.id + '-desktop.png', fullPage: true });
      if (index === 0) {
        await page.setViewportSize({ width: 390, height: 900 });
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile overflow');
        await axe(locale + '-mobile');
        if (locale === 'es') await page.screenshot({ path: runDir + '/mobile.png', fullPage: true });
        await page.setViewportSize({ width: 1512, height: 1050 });
      }
    }
  }
  // Refresh failure preserves the current dossier and offers retry.
  await page.route('**/api/admin/users/**/trace?*', route => route.abort());
  await page.locator('.claim-trace').getByRole('button', { name: copy.pt.auditRefresh }).click();
  await expect(page.getByRole('alert')).toContainText(copy.pt['trace.error']);
  await expect(page.locator('.trace-current')).toBeVisible();
  await page.unroute('**/api/admin/users/**/trace?*');
  await page.locator('.claim-trace').getByRole('button', { name: copy.pt.auditRefresh }).click();
  await page.locator('[data-trace-ready=true]').waitFor();
  const customer = customerContexts[0];
  const forbidden = await customer.context.request.get(origin + '/api/admin/users/' + pack.cases[0].userId + '/requests/' + report.cases[0].requestId + '/trace');
  assert.equal(forbidden.status(), 403);
  const foreign = await customer.context.request.get(origin + '/api/requests/' + report.cases[1].requestId + '/trace');
  assert.equal(foreign.status(), 404);
  const customerPage = await customer.context.newPage(); page = customerPage;
  page.on('pageerror', e => report.errors.push(e.message));
  await page.goto(origin + '/complaints'); await page.locator('.claim-choice').click(); await page.locator('.claims-detail-header button').click();
  await page.locator('dialog [data-trace-ready=true]').waitFor();
  await expect(page.locator('dialog .trace-current')).toContainText(copy.es['trace.outcome.refund_pending']);
  await axe('customer-case');
  for (const [index, customer] of customerContexts.entries()) assert.deepEqual(await bankData(customer.context), baselines[index], 'Reading a dossier must not change financial or request state');
  report.bankingDataUnchangedByReads = true;
  assert.deepEqual(report.errors, []);
  assert.equal(report.accessibility.flatMap(a => a.violations).length, 0, JSON.stringify(report.accessibility));
  const guide = '# Accesos privados · Panel de reclamos\n\n' +
    'Banco: ' + origin + '/admin/complaints\n\n' +
    '| Perfil | Correo | Contraseña |\n| --- | --- | --- |\n' +
    [pack.admin, ...pack.cases].map(p => `| ${p.name} | ${p.email} | ${p.password} |`).join('\n') + '\n\n' +
    report.cases.map(c => '- [' + c.id + '](' + c.url + ')').join('\n') +
    '\n\nRegistros nuevos de verificación persistentes: devolución pendiente, devolución aprobada y atención humana solicitada. Ningún cliente anterior fue modificado. Este archivo no se publica.\n';
  writeFileSync(runDir + '/INICIAR.private.md', guide, { mode: 0o600 });
  writeFileSync(output + '/latest.json', JSON.stringify({ runId: pack.runId, guide: runDir + '/INICIAR.private.md', report: runDir + '/report.json', cases: report.cases }, null, 2));
  console.log(JSON.stringify({ passed: true, cases: report.cases.length, languages: ['es', 'en', 'pt'], accessibility: report.accessibility.length, financialReadsUnchanged: true, report: runDir + '/report.json' }));
} catch (e) {
  if (page) await page.screenshot({ path: runDir + '/failure.png', fullPage: true });
  throw e;
} finally {
  writeFileSync(runDir + '/report.json', JSON.stringify(report, null, 2));
  await browser.close();
}
