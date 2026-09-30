import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
const out = '.local/intent-lab/verification';
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await context.newPage();
const errors = [], network = [], checks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:5190/')) network.push(r.url()); });
await page.goto('http://127.0.0.1:5190/');
await page.getByRole('heading', { name: 'Evaluar conversaciones' }).waitFor();
await page.screenshot({ path: `${out}/walkthrough-desktop.png`, fullPage: true });
if (await page.getByText('/services/catalog/unrecognized-charge', { exact: true }).count() !== 1) throw new Error('Claim route missing');
for (const scenario of ['unknown', 'duplicate', 'app', 'branch', 'quality']) {
  await page.locator('#case').selectOption(scenario);
  if (!await page.locator('.next-action code').count()) throw new Error('Scenario route missing');
  checks.push(`case:${scenario}`);
}
for (const condition of ['Desacuerdo', 'Falla un modelo', 'Falta información']) {
  await page.getByRole('button', { name: condition, exact: true }).click();
  if (await page.locator('.next-action code').count()) throw new Error('Unsafe reference proposes route');
}
await page.getByRole('button', { name: 'Acuerdo', exact: true }).click();
await page.locator('#customer-message').fill('Un texto nuevo sin etiqueta revisada');
if (await page.locator('.next-action code').count()) throw new Error('Edited case reused gold label');
await page.getByRole('button', { name: 'Restablecer caso' }).click();
await page.locator('.prompt-editor > summary').click();
await page.locator('#instructions').fill('Test instruction v2. Classify only.');
await page.getByRole('button', { name: 'Ver entrada a los modelos' }).click();
await page.locator('.payload pre').waitFor();
const payload = JSON.parse(await page.locator('.payload pre').innerText());
if (payload.jev.questions.intent.instructions !== payload.llm.instructions) throw new Error('Different criteria');
if (payload.status !== 'not_sent') throw new Error('Provider unexpectedly called');
if (payload.jev.state.messages.length !== 5) throw new Error('Conversation context lost');
const persisted = (await (await page.request.get('http://127.0.0.1:5190/lab-api/conversations')).json()).conversations;
const previous = persisted.find(c => c.title === 'Verificación · conversación LAB');
if (previous) await page.locator('#case').selectOption(previous.id);
else await page.getByRole('button', {name:'Nueva conversación',exact:true}).click();
await page.locator('#conversation-title').fill('Verificación · conversación LAB');
await page.locator('#message-0').fill('Verificación: mi pago ya se envió, pero sigue pendiente.');
await page.locator('#expected-intent').selectOption('payment-status');
await page.getByRole('button',{name:'Guardar conversación',exact:true}).click();
await page.getByText('Guardado en JSON local',{exact:true}).waitFor();
const saved = (await (await page.request.get('http://127.0.0.1:5190/lab-api/conversations')).json()).conversations.find(c=>c.title==='Verificación · conversación LAB');
if (!saved || saved.messages[0].content !== 'Verificación: mi pago ya se envió, pero sigue pendiente.') throw new Error('JSON persistence failed');
await page.reload();
await page.locator('#case').selectOption(saved.id);
if (await page.locator('#message-0').inputValue() !== saved.messages[0].content) throw new Error('Saved conversation not restored');
const customAxe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
const downloadPromise = page.waitForEvent('download');
await page.getByRole('button',{name:'Descargar conversaciones',exact:true}).click();
const downloaded = await downloadPromise;
await downloaded.saveAs(`${out}/conversations-export.json`);
const exported = JSON.parse(await fs.readFile(`${out}/conversations-export.json`,'utf8'));
if (exported.conversations.length < 6) throw new Error('Missing builtin or saved conversations in export');
await page.locator('#case').selectOption('unknown');
const axeReports = [{lang:'es',tab:'custom',violations:customAxe.violations}];
for (const [lang, tabNames] of [['es', ['Conversaciones','Benchmark','Problemas del dataset']], ['en', ['Conversations','Benchmark','Dataset problems']], ['pt', ['Conversas','Benchmark','Problemas do dataset']]]) {
  const names = {es:'Español',en:'English',pt:'Português'};
  await page.locator('.language summary').click();
  await page.getByRole('button', { name: names[lang], exact: true }).click();
  for (const tab of tabNames) {
    await page.getByRole('button', { name: tab, exact: true }).click();
    const report = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    axeReports.push({lang,tab,violations:report.violations});
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Desktop overflow');
    checks.push(`${lang}:${tab}`);
  }
}
await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
await page.getByRole('button', { name: 'Executar benchmark NLP' }).click();
await page.getByRole('button', { name: 'Baixar resultados' }).waitFor();
await page.screenshot({ path: `${out}/benchmark.png`, fullPage: true });
await page.getByRole('button', { name: 'Conversas', exact: true }).click();
await page.setViewportSize({ width: 390, height: 844 });
if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Mobile overflow');
await page.screenshot({ path: `${out}/walkthrough-mobile.png`, fullPage: true });
axeReports.push({lang:'pt',tab:'mobile',violations:(await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations});
await fs.writeFile(`${out}/ui.json`, JSON.stringify({checks,errors,network,axeReports},null,2));
await browser.close();
const violations = axeReports.flatMap(r=>r.violations);
if(errors.length || network.length || violations.length) { console.log(JSON.stringify({errors,network,violations})); process.exit(1); }
console.log(JSON.stringify({checks:checks.length,axe:axeReports.length,errors:0,externalRequests:0}));
