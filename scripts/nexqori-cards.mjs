// Dedicated card journey. Credentials and screenshots stay local.
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { strict as assert } from 'node:assert';
const credentials = parseEnv(readFileSync('.env', 'utf8'));
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
const page = await context.newPage(); const errors = []; page.on('pageerror', e => errors.push(e.message));
const result = { checks: [], accessibility: [] }; mkdirSync('.local/verification', { recursive: true });
async function choose(lang) { await page.locator('.language-trigger').click(); await page.locator('[data-locale="' + lang + '"]').click(); await page.waitForFunction(lang => document.documentElement.lang === lang, lang); }
async function reveal() { await page.getByRole('button', {name:'Ver datos de la tarjeta',exact:true}).click(); await page.getByLabel('Contraseña', {exact:true}).fill(credentials.CUSTOMER_PASSWORD); await page.getByRole('dialog').getByRole('button',{name:'Ver datos de la tarjeta',exact:true}).click(); await page.waitForFunction(() => /^\d{3}$/.test(document.querySelector('[data-testid="card-cvv"]')?.textContent || '')); }
try {
  await page.goto('http://localhost:5180'); await page.getByLabel('Correo electrónico', {exact:true}).fill('andrea@nexqori.com'); await page.getByLabel('Contraseña', {exact:true}).fill(credentials.CUSTOMER_PASSWORD); await page.getByRole('button', {name:'Entrar a mi espacio'}).click(); await page.locator('.assistant-panel').waitFor();
  await page.goto('http://localhost:5180/cards'); await page.locator('.bank-card').waitFor();
  for (const lang of ['es','en','pt']) {
    await choose(lang);
    for (const width of [1512,390]) {
      await page.setViewportSize({width,height:1050});
      assert.equal(await page.getByTestId('card-cvv').innerText(),'•••');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
      const a = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      result.accessibility.push({lang,width,violations:a.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
      await page.screenshot({path:`.local/verification/cards-${lang}-${width}.png`,fullPage:true});
    }
  }
  await choose('es'); await page.setViewportSize({width:1512,height:1050});
  await reveal(); assert.equal((await page.locator('.card-number').innerText()).replaceAll(' ',''),'0000000000008942');
  await page.evaluate(() => window.dispatchEvent(new Event('blur'))); assert.equal(await page.getByTestId('card-cvv').innerText(),'•••');
  result.checks.push('owned card, three languages, two widths, password reveal and blur concealment');
  await page.clock.install(); await reveal(); await page.clock.runFor(61000);
  assert.equal(await page.getByTestId('card-cvv').innerText(),'•••'); result.checks.push('automatic 60-second concealment');
  assert.deepEqual(await page.evaluate(() => Object.keys(localStorage)),['nexqori-language']);
  await page.goto('http://localhost:5180/products?kind=cards'); await page.locator('.bank-card').waitFor(); assert.equal(await page.getByTestId('card-cvv').innerText(),'•••'); result.checks.push('existing assistant destination opens cards masked');
  writeFileSync('.local/verification/cards.json',JSON.stringify(result,null,2));
  assert.deepEqual(errors,[]); assert.ok(result.accessibility.every(a=>a.violations.length===0));
  writeFileSync('.local/verification/cards.json',JSON.stringify(result,null,2)); console.log(JSON.stringify(result));
} finally { await browser.close(); }
