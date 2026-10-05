// Isolated customer → admin → customer journey; no live providers or manual accounts.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin = 'http://127.0.0.1:5192';
const folder = await fs.mkdtemp(path.resolve('.local/verification/admin-decision-'));
assert.equal(await fetch(origin + '/api/health').then(() => true).catch(() => false), false, 'Port 5192 must be free');
const python = process.env.NEXQORI_BANK_PYTHON || path.resolve(process.platform === 'win32' ? '.venv-app/Scripts/python.exe' : '.venv-app/bin/python');
const server = spawn(python, ['-m', 'backend.tests.attention_ui_server'], { env: { ...process.env, BANK_VOICE_ENABLED: 'false', NEXQORI_CHAT_UI_CHECK: '1', NEXQORI_CHAT_UI_DATA: folder }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let diagnostics = '', browser, page;
server.stderr.on('data', chunk => diagnostics += chunk.toString());
const report = { checks: [], accessibility: [], errors: [] };
async function login(person) {
  const context = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
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
  for (let i = 0; i < 150; i++) { if (await fetch(origin + '/api/health').then(r => r.ok).catch(() => false)) break; if (server.exitCode !== null) throw new Error(diagnostics); await new Promise(resolve => setTimeout(resolve, 150)); }
  const people = JSON.parse(await fs.readFile(path.join(folder, 'credentials.private.json'), 'utf8'));
  const adminPerson = JSON.parse(await fs.readFile(path.join(folder, 'admin.private.json'), 'utf8'));
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
  const admin = await login(adminPerson);
  for (const locale of ['es', 'en', 'pt']) {
    const copy = JSON.parse(await fs.readFile('src/locales/' + locale + '.json', 'utf8'));
    for (const decision of ['approve', 'reject', 'pending']) {
      const person = people.find(p => p.locale === locale && p.intent === (decision === 'pending' ? 'payment-status' : decision === 'approve' ? 'incorrect-charge' : 'unrecognized-charge'));
      const customer = await login(person);
      const before = await (await customer.context.request.get(origin + '/api/bootstrap')).json();
      const created = await customer.context.request.post(origin + '/api/requests', { headers: customer.headers, data: { transactionId: person.transactionId, requestKey: crypto.randomUUID(), service: 'payments', reason: decision === 'pending' ? 'payment' : 'amount', details: 'Verificación: el cliente solicita revisar el cobro vinculado.', confirmed: true } });
      assert.equal(created.status(), 201); const claim = await created.json();
      if (decision !== 'pending') assert.equal((await customer.context.request.post(origin + '/api/requests/' + claim.id + '/refund', { headers: customer.headers, data: { confirmed: true, requestKey: crypto.randomUUID() } })).status(), 200);
      const customerPage = await customer.context.newPage();
      page = customerPage; await page.goto(origin + '/complaints?case=' + claim.id); await language(locale);
      await expect(page.locator('.claim-trace')).toHaveAttribute('data-trace-ready', 'true');
      page = await admin.context.newPage(); page.on('pageerror', error => report.errors.push(error.message));
      await page.goto(origin + '/admin/complaints?case=' + claim.id); await language(locale);
      const detail = page.locator('.claims-detail');
      await expect(detail.locator('.case-review-context')).toBeVisible();
      const actions = detail.locator('.admin-case-decision');
      await actions.getByLabel(copy['caseDecision.reviewConfirm'], { exact: true }).check();
      await actions.getByRole('button', { name: copy['caseDecision.start'], exact: true }).click();
      await expect(actions.locator('.case-review-start')).toHaveCount(0);
      if (decision === 'pending') {
        await expect(detail).toContainText(copy['caseDecision.missing.payment_confirmation']);
        await expect(actions.locator('.refund-panel form')).toHaveCount(0);
        await expect(detail.locator('.attention-review')).toContainText(copy['attention.pending']);
      } else {
        const refund = actions.locator('.refund-panel');
        await refund.locator('select').selectOption(decision);
        const note = 'Verificación: ' + (decision === 'approve' ? 'se aprueba el importe completo después de revisar los registros.' : 'se rechaza la devolución; el pago original conserva su estado.');
        await refund.getByLabel(copy.refundEvidence, { exact: true }).fill(note);
        await refund.getByLabel(copy.password, { exact: true }).fill(adminPerson.password);
        await refund.getByLabel(copy[decision === 'approve' ? 'refundConfirmApprove' : 'refundConfirmReject'], { exact: true }).check();
        await refund.getByRole('button', { name: copy.refundSaveDecision, exact: true }).click();
        await expect(refund.locator('form')).toHaveCount(0);
        await expect(refund).toContainText(note);
        const attention = detail.locator('.attention-review');
        await attention.getByLabel(copy['attention.summary'], { exact: true }).fill('Verificación: resultado explicado al cliente y sin gestiones pendientes.');
        await attention.getByLabel(copy['attention.confirm'], { exact: true }).check();
        await attention.getByRole('button', { name: copy['attention.resolve'], exact: true }).click();
        await expect(attention).toContainText(copy['attention.scheduled']);
      }
      await checkAxe('admin-' + locale + '-' + decision);
      if (locale === 'es' && decision === 'approve') await detail.screenshot({ path: path.join(folder, 'admin-es.png') });
      await page.close(); page = customerPage; page.on('pageerror', error => report.errors.push(error.message));
      await page.locator('.claims-refresh button').click();
      const trace = page.locator('.claim-trace'); await expect(trace).toHaveAttribute('data-trace-ready', 'true');
      if (decision !== 'pending') {
        await expect(trace).toContainText(copy['trace.outcome.refund_' + (decision === 'approve' ? 'approved' : 'rejected')]);
        await expect(trace.locator('.trace-decision')).toContainText('Verificación:');
        await expect(trace.locator('.attention-review')).toContainText(copy['attention.scheduled']);
      }
      if (decision === 'approve') {
        const survey = trace.locator('.attention-review');
        await survey.getByRole('button', { name: copy['attention.answer'], exact: true }).click();
        await survey.locator('.survey-scale-nps input[value="8"]').check({ force: true });
        await survey.locator('.survey-scale-csat input[value="4"]').check({ force: true });
        await survey.getByLabel(copy['attention.comment'], { exact: true }).fill('Borrador de opinión que se conserva al actualizar');
        await page.locator('.claims-refresh button').click();
        await expect(trace).toHaveAttribute('data-trace-ready', 'true');
        await expect(survey.locator('.survey-scale-nps input[value="8"]')).toBeChecked();
        await expect(survey.locator('.survey-scale-csat input[value="4"]')).toBeChecked();
        await expect(survey.locator('.chat-survey textarea')).toHaveValue('Borrador de opinión que se conserva al actualizar');
        await expect(survey).toContainText(copy['attention.unsaved']);
        // Hold a committed write response while the reader refreshes the same case.
        // A refresh must neither abort the write nor leave its button stuck busy.
        let acknowledge, release;
        const received = new Promise(resolve => { acknowledge = resolve; });
        const responseGate = new Promise(resolve => { release = resolve; });
        const feedbackPath = '**/api/attention/requests/' + claim.id + '/feedback';
        await page.route(feedbackPath, async route => { const response = await route.fetch(); acknowledge(); await responseGate; await route.fulfill({ response }); });
        await survey.getByRole('button', { name: copy['attention.saveDraft'], exact: true }).click();
        await received;
        await page.locator('.claims-refresh button').click();
        await expect(trace).toHaveAttribute('data-trace-ready', 'true');
        release();
        await expect(survey).toContainText(copy['attention.saved']);
        await expect(survey.getByRole('button', { name: copy.submitSurvey, exact: true })).toBeEnabled();
        await page.unroute(feedbackPath);
        const persisted = await (await customer.context.request.get(origin + '/api/attention/requests/' + claim.id)).json();
        assert.equal(persisted.review.answers.nps, 8); assert.equal(persisted.review.answers.csat, 4);
        assert.equal(persisted.review.answers.comment, 'Borrador de opinión que se conserva al actualizar');
      }
      await page.setViewportSize({ width: 390, height: 844 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await checkAxe('customer-mobile-' + locale + '-' + decision);
      if (locale === 'es' && decision === 'approve') await trace.screenshot({ path: path.join(folder, 'customer-es.png') });
      if (decision === 'approve') {
        await page.setViewportSize({ width: 1512, height: 1050 });
        await page.locator('.paste-composer textarea').fill('Borrador conservado al ver el abono');
        await page.evaluate(() => window.__adminDecisionNavigation = true);
        await page.getByRole('button', { name: copy['caseDecision.viewCredit'], exact: true }).click();
        await expect(page).toHaveURL(/\/movements\?transaction=CR-/);
        assert.equal(await page.evaluate(() => window.__adminDecisionNavigation), true, 'Must not reload the application');
        await expect(page.locator('.paste-composer textarea')).toHaveValue('Borrador conservado al ver el abono');
        await expect(page.locator('.transaction-panel .transaction-row')).toHaveCount(1);
      }
      const after = await (await customer.context.request.get(origin + '/api/bootstrap')).json();
      const credits = after.transactions.filter(tx => tx.category === 'refund');
      assert.equal(credits.length, decision === 'approve' ? 1 : 0);
      assert.equal(after.transactions.find(tx => tx.id === person.transactionId).status, decision === 'pending' ? 'pending' : 'completed');
      if (decision !== 'approve') assert.deepEqual(after.products, before.products);
      report.checks.push({ locale, decision, customerRefresh: true, surveyDraftAndWriteSurviveRefresh: decision === 'approve' ? true : undefined, originalPaymentPreserved: true, credits: credits.length });
      await customer.context.close();
    }
  }
  assert.deepEqual(report.errors, []); await fs.writeFile(path.join(folder, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ folder, ...report }, null, 2));
} catch (error) { if (page && !page.isClosed()) await page.screenshot({ path: path.join(folder, 'failure.png'), fullPage: true }).catch(() => {}); throw error; }
finally { await browser?.close(); server.kill(); await fs.writeFile(path.join(folder, 'server.private.log'), diagnostics); }
