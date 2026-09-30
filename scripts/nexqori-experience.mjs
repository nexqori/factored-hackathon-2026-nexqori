// Browser contracts for conversations, settings in the banking workspace.
import { chromium } from '@playwright/test';
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
const result = { accessibility: [], checks: [] };
const shot = name => page.screenshot({ path: output + '/' + name + '.png', fullPage: true });
async function axe(name) { const r = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze(); result.accessibility.push({ name, violations: r.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })) }); }
async function choose(locale) { await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + locale + '"]').click(); await page.waitForFunction(locale => document.documentElement.lang === locale, locale); }
async function send(text) { await page.locator('.paste-composer textarea').fill(text); await page.locator('.paste-entry button').click(); await page.locator('.chat-bubble.user').getByText(text, { exact: true }).waitFor(); await page.waitForFunction(() => !document.querySelector('.paste-composer textarea').disabled); }
try {
  await page.goto(origin);
  await page.locator('.language-trigger').click();
  await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.documentElement.lang === 'en');
  await choose('es');
  await page.getByRole('radio', { name: 'Documento', exact: true }).check();
  await page.getByLabel('Número de identidad').fill('00000001');
  await page.getByLabel('Contraseña', { exact: true }).fill(credentials.CUSTOMER_PASSWORD);
  await page.getByRole('button', { name: 'Mostrar contraseña' }).click();
  assert.equal(await page.getByLabel('Contraseña', { exact: true }).getAttribute('type'), 'text');
  await page.getByRole('button', { name: 'Ocultar contraseña' }).click();
  await axe('document-login'); await shot('login-document');
  await page.getByRole('button', { name: 'Entrar a mi espacio' }).click();
  await page.getByRole('heading', { name: 'Qué bueno tenerte aquí.' }).waitFor();
  assert.equal(await page.locator('.chat-bubble').count(), 0);
  assert.equal(await page.locator('.text-size').count(), 0);
  assert.ok(await page.locator('.bot-avatar').first().evaluate(image => image.complete && image.naturalWidth > 0));
  const stamp = Date.now();
  const first = 'Verificación de conversación A ' + stamp, second = 'Verificación de conversación B ' + stamp;
  await send(first);
  await page.getByRole('button', { name: 'Nueva', exact: true }).click();
  assert.equal(await page.locator('.chat-bubble').count(), 0);
  await send(second);
  assert.equal(await page.locator('.chat-bubble').filter({ hasText: first }).count(), 0);
  await page.getByRole('button', { name: 'Conversaciones', exact: true }).click();
  await page.locator('.conversation-list button').filter({ hasText: first }).click();
  await page.locator('.chat-bubble').filter({ hasText: first }).waitFor();
  assert.equal(await page.locator('.chat-bubble').filter({ hasText: second }).count(), 0);
  await page.getByRole('button', { name: 'Conversaciones', exact: true }).click(); await axe('conversation-history'); await shot('conversation-history');
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click();
  result.checks.push('new conversation, resume, isolated history, reload starts empty');
  await page.reload(); await page.locator('.assistant-panel').waitFor(); assert.equal(await page.locator('.chat-bubble').count(), 0);
  await page.getByRole('link', { name: 'Configuración', exact: true }).click();
  for (const [name,size] of [['Pequeña','small'],['Grande','large'],['Mediana','medium']]) {
    await page.getByRole('radio', { name, exact: true }).check();
    await page.waitForFunction(size => document.documentElement.dataset.textSize === size, size);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  }
  await page.getByRole('radio', { name: 'Grande', exact: true }).check();
  await page.waitForFunction(() => document.documentElement.dataset.textSize === 'large');
  await page.reload(); await page.getByRole('heading', { name: 'Configuración', exact: true }).waitFor();
  assert.equal(await page.locator('html').getAttribute('data-text-size'), 'large');
  await page.getByRole('radio', { name: 'Mediana', exact: true }).check();
  await page.waitForFunction(() => document.documentElement.dataset.textSize === 'medium');
  await axe('settings'); await shot('settings-desktop'); result.checks.push('reading sizes persist in profile');
  await page.goto(origin); await page.locator('.assistant-panel').waitFor();
  await page.locator('.language-trigger').click(); await axe('language-menu'); await shot('language-menu'); await page.keyboard.press('Escape');
  assert.ok(await page.locator('.language-trigger').evaluate(el => el === document.activeElement));
  assert.equal(await page.locator('.call-launch, .voice-call').count(), 0);
  await page.setViewportSize({width:390,height:844}); await shot('assistant-mobile'); await axe('assistant-mobile');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.goto(origin+'/settings'); await page.locator('.size-options').waitFor();
  for (const locale of ['es','en','pt']) {
    await choose(locale);
    for (const size of ['small','medium','large']) {
      await page.locator('input[name="textSize"][value="'+size+'"]').check();
      await page.waitForFunction(size => document.documentElement.dataset.textSize === size, size);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), locale+' '+size+' mobile overflow');
    }
  }
  await choose('es'); await page.locator('input[name="textSize"][value="medium"]').check();
  await page.waitForFunction(() => document.documentElement.dataset.textSize === 'medium');
  result.checks.push('mobile reading settings: ES/EN/PT × small/medium/large');
  assert.deepEqual(errors, []); assert.ok(result.accessibility.every(check => check.violations.length === 0), JSON.stringify(result.accessibility));
  writeFileSync(output+'/experience-results.json',JSON.stringify(result,null,2)); console.log(JSON.stringify(result,null,2));
} finally { await browser.close(); }
