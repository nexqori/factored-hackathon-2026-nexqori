// Acceptance against local Compose, using new isolated verification customers.
// No model calls, external collectors, real accounts, or existing data changes.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const origin = 'http://localhost:5180';
const output = '.local/verification/banking-integrated';
const definitions = JSON.parse(readFileSync('tests/scenarios/banking-cases.json', 'utf8')).cases
  .map(value => ({ ...value, initialBalanceMinor: 300000 }));
mkdirSync(output, { recursive: true });
function fixture(payload) {
  const result = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1',
    '-e', 'NEXQORI_CASES_INPUT=' + Buffer.from(JSON.stringify(payload)).toString('base64'), 'api', 'python', '-'],
  { input: readFileSync('scripts/banking-cases-fixtures.py', 'utf8'), encoding: 'utf8', windowsHide: true, timeout: 120000 });
  if (result.status !== 0) {
    writeFileSync(output + '/fixture-error.private.txt', result.stderr || 'No diagnostic output', { mode: 0o600 });
    throw new Error('Fixture operation failed; see the private diagnostic file.');
  }
  return JSON.parse(result.stdout);
}
const pack = fixture({ mode: 'prepare', languages: ['es'], definitions, integratedBanking: true });
const folder = output + '/' + pack.runId;
mkdirSync(folder, { recursive: true });
writeFileSync(folder + '/credentials.private.json', JSON.stringify(pack, null, 2), { mode: 0o600 });
const report = { runId: pack.runId, status: 'running', cases: [], accessibility: [], errors: [], modelRequests: 0 };
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
let page;
async function axe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const violations = result.violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }));
  report.accessibility.push({ name, violations });
  assert.deepEqual(violations, [], name + ' accessibility');
}
async function checkedJson(response, status = 200) {
  assert.equal(response.status(), status, response.url());
  return response.json();
}
async function login(context, person) {
  const result = await checkedJson(await context.request.post(origin + '/api/auth/login', {
    headers: { Origin: origin }, data: { identifier: person.email, password: person.password },
  }));
  return { Origin: origin, 'X-CSRF-Token': result.csrfToken };
}
const balance = (snapshot, id) => snapshot.products.find(p => p.id === id).balanceMinor;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

try {
  const receiverContext = await browser.newContext();
  await login(receiverContext, pack.beneficiary);
  const recipientBefore = await checkedJson(await receiverContext.request.get(origin + '/api/bootstrap'));
  for (const [index, locale] of ['es', 'en', 'pt'].entries()) {
    const person = pack.cases[index]; const copy = JSON.parse(readFileSync('src/locales/' + locale + '.json', 'utf8'));
    const context = await browser.newContext({ viewport: { width: 1512, height: 1050 }, acceptDownloads: true });
    page = await context.newPage(); page.on('pageerror', error => report.errors.push(error.message));
    await page.route('**/api/assistant/flow', route => { report.modelRequests++; return route.abort('blockedbyclient'); });
    const headers = await login(context, person);
    await checkedJson(await context.request.patch(origin + '/api/profile/locale', { headers, data: { locale } }));
    const before = await checkedJson(await context.request.get(origin + '/api/bootstrap'));
    const result = { locale, userId: person.userId, payments: [], documents: [], transferId: null };
    const phone = person.bills[0], secondPhone = person.bills[1], internet = person.bills[2];
    const label = service => copy[service === 'phone-bill' ? 'catalogReference_phone' : service === 'utilities-bill' ? 'catalogReference_receipt' : 'catalogReference_customer'];

    async function lookup(bill, { saved = false, navigate = true } = {}) {
      if (navigate) await page.goto(origin + '/services/catalog/' + bill.serviceId);
      if (saved) await page.getByRole('button', { name: bill.reference, exact: true }).click();
      else {
        await page.getByRole('textbox', { name: label(bill.serviceId), exact: true }).fill(bill.reference);
        await page.getByRole('button', { name: copy['bills.lookup'], exact: true }).click();
      }
      await expect(page.locator('.bill-result')).toContainText(bill.reference);
      await expect(page.locator('.bill-result h2')).toBeFocused();
    }
    async function pay(bill, amountMinor, { partial = false, loseResponse = false } = {}) {
      assert.equal(await page.locator('.bill-result input[inputmode=decimal]').count(), 0, 'A total invoice must not be editable');
      if (partial) {
        await page.getByRole('radio', { name: copy['bills.partial'], exact: true }).check();
        const input = page.getByRole('textbox', { name: copy['bills.partialAmount'], exact: true });
        await input.fill('999999');
        await expect(page.getByRole('button', { name: copy['pay.review'], exact: true })).toBeDisabled();
        await expect(page.getByText(copy['error.payment_exceeds_bill'], { exact: true })).toBeVisible();
        await input.fill((amountMinor / 100).toFixed(2));
      }
      await page.getByRole('button', { name: copy['pay.review'], exact: true }).click();
      await expect(page.getByRole('button', { name: copy['pay.confirm'], exact: true })).toBeDisabled();
      await expect(page.locator('.bill-result')).toContainText(bill.reference);
      await page.getByRole('checkbox', { name: copy['pay.confirmCheck'], exact: true }).check();
      if (loseResponse) await page.route('**/api/service-bills/*/pay', async route => {
        const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort('failed');
      }, { times: 1 });
      await page.getByRole('button', { name: copy['pay.confirm'], exact: true }).click();
      if (loseResponse) {
        await expect(page.getByRole('alert')).toContainText(copy['error.network']);
        await page.getByRole('button', { name: copy['pay.confirm'], exact: true }).click();
      }
      await expect(page.getByRole('heading', { name: copy['pay.done'], exact: true })).toBeVisible();
      const id = await page.locator('[data-payment-id]').getAttribute('data-payment-id');
      const receipt = await checkedJson(await context.request.get(origin + '/api/payments/' + id));
      assert.equal(receipt.amountMinor, amountMinor); assert.equal(receipt.reference, bill.reference);
      assert.equal(receipt.billId, bill.id); result.payments.push({ id, billId: bill.id, amountMinor, remainingMinor: receipt.remainingMinor });
      return receipt;
    }

    await page.goto(origin + '/services/catalog/phone-bill');
    await page.getByRole('textbox', { name: copy.catalogReference_phone, exact: true }).fill(pack.cases[(index + 1) % 3].bills[0].reference);
    await page.getByRole('button', { name: copy['bills.lookup'], exact: true }).click();
    await expect(page.getByText(copy['bills.empty'], { exact: true })).toBeVisible();
    await expect(page.locator('.bill-result')).toHaveCount(0);
    await lookup(phone, { saved: true, navigate: false }); await axe('phone-lookup-' + locale);
    await pay(phone, phone.amountMinor, { loseResponse: index === 0 }); await axe('phone-receipt-' + locale);
    await page.getByRole('link', { name: copy['bills.another'], exact: true }).click();
    await lookup(secondPhone, { saved: true, navigate: false }); await pay(secondPhone, secondPhone.amountMinor);
    await lookup(phone); await expect(page.getByRole('link', { name: copy['pay.receipt'], exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: copy['pay.review'], exact: true })).toHaveCount(0);
    await lookup(internet); const partial = await pay(internet, 10000, { partial: true }); assert.equal(partial.remainingMinor, 35900);
    await page.getByRole('link', { name: copy['bills.another'], exact: true }).click();
    await lookup(internet, { navigate: false }); await expect(page.locator('.bill-total')).toContainText(/359[.,]00/);
    const paid = await pay(internet, 35900); assert.equal(paid.remainingMinor, 0);
    for (const bill of person.bills.slice(3)) {
      await lookup(bill);
      if (!bill.allowPartial) await expect(page.getByRole('radio', { name: copy['bills.partial'], exact: true })).toHaveCount(0);
      await pay(bill, bill.amountMinor);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: folder + '/payment-mobile-' + locale + '.png', fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); await axe('payment-mobile-' + locale);
    await page.getByRole('link', { name: copy['bills.another'], exact: true }).click(); await lookup(phone, { saved: true });
    await axe('lookup-mobile-' + locale); await page.setViewportSize({ width: 1512, height: 1050 });

    await page.goto(origin + '/services/catalog/bank-transfer');
    await page.getByRole('textbox', { name: copy['transfer.reference'], exact: true }).fill('000000000000000000');
    await page.getByRole('button', { name: copy['transfer.find'], exact: true }).click();
    await expect(page.getByRole('alert')).toContainText(copy['error.recipient_not_found']);
    await page.getByRole('textbox', { name: copy['transfer.reference'], exact: true }).fill(pack.beneficiary.reference.replace(/(.{6})/g, '$1 '));
    await page.getByRole('button', { name: copy['transfer.find'], exact: true }).click();
    await expect(page.locator('.recipient-card')).toContainText(pack.beneficiary.name);
    await expect(page.locator('.recipient-card')).toContainText(pack.beneficiary.reference);
    await page.getByRole('textbox', { name: copy.amount, exact: true }).fill('99999');
    await expect(page.getByText(copy['error.insufficient_funds'], { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: copy['transfer.review'], exact: true })).toBeDisabled();
    await page.getByRole('textbox', { name: copy.amount, exact: true }).fill('75.25');
    await page.getByRole('textbox', { name: copy['transfer.note'], exact: true }).fill('Verificación · ' + locale);
    await page.getByRole('button', { name: copy['transfer.review'], exact: true }).click();
    await expect(page.getByRole('button', { name: copy['transfer.confirm'], exact: true })).toBeDisabled();
    await expect(page.locator('.recipient-card')).toContainText(pack.beneficiary.reference);
    await axe('transfer-review-' + locale);
    await page.getByRole('checkbox', { name: copy['transfer.confirmCheck'], exact: true }).check();
    if (index === 0) await page.route('**/api/transfers', async route => {
      const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort('failed');
    }, { times: 1 });
    await page.getByRole('button', { name: copy['transfer.confirm'], exact: true }).click();
    if (index === 0) {
      await expect(page.getByRole('alert')).toContainText(copy['error.network']);
      await page.getByRole('button', { name: copy['transfer.confirm'], exact: true }).click();
    }
    await expect(page.getByRole('heading', { name: copy['transfer.done'], exact: true })).toBeVisible();
    result.transferId = await page.locator('[data-transfer-id]').getAttribute('data-transfer-id');
    const sent = await checkedJson(await context.request.get(origin + '/api/transfers/' + result.transferId));
    const received = await checkedJson(await receiverContext.request.get(origin + '/api/transfers/' + result.transferId));
    assert.equal(sent.amountMinor, 7525); assert.equal(sent.direction, 'sent'); assert.equal(received.direction, 'received');
    assert.notEqual(sent.transactionId, received.transactionId);
    await page.reload(); await expect(page.locator('[data-transfer-id]')).toHaveAttribute('data-transfer-id', result.transferId);
    await page.setViewportSize({ width: 390, height: 844 }); await axe('transfer-mobile-' + locale);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: folder + '/transfer-mobile-' + locale + '.png', fullPage: true });
    await page.setViewportSize({ width: 1512, height: 1050 });
    await page.goto(origin + '/movements');
    await page.locator('[data-transaction-id="' + sent.transactionId + '"]').click();
    await expect(page.locator('dialog')).toContainText(result.transferId);
    await page.getByRole('button', { name: copy.close, exact: true }).click();

    async function openHistory() {
      await page.getByRole('button', { name: copy.conversations, exact: true }).click();
      await page.locator('.conversation-list button').first().click();
      await expect(page.getByRole('button', { name: copy['documents.prepare'], exact: true })).toBeVisible();
    }
    await openHistory();
    for (const [docIndex, kind] of ['statement', 'products_summary', 'requests_summary'].entries()) {
      await page.getByRole('button', { name: copy['documents.prepare'], exact: true }).click();
      const dialog = page.locator('dialog');
      await expect(dialog.getByRole('combobox', { name: copy['documents.type'], exact: true })).toBeEnabled();
      await expect(dialog.getByRole('combobox', { name: copy['documents.type'], exact: true })).toHaveValue('');
      await expect(dialog.getByRole('button', { name: copy['documents.generate'], exact: true })).toBeDisabled();
      await dialog.getByRole('combobox', { name: copy['documents.type'], exact: true }).selectOption(kind);
      if (kind === 'statement') {
        await dialog.getByLabel(copy['documents.from'], { exact: true }).fill('2024-01-01');
        await dialog.getByLabel(copy['documents.to'], { exact: true }).fill('2026-10-31');
        await expect(dialog.getByText(copy['documents.periodInvalid'], { exact: true })).toBeVisible();
        await expect(dialog.getByRole('button', { name: copy['documents.generate'], exact: true })).toBeDisabled();
        await dialog.getByRole('checkbox', { name: copy['documents.allHistory'], exact: true }).check();
      }
      if (kind === 'products_summary') {
        await dialog.getByRole('combobox', { name: copy['documents.scope'], exact: true }).selectOption('selected');
        await dialog.getByRole('combobox', { name: copy.product, exact: true }).selectOption(person.accountId);
      }
      if (docIndex === 0) {
        await axe('pdf-form-' + locale); await page.setViewportSize({ width: 390, height: 844 });
        await axe('pdf-mobile-' + locale); await page.screenshot({ path: folder + '/pdf-form-mobile-' + locale + '.png', fullPage: true });
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.setViewportSize({ width: 1512, height: 1050 });
      }
      if (index === 0 && docIndex === 0) await page.route('**/api/conversations/*/documents', async route => {
        const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort('failed');
      }, { times: 1 });
      await dialog.getByRole('button', { name: copy['documents.generate'], exact: true }).click();
      if (index === 0 && docIndex === 0) {
        await expect(dialog.getByRole('alert')).toContainText(copy['error.network']);
        await dialog.getByRole('button', { name: copy['documents.generate'], exact: true }).click();
      }
      await expect(dialog).toHaveCount(0);
      const card = page.locator('.assistant-panel .chat-document').last(); await card.waitFor();
      const docId = await card.getAttribute('data-document-id');
      await expect(page).toHaveURL(origin + '/documents?document=' + docId);
      const documentRequest = page.locator('[data-document-request-id="' + docId + '"]');
      await expect(documentRequest).toBeVisible();
      await documentRequest.getByRole('button', { name: copy['documents.viewDetails'], exact: true }).click();
      await expect(page.locator('dialog')).toContainText(copy['documents.records']);
      await expect(page.locator('dialog pre')).toHaveCount(0);
      await page.getByRole('button', { name: copy.close, exact: true }).click();
      const downloadPromise = page.waitForEvent('download'); await documentRequest.getByRole('button', { name: new RegExp('^' + copy['documents.download']) }).click();
      const download = await downloadPromise; const pdfPath = folder + '/' + locale + '-' + kind + '.pdf';
      await download.saveAs(pdfPath); const bytes = readFileSync(pdfPath); assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
      const stored = await context.request.get(origin + '/api/documents/' + docId);
      assert.equal(stored.status(), 200); assert.equal(digest(await stored.body()), digest(bytes));
      assert.equal((await receiverContext.request.get(origin + '/api/documents/' + docId)).status(), 404);
      result.documents.push({ id: docId, kind, sha256: digest(bytes), bytes: bytes.length });
    }
    const history = await checkedJson(await context.request.get(origin + '/api/conversations/' + person.conversationId));
    assert.equal(history.messages.filter(message => message.document).length, 3, 'Retry must not duplicate the document message');
    await page.reload(); await openHistory(); await expect(page.locator('.assistant-panel .chat-document')).toHaveCount(3);
    await expect(page.locator('.assistant-panel pre')).toHaveCount(0); await axe('pdf-history-' + locale);
    const oldestDownload = page.waitForEvent('download'); await page.locator('.assistant-panel .chat-document').first().getByRole('button').click();
    const old = await oldestDownload; const oldPath = folder + '/' + locale + '-historical.pdf'; await old.saveAs(oldPath);
    assert.equal(digest(readFileSync(oldPath)), result.documents[0].sha256);
    const after = await checkedJson(await context.request.get(origin + '/api/bootstrap'));
    const expectedDebit = person.bills.reduce((sum, bill) => sum + bill.amountMinor, 0) + 7525;
    assert.equal(balance(after, person.accountId), balance(before, person.accountId) - expectedDebit);
    assert.equal(after.transactions.length, before.transactions.length + 7); // Six payments + transfer.
    assert.deepEqual(after.requests, before.requests, 'Payment/transfer/PDF must not create a request');
    result.balanceMinor = balance(after, person.accountId); result.requestsUnchanged = true;
    report.cases.push(result); await context.close();
  }
  const recipientAfter = await checkedJson(await receiverContext.request.get(origin + '/api/bootstrap'));
  assert.equal(balance(recipientAfter, pack.beneficiary.accountId), balance(recipientBefore, pack.beneficiary.accountId) + 3 * 7525);
  assert.equal(recipientAfter.transactions.length, recipientBefore.transactions.length + 3);
  report.recipientCreditedMinor = 3 * 7525;
  await receiverContext.close();
  assert.equal(report.modelRequests, 0); assert.deepEqual(report.errors, []);
  report.database = fixture({ mode: 'verify_banking', pack: {
    adminId: pack.admin.userId, integratedBanking: true, untouchedHash: pack.untouchedHash,
    beneficiary: { userId: pack.beneficiary.userId, accountId: pack.beneficiary.accountId, initialBalanceMinor: pack.beneficiary.initialBalanceMinor },
    cases: pack.cases.map(({ password, email, ...person }) => ({ ...person, transferAmountMinor: 7525, documentCount: 3 })),
  } });
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.failure = String(error);
  if (page && !page.isClosed()) await page.screenshot({ path: folder + '/failure.png', fullPage: true }).catch(() => {});
  throw error;
} finally {
  writeFileSync(folder + '/report.json', JSON.stringify(report, null, 2));
  writeFileSync(output + '/latest.json', JSON.stringify({ folder, runId: pack.runId, status: report.status }));
  await browser.close();
  console.log(JSON.stringify({ runId: pack.runId, status: report.status, cases: report.cases.length,
    accessibilityChecks: report.accessibility.length, modelRequests: report.modelRequests, report: folder + '/report.json' }, null, 2));
}
