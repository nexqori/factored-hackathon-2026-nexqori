// Real React/FastAPI + authenticated local PostgreSQL bank. Controlled Jev/Luna;
// no external provider traffic and no financial actions. Credentials stay local.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn,spawnSync} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const bank='http://localhost:5180',base='http://localhost:5191',folder=path.resolve('.local/intent-lab/verification');
const latest=JSON.parse(await fs.readFile('.local/verification/cases/latest-manual.json','utf8'));
const pack=JSON.parse(await fs.readFile(path.join(latest.path,'credentials.private.json'),'utf8'));
assert(pack.cases.length>=3,'Run npm run test:cases:prepare first');
const accounts=pack.cases.slice(0,3);
await fs.mkdir(folder,{recursive:true});
assert(!(await fetch(base+'/lab-api/health').then(()=>true).catch(()=>false)),'Port 5191 must be free');
assert((await fetch(bank+'/api/health')).ok,'Start the local bank first');
const data=await fs.mkdtemp(path.join(folder,'bank-ui-'));
const python=process.env.NEXQORI_LAB_PYTHON||path.resolve(process.platform==='win32'?'.local/intent-lab-venv/Scripts/python.exe':'.local/intent-lab-venv/bin/python');
const server=spawn(python,['experiments/intent-lab/tests/master_ui_server.py'],{env:{...process.env,PYTHONPATH:[path.resolve('.'),path.resolve('experiments/intent-lab')].join(path.delimiter),NEXQORI_LAB_DATA:data,NEXQORI_MASTER_UI_CHECK:'1'},windowsHide:true,stdio:['ignore','ignore','pipe']});
let serverOutput='';server.stderr.on('data',chunk=>{serverOutput+=chunk.toString();});
let browser,page;const runs=[],checks=[],errors=[],auditIds=[];
const words={full:['Flujo completo','Full workflow','Fluxo completo'],expand:['Ampliar panel','Expand panel','Ampliar painel']};
async function value(){const id=new URL(page.url()).searchParams.get('execution');const r=await page.request.get(base+'/api/lab-api/editor/executions/'+id);assert.equal(r.status(),200);return r.json();}
try{
 for(let i=0;i<100;i++){if(await fetch(base+'/lab-api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error(serverOutput);await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 let protectedRun;
 for(const [caseIndex,account] of accounts.entries()){
  const context=await browser.newContext({viewport:{width:1700,height:1100}});page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));
  const login=await page.request.post(bank+'/api/auth/login',{data:{identifier:account.email,password:account.password},headers:{Origin:bank}});assert.equal(login.status(),200);
  const before=await (await page.request.get(bank+'/api/bootstrap')).json();
  if(protectedRun){const denied=await page.request.get(base+'/api/lab-api/editor/executions/'+protectedRun);assert.equal(denied.status(),404);}
  for(const [i,language] of ['es','en','pt'].entries()){
   await page.goto(base+'/?view=flows&mode=editor&lang='+language);
   const editor=page.locator('.workflow-editor');await expect(editor.locator('[data-block-kind]')).toHaveCount(24);
   await editor.locator('[data-bank-connect]').click();
   const dropdown=editor.locator('[data-bank-transaction]');await expect(dropdown).toBeEnabled();
   assert.deepEqual(await dropdown.locator('option').evaluateAll(options=>options.map(o=>o.value).filter(Boolean)),[account.transactionId]);
   const missingSelection=caseIndex===0&&language==='es';
   if(!missingSelection)await dropdown.selectOption(account.transactionId);
   const marker=['charge','incorrect','payment'][caseIndex];
   await editor.locator('#editor-message').fill('['+marker+'] '+account.messages[language]);
   await editor.locator('.editor-toolbar').getByRole('button',{name:words.full[i],exact:true}).click();
   await expect(editor.locator('[data-execution-phase]')).toHaveAttribute('data-execution-phase',missingSelection||caseIndex===1?'waiting_reply':'completed');
   let result=await value();assert.equal(result.jev.intent,account.intent);assert.equal(result.bank_context.owner_id,account.userId);
   if(missingSelection){
    assert.ok(result.missing_fields.includes('transaction_id'));
    await editor.locator('[data-bank-connect]').click();await editor.locator('[data-bank-transaction]').selectOption(account.transactionId);
    assert.equal(await editor.locator('#editor-message').inputValue(),'');
    await editor.locator('.editor-toolbar').getByRole('button',{name:words.full[i],exact:true}).click();
    await expect(editor.locator('[data-execution-phase]')).toHaveAttribute('data-execution-phase','completed');result=await value();
    assert.equal(result.messages.filter(m=>m.role==='user').length,1,'Selecting evidence must not invent customer messages');
   }
   assert.equal(result.bank_evidence.source,'authenticated_bank');
   assert.ok(result.verified_facts.some(f=>f.reference_id===account.transactionId));
   assert.deepEqual(result.executed_operations,[]);
   // Inspecting simple/JSON results and resizing must not execute reads or models.
   if(!await editor.locator('.editor-trace').count())await editor.locator('.editor-dock-tabs button').nth(1).click();
   await editor.locator('.editor-trace button').filter({hasText:result.workflow.nodes.find(n=>n.id==='context').label[language]}).last().click();
   await expect(editor.locator('[data-simple-result="context"]')).toBeVisible();
   await expect(editor.locator('.result-facts')).not.toHaveCount(0);
   await expect(editor.locator('.editor-config .bank-read')).not.toHaveCount(0);
   const initialWidth=(await editor.locator('.editor-config').boundingBox()).width;
   await editor.getByRole('button',{name:words.expand[i],exact:true}).click();
   assert.ok((await editor.locator('.editor-config').boundingBox()).width>initialWidth);
   await editor.locator('.editor-inspector-tabs button').nth(2).click();
   await expect(editor.locator('.editor-config pre')).toContainText(account.transactionId);
   await editor.locator('.editor-inspector-tabs button').nth(1).click();
   assert.deepEqual(await value(),result,'Inspection cannot change a checkpoint');
   for(const size of [{width:1700,height:1100},{width:390,height:1100}]){
    await page.setViewportSize(size);const scan=await new AxeBuilder({page}).analyze();const violations=scan.violations.map(v=>v.id);checks.push({case:account.id,language,width:size.width,violations});assert.deepEqual(violations,[]);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   }
   await page.setViewportSize({width:1700,height:1100});
   if(language==='es')await page.screenshot({path:path.join(folder,'bank-context-'+account.id+'.png'),fullPage:true});
   if(caseIndex===1){
    assert.deepEqual(result.missing_fields,['difference']);
    await editor.locator('[data-respond-now]').click();
    await editor.locator('#editor-message').fill({es:'Esperaba 100 MXN; la diferencia es 359,90 MXN.',en:'I expected 100 MXN; the difference is 359.90 MXN.',pt:'Esperava 100 MXN; a diferença é 359,90 MXN.'}[language]);
    await editor.locator('.editor-toolbar').getByRole('button',{name:words.full[i],exact:true}).click();
    await expect(editor.locator('[data-execution-phase]')).toHaveAttribute('data-execution-phase','completed');result=await value();
    assert.deepEqual(result.missing_fields,[]);assert.equal(result.trace.filter(t=>t.kind==='intake').length,1);assert.equal(result.trace.filter(t=>t.kind==='jev').length,1);
   }
   assert.equal(result.state,'review_in_bank');assert.deepEqual(result.executed_operations,[]);
   for(const read of result.executed_tools)auditIds.push({id:read.auditEventId,owner:account.userId});
   protectedRun=result.execution.id;runs.push({case:account.id,language,state:result.state,verified:result.verified_facts.length,reads:result.executed_tools.length,questionsAnswered:result.execution.turn,activeMs:result.latency_ms});
   await page.reload();assert.equal((await value()).execution.id,result.execution.id);
  }
  const after=await (await page.request.get(bank+'/api/bootstrap')).json();for(const key of ['products','transactions','requests'])assert.deepEqual(after[key],before[key],'Bank '+key+' must remain unchanged');
  await context.close();
 }
 // Check audit records independently inside PostgreSQL, without credentials in output.
 const payload=Buffer.from(JSON.stringify(auditIds)).toString('base64');
 const sqlCheck=spawnSync('docker',['compose','exec','-T','-e','NEXQORI_AUDIT_CHECK='+payload,'api','python','-'],{windowsHide:true,encoding:'utf8',input:`import os,json,base64\nfrom backend.db import make_sessions,make_engine\nfrom backend.models import AuditEvent\nrows=json.loads(base64.b64decode(os.environ['NEXQORI_AUDIT_CHECK']))\nwith make_sessions(make_engine())() as db:\n for row in rows:\n  event=db.get(AuditEvent,row['id'])\n  assert event and event.user_id==row['owner'] and event.actor_id==row['owner'] and event.action.startswith('tool_')\nprint(len(rows))\n`});
 assert.equal(sqlCheck.status,0,'PostgreSQL audit verification failed');assert.equal(Number(sqlCheck.stdout.trim()),auditIds.length);
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(folder,'bank-context-ui.json'),JSON.stringify({scope:'Real local authenticated bank; controlled Jev/Luna, no financial operations',fixtureRun:pack.runId,runs,checks,errors,postgresAuditReads:auditIds.length},null,2));
 console.log(JSON.stringify({runs:runs.length,accessibility:checks.length,errors,postgresAuditReads:auditIds.length}));
}catch(error){if(page&&!page.isClosed())await page.screenshot({path:path.join(folder,'bank-context-failure.png'),fullPage:true});throw error;}finally{if(browser)await browser.close();server.kill();}
