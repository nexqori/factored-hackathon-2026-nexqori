// Real compiled interface and isolated SQLite bank. No paid providers or manual users.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin = 'http://127.0.0.1:5192';
const root = path.resolve('.local/verification'); await fs.mkdir(root, { recursive: true });
const folder = await fs.mkdtemp(path.join(root, 'attention-'));
assert.equal(await fetch(origin + '/api/health').then(() => true).catch(() => false), false, 'Port 5192 must be free');
const python = process.env.NEXQORI_BANK_PYTHON || path.resolve(process.platform === 'win32' ? '.venv-app/Scripts/python.exe' : '.venv-app/bin/python');
const server = spawn(python, ['-m', 'backend.tests.attention_ui_server'], { env: { ...process.env, BANK_VOICE_ENABLED: 'false', NEXQORI_CHAT_UI_CHECK: '1', NEXQORI_CHAT_UI_DATA: folder }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let diagnostics = '', browser, page; server.stderr.on('data', b => diagnostics += b.toString());
const report = { checks: [], accessibility: [], errors: [] };
async function axe(name) { const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze(); report.accessibility.push({ name, violations: result.violations.map(v => v.id) }); assert.equal(result.violations.length, 0, JSON.stringify(result.violations)); }
async function login(person) {
  const context = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
  const r = await context.request.post(origin + '/api/auth/login', { headers: { Origin: origin }, data: { identifier: person.email, password: person.password } }); assert.equal(r.status(), 200);
  return { context, headers: { Origin: origin, 'X-CSRF-Token': (await r.json()).csrfToken } };
}
try {
  for (let i = 0; i < 150; i++) { if (await fetch(origin + '/api/health').then(r => r.ok).catch(() => false)) break; if (server.exitCode !== null) throw new Error(diagnostics); await new Promise(r => setTimeout(r, 150)); }
  const people = JSON.parse(await fs.readFile(path.join(folder, 'credentials.private.json'), 'utf8'));
  const adminPerson = JSON.parse(await fs.readFile(path.join(folder, 'admin.private.json'), 'utf8'));
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
  const admin = await login(adminPerson);
  for (const [index, locale] of ['es', 'en', 'pt'].entries()) {
    const person = people.find(p => p.locale === locale && p.intent === 'incorrect-charge');
    const copy = JSON.parse(await fs.readFile('src/locales/' + locale + '.json', 'utf8'));
    const customer = await login(person);
    const created = await customer.context.request.post(origin + '/api/requests', { headers: customer.headers, data: { transactionId: person.transactionId, requestKey: crypto.randomUUID(), service: 'cards', reason: 'amount', details: 'Verificación: se revisó una diferencia del cobro.', confirmed: true } }); assert.equal(created.status(), 201);
    const claim = await created.json();
    const chat = await customer.context.request.post(origin + '/api/assistant/flow', { headers: customer.headers, data: { requestKey: crypto.randomUUID(), locale, transactionId: person.transactionId, message: '[incorrect-charge] me cobraron de más' } }); assert.equal(chat.status(), 200); const conversation = (await chat.json()).conversation;
    const before = await (await customer.context.request.get(origin + '/api/bootstrap')).json();
    page = await admin.context.newPage(); page.on('pageerror', e => report.errors.push(e.message));
    await page.goto(origin + '/admin/complaints?case=' + claim.id);
    await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click();
    let panel = page.locator('.claims-detail .attention-review');
    if (await panel.count() === 0) panel = page.locator('.attention-review').first();
    await panel.locator('[data-attention-ready=true]').count();
    await expect(panel).toHaveAttribute('data-attention-ready', 'true');
    await panel.getByLabel(copy['attention.summary'], { exact: true }).fill('Verificación: explicamos el origen del cobro con el recibo del titular.');
    await panel.getByLabel(copy['attention.confirm'], { exact: true }).check();
    await panel.getByRole('button', { name: copy['attention.resolve'], exact: true }).click();
    await expect(panel).toContainText(copy['attention.scheduled']); await axe('admin-' + locale);
    await page.close(); page = await customer.context.newPage(); page.on('pageerror', e => report.errors.push(e.message));
    await page.goto(origin + '/complaints?case=' + claim.id);
    await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click();
    panel = page.locator('.attention-review').first(); await expect(panel).toContainText(copy['attention.scheduled']);
    await panel.getByRole('button', { name: copy['attention.answer'], exact: true }).click();
    await panel.locator('.survey-scale-nps input[value="9"]').check({ force: true });
    await panel.getByLabel(copy['attention.comment'], { exact: true }).fill('Verificación: explicación clara.');
    await panel.getByRole('button', { name: copy['attention.saveDraft'], exact: true }).click();
    await expect(panel).toContainText(copy['attention.saved']); await axe('partial-' + locale);
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); await axe('mobile-' + locale);
    await panel.screenshot({ path: path.join(folder, 'partial-' + locale + '.png') });
    const clock = spawnSync(python, ['-m', 'backend.tests.attention_ui_clock', path.join(folder, 'bank.sqlite'), claim.id], { encoding: 'utf8', windowsHide: true }); assert.equal(clock.status, 0, clock.stderr);
    await page.reload(); panel = page.locator('.attention-review').first(); await expect(panel).toContainText(copy['attention.closed']);
    await expect(panel).toContainText(copy['attention.snapshot.partial']);
    await panel.getByRole('button', { name: copy['attention.answer'], exact: true }).click();
    await expect(panel.locator('.survey-scale-nps input[value="9"]')).toBeChecked();
    await panel.locator('.survey-scale-csat input[value="4"]').check({ force: true });
    await panel.getByRole('button', { name: copy.submitSurvey, exact: true }).click();
    await expect(panel).toContainText(copy.surveyThanks); await axe('submitted-' + locale);
    const saved = await (await customer.context.request.get(origin + '/api/attention/requests/' + claim.id)).json();
    assert.equal(saved.review.snapshots[0].feedback, 'partial'); assert.equal(saved.review.answers.csat, 4);
    const metrics = await (await admin.context.request.get(origin + '/api/admin/overview')).json(); assert.equal(metrics.chatFeedback.nps.responses, index + 1);
    const after = await (await customer.context.request.get(origin + '/api/bootstrap')).json();
    for (const key of ['products', 'transactions', 'requests']) assert.deepEqual(after[key], before[key]);
    await page.setViewportSize({ width: 1512, height: 1050 }); await page.goto(origin);
    await page.getByRole('button', { name: copy.conversations, exact: true }).click();
    await page.locator('.conversation-list button').filter({ hasText: conversation.title }).click();
    await expect.poll(() => page.locator('.chat-bubble').count()).toBeGreaterThan(0);
    const messages = await page.locator('.chat-bubble').count();
    await page.locator('.paste-composer textarea').fill('Borrador conservado');
    await page.locator('.chat-details-button').click(); await page.getByRole('dialog').locator('.attention-review[data-attention-ready=true]').waitFor();
    await page.getByRole('button', { name: copy['chatDetails.back'], exact: true }).click();
    await expect(page.locator('.paste-composer textarea')).toHaveValue('Borrador conservado'); assert.equal(await page.locator('.chat-bubble').count(), messages);
    report.checks.push({ locale, claimId: claim.id, adminResolution: true, partialSaved: true, closureAfter15Minutes: true, lateSubmission: true, bankingDataUnchanged: true, chatPreserved: true });
    await customer.context.close();
  }
  assert.deepEqual(report.errors, []); await fs.writeFile(path.join(folder, 'report.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ folder, ...report }, null, 2));
} catch (error) { if (page && !page.isClosed()) await page.screenshot({ path: path.join(folder, 'failure.png'), fullPage: true }).catch(() => {}); throw error; }
finally { await browser?.close(); server.kill(); await fs.writeFile(path.join(folder, 'server.private.log'), diagnostics); }
