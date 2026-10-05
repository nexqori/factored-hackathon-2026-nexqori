// Real bank API + shared interpreter + compiled React, isolated SQLite/model fixtures.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin='http://127.0.0.1:5192',root=path.resolve('.local/verification');await fs.mkdir(root,{recursive:true});
const folder=await fs.mkdtemp(path.join(root,'bank-chat-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5192 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.chat_ui_server'],{env:{...process.env,NEXQORI_CHAT_UI_CHECK:'1',NEXQORI_CHAT_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='';server.stderr.on('data',b=>{diagnostics+=b.toString();});let browser,page;
const report={cases:[],accessibility:[],errors:[]};
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();report.accessibility.push({name,violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))});}
try{
 for(let i=0;i<100;i++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error(diagnostics);await new Promise(r=>setTimeout(r,150));}
 const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const person of people){
  const copy=JSON.parse(await fs.readFile('src/locales/'+person.locale+'.json','utf8'));
  const context=await browser.newContext({viewport:{width:1512,height:1050}});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
  await page.goto(origin);await page.locator('.language-trigger').click();await page.locator('[data-locale="'+person.locale+'"]').click();
  const panel=page.locator('.assistant-panel');
  await expect(panel.getByRole('button',{name:copy['chatMovement.choose'],exact:true})).toHaveCount(0);
  if(person.locale==='pt' && person.intent==='unrecognized-charge'){
   const pasted='Relato colado para verificar a recuperação do texto.\n'.repeat(5);
   await panel.locator('.paste-composer textarea').fill('Meu relato');
   await panel.locator('.paste-composer textarea').evaluate((el,value)=>{const data=new DataTransfer();data.setData('text/plain',value);el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));},pasted);
   await expect(panel.locator('.pasted-card')).toBeVisible();
   await page.route('**/api/assistant/flow',route=>route.abort('failed'),{times:1});
   await panel.locator('.paste-entry button').click();
   await expect(panel.locator('.paste-composer [role=alert]')).toHaveText(copy['chatSending.failed']);
   await expect(panel.locator('.paste-composer textarea')).toHaveValue('Meu relato');await expect(panel.locator('.pasted-card pre')).toHaveText(pasted);
   await panel.locator('.paste-remove').click();
  }
  await panel.locator('.paste-composer textarea').fill('Mi borrador');
  await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
  const details=page.locator('.chat-details-dialog');await expect(details.getByRole('tab')).toHaveCount(0);
  await expect(details.locator('pre')).toHaveCount(0);await axe('details-'+person.locale+'-'+person.intent);
  await page.keyboard.press('Escape');await expect(panel.locator('.paste-composer textarea')).toHaveValue('Mi borrador');
  await expect(panel.getByRole('button',{name:copy['chatDetails.open'],exact:true})).toBeFocused();
  if(person.intent!=='unrecognized-charge'){
   const counts=await(await context.request.get(origin+'/api/verification/summary')).json();
   await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
   await details.getByRole('checkbox',{name:copy['chatSelection.movement'],exact:true}).check();
   await details.getByLabel(copy.chooseTransaction,{exact:true}).selectOption(person.transactionId);
   await expect(details.locator('[data-selected-movement]')).toContainText(person.transactionId);
   await details.getByRole('button',{name:copy['chatSelection.apply'],exact:true}).click();
   await expect(panel.locator('.paste-composer textarea')).toHaveValue('Mi borrador');
   await expect(panel.locator('[data-chat-movement]')).toHaveAttribute('data-chat-movement',person.transactionId);
   assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),counts,'Preparing a movement before conversation must not execute models');
  }
  const message={es:'Verificación',en:'Verification',pt:'Verificação'}[person.locale]+' [CASE-'+(['unrecognized-charge','incorrect-charge','payment-status'].indexOf(person.intent)+1)+'] '+(person.intent==='unrecognized-charge'?{es:'no reconozco e lcobro del celualar',en:'I do not recognize the phone charge.',pt:'Não reconheço a cobrança do celular.'}[person.locale]:{es:'Quiero revisar este movimiento.',en:'I need to review this transaction.',pt:'Quero revisar esta movimentação.'}[person.locale]);
  // Hold the network before the server answers: the outgoing bubble and empty
  // composer must already be visible. A response lost after commit must reuse
  // its original request key, rather than append a second turn or call models.
  let release;const gate=new Promise(resolve=>{release=resolve;});let firstBody;
  const loseResponse=person.intent==='unrecognized-charge'&&person.locale==='es';
  await page.route('**/api/assistant/flow',async route=>{
   firstBody=route.request().postDataJSON();await gate;
   if(loseResponse){await route.fetch();await route.abort('failed');}else await route.continue();
  },{times:1});
  let post=loseResponse?null:page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
  await panel.locator('.paste-composer textarea').fill(message);await panel.locator('.paste-entry button').click();
  await expect(panel.locator('.chat-pending')).toHaveText(message);await expect(panel.locator('.paste-composer textarea')).toHaveValue('');
  await expect(panel.locator('.chat-thinking')).toHaveText(copy['chatSending.thinking']);await expect(panel.locator('.paste-entry button')).toBeDisabled();
  if(person.intent==='unrecognized-charge'){await axe('thinking-'+person.locale);await page.screenshot({path:path.join(folder,'thinking-'+person.locale+'.png'),fullPage:true});}
  release();
  if(loseResponse){
   await expect(panel.locator('.paste-composer textarea')).toHaveValue(message);await expect(panel.locator('.chat-pending')).toHaveCount(0);
   await expect(panel.locator('.paste-composer [role=alert]')).toHaveText(copy['chatSending.failed']);
   const counts=await(await context.request.get(origin+'/api/verification/summary')).json();
   post=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
   await panel.locator('.paste-entry button').click();const retried=await post;
   assert.equal(retried.request().postDataJSON().requestKey,firstBody.requestKey);
   await expect(panel.locator('.chat-bubble.user')).toHaveCount(1);await expect(panel.locator('.paste-composer textarea')).toHaveValue('');
   assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),counts);
  }
  const response=await post;assert.equal(response.status(),200);let result=await response.json();
  assert.equal(result.flow.jev.intent,person.intent);const cid=result.conversation.id;
  if(person.intent==='unrecognized-charge'){
   assert.equal(result.flow.suggestedTransaction.id,person.transactionId);assert.equal(result.conversation.transactionId,null);assert.equal(result.flow.canRegister,false);
   await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(person.transactionId);
   await expect(panel.locator('.chat-bubble.assistant').last()).toContainText('Empresa Telefónica');await axe('suggestion-'+person.locale);
   await page.screenshot({path:path.join(folder,'suggestion-'+person.locale+'.png'),fullPage:true});
   if(person.locale==='es'){
    await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await panel.scrollIntoViewIfNeeded();await axe('suggestion-mobile');await page.screenshot({path:path.join(folder,'suggestion-mobile.png'),fullPage:true});await page.setViewportSize({width:1512,height:1050});
   }
   await panel.getByRole('button',{name:copy['chatMovement.choose'],exact:true}).click();await details.getByRole('checkbox',{name:copy['chatSelection.movement'],exact:true}).check();await expect(details.locator('select').first()).toBeEnabled();await page.keyboard.press('Escape');
   const confirmation=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
   if(person.locale==='pt'){await panel.locator('.paste-composer textarea').fill(copy['chatSending.confirmMessage']);await panel.locator('.paste-entry button').click();}
   else await panel.getByRole('button',{name:copy['chatSending.confirm'],exact:true}).click();
   result=await(await confirmation).json();assert.equal(result.conversation.transactionId,person.transactionId);assert.equal(result.flow.canRegister,true);
   await expect(panel.getByRole('button',{name:copy['chatSending.confirm'],exact:true})).toHaveCount(0);
   // Rebinding is explicit and persisted: selecting an option alone has no
   // effect, while applying asks the server to invalidate old evidence.
   const prior=await(await context.request.get(origin+'/api/verification/summary')).json();
   await panel.locator('.paste-composer textarea').fill('Borrador que se conserva');
   await expect(panel.getByRole('button',{name:copy['chatMovement.change'],exact:true})).toHaveCount(0);
   await expect(panel.getByRole('button',{name:copy['chatMovement.choose'],exact:true})).toHaveCount(0);
   await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(person.transactionId);
   await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
   await details.getByLabel(copy.chooseTransaction,{exact:true}).selectOption(person.alternateTransactionId);
   const unchanged=await(await context.request.get(origin+'/api/conversations/'+cid)).json();assert.equal(unchanged.conversation.transactionId,person.transactionId);
   assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),prior);
   if(person.locale==='es'){
    await page.setViewportSize({width:390,height:844});await axe('movement-picker-mobile');
    await page.screenshot({path:path.join(folder,'movement-picker-mobile.png'),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1512,height:1050});
   }
   const replacement=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
   await details.getByRole('button',{name:copy['chatSelection.apply'],exact:true}).click();
   const replaced=await replacement;assert.equal(replaced.status(),200);result=await replaced.json();
   assert.equal(replaced.request().postDataJSON().updateSelection,true);
   assert.equal(replaced.request().postDataJSON().message,copy['chatSelection.movementMessage']);
   assert.equal(result.conversation.transactionId,person.alternateTransactionId);assert.equal(result.flow.canRegister,true);
   assert.equal(result.flow.jev.intent,person.intent);assert(!JSON.stringify(result.flow.verified_facts).includes(person.transactionId));
   await expect(panel.locator('.paste-composer textarea')).toHaveValue('Borrador que se conserva');
   await expect(panel.locator('[data-chat-movement]')).toHaveCount(0);
   await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(person.alternateTransactionId);
   const following=await(await context.request.get(origin+'/api/verification/summary')).json();
   assert.equal(following.counts.triage,prior.counts.triage);assert.equal(following.counts.jev,prior.counts.jev);
  }
  if(person.intent==='incorrect-charge'){
   assert.deepEqual(result.flow.missing_fields,['difference']);
   assert(result.text.includes('100') && result.text.includes('85.0'));
   const commands={es:['Llévame a mis solicitudes','Llévame a mis tarjetas','Llévame al inicio','Llévame a centro de ayuda'],en:['Show my requests','Show me my cards','Go home','Open the help center'],pt:['Me leve às minhas solicitações','Mostre meus cartões','Vá ao início','Abra a central de ajuda']}[person.locale];
   for(const [index,route] of ['/requests','/cards','/','/help'].entries()){
    const response=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
    await panel.locator('.paste-composer textarea').fill(commands[index]);await panel.locator('.paste-entry button').click();
    const command=await(await response).json();assert.deepEqual(command.flow,result.flow,'Application commands preserve pending attention');
    await page.waitForURL(origin+route);
    await expect(page.locator('.sidebar .nav-link.active')).toHaveCount(1);
    await expect(page.locator('.sidebar .nav-link.active')).toHaveAttribute('href',route);
    if(route==='/cards')await page.screenshot({path:path.join(folder,'chat-cards-'+person.locale+'.png'),fullPage:true});
   }
   const next=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
   await panel.locator('.paste-composer textarea').fill('100 MXN');await panel.locator('.paste-entry button').click();result=await(await next).json();assert(result.flow.canRegister);
   assert(result.text.includes('100') && result.text.includes('85.0'));
  }
  await expect(panel.locator(':scope > .chat-flow')).toHaveCount(0);await expect(panel.locator('pre')).toHaveCount(0);
  assert(await panel.locator('.chat-messages').evaluate(el=>el.clientHeight>300));await axe(person.locale+'-'+person.intent);
  if(person.intent==='incorrect-charge')await page.screenshot({path:path.join(folder,'chat-clean-'+person.locale+'.png'),fullPage:true});
  const before=await(await context.request.get(origin+'/api/verification/summary')).json();
  await page.reload();await panel.locator('.conversation-toolbar button').nth(1).click();await page.locator('.conversation-list button').first().click();
  await expect(panel.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true})).toBeVisible();assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),before);
  await panel.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();
  await expect(details).toContainText(copy['chatFlow.state.review_in_bank']);await expect(details.locator('pre')).toHaveCount(0);
  await expect(details).not.toContainText('needs-clarification');await expect(details).not.toContainText(' ms');
  const previewResponse=page.waitForResponse(r=>r.url().includes('/claim-preview?')&&r.request().method()==='GET');
  await details.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();
  const preview=await(await previewResponse).json();const review=page.locator('.chat-claim-review');
  await expect(review.locator('.chat-claim-summary p')).toHaveText(preview.summary);
  assert(preview.summary.length>=10);assert(!preview.summary.includes('Verificación ['),'Claim starts from a server summary, not the transcript');
  assert.equal(preview.transactionId,person.intent==='unrecognized-charge'?person.alternateTransactionId:person.transactionId);
  await expect(review.getByRole('button',{name:copy['chatClaim.register'],exact:true})).toBeEnabled();
  await expect(review.getByRole('checkbox')).toHaveCount(0);
  await review.getByRole('button',{name:copy['chatClaim.edit'],exact:true}).click();
  const editedSummary=preview.summary+' '+{es:'Solicito revisar lo ocurrido.',en:'Please review what happened.',pt:'Peço a revisão do ocorrido.'}[person.locale];
  await review.getByLabel(copy['chatClaim.summary'],{exact:true}).fill(editedSummary);await expect(review.getByRole('checkbox')).toHaveCount(0);
  await axe('claim-summary-'+person.locale+'-'+person.intent);
  if(person.intent==='unrecognized-charge')await page.screenshot({path:path.join(folder,'claim-summary-'+person.locale+'.png'),fullPage:true});
  let lostClaim;
  if(person.locale==='es'&&person.intent==='unrecognized-charge'){
   await page.route('**/api/conversations/'+cid+'/claim',async route=>{lostClaim=route.request().postDataJSON();await route.fetch();await route.abort('failed');},{times:1});
   await review.getByRole('button',{name:copy['chatClaim.register'],exact:true}).click();await expect(review.getByRole('alert')).toBeVisible();
   await expect(review.getByLabel(copy['chatClaim.summary'],{exact:true})).toHaveValue(editedSummary);
  }
  const registration=page.waitForResponse(r=>r.url().endsWith('/'+cid+'/claim')&&r.request().method()==='POST');
  await review.getByRole('button',{name:copy['chatClaim.register'],exact:true}).click();
  const registered=await registration;assert.equal(registered.status(),200);const receipt=await registered.json();
  assert.equal(receipt.summary,editedSummary);assert.equal(registered.request().postDataJSON().previewToken,preview.previewToken);
  if(lostClaim)assert.equal(registered.request().postDataJSON().requestKey,lostClaim.requestKey);
  await page.waitForURL(/\/complaints\?case=/);await expect(page.locator('.claim-choice')).toHaveCount(1);await page.locator('.trace-current').waitFor();
  const rid=new URL(page.url()).searchParams.get('case');await expect(page.locator('.claims-detail')).toContainText(rid);
  await expect(panel.locator('.chat-bubble.assistant').filter({hasText:receipt.message.text})).toHaveCount(1);
  await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(rid);await expect(panel.locator('.chat-bubble.assistant').last()).toContainText(receipt.nextStep);
  await expect(panel.getByRole('button',{name:copy['chatMovement.change'],exact:true})).toHaveCount(0);
  const stored=await(await context.request.get(origin+'/api/conversations/'+cid)).json();assert.equal(stored.messages.filter(m=>m.id===receipt.message.id).length,1);
  assert.equal(stored.messages.find(m=>m.id===receipt.message.id).text,receipt.message.text);
  await page.locator('.claims-detail .trace-conversation').first().click();await expect(page.locator('.claims-detail')).toContainText(copy['chatFlow.title']);
  await expect(page.locator('.claims-detail pre')).toHaveCount(0);await expect(page.locator('.claims-detail .trace-tabs')).toHaveCount(0);await axe('claim-'+person.locale+'-'+person.intent);
  if(person.intent==='incorrect-charge'){await page.screenshot({path:path.join(folder,'chat-claim-'+person.locale+'.png'),fullPage:true});await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('mobile-'+person.locale);}
  // Each reference is optional. Staging and cancelling never run the model or
  // mutate an existing conversation; all four choices work in the same dialog.
  await page.setViewportSize({width:1512,height:1050});
  await panel.locator('.conversation-toolbar button').first().click();
  const selectionCounts=await(await context.request.get(origin+'/api/verification/summary')).json();
  for(const [movement,useCase] of [[false,false],[true,false],[false,true],[true,true]]){
   await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
   await expect(details.locator('.chat-details-tabs')).toHaveCount(0);
   await details.getByRole('checkbox',{name:copy['chatSelection.movement'],exact:true}).setChecked(movement);
   await details.getByRole('checkbox',{name:copy['chatSelection.case'],exact:true}).setChecked(useCase);
   if(movement)await details.getByLabel(copy.chooseTransaction,{exact:true}).selectOption(preview.transactionId);
   if(useCase)await details.getByLabel(copy['chatFlow.case'],{exact:true}).selectOption(rid);
   await expect(details.getByRole('button',{name:copy[movement||useCase?'chatSelection.apply':'chatSelection.none'],exact:true})).toBeEnabled();
   await details.getByRole('button',{name:copy[movement||useCase?'chatSelection.apply':'chatSelection.none'],exact:true}).click();
   await expect(details).toHaveCount(0);
   await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
   await expect(details.getByRole('checkbox',{name:copy['chatSelection.movement'],exact:true})).toBeChecked({checked:movement});
   await expect(details.getByRole('checkbox',{name:copy['chatSelection.case'],exact:true})).toBeChecked({checked:useCase});
   if(useCase)await expect(details.getByLabel(copy['chatFlow.case'],{exact:true})).toHaveValue(rid);
   if(movement&&useCase){
    await axe('unified-details-'+person.locale+'-'+person.intent);
    if(person.intent==='incorrect-charge'){
     await page.screenshot({path:path.join(folder,'unified-details-'+person.locale+'.png'),fullPage:true});
     await page.setViewportSize({width:390,height:844});await axe('unified-details-mobile-'+person.locale);
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
     await page.screenshot({path:path.join(folder,'unified-details-mobile-'+person.locale+'.png'),fullPage:true});
     await page.setViewportSize({width:1512,height:1050});
    }
   }
   await page.keyboard.press('Escape');
  }
  await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
  await details.getByRole('checkbox',{name:copy['chatSelection.movement'],exact:true}).uncheck();
  await details.getByRole('checkbox',{name:copy['chatSelection.case'],exact:true}).uncheck();
  await details.getByRole('button',{name:copy['chatDetails.back'],exact:true}).click();
  await panel.getByRole('button',{name:copy['chatDetails.open'],exact:true}).click();
  await expect(details.getByRole('checkbox')).toHaveCount(2);
  for(const checkbox of await details.getByRole('checkbox').all())await expect(checkbox).toBeChecked();
  assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),selectionCounts);
  await page.keyboard.press('Escape');await expect(details).toHaveCount(0);
  if(person.intent==='incorrect-charge'){
   await page.setViewportSize({width:1512,height:1050});
   for(const [target,text] of [['en','Cambia el idioma a inglés'],['pt','Switch to Portuguese'],['es','Mude o idioma para espanhol']]){
    await panel.locator('.paste-composer textarea').fill(text);await panel.locator('.paste-entry button').click();
    await expect(page.locator('html')).toHaveAttribute('lang',target);
    const session=await(await context.request.get(origin+'/api/session')).json();assert.equal(session.user.locale,target);
    await page.reload();await expect(page.locator('html')).toHaveAttribute('lang',target);
   }
   const logout=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
   await panel.locator('.paste-composer textarea').fill('Cierra sesión');await panel.locator('.paste-entry button').click();
   assert.equal((await logout).status(),200);await expect(page.locator('.login-page')).toBeVisible();
   assert.equal((await context.request.get(origin+'/api/session')).status(),401);
  }
  report.cases.push({locale:person.locale,intent:person.intent,conversationId:cid,requestId:rid});await context.close();
 }
 const summary=await(await fetch(origin+'/api/verification/summary')).json();assert.deepEqual(summary.counts,{triage:9,jev:9,llm:18});assert.equal(summary.bankRecordsSentToModels,false);
 assert.deepEqual(report.errors,[]);assert(report.accessibility.every(r=>!r.violations.length),JSON.stringify(report.accessibility));
 await fs.writeFile(path.join(folder,'report.json'),JSON.stringify({...report,summary},null,2));console.log(JSON.stringify({folder,...report,summary},null,2));
}catch(error){if(page){await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(folder,'failure.private.txt'),await page.locator('body').innerText().catch(()=>''));}throw error;}finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
