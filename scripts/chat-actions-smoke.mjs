// Contrato UI con transporte simulado. API/aislamiento reales se prueban con pytest.
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { strict as assert } from 'node:assert';
const credentials = parseEnv(readFileSync('.env', 'utf8'));
const origin = 'http://localhost:5180';
const browser = await chromium.launch({channel: 'msedge', headless: true});
const customer = await browser.newContext({viewport:{width:1512,height:1100}});
const operator = await browser.newContext({viewport:{width:1512,height:1100}});
const errors = [];
const ticket = {id:'00000000-0000-4000-8000-000000000007', customerName:'Cliente UI',status:'draft',assignedTo:null,
  context:{intent:'human',reason:'rule',language:'es',messages:[{role:'user',text:'Necesito hablar con una persona.',language:'es',timestamp:new Date().toISOString()}]}, messages:[]};
let offered = false;
for (const [context, isOperator] of [[customer,false],[operator,true]]) {
  await context.route('**/api/assistant/handoffs', route => route.fulfill({json: offered ? [ticket] : []}));
  await context.route('**/api/admin/chat-handoffs', route => route.fulfill({json: offered && ticket.status !== 'draft' ? [ticket] : []}));
  await context.route('**/api/**/handoffs/*/confirm', route => {ticket.status='queued'; return route.fulfill({json:ticket});});
  await context.route('**/api/**/messages', route => {
    const body = route.request().postDataJSON(); ticket.status='active';
    ticket.messages.push({id:body.messageId,text:body.text,role:isOperator?'agent':'user',name:isOperator?'Operador UI':'Cliente UI',at:new Date().toISOString()});
    return route.fulfill({json:ticket});
  });
}
await customer.route('**/api/assistant', route => {
  const body = route.request().postDataJSON();
  if (body.message.includes('PDF')) return route.fulfill({json:{status:'document_ready',text:'Tu PDF está listo.',conversationId:null,
    document:{id:'00000000-0000-4000-8000-000000000006',filename:'nexqori-products_summary.pdf'}}});
  offered=true;
  return route.fulfill({json:{status:'human_offer',text:'Revisa y confirma compartir el contexto.',conversationId:null,handoff:{id:ticket.id}}});
});
await customer.route('**/api/assistant/documents/*', route => route.fulfill({contentType:'application/pdf',path:'.local/verification/pdf-templates/products_summary.pdf'}));
async function login(context, email, password) {
  const page=await context.newPage(); page.on('pageerror', e=>errors.push(e.message));
  await page.goto(origin); await page.locator('.language-picker select').selectOption('es');
  await page.getByLabel('Correo electrónico').fill(email);
  await page.getByLabel('Contraseña',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Entrar a mi espacio'}).click();
  await page.locator('.avatar').waitFor(); return page;
}
try {
  const page=await login(customer,'andrea@nexqori.local',credentials.CUSTOMER_PASSWORD);
  const admin=await login(operator,'admin@nexqori.local',credentials.ADMIN_PASSWORD);
  await page.locator('.chat-composer input').fill('PDF de mis productos');
  await page.locator('.chat-composer button').click();
  const download=page.waitForEvent('download'); await page.getByRole('button',{name:'Descargar PDF'}).click();
  const saved=await download; await saved.saveAs('.local/verification/ui-downloaded.pdf');
  assert.ok(readFileSync('.local/verification/ui-downloaded.pdf').subarray(0,5).equals(Buffer.from('%PDF-')));
  await page.locator('.chat-composer input').fill('Necesito hablar con una persona.');
  await page.locator('.chat-composer button').click();
  await page.getByRole('button',{name:'Confirmar y compartir contexto'}).waitFor();
  assert.equal(await admin.locator('.human-ticket').count(),0);
  await page.getByText('Revisar contexto compartido',{exact:true}).click();
  await page.getByRole('button',{name:'Confirmar y compartir contexto'}).click();
  await admin.locator('.human-ticket').waitFor();
  await admin.locator('.human-ticket > summary').click();
  await admin.getByLabel('Escribe un mensaje').fill('Respuesta de verificación humana.');
  await admin.getByRole('button',{name:'Enviar mensaje',exact:true}).click();
  await page.locator('.human-ticket > summary').click();
  await page.getByText(/Operador UI: Respuesta de verificación humana/).waitFor();
  await page.getByLabel('Escribe un mensaje').fill('Gracias, respuesta del cliente UI.');
  await page.locator('.human-support').getByRole('button',{name:'Enviar mensaje',exact:true}).click();
  await admin.getByText(/Cliente UI: Gracias, respuesta del cliente UI/).waitFor();
  await admin.screenshot({path:'.local/verification/human-admin.png',fullPage:true});
  await page.screenshot({path:'.local/verification/human-customer.png',fullPage:true});
  const violations=[];
  for (const target of [page,admin]) violations.push(...(await new AxeBuilder({page:target}).withTags(['wcag2a','wcag2aa']).analyze()).violations);
  await page.setViewportSize({width:390,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.ok(await page.locator('.assistant-panel').evaluate(panel => panel.querySelector('.human-support textarea').getBoundingClientRect().bottom <= panel.getBoundingClientRect().bottom), 'Human reply must not be clipped');
  assert.ok(await page.locator('.chat-messages').evaluate(log => log.getBoundingClientRect().height >= 300), 'Chat must keep usable height');
  await page.screenshot({path:'.local/verification/human-mobile.png',fullPage:true});
  await page.locator('.assistant-panel').screenshot({path:'.local/verification/human-mobile-panel.png'});
  assert.equal(violations.length,0,JSON.stringify(violations)); assert.equal(errors.length,0);
  writeFileSync('.local/verification/chat-actions-ui.json',JSON.stringify({transport:'local doubles',pdfDownload:true,confirmedHandoff:true,twoWayMessages:true,violations:[],errors},null,2));
  console.log('PDF descargado; confirmación y mensajes cliente/operador verificados con dobles UI; sin errores ni violaciones.');
} finally { await browser.close(); }
