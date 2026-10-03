import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { strict as assert } from 'node:assert';
const credentials = parseEnv(readFileSync('.env', 'utf8'));
const origin = process.env.NEXQORI_URL || 'http://localhost:5180';
const output = process.env.NEXQORI_TEST_OUTPUT || '.local/verification';
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 }, locale: 'es-MX' });
const page = await context.newPage();
const pageErrors = [];
page.on('pageerror', error => pageErrors.push(error.message));
const results = { pages: [], accessibility: [], screenshots: [], createdRequest: null, chatReadOnly: [], securityHeaders: false };
const snapshot = async name => { const path = output + '/' + name + '.png'; await page.screenshot({ path, fullPage: true }); results.screenshots.push(path); };
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
  await page.getByLabel('Correo electrónico').fill('andrea@nexqori.local');
  await page.getByLabel('Contraseña', { exact: true }).fill(credentials.CUSTOMER_PASSWORD);
  await page.getByRole('button', { name: 'Entrar a mi espacio' }).click();
  await page.getByRole('heading', { name: 'Qué bueno tenerte aquí.' }).waitFor();
  await snapshot('home-desktop');
  await axe('home');
  const labels = {
    es: {language:'Idioma', home:'Qué bueno tenerte aquí.', movements:'Movimientos', products:'Mis productos', services:'Servicios', requests:'Mis solicitudes',help:'Siempre hay un siguiente paso.'},
    en: {language:'Language',home:'It’s good to have you here.',movements:'Transactions',products:'My products',services:'Services',requests:'My requests',help:'There’s always a next step.'},
    pt: {language:'Idioma',home:'Que bom ter você aqui.',movements:'Movimentações',products:'Meus produtos',services:'Serviços',requests:'Minhas solicitações',help:'Sempre há um próximo passo.'}
  };
  for (const locale of ['en','pt','es']) {
    await page.locator('.language-picker select').selectOption(locale);
    await page.waitForFunction(language => document.documentElement.lang === language, locale);
    for (const route of ['home','movements','products','services','requests','help']) {
      await page.goto(origin + (route === 'home' ? '/' : '/' + route));
      await page.getByRole('heading',{ name:labels[locale][route],exact:true }).waitFor();
      await noOverflow();
      results.pages.push({locale,route,width:1512});
    }
  }
  // Contrato conversacional del navegador: doble local, sin llamadas a proveedores.
  const turns = [];
  const fixtureConversation = '00000000-0000-4000-8000-000000000001';
  await page.route('**/api/assistant', async route => {
    turns.push(route.request().postDataJSON());
    await route.fulfill({ json: {
      text: turns.length === 1 ? '¿Una cuenta o todas?' : 'Respuesta de verificación local.',
      status: turns.length === 1 ? 'awaiting_user' : 'answered', conversationId: fixtureConversation,
      // Incluso una respuesta no confiable no puede abrir pantallas/formularios.
      destination: 'new-request', navigation: { tool: 'navigate_in_app', destination: 'transfers', route: '/services/transfers' }
    } });
  });
  const initialChatURL = page.url();
  for (const text of ['saldo', 'todas']) {
    const count = await page.locator('.chat-bubble.assistant').count();
    await page.locator('.chat-composer input').fill(text);
    await page.locator('.chat-composer button').click();
    await page.waitForFunction(expected => document.querySelectorAll('.chat-bubble.assistant').length === expected, count + 1);
  }
  assert.equal(turns[0].conversationId, null);
  assert.equal(turns[1].conversationId, fixtureConversation);
  assert.notEqual(turns[0].messageId, turns[1].messageId);
  assert.ok(turns.every(turn => !('user_id' in turn) && !('session_token' in turn) && !('history' in turn)));
  assert.equal(page.url(), initialChatURL);
  assert.equal(await page.locator('dialog').count(), 0);
  await page.getByRole('button', {name:'Nueva conversación', exact:true}).click();
  assert.equal(await page.locator('.chat-bubble').count(), 0);
  await page.unroute('**/api/assistant');
  const commands = {
    es: [['Llévame a transferencias','/services/transfers'],['Ver tarjetas','/products?kind=cards']],
    en: [['Open bill payments','/services/payments'],['Show my accounts','/products?kind=accounts']],
    pt: [['Abrir empréstimos','/services/loans'],['Abrir seguros','/services/insurance']]
  };
  for (const [locale, cases] of Object.entries(commands)) {
    await page.locator('.language-picker select').selectOption(locale);
    await page.waitForFunction(language => document.documentElement.lang === language, locale);
    for (const [message, route] of cases) {
      const unchangedURL = page.url();
      const count = await page.locator('.chat-bubble.assistant').count();
      await page.locator('.chat-composer input').fill(message);
      await page.locator('.chat-composer button').click();
      await page.waitForFunction(expected => document.querySelectorAll('.chat-bubble.assistant').length === expected, count + 1);
      assert.equal(page.url(), unchangedURL, 'Chat must not navigate');
      assert.match(await page.locator('.chat-bubble.assistant').last().innerText(), /pendiente|pending|pendente/);
      await page.locator('.chat-composer input').waitFor({state:'visible'});
      await noOverflow();
      results.chatReadOnly.push({locale,message,route});
      assert.equal(await page.locator('dialog').count(), 0, 'Chat must not open write forms');
    }
    for (const service of ['transfers','payments','loans','investments','insurance','cash']) {
      await page.goto(origin+'/services/'+service);
      await page.locator('.service-detail').waitFor();
      await noOverflow();
      results.pages.push({locale,route:'/services/'+service,width:1512});
    }
  }
  await page.locator('.language-picker select').selectOption('es');
  await page.waitForFunction(() => document.documentElement.lang === 'es');
  await page.goto(origin + '/movements');
  await page.getByPlaceholder('Buscar comercio o referencia').fill('Stream');
  await page.getByRole('button', { name: /Stream Plus/ }).click();
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
  await page.getByRole('heading',{name:'Mis solicitudes',exact:true}).waitFor();
  assert.ok(await page.getByText(results.createdRequest,{exact:true}).count()>0,'Request persisted');
  await page.getByRole('textbox', {name:'Mensaje para Nexqori'}).fill('¿Cuál es mi saldo?');
  await page.getByRole('button',{name:'Enviar mensaje',exact:true}).click();
  assert.equal(page.url(), origin + '/requests', 'Balance query must not navigate');
  await page.locator('.chat-bubble.assistant').last().waitFor();
  assert.ok((await page.locator('.chat-bubble.assistant').last().innerText()).includes('24,850.00'));
  await snapshot('chat-readonly-desktop');
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
  await page.getByLabel('Correo electrónico').fill('admin@nexqori.local');
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
  console.log(JSON.stringify({pages:results.pages.length,accessibility:results.accessibility.length,pageErrors:pageErrors.length,createdRequest:results.createdRequest,chatReadOnly:results.chatReadOnly.length,securityHeaders:results.securityHeaders}));
} finally {
  writeFileSync(output+'/ui-results.json',JSON.stringify({...results,pageErrors},null,2));
  await browser.close();
}
