import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { strict as assert } from 'node:assert';
import { verificationUser } from './verification-user.mjs';
const credentials = parseEnv(readFileSync('.env', 'utf8'));
const testUser = verificationUser();
const origin = process.env.NEXQORI_URL || 'http://localhost:5180';
const output = '.local/verification';
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 }, locale: 'es-MX' });
const page = await context.newPage();
// Exercise the guided navigation fallback without spending provider credits.
await page.route('**/api/assistant/capabilities',route=>route.fulfill({json:{connected:false,providers:{}}}));
const pageErrors = [];
page.on('pageerror', error => pageErrors.push(error.message));
const results = { pages: [], accessibility: [], screenshots: [], createdRequest: null, agentNavigation: [], securityHeaders: false };
const snapshot = async name => { const path = output + '/' + name + '.png'; await page.screenshot({ path, fullPage: true }); results.screenshots.push(path); };
async function chooseLanguage(locale) { await page.locator('.language-trigger').click(); await page.locator('[data-locale="'+locale+'"]').click(); }
async function noOverflow() { assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal overflow: ' + page.url()); }
async function axe(name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  results.accessibility.push({ name, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target) })) });
}
try {
  const initialResponse = await page.goto(origin);
  assert.ok(initialResponse.headers()['content-security-policy'].includes("frame-ancestors 'none'"));
  assert.equal(initialResponse.headers()['x-content-type-options'], 'nosniff');
  results.securityHeaders = true;
  await page.getByRole('button', { name: 'Entrar a mi espacio' }).waitFor();
  await snapshot('login-desktop');
  await axe('login');
  await page.getByLabel('Correo electrónico').fill(testUser.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(testUser.password);
  await page.getByRole('button', { name: 'Entrar a mi espacio' }).click();
  await page.getByRole('heading', { name: 'Qué bueno tenerte aquí.' }).waitFor();
  await page.setViewportSize({width:1512,height:780});
  await expect(page.getByRole('button',{name:'Cerrar sesión',exact:true})).toBeInViewport({ratio:1});
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).overflowY),'auto');
  await snapshot('home-short-desktop');
  await page.setViewportSize({width:1512,height:1050});
  await snapshot('home-desktop');
  await axe('home');
  const labels = {
    es: {language:'Idioma', home:'Qué bueno tenerte aquí.', movements:'Movimientos', products:'Mis productos', services:'Servicios', requests:'Mis solicitudes',help:'Siempre hay un siguiente paso.'},
    en: {language:'Language',home:'It’s good to have you here.',movements:'Transactions',products:'My products',services:'Services',requests:'My requests',help:'There’s always a next step.'},
    pt: {language:'Idioma',home:'Que bom ter você aqui.',movements:'Movimentações',products:'Meus produtos',services:'Serviços',requests:'Minhas solicitações',help:'Sempre há um próximo passo.'}
  };
  for (const locale of ['en','pt','es']) {
    await chooseLanguage(locale);
    await page.waitForFunction(language => document.documentElement.lang === language, locale);
    for (const route of ['home','movements','products','services','requests','help']) {
      await page.goto(origin + (route === 'home' ? '/' : '/' + route));
      await page.getByRole('heading',{ name:labels[locale][route],exact:true }).waitFor();
      await noOverflow();
      results.pages.push({locale,route,width:1512});
    }
  }
  const commands = {
    es: [['Llévame a transferencias','/services/transfers'],['Ver tarjetas','/cards'],['Ver mis movimientos','/movements'],['Ver mis solicitudes','/requests']],
    en: [['Open bill payments','/services/payments'],['Show my accounts','/products?kind=accounts']],
    pt: [['Abrir empréstimos','/services/loans'],['Abrir seguros','/services/insurance']]
  };
  for (const [locale, cases] of Object.entries(commands)) {
    await chooseLanguage(locale);
    await page.waitForFunction(language => document.documentElement.lang === language, locale);
    for (const [message, route] of cases) {
      await page.locator('.paste-composer textarea').fill(message);
      await page.locator('.paste-entry button').click();
      await page.waitForURL(origin+route);
      await page.locator('.paste-composer textarea').waitFor({state:'visible'});
      await noOverflow();
      results.agentNavigation.push({locale,message,route});
      if (route.includes('kind=cards')) { await page.locator('.bank-card').waitFor(); assert.equal(await page.locator('.bank-card').count(),1); }
      if (route.includes('kind=accounts')) assert.equal(await page.locator('.product-card').count(),2);
    }
    for (const service of ['transfers','payments','loans','investments','insurance','cash']) {
      await page.goto(origin+'/services/'+service);
      await page.locator('[data-catalog-ready="true"]').waitFor();
      await noOverflow();
      results.pages.push({locale,route:'/services/'+service,width:1512});
    }
  }
  // A Portuguese report opens the existing review form. It must not silently
  // route a complaint into applications or create a request without confirmation.
  await chooseLanguage('pt');
  const beforePortuguese=await(await context.request.get(origin+'/api/bootstrap')).json();
  const responsePromise=page.waitForResponse(response=>response.url()===origin+'/api/assistant'&&response.request().method()==='POST');
  await page.locator('.paste-composer textarea').fill('Não reconheço uma compra');
  await page.locator('.paste-entry button').click();
  const portuguese=await(await responsePromise).json();
  assert.equal(portuguese.intent,'report'); assert.equal(portuguese.destination,'new-request');
  assert.ok(portuguese.text.startsWith('Vamos por partes.'));
  assert.deepEqual(portuguese.messages.map(message=>message.locale),['pt','pt']);
  await page.getByRole('dialog',{name:'Nova solicitação',exact:true}).waitFor();
  await page.getByRole('button',{name:'Fechar',exact:true}).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toHaveAttribute('lang','pt');
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('Vamos por partes.');
  const afterPortuguese=await(await context.request.get(origin+'/api/bootstrap')).json();
  assert.deepEqual(afterPortuguese.requests,beforePortuguese.requests);
  assert.deepEqual(afterPortuguese.products,beforePortuguese.products);
  assert.deepEqual(afterPortuguese.transactions,beforePortuguese.transactions);
  results.agentNavigation.push({locale:'pt',message:'Não reconheço uma compra',destination:'new-request',replyLocale:'pt',confirmed:false});
  await chooseLanguage('es');
  await page.waitForFunction(() => document.documentElement.lang === 'es');
  await page.goto(origin + '/movements');
  await page.getByPlaceholder('Buscar comercio o referencia').fill(testUser.merchant);
  await page.getByRole('button', { name: new RegExp(testUser.merchant) }).click();
  await page.getByRole('button', { name: 'Solicitar revisión', exact:true }).click();
  await page.getByLabel('Selecciona el movimiento').selectOption('');
  await page.getByLabel('Cuéntanos qué ocurrió').fill('UI verification: consulta general de prueba, sin ejecutar un reembolso.');
  await page.getByLabel('Revisé los datos').check();
  await axe('request-form');
  await page.getByRole('button', { name:'Confirmar solicitud',exact:true }).click();
  await page.getByRole('heading', {name:'Tu solicitud, paso a paso'}).waitFor();
  results.createdRequest = (await page.locator('dialog .case-top strong').innerText()).trim();
  await page.getByRole('button', {name:'Pedir atención humana',exact:true}).click();
  await page.getByRole('button', {name:'Confirmar derivación',exact:true}).click();
  await page.locator('dialog').getByText('Enviada a atención',{exact:true}).waitFor();
  await snapshot('request-handoff');
  await page.getByRole('button', {name:'Cerrar',exact:true}).click();
  await page.reload();
  await page.getByRole('heading',{name:'Mis reclamos',exact:true}).waitFor();
  assert.ok(await page.getByText(results.createdRequest,{exact:true}).count()>0,'Request persisted');
  const currentData=await(await context.request.get(origin+'/api/bootstrap')).json();
  const currentBalance=currentData.products.filter(p=>['account','savings'].includes(p.type)).reduce((sum,p)=>sum+(p.balanceMinor||0),0);
  const expectedBalance=new Intl.NumberFormat('es-MX',{minimumFractionDigits:2,maximumFractionDigits:2}).format(currentBalance/100);
  await page.getByRole('textbox', {name:'Mensaje para Nexqori'}).fill('¿Cuál es mi saldo?');
  await page.getByRole('button',{name:'Enviar mensaje',exact:true}).click();
  await page.getByRole('heading',{name:'Mis productos',exact:true}).waitFor();
  await page.locator('.chat-bubble.assistant').last().waitFor();
  assert.ok((await page.locator('.chat-bubble.assistant').last().innerText()).includes(expectedBalance),'Chat must show the current persisted balance');
  for (const width of [1024,768,390,320]) {
    await page.setViewportSize({width,height:900});
    for (const route of ['/','/movements','/services','/requests','/help']) {
      await page.goto(origin+route);
      await page.locator('.loading-panel').waitFor({state:'hidden'});
      await noOverflow();
      results.pages.push({route,width,locale:'es'});
    }
    if (width===390) { await page.goto(origin); await page.getByRole('heading',{name:'Qué bueno tenerte aquí.'}).waitFor(); assert.equal(await page.evaluate(() => scrollY),0,'Mobile load must start at page top'); await snapshot('home-mobile'); await axe('mobile'); await page.getByRole('button',{name:'Abrir navegación'}).click(); await page.locator('.menu-close').click(); assert.equal(await page.locator('.sidebar.mobile-open').count(),0); }
  }
  await page.setViewportSize({width:1512,height:1050});
  await page.goto(origin);
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
  await page.getByRole('button',{name:'Entrar a mi espacio'}).waitFor();
  assert.equal((await context.request.get(origin+'/api/bootstrap')).status(),401);
  await page.getByLabel('Correo electrónico').fill('admin@nexqori.com');
  await page.getByLabel('Contraseña',{exact:true}).fill(credentials.ADMIN_PASSWORD);
  await page.getByRole('button',{name:'Entrar a mi espacio'}).click();
  await page.getByRole('heading',{name:'Solicitudes y trazabilidad'}).waitFor();
  await snapshot('admin-desktop');
  await axe('admin');
  await noOverflow();
  assert.equal(pageErrors.length,0,JSON.stringify(pageErrors));
  writeFileSync(output+'/ui-results.json',JSON.stringify({...results,pageErrors},null,2));
  const violations=results.accessibility.flatMap(r=>r.violations);
  assert.equal(violations.length,0,JSON.stringify(violations));
  console.log(JSON.stringify({pages:results.pages.length,accessibility:results.accessibility.length,pageErrors:pageErrors.length,createdRequest:results.createdRequest,agentNavigation:results.agentNavigation.length,securityHeaders:results.securityHeaders}));
} finally {
  writeFileSync(output+'/ui-results.json',JSON.stringify({...results,pageErrors},null,2));
  await browser.close();
}
