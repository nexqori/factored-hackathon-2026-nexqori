// Reproducible frontend operations, fresh local PostgreSQL fixtures and evidence.
// No provider keys, no reset of existing accounts, no credentials in console/report.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { strict as assert } from 'node:assert';
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { randomUUID } from 'node:crypto';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
if (args.includes('--help')) {
  console.log('npm run test:cases [-- --headed] [-- --locale=es|en|pt]\nnpm run test:cases:prepare [-- --locale=es|en|pt]');
  process.exit(0);
}
assert(args.every(a => ['--prepare', '--headed'].includes(a) || /^--locale=(es|en|pt)$/.test(a)), 'Unknown argument; use --help');
assert(args.filter(a => a.startsWith('--locale=')).length <= 1, 'Choose one locale or omit it to test all three');
const prepareOnly = args.includes('--prepare');
const localeArg = args.find(a => a.startsWith('--locale='))?.split('=')[1];
const languages = localeArg ? [localeArg] : prepareOnly ? ['es'] : ['es', 'en', 'pt'];
const origin = (process.env.NEXQORI_URL || 'http://localhost:5180').replace(/\/$/, '');
assert(['http://localhost:5180', 'http://127.0.0.1:5180'].includes(origin), 'Only local Nexqori Compose on port 5180 is supported');
const definitions = JSON.parse(readFileSync(join(root, 'tests/scenarios/banking-cases.json'), 'utf8'));
const strings = Object.fromEntries(['es', 'en', 'pt'].map(locale => [locale, JSON.parse(readFileSync(join(root, `src/locales/${locale}.json`), 'utf8'))]));
const t = (locale, key) => { assert.equal(typeof strings[locale][key], 'string', `Missing ${locale}/${key}`); return strings[locale][key]; };
const outputRoot = join(root, '.local/verification/cases');
mkdirSync(outputRoot, { recursive: true });

function database(input) {
  const result = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1', '-e',
    'NEXQORI_CASES_INPUT=' + Buffer.from(JSON.stringify(input)).toString('base64'), 'api', 'python', '-'], {
    cwd: root, encoding: 'utf8', input: readFileSync(join(root, 'scripts/banking-cases-fixtures.py'), 'utf8'),
    timeout: 120000, maxBuffer: 4 * 1024 * 1024, windowsHide: true,
  });
  // stdout may contain fresh passwords. Never echo it, even on parse failures.
  if (result.error || result.status !== 0) {
    const log = join(outputRoot, `database-error-${Date.now()}.private.log`);
    writeFileSync(log, result.stderr || String(result.error || 'No diagnostic output'), { mode: 0o600 });
    throw new Error(`Fixture/verification failed (${result.status ?? result.error?.code}). Private diagnostic: ${log}`);
  }
  try { return JSON.parse(result.stdout); } catch { throw new Error('Invalid fixture output; stdout suppressed because it may contain credentials.'); }
}

function savePack(pack, purpose) {
  const output = join(outputRoot, `${purpose}-${pack.runId}`);
  mkdirSync(output, { recursive: true });
  writeFileSync(join(output, 'credentials.private.json'), JSON.stringify(pack, null, 2), { mode: 0o600 });
  const accounts = [...pack.cases.map(c => `| ${c.id} (${c.locale}) | ${c.email} | ${c.password} |`),
    `| Administrador de verificación | ${pack.admin.email} | ${pack.admin.password} |`];
  const manual = `# Accesos privados — ${pack.runId}

Paquete ${purpose === 'manual' ? 'nuevo, sin acciones ejecutadas' : 'utilizado por la prueba automática'}. Creado ${pack.createdAt}.

Banco: [abrir Nexqori](${origin}). Usa otra ventana/perfil para el administrador.
Guía compartible: [tres casos](../../../../docs/pruebas-tres-casos.md).

| Perfil | Correo | Contraseña |
| --- | --- | --- |
${accounts.join('\n')}

${pack.cases.map(c => `## ${c.title} (${c.locale})

- Movimiento: \`${c.transactionId}\`; tarjeta terminada en ${c.last4}.
- Saldo inicial: ${(c.initialBalanceMinor / 100).toFixed(2)} MXN.
- Contrato esperado: \`${c.intent}\`.
- Texto para el formulario o para una prueba separada del LAB: ${c.messages[c.locale]}
- Resultado esperado: ${c.expected}
`).join('\n')}

Los folios NQ, operaciones RF y abonos CR se generan al actuar, no al preparar.
Este archivo contiene contraseñas locales y permanece ignorado por Git. No compartir.
Las cuentas del paquete son persistentes; para volver a empezar ejecuta npm run test:cases:prepare.
`;
  writeFileSync(join(output, 'INICIAR.private.md'), manual, { mode: 0o600 });
  return output;
}

const health = await fetch(origin + '/api/health', { signal: AbortSignal.timeout(10000) }).catch(() => null);
assert(health?.ok, 'El banco no responde. Ejecuta npm run docker:up y vuelve a intentar.');
const pack = database({ mode: 'prepare', languages, definitions: definitions.cases });
const output = savePack(pack, prepareOnly ? 'manual' : 'run');
if (prepareOnly) {
  writeFileSync(join(outputRoot, 'latest-manual.json'), JSON.stringify({ runId: pack.runId, path: output, guide: join(output, 'INICIAR.private.md') }, null, 2));
  console.log(`Tres casos nuevos listos. Accesos privados y pasos: ${join(output, 'INICIAR.private.md')}`);
  process.exit(0);
}

const report = { schemaVersion: 1, runId: pack.runId, startedAt: new Date().toISOString(), status: 'running',
  scope: 'Acciones locales en frontend + API de control + PostgreSQL; sin Jev/LLM ni procesadores externos.',
  timingScope: 'Tiempos de navegador automatizado local, no latencia de modelos ni SLA bancario.',
  languages, cases: [], accessibility: [], consoleErrors: [], database: null };
const secrets = [pack.admin.password, ...pack.cases.map(c => c.password)];
function redact(value) { let text = String(value); for (const secret of secrets) text = text.replaceAll(secret, '[REDACTED]'); return text; }
let browser;
let currentCase;
const totalStart = performance.now();
const contextOptions = { viewport: { width: 1512, height: 1050 }, locale: 'es-MX' };
async function createPage() {
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => report.consoleErrors.push(redact(error.message)));
  return page;
}
async function step(name, work) {
  const start = performance.now();
  try { const value = await work(); currentCase.steps.push({ name, status: 'passed', ms: Math.round(performance.now() - start) }); return value; }
  catch (error) { currentCase.steps.push({ name, status: 'failed', ms: Math.round(performance.now() - start) }); throw error; }
}
async function choose(page, locale) {
  await page.locator('.language-trigger').click();
  await page.locator(`[data-locale="${locale}"]`).click();
  await expect(page.locator('html')).toHaveAttribute('lang', locale);
}
async function login(page, account, locale) {
  await page.goto(origin);
  await choose(page, locale);
  await page.getByLabel(t(locale, 'email'), { exact: true }).fill(account.email);
  await page.getByLabel(t(locale, 'password'), { exact: true }).fill(account.password);
  await page.getByRole('button', { name: t(locale, 'signIn'), exact: true }).click();
  await page.locator('.workspace').waitFor();
}
async function get(page, path) {
  const response = await page.request.get(origin + '/api' + path);
  assert.equal(response.status(), 200, `GET ${path}`);
  return response.json();
}
async function controlledPost(page, path, body) {
  const session = await get(page, '/session');
  return page.request.post(origin + '/api' + path, { data: body, headers: { Origin: origin, 'X-CSRF-Token': session.csrfToken } });
}
async function snapshot(page, name, scope) {
  const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const violations = scan.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) }));
  report.accessibility.push({ name, violations });
  assert.deepEqual(violations, [], `Accessibility: ${name}`);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Horizontal overflow: ${name}`);
  const filename = name + '.png';
  if (scope) await page.locator(scope).screenshot({ path: join(output, filename) });
  else await page.screenshot({ path: join(output, filename), fullPage: true });
  currentCase.screenshots.push(filename);
}
async function askMovement(page, fixture) {
  await page.goto(origin + '/movements');
  await page.locator(`[data-transaction-id="${fixture.transactionId}"]`).click();
  await page.getByRole('button', { name: t(fixture.locale, 'askTransaction'), exact: true }).click();
  await expect(page.locator('.transaction-context code')).toHaveText(fixture.transactionId);
  const reply = page.locator('.chat-bubble.assistant').last();
  await expect(reply).toContainText(fixture.transactionId);
  return reply;
}
async function createClaim(page, fixture) {
  const locale = fixture.locale;
  await page.goto(origin + '/services/catalog/' + fixture.intent);
  await page.locator('.service-operation form').waitFor();
  await page.getByRole('combobox', { name: t(locale, 'chooseTransaction'), exact: true }).selectOption(fixture.transactionId);
  await page.getByLabel(t(locale, 'detailLabel'), { exact: true }).fill(fixture.messages[locale]);
  await page.getByRole('button', { name: t(locale, 'catalogReview'), exact: true }).click();
  await expect(page.locator('.service-operation')).toContainText(fixture.transactionId);
  await page.getByRole('checkbox', { name: t(locale, 'catalogConfirmCheck'), exact: true }).check();
  await page.getByRole('button', { name: t(locale, 'catalogConfirm'), exact: true }).click();
  await page.getByRole('heading', { name: t(locale, 'catalogReceived'), exact: true }).waitFor();
  const requestId = (await page.locator('.service-success .case-reference').textContent()).trim();
  assert.match(requestId, /^NQ-/);
  return requestId;
}
async function openClaim(page, id, admin = false) {
  await page.goto(origin + (admin ? '/admin' : '/requests'));
  await page.locator('.case-card').filter({ hasText: id }).click();
  await expect(page.getByRole('dialog')).toContainText(id);
}
async function closeDialog(page, locale) {
  await page.getByRole('dialog').getByRole('button', { name: t(locale, 'close'), exact: true }).click();
}
async function money(page, fixture, expected, credits = 0) {
  const state = await get(page, '/bootstrap');
  assert.equal(state.products.find(p => p.id === fixture.accountId).balanceMinor, expected);
  assert.equal(state.transactions.filter(tx => tx.category === 'refund').length, credits);
  assert.equal(state.transactions.find(tx => tx.id === fixture.transactionId).status, fixture.transactionStatus);
  return state;
}
async function auditUI(operator, fixture, action) {
  const locale = fixture.locale;
  await operator.goto(origin + '/admin');
  const panel = operator.locator('.audit-panel');
  await panel.getByRole('combobox', { name: t(locale, 'customer'), exact: true }).selectOption(fixture.userId);
  await panel.getByRole('combobox', { name: t(locale, 'auditAction'), exact: true }).selectOption(action);
  await expect(panel.locator('tbody tr')).toHaveCount(1);
  await expect(panel.locator('tbody')).toContainText(t(locale, 'auditActions.' + action));
  await expect(panel.locator('tbody')).toContainText(action === 'refund_approved' ? pack.admin.name : fixture.name);
  await snapshot(operator, `${fixture.id}-${locale}-auditoria`, '.audit-panel');
  await panel.getByRole('combobox', { name: t(locale, 'auditAction'), exact: true }).selectOption('transaction_context_viewed');
  await expect(panel.locator('tbody tr')).toHaveCount(2);
  await panel.getByRole('button', { name: t(locale, 'viewConversation'), exact: true }).first().click();
  await expect(operator.locator('.audit-conversation')).toContainText(fixture.transactionId);
  await closeDialog(operator, locale);
}

try {
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: !args.includes('--headed'), slowMo: args.includes('--headed') ? 100 : 0 });
  const operator = await createPage();
  await login(operator, pack.admin, 'es');
  for (const fixture of pack.cases) {
    const start = performance.now();
    const { locale } = fixture;
    currentCase = { id: fixture.id, locale, title: fixture.title, expectedIntent: fixture.intent, status: 'running',
      expected: fixture.expected, transactionId: fixture.transactionId, steps: [], screenshots: [] };
    report.cases.push(currentCase);
    console.log(`Ejecutando ${fixture.id} (${locale})…`);
    const page = await createPage();
    await choose(operator, locale);
    await step('inicio de sesión del titular', () => login(page, fixture, locale));
    await step('consulta del movimiento propio en el bot', async () => {
      await askMovement(page, fixture);
      await money(page, fixture, fixture.initialBalanceMinor);
    });
    currentCase.requestId = await step('contrato → revisión → confirmación → folio', () => createClaim(page, fixture));
    const requestId = currentCase.requestId;
    if (fixture.id === 'bloqueo') {
      await step('bloqueo confirmado desde Tarjetas', async () => {
        await page.goto(origin + '/cards');
        await page.getByRole('button', { name: t(locale, 'blockCard'), exact: true }).click();
        await expect(page.getByRole('button', { name: t(locale, 'confirmBlockCard'), exact: true })).toBeDisabled();
        await page.getByRole('dialog').getByLabel(t(locale, 'password'), { exact: true }).fill(fixture.password);
        await page.getByRole('checkbox', { name: t(locale, 'blockCardConfirm'), exact: true }).check();
        await page.getByRole('button', { name: t(locale, 'confirmBlockCard'), exact: true }).click();
        await page.locator('.card-blocked-label').waitFor();
        await page.reload();
        await page.locator('.card-blocked-label').waitFor();
        await expect(page.getByRole('button', { name: t(locale, 'showCardDetails'), exact: true })).toBeDisabled();
        await snapshot(page, `bloqueo-${locale}-tarjeta`);
        await money(page, fixture, fixture.initialBalanceMinor);
      });
      await step('servidor rechaza revelar la tarjeta bloqueada', async () => {
        const denied = await controlledPost(page, '/cards/' + fixture.cardId + '/reveal', { password: fixture.password });
        assert.equal(denied.status(), 409);
        assert.equal((await denied.json()).error, 'card_blocked');
      });
    } else if (fixture.id === 'devolucion') {
      await step('solicitud RF pendiente sin abono', async () => {
        await openClaim(page, requestId);
        await page.locator('.refund-panel .refund-summary').waitFor();
        await expect(page.getByRole('button', { name: t(locale, 'refundRequest'), exact: true })).toBeDisabled();
        await page.getByRole('checkbox', { name: t(locale, 'refundConfirmRequest'), exact: true }).check();
        await page.getByRole('button', { name: t(locale, 'refundRequest'), exact: true }).click();
        await expect(page.locator('.refund-panel')).toContainText(t(locale, 'refundStatus.pending'));
        const state = await money(page, fixture, fixture.initialBalanceMinor);
        currentCase.operationId = state.requests.find(r => r.id === requestId).refund.id;
        assert.match(currentCase.operationId, /^RF-/);
        await snapshot(page, `devolucion-${locale}-pendiente`);
      });
      await step('administrador inicia revisión y aprueba desde frontend', async () => {
        await openClaim(operator, requestId, true);
        await operator.getByRole('button', { name: t(locale, 'startReview'), exact: true }).click();
        await operator.getByRole('dialog').getByRole('button', { name: t(locale, 'startReview'), exact: true }).click();
        await expect(operator.locator('.refund-panel')).toContainText(t(locale, 'refundStatus.pending'));
        assert.equal((await get(operator, '/admin/overview')).requests.find(r => r.id === requestId).status, 'in_review');
        await operator.getByLabel(t(locale, 'refundEvidence'), { exact: true }).fill('Verificación: compra cancelada y cargo completado revisados. Se aprueba devolución completa a la cuenta del titular.');
        await operator.getByRole('dialog').getByLabel(t(locale, 'password'), { exact: true }).fill(pack.admin.password);
        await expect(operator.getByRole('button', { name: t(locale, 'refundSaveDecision'), exact: true })).toBeDisabled();
        await operator.getByRole('checkbox', { name: t(locale, 'refundConfirmApprove'), exact: true }).check();
        const sent = operator.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/decision'));
        await operator.getByRole('button', { name: t(locale, 'refundSaveDecision'), exact: true }).click();
        const decision = (await sent).postDataJSON(); // In memory only: includes password and idempotency key.
        await expect(operator.locator('.refund-panel')).toContainText(t(locale, 'refundStatus.approved'));
        const final = await get(operator, '/admin/requests/' + requestId + '/refund');
        currentCase.creditId = final.refund.creditTransactionId;
        assert.match(currentCase.creditId, /^CR-/);
        const repeated = await controlledPost(operator, '/admin/refunds/' + currentCase.operationId + '/decision', decision);
        assert.equal(repeated.status(), 200);
        assert.equal((await repeated.json()).creditTransactionId, currentCase.creditId);
        await closeDialog(operator, locale);
      });
      await step('titular ve un único abono y puede rastrearlo por RF', async () => {
        await openClaim(page, requestId);
        await expect(page.locator('.refund-panel')).toContainText(t(locale, 'refundStatus.approved'));
        await expect(page.locator('.refund-panel')).toContainText(currentCase.creditId);
        await snapshot(page, `devolucion-${locale}-aprobada`);
        await money(page, fixture, fixture.initialBalanceMinor + fixture.amountMinor, 1);
        await closeDialog(page, locale);
        await page.locator('.request-search input').fill(currentCase.operationId);
        await expect(page.locator('.case-card')).toHaveCount(1);
        await expect(page.locator('.case-card')).toContainText(requestId);
      });
    } else {
      await step('pago pendiente sin devolución disponible', async () => {
        await openClaim(page, requestId);
        await expect(page.locator('.refund-panel')).toContainText(t(locale, 'error.refund_not_eligible'));
        await expect(page.getByRole('button', { name: t(locale, 'refundRequest'), exact: true })).toHaveCount(0);
        const denied = await controlledPost(page, '/requests/' + requestId + '/refund', { confirmed: true, requestKey: randomUUID() });
        assert.equal(denied.status(), 409);
        assert.equal((await denied.json()).error, 'refund_not_eligible');
      });
      await step('derivación explícita y persistente desde frontend', async () => {
        await page.getByRole('button', { name: t(locale, 'handoff'), exact: true }).click();
        await page.getByRole('button', { name: t(locale, 'confirmHandoff'), exact: true }).click();
        await expect(page.getByRole('dialog')).toContainText(t(locale, 'handed_off'));
        await openClaim(page, requestId);
        await expect(page.getByRole('dialog')).toContainText(t(locale, 'handed_off'));
        await snapshot(page, `derivacion-${locale}-atencion`);
        await money(page, fixture, fixture.initialBalanceMinor);
      });
    }
    await step('seguimiento actualizado y conversación recuperada', async () => {
      const reply = await askMovement(page, fixture);
      await expect(reply).toContainText(requestId);
      if (currentCase.creditId) { await expect(reply).toContainText(currentCase.operationId); await expect(reply).toContainText(currentCase.creditId); }
      await page.reload();
      await page.getByRole('button', { name: t(locale, 'conversations'), exact: true }).click();
      await page.locator('.conversation-list button').first().click();
      await expect(page.locator('.transaction-context code')).toHaveText(fixture.transactionId);
      await expect(page.locator('.chat-bubble.assistant').last()).toContainText(requestId);
      await snapshot(page, `${fixture.id}-${locale}-conversacion`);
    });
    await step('resultado legible en móvil', async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openClaim(page, requestId);
      await snapshot(page, `${fixture.id}-${locale}-movil`);
      await page.setViewportSize(contextOptions.viewport);
    });
    await step('auditoría y conversación visibles al administrador', () => auditUI(operator, fixture,
      fixture.id === 'bloqueo' ? 'card_blocked' : fixture.id === 'devolucion' ? 'refund_approved' : 'handed_off'));
    await step('aislamiento de titular y rol', async () => {
      const other = pack.cases.find(c => c.userId !== fixture.userId);
      const denied = await controlledPost(page, '/cards/' + other.cardId + '/block', { confirmed: true, password: fixture.password, requestKey: randomUUID() });
      assert.equal(denied.status(), 404);
      assert.equal((await page.request.get(origin + '/api/admin/audit')).status(), 403);
    });
    currentCase.status = 'passed'; currentCase.totalMs = Math.round(performance.now() - start);
    await page.context().close();
    console.log(`OK ${fixture.id} (${locale}): ${requestId}`);
  }
  report.database = database({ mode: 'verify', pack: { adminId: pack.admin.userId, untouchedHash: pack.untouchedHash,
    cases: pack.cases.map(({ password, email, name, messages, ...safe }) => safe) } });
  assert.deepEqual(report.consoleErrors, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = redact(error.stack || error);
  if (currentCase?.status === 'running') currentCase.status = 'failed';
  // Do not capture a failure screen: it might still contain a password field.
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  report.finishedAt = new Date().toISOString(); report.totalMs = Math.round(performance.now() - totalStart);
  writeFileSync(join(output, 'report.json'), JSON.stringify(report, null, 2));
  const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const html = `<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Nexqori · tres casos</title>
  <style>body{margin:2rem auto;padding:0 1rem;max-width:1050px;background:#fffcf9;color:#392c27;font:16px/1.6 system-ui}h1,h2{color:#9a4b32}section{background:white;border:1px solid #f2d8c8;border-radius:14px;padding:1.2rem;margin:1rem 0}table{border-collapse:collapse;width:100%}td,th{padding:.5rem;text-align:left;border-bottom:1px solid #f2d8c8}a{color:#9a4b32}code{overflow-wrap:anywhere}img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
  <h1>Nexqori · tres casos bancarios</h1><p><strong>${escape(report.status.toUpperCase())}</strong> · ${escape(pack.runId)} · ${escape(report.finishedAt)}</p>
  <p>${escape(report.scope)}</p><p>${escape(report.timingScope)} Duración total: ${(report.totalMs / 1000).toFixed(1)} s, incluye accesibilidad y capturas.</p>
  <p>${report.cases.filter(c => c.status === 'passed').length}/${pack.cases.length} recorridos completados. ${report.accessibility.length} comprobaciones de accesibilidad. Registros financieros ajenos intactos: ${report.database?.otherFinancialAndCaseRecordsUnchanged === true ? 'verificado' : 'sin verificación final'}.</p>
  ${report.cases.map(c => `<section><h2>${escape(c.title)} · ${c.locale.toUpperCase()} · ${escape(c.status)}</h2><p>${escape(c.expected)}</p><p>Folio: <code>${escape(c.requestId)}</code><br>Operación: <code>${escape(c.operationId || '—')}</code><br>Abono: <code>${escape(c.creditId || '—')}</code></p><table><thead><tr><th>Paso</th><th>Resultado</th><th>Tiempo</th></tr></thead><tbody>${c.steps.map(s => `<tr><td>${escape(s.name)}</td><td>${escape(s.status)}</td><td>${(s.ms / 1000).toFixed(2)} s</td></tr>`).join('')}</tbody></table><p>${c.screenshots.map(s => `<a href="${escape(s)}">${escape(s)}</a>`).join(' · ')}</p><details><summary>Ver resultado</summary>${c.screenshots[0] ? `<img alt="Resultado de ${escape(c.id)}" src="${escape(c.screenshots[0])}">` : ''}</details></section>`).join('')}
  ${report.error ? `<section><h2>Fallo</h2><pre>${escape(report.error)}</pre></section>` : ''}<p><a href="report.json">Informe JSON con tiempos y verificación de PostgreSQL</a></p></html>`;
  writeFileSync(join(output, 'report.html'), html);
  writeFileSync(join(outputRoot, 'latest-run.json'), JSON.stringify({ runId: pack.runId, status: report.status, path: output, report: join(output, 'report.html') }, null, 2));
  console.log(`Resultado: ${report.status}. Informe: ${join(output, 'report.html')}`);
  if (report.error) console.error(report.error);
}
