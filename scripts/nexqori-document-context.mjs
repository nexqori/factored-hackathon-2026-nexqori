// Real API, interpreter and React with isolated SQLite and controlled providers.
// No Compose data, customer account, secret or external provider is used.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';

const origin='http://127.0.0.1:5193',root=path.resolve('.local/verification');
await fs.mkdir(root,{recursive:true});const folder=await fs.mkdtemp(path.join(root,'document-context-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5193 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.document_ui_server'],{env:{...process.env,NEXQORI_DOCUMENT_UI_CHECK:'1',NEXQORI_DOCUMENT_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='',browser,page;server.stderr.on('data',b=>{diagnostics+=b.toString();});
const report={cases:[],accessibility:[],errors:[]};
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
async function json(response){assert.equal(response.status(),200,response.url());return response.json();}
async function axe(name){const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();const violations=result.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}));report.accessibility.push({name,violations});assert.deepEqual(violations,[],name);}
try{
 for(let i=0;i<100;i++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error('Isolated server did not start; see private diagnostics');await new Promise(r=>setTimeout(r,150));}
 const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const person of people){
  const copy=JSON.parse(await fs.readFile('src/locales/'+person.locale+'.json','utf8'));
  const context=await browser.newContext({viewport:{width:1512,height:1050},acceptDownloads:true});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await json(await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}}));
  const before=await json(await context.request.get(origin+'/api/bootstrap'));
  await page.goto(origin);await page.locator('.language-trigger').click();await page.locator('[data-locale="'+person.locale+'"]').click();
  const panel=page.locator('.assistant-panel');
  async function send(text){const response=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');await panel.locator('.paste-composer textarea').fill(text);await panel.locator('.paste-entry button').click();return json(await response);}
  const question={es:'Muéstrame mis movimientos de septiembre de 2026.',en:'Show my transactions for September 2026.',pt:'Mostre minhas movimentações de setembro de 2026.'}[person.locale];
  const answer=await send(question);const cid=answer.conversation.id;
  assert.equal(answer.flow.triage.family,'query');assert.equal(answer.flow.jev.intent,'account-activity');
  await expect(page).toHaveURL(origin+'/movements?start=2026-09-01&end=2026-09-30');
  await expect(page.locator('.movement-filters').getByLabel(copy['documents.from'],{exact:true})).toHaveValue('2026-09-01');
  await expect(page.locator('.movement-filters').getByLabel(copy['documents.to'],{exact:true})).toHaveValue('2026-09-30');
  await expect(page.locator('.transaction-panel [data-transaction-id]')).toHaveCount(1);
  await expect(page.locator('.transaction-panel [data-transaction-id]')).toHaveAttribute('data-transaction-id',person.transactionId);
  await expect(page.locator('.transaction-panel .movement-meta')).toContainText('9101');
  await expect(page.locator('.transaction-panel time')).toContainText('2026');
  await expect(page.locator('.transaction-panel .badge')).toBeVisible();
  await page.setViewportSize({width:390,height:844});await expect(page.locator('.transaction-panel .badge')).toBeVisible();await page.screenshot({path:path.join(folder,'movements-'+person.locale+'.png'),fullPage:true});await page.setViewportSize({width:1512,height:1050});
  await expect(panel.locator('.chat-bubble.assistant').last()).toContainText('2026-09-01');
  await expect(panel.locator('.chat-bubble.assistant').last()).toContainText('2026-09-30');await axe('filtered-movements-'+person.locale);
  const draftBefore=await json(await context.request.get(origin+'/api/conversations/'+cid+'/document-context'));
  assert.equal(draftBefore.draft.kind,'statement');assert.equal(draftBefore.draft.startDate,'2026-09-01');assert.deepEqual(draftBefore.missing,[]);
  const followup={es:'Prepara ese estado de cuenta en PDF.',en:'Prepare that statement as a PDF.',pt:'Prepare esse extrato em PDF.'}[person.locale];
  const prepared=await send(followup);assert.equal(prepared.conversation.id,cid);assert.equal(prepared.flow.canDocument,true);
  assert.equal((await json(await context.request.get(origin+'/api/documents'))).documents.length,0,'Conversation must not generate a document automatically');
  await panel.getByRole('button',{name:copy['documents.prepare'],exact:true}).click();const dialog=page.locator('.chat-documents-dialog');
  await expect(dialog.getByRole('combobox',{name:copy['documents.type'],exact:true})).toHaveValue('statement');
  await expect(dialog.getByLabel(copy['documents.from'],{exact:true})).toHaveValue('2026-09-01');
  await expect(dialog.getByLabel(copy['documents.to'],{exact:true})).toHaveValue('2026-09-30');
  await expect(dialog.getByRole('checkbox',{name:copy['documents.allHistory'],exact:true})).not.toBeChecked();
  await expect(dialog.getByRole('button',{name:copy['documents.generate'],exact:true})).toBeEnabled();
  await axe('prefilled-pdf-'+person.locale);await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('prefilled-pdf-mobile-'+person.locale);
  await page.screenshot({path:path.join(folder,'prefilled-'+person.locale+'.png'),fullPage:true});await page.setViewportSize({width:1512,height:1050});
  let lost;
  if(person.locale==='es'){
   await page.route('**/api/conversations/'+cid+'/documents',async route=>{lost=route.request().postDataJSON();assert.equal((await route.fetch()).status(),200);await route.abort('failed');},{times:1});
   await dialog.getByRole('button',{name:copy['documents.generate'],exact:true}).click();await expect(dialog.getByRole('alert')).toContainText(copy['error.network']);
   await expect(dialog.getByLabel(copy['documents.from'],{exact:true})).toHaveValue('2026-09-01');
  }
  const generated=page.waitForResponse(r=>r.url().endsWith('/'+cid+'/documents')&&r.request().method()==='POST');
  await dialog.getByRole('button',{name:copy['documents.generate'],exact:true}).click();const generatedResponse=await generated;const output=await json(generatedResponse);
  const body=generatedResponse.request().postDataJSON();assert.equal(body.kind,'statement');assert.equal(body.startDate,'2026-09-01');assert.equal(body.endDate,'2026-09-30');
  if(lost)assert.equal(body.requestKey,lost.requestKey);
  const doc=output.document;await expect(page).toHaveURL(origin+'/documents?document='+doc.id);
  assert.equal(doc.locale,person.locale);assert.equal(doc.details.startDate,'2026-09-01');assert.equal(doc.details.endDate,'2026-09-30');assert.equal(doc.details.recordCount,2,'Only own product and September transaction are included');
  const card=page.locator('[data-document-request-id="'+doc.id+'"]');await expect(card).toBeVisible();
  await card.getByRole('button',{name:copy['documents.viewDetails'],exact:true}).click();
  await expect(page.locator('dialog')).toContainText('2026-09-01 — 2026-09-30');await expect(page.locator('dialog pre')).toHaveCount(0);
  await page.getByRole('button',{name:copy.close,exact:true}).click();
  const downloadPromise=page.waitForEvent('download');await card.getByRole('button',{name:new RegExp('^'+copy['documents.download'])}).click();
  const downloaded=await downloadPromise;const pdfPath=path.join(folder,person.locale+'-september.pdf');await downloaded.saveAs(pdfPath);
  const bytes=await fs.readFile(pdfPath);assert.equal(bytes.subarray(0,5).toString(),'%PDF-');
  const stored=await json(await context.request.get(origin+'/api/conversations/'+cid));assert.equal(stored.messages.filter(m=>m.document).length,1);assert.equal(stored.conversation.closed,true);await expect(panel.locator('textarea')).toHaveCount(0);await expect(panel).toContainText(copy['error.conversation_closed']);
  await page.reload();await panel.getByRole('button',{name:copy.conversations,exact:true}).click();await page.locator('.conversation-list button').first().click();
  await expect(panel.locator('[data-document-id="'+doc.id+'"]')).toHaveCount(1);await expect(panel.locator('textarea')).toHaveCount(0);await expect(panel.locator('pre')).toHaveCount(0);
  const historical=page.waitForEvent('download');await panel.locator('[data-document-id="'+doc.id+'"] button').click();
  const historicalPath=path.join(folder,person.locale+'-history.pdf');await(await historical).saveAs(historicalPath);assert.equal(hash(await fs.readFile(historicalPath)),hash(bytes));
  await axe('documents-history-'+person.locale);
  // A generic PDF request must ask for its missing type. It must not inherit
  // September or choose a product from an unrelated, new conversation.
  await panel.getByRole('button',{name:copy.newConversationShort,exact:true}).click();
  await send({es:'Quiero un documento PDF.',en:'I want a PDF document.',pt:'Quero um documento PDF.'}[person.locale]);
  await panel.getByRole('button',{name:copy['documents.prepare'],exact:true}).click();
  await expect(dialog.getByRole('combobox',{name:copy['documents.type'],exact:true})).toBeEnabled();
  await expect(dialog.getByRole('combobox',{name:copy['documents.type'],exact:true})).toHaveValue('');
  await expect(dialog.getByRole('button',{name:copy['documents.generate'],exact:true})).toBeDisabled();
  await dialog.getByRole('combobox',{name:copy['documents.type'],exact:true}).selectOption('statement');
  await expect(dialog.getByLabel(copy['documents.from'],{exact:true})).toHaveValue('');await expect(dialog.getByLabel(copy['documents.to'],{exact:true})).toHaveValue('');
  await expect(dialog.getByRole('button',{name:copy['documents.generate'],exact:true})).toBeDisabled();await page.keyboard.press('Escape');
  for(const [kind,reference,excluded,text] of [
   ['requests_summary',person.applicationId,person.claimId,{es:'Quiero un PDF de mis solicitudes',en:'I want a PDF of my requests',pt:'Quero um PDF das minhas solicitações'}[person.locale]],
   ['claims_summary',person.claimId,person.applicationId,{es:'Quiero un PDF de mis reclamos',en:'I want a PDF of my complaints',pt:'Quero um PDF das minhas reclamações'}[person.locale]],
  ]){
   await panel.getByRole('button',{name:copy.newConversationShort,exact:true}).click();await send(text);
   await panel.getByRole('button',{name:copy['documents.prepare'],exact:true}).click();
   await expect(dialog.getByRole('combobox',{name:copy['documents.type'],exact:true})).toHaveValue(kind);
   assert.deepEqual(await dialog.getByRole('combobox',{name:copy['documents.scope'],exact:true}).locator('option').allTextContents(),[copy[kind==='claims_summary'?'documents.allClaims':'documents.allRequests'],copy['documents.selected']]);await dialog.getByRole('combobox',{name:copy['documents.scope'],exact:true}).selectOption('selected');
   const selection=dialog.getByRole('combobox',{name:copy['chatFlow.case'],exact:true});
   assert((await selection.locator('option').allTextContents()).some(t=>t.includes(reference)));
   assert(!(await selection.locator('option').allTextContents()).some(t=>t.includes(excluded)));
   await selection.selectOption(reference);await axe(kind+'-'+person.locale);
   const generated=page.waitForResponse(r=>r.url().endsWith('/documents')&&r.request().method()==='POST');
   await dialog.getByRole('button',{name:copy['documents.generate'],exact:true}).click();const result=await json(await generated);
   assert.equal(result.document.kind,kind);assert.equal(result.document.details.recordCount,1);
   const pdf=await context.request.get(origin+'/api/documents/'+result.document.id);assert.equal(pdf.status(),200);
   await fs.writeFile(path.join(folder,kind+'-'+person.locale+'.pdf'),await pdf.body());
   await expect(dialog).not.toBeVisible();
  }
  const after=await json(await context.request.get(origin+'/api/bootstrap'));
  assert.deepEqual(after.products,before.products);assert.deepEqual(after.transactions,before.transactions);assert.deepEqual(after.requests,before.requests);
  assert.equal((await json(await context.request.get(origin+'/api/documents'))).documents.length,3);
  report.cases.push({locale:person.locale,conversationId:cid,documentId:doc.id,sha256:hash(bytes),unchangedFinancialData:true});await context.close();
 }
 const summary=await(await fetch(origin+'/api/verification/summary')).json();assert.equal(summary.bankRecordsSentToModels,false);assert.deepEqual(report.errors,[]);
 await fs.writeFile(path.join(folder,'report.json'),JSON.stringify({...report,summary},null,2));console.log(JSON.stringify({folder,...report,summary},null,2));
}catch(error){if(page){await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(folder,'failure.private.txt'),await page.locator('body').innerText().catch(()=>''));}throw error;}
finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
