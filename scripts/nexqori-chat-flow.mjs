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
  const panel=page.locator('.assistant-panel');await panel.getByText(copy['chatFlow.references'],{exact:true}).click();
  await panel.locator('.chat-flow select').first().selectOption(person.transactionId);
  const message='Verificación ['+person.intent+'] '+{es:'Quiero revisar este movimiento.',en:'I need to review this transaction.',pt:'Quero revisar esta movimentação.'}[person.locale];
  const post=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
  await panel.locator('.paste-composer textarea').fill(message);await panel.locator('.paste-entry button').click();
  const response=await post;assert.equal(response.status(),200);let result=await response.json();
  assert.equal(result.flow.jev.intent,person.intent);const cid=result.conversation.id;
  if(person.intent==='incorrect-charge'){
   await expect(panel).toContainText(copy['chatFlow.state.ask_customer']);assert.deepEqual(result.flow.missing_fields,['difference']);
   const next=page.waitForResponse(r=>r.url().endsWith('/api/assistant/flow')&&r.request().method()==='POST');
   await panel.locator('.paste-composer textarea').fill('100 MXN');await panel.locator('.paste-entry button').click();result=await(await next).json();assert(result.flow.canRegister);
  }
  await expect(panel).toContainText(copy['chatFlow.state.review_in_bank']);await axe(person.locale+'-'+person.intent);
  const before=await(await context.request.get(origin+'/api/verification/summary')).json();
  await page.reload();await panel.locator('.conversation-toolbar button').nth(1).click();await page.locator('.conversation-list button').first().click();
  await expect(panel).toContainText(copy['chatFlow.state.review_in_bank']);assert.deepEqual(await(await context.request.get(origin+'/api/verification/summary')).json(),before);
  await panel.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();await page.locator('dialog input[type=checkbox]').check();await page.locator('dialog').getByRole('button',{name:copy.confirm,exact:true}).click();
  await page.waitForURL(/\/complaints\?case=/);await expect(page.locator('.claim-choice')).toHaveCount(1);await page.locator('.trace-current').waitFor();
  const rid=new URL(page.url()).searchParams.get('case');await expect(page.locator('.claims-detail')).toContainText(rid);
  await page.locator('.claims-detail .trace-conversation').first().click();await expect(page.locator('.claims-detail')).toContainText(copy['chatFlow.title']);
  await axe('claim-'+person.locale+'-'+person.intent);
  if(person.intent==='incorrect-charge'){await page.screenshot({path:path.join(folder,'chat-claim-'+person.locale+'.png'),fullPage:true});await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('mobile-'+person.locale);}
  report.cases.push({locale:person.locale,intent:person.intent,conversationId:cid,requestId:rid});await context.close();
 }
 const summary=await(await fetch(origin+'/api/verification/summary')).json();assert.deepEqual(summary.counts,{triage:9,jev:9,llm:12});assert.equal(summary.bankRecordsSentToModels,false);
 assert.deepEqual(report.errors,[]);assert(report.accessibility.every(r=>!r.violations.length),JSON.stringify(report.accessibility));
 await fs.writeFile(path.join(folder,'report.json'),JSON.stringify({...report,summary},null,2));console.log(JSON.stringify({folder,...report,summary},null,2));
}catch(error){if(page){await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(folder,'failure.private.txt'),await page.locator('body').innerText().catch(()=>''));}throw error;}finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
