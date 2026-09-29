// Catalog discovery, review and persisted requests against Docker/PostgreSQL.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { strict as assert } from 'node:assert';

const credentials = parseEnv(readFileSync('.env', 'utf8'));
const origin = process.env.NEXQORI_URL || 'http://localhost:5180';
const output = '.local/verification'; mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 }, locale: 'es-MX' });
const page = await context.newPage(); const errors = []; page.on('pageerror', e => errors.push(e.message));
const result = { checks: [], accessibility: [], pages: [] };
async function ready() { await page.locator('[data-catalog-ready="true"]').waitFor(); }
async function search(value) { await page.locator('.catalog-search input').fill(value); await page.waitForTimeout(250); await ready(); }
async function choose(locale) { await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click(); await page.waitForFunction(value => document.documentElement.lang === value, locale); }
async function axe(name) { const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze(); result.accessibility.push({ name, violations: report.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })) }); }
async function snapshot(name) { await page.screenshot({ path: output + '/' + name + '.png', fullPage: true }); }
async function noOverflow() { assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), page.url() + ' overflow'); }
async function login(email, password) {
  await page.goto(origin); await page.getByLabel('Correo electrónico').fill(email);
  await page.getByLabel('Contraseña', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Entrar a mi espacio' }).click();
  await page.locator('.sidebar').waitFor();
}
try {
  await login('andrea@nexqori.com', credentials.CUSTOMER_PASSWORD);
  const before = (await (await page.request.get(origin + '/api/bootstrap')).json()).products;
  await page.goto(origin + '/services'); await ready();
  await expect(page.locator('.catalog-card')).toHaveCount(20);
  await axe('catalog-desktop'); await snapshot('services-catalog-desktop');
  await search('pagar celular'); assert.equal(await page.locator('.catalog-card').count(), 1);
  await page.locator('[data-service-id="phone-bill"]').waitFor(); await snapshot('services-search-phone');
  await search('Empresa Telefonica'); assert.equal(await page.locator('.catalog-card').count(), 1);
  await search('xyz proveedor inexistente'); assert.equal(await page.locator('.catalog-card').count(), 0);
  await page.getByRole('button', { name: 'Ver todos los servicios' }).click(); await ready();
  await expect(page.locator('.catalog-card')).toHaveCount(20);
  await page.locator('.catalog-categories button').filter({ hasText: 'Préstamos' }).click(); await ready();
  await expect(page.locator('.catalog-card')).toHaveCount(2);
  await page.goto(origin + '/services/catalog/phone-bill');
  await page.getByLabel('Número de celular o teléfono', { exact: true }).fill('5512345678');
  await page.getByRole('textbox', { name: 'Importe MXN', exact: true }).fill('459,90');
  await page.getByLabel('Nota adicional (opcional)').fill('UI verification: catálogo de telefonía ' + Date.now());
  await page.getByRole('button', { name: 'Revisar datos', exact: true }).click();
  await page.getByRole('heading', { name: 'Revisa antes de confirmar' }).waitFor();
  assert.match(await page.locator('.service-review-amount').textContent(), /459[.,]90/);
  await axe('service-review'); await snapshot('service-phone-review');
  await page.getByRole('button', { name: 'Editar datos' }).click();
  assert.equal(await page.getByLabel('Número de celular o teléfono', { exact: true }).inputValue(), '5512345678');
  await page.getByRole('button', { name: 'Revisar datos', exact: true }).click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Confirmar solicitud', exact: true }).click();
  await page.getByRole('heading', { name: 'Tu solicitud está registrada' }).waitFor();
  const id = await page.locator('.service-success .case-reference').textContent(); result.requestId = id;
  await snapshot('service-request-receipt');
  await page.goto(origin + '/requests');
  await page.locator('.case-card').filter({ hasText: id }).click();
  await page.locator('dialog').waitFor();
  assert.match(await page.locator('dialog').textContent(), /Empresa Telefónica/);
  assert.match(await page.locator('dialog').textContent(), /5512345678/);
  await axe('service-request-history'); await snapshot('service-history-details');
  assert.deepEqual((await (await page.request.get(origin + '/api/bootstrap')).json()).products, before);
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click();
  result.checks.push('natural and provider search, empty state, category filter, review/edit/confirm, persisted details, no debit');
  for (const [locale, query, heading] of [['es', 'pagar celular', 'Pagar celular o teléfono'], ['en', 'pay phone bill', 'Pay a phone bill'], ['pt', 'pagar celular', 'Pagar celular ou telefone']]) {
    await choose(locale); await page.goto(origin + '/services'); await ready(); await search(query);
    assert.equal(await page.locator('.catalog-card').count(), 1);
    await page.locator('[data-service-id="phone-bill"]').click(); await page.getByRole('heading', { name: heading, exact: true }).waitFor();
    await axe('service-form-' + locale); await noOverflow();
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 900 }); await noOverflow();
      result.pages.push({ locale, width, route: 'phone-bill' });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(origin + '/services'); await ready(); await noOverflow(); await snapshot('services-mobile-' + locale);
    await axe('catalog-mobile-' + locale);
  }
  await page.setViewportSize({ width: 1512, height: 1050 }); await choose('es');
  for (const service of ['internet-bill', 'tv-bill', 'utilities-bill', 'bank-transfer', 'personal-loan', 'mortgage', 'unrecognized-charge', 'incorrect-charge', 'payment-status', 'app-support', 'cash-deposit']) {
    await page.goto(origin + '/services/catalog/' + service); await page.locator('.service-operation form').waitFor(); await noOverflow();
    result.pages.push({ locale: 'es', width: 1512, route: service });
  }
  await page.goto(origin); await page.locator('.chat-composer input').fill('quiero pagar celular'); await page.locator('.chat-composer button').click();
  await page.waitForURL(origin + '/services/catalog/phone-bill');
  await page.getByRole('heading', { name: 'Pagar celular o teléfono', exact: true }).waitFor();
  result.checks.push('specific service navigation from assistant; ES/EN/PT and responsive forms');
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  await login('admin@nexqori.com', credentials.ADMIN_PASSWORD);
  await page.locator('.case-card').filter({ hasText: id }).click();
  await page.locator('dialog').waitFor(); assert.match(await page.locator('dialog').textContent(), /Empresa Telefónica/);
  result.checks.push('admin receives the selected service and structured details');
  assert.deepEqual(errors, []);
  assert.ok(result.accessibility.every(check => !check.violations.length), JSON.stringify(result.accessibility));
  writeFileSync(output + '/services-results.json', JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2));
} finally { await browser.close(); }
