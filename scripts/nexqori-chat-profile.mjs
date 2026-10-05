// Real API and UI, isolated fixtures with two cards per verification customer.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin='http://127.0.0.1:5193',root=path.resolve('.local/verification');
await fs.mkdir(root,{recursive:true});const folder=await fs.mkdtemp(path.join(root,'chat-profile-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5193 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.document_ui_server'],{env:{...process.env,NEXQORI_DOCUMENT_UI_CHECK:'1',NEXQORI_PROFILE_UI_CHECK:'1',NEXQORI_DOCUMENT_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='',browser,page;server.stderr.on('data',b=>diagnostics+=b.toString());
const report={checks:[],accessibility:[],errors:[]};
async function json(r){assert.equal(r.status(),200,r.url());return r.json();}
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(r.violations.map(v=>v.id),[],name);report.accessibility.push(name);}
try{
 for(let i=0;i<100;i++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error('Fixture failed');await new Promise(r=>setTimeout(r,150));}
 const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const person of people){
  const lang=person.locale,copy=JSON.parse(await fs.readFile('src/locales/'+lang+'.json','utf8'));
  const context=await browser.newContext({viewport:{width:1512,height:1050}});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await json(await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}}));
  await page.goto(origin);await page.locator('.language-trigger').click();await page.locator('[data-locale="'+lang+'"]').click();
  const panel=page.locator('.assistant-panel');
  async function send(text){const response=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');await panel.locator('textarea').fill(text);await panel.locator('.paste-entry button').click();return json(await response);}
  let mutations=0;page.on('request',r=>{if(r.method()==='PATCH'&&(r.url().endsWith('/profile/field')||r.url().endsWith('/profile/experience')))mutations++;});
  for(const [field,text,value] of [
   ['birthDate',{es:'Cambia mi fecha de nacimiento',en:'Change my date of birth',pt:'Altere minha data de nascimento'}[lang],'1990-12-31'],
   ['bankingExperience',{es:'Cambia mi frecuencia bancaria',en:'Change my banking frequency',pt:'Altere minha frequência bancária'}[lang],'occasional'],
   ['digitalExperience',{es:'Cambia mi experiencia en banca digital',en:'Change my digital banking experience',pt:'Altere minha experiência no banco digital'}[lang],'learning'],
   ['assistance',{es:'Cambia mi preferencia de acompañamiento',en:'Change my support preference',pt:'Altere minha preferência de ajuda'}[lang],'guided'],
   ...['small','medium','large'].map(v=>['textSize',{es:'Cambia el tamaño de letra',en:'Change my font size',pt:'Altere o tamanho da letra'}[lang],v]),
  ]){
   const before=mutations;const result=await send(text);assert.equal(result.appCommand.field,field);
   const form=panel.locator('.chat-profile');await expect(form).toBeVisible();
   if(field==='birthDate'&&lang==='es'){await expect(form).toContainText(copy['chatProfile.complete']);await form.locator('select').nth(0).selectOption('frequent');await form.locator('select').nth(1).selectOption('confident');}
   if(field==='birthDate')await form.locator('input').fill(value);else await form.locator('select').selectOption(value);
   assert.equal(mutations,before);await form.getByRole('button',{name:copy['chatProfile.reviewButton'],exact:true}).click();assert.equal(mutations,before);
   await expect(form).toContainText(copy['chatProfile.review']);await axe(lang+'-'+field+'-'+value);
   await form.getByRole('button',{name:copy['chatProfile.confirm'],exact:true}).click();await expect(form).toHaveCount(0);
   const session=await json(await context.request.get(origin+'/api/session'));
   if(field==='birthDate')assert.equal((await json(await context.request.get(origin+'/api/profile/experience'))).birthDate,value);
   else if(field==='textSize'){assert.equal(session.user.textSize,value);await expect(page.locator('html')).toHaveAttribute('data-text-size',value);}
   else assert.equal(session.user.experience[field],value);
  }
  const cards=(await json(await context.request.get(origin+'/api/cards'))).cards;
  const show={es:'Ver datos de mi tarjeta',en:'Show my card details',pt:'Mostre os dados do meu cartão'}[lang];
  await send(show);const dialog=page.locator('dialog');const selector=dialog.getByRole('combobox');
  await expect(selector).toHaveValue('');assert.equal(await selector.locator('option').count(),3);
  for(const card of cards)await expect(selector).toContainText(copy.cardName+' · '+card.last4);
  await selector.selectOption(cards[1].id);await expect(selector).toHaveValue(cards[1].id);
  await dialog.getByLabel(copy.password,{exact:true}).fill(person.password);await dialog.getByRole('button',{name:copy.showCardDetails,exact:true}).click();
  await expect(page.locator('[data-card-id="'+cards[1].id+'"] [data-testid="card-expiry"]')).not.toHaveText('••/••');
  await expect(page.locator('[data-card-id="'+cards[0].id+'"] [data-testid="card-expiry"]')).toHaveText('••/••');
  await page.evaluate(()=>window.dispatchEvent(new Event('blur')));
  await send(show+{es:' terminada en ',en:' ending in ',pt:' final '}[lang]+cards[0].last4);
  await expect(selector).toHaveValue(cards[0].id);await axe('card-selector-'+lang);
  await page.setViewportSize({width:390,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('card-selector-mobile-'+lang);
  await page.screenshot({path:path.join(folder,'card-selector-'+lang+'.png'),fullPage:true});await dialog.getByRole('button',{name:copy.close,exact:true}).click();
  await page.setViewportSize({width:1512,height:1050});
  await send({es:'Bloquea mi tarjeta terminada en ',en:'Block my card ending in ',pt:'Bloqueie meu cartão final '}[lang]+cards[1].last4);
  await dialog.getByLabel(copy.password,{exact:true}).fill(person.password);await dialog.getByRole('checkbox').check();await dialog.getByRole('button',{name:copy.confirmBlockCard,exact:true}).click();await expect(dialog).toHaveCount(0);
  await send({es:'Ver datos de mi tarjeta Nexqori',en:'Show details of my card Nexqori',pt:'Mostre os dados do meu cartão Nexqori'}[lang]);
  await expect(selector).toHaveValue(cards[0].id);assert.equal(await selector.locator('option').count(),2);await dialog.getByRole('button',{name:copy.close,exact:true}).click();
  await send({es:'Abre mis solicitudes',en:'Open my requests',pt:'Abra minhas solicitações'}[lang]);
  await expect(page).toHaveURL(origin+'/requests');await expect(page.locator('.my-documents')).toHaveCount(0);
  await expect(page.getByRole('button',{name:copy.allServices,exact:true})).toBeVisible();
  const filter=page.locator('.request-filters select');await filter.selectOption('in_review');await expect(page.locator('.requests-grid').locator('article')).toHaveCount(0);
  await filter.selectOption('received');await expect(page.locator('.requests-grid')).toContainText(person.applicationId);
  await page.locator('.requests-grid button').first().click();await expect(dialog.locator('.trace-current')).toContainText(copy['application.trace.outcome.received']);
  await expect(dialog.locator('.trace-current')).not.toContainText(copy['trace.outcome.received']);await dialog.getByRole('button',{name:copy.close,exact:true}).click();
  await send({es:'Abre mis reclamos',en:'Open my complaints',pt:'Abra minhas reclamações'}[lang]);
  await page.locator('.claim-choice').first().click();await expect(page.locator('.claims-detail')).toContainText(copy['claim.auditCreated']);await expect(page.locator('.claims-detail')).toContainText(copy['claim.eventCreated']);await expect(page.locator('.claims-detail')).toContainText(copy['claim.activityHint']);await axe('case-copy-'+lang);
  for(const foreign of ['es','en','pt'].filter(v=>v!==lang)){
   const r=await send({es:'Llévame al inicio',en:'Go home',pt:'Vá ao início'}[foreign]);assert.equal(r.navigation,null);assert.equal(r.appCommand,null);
  }
  report.checks.push({locale:lang,confirmedProfile:true,multipleCards:true,separateCaseCopy:true,foreignCommandsRejected:true});await context.close();
 }
 assert.deepEqual(report.errors,[]);await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({folder,...report},null,2));
}catch(error){if(page){await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(folder,'failure.private.txt'),await page.locator('body').innerText().catch(()=>''));}throw error;}
finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
