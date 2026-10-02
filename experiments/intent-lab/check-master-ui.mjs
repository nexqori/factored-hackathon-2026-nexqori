// Same FastAPI interpreter and React bundle, isolated records and controlled model fixtures.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const base='http://127.0.0.1:5191',folder=path.resolve('.local/intent-lab/verification');
await fs.mkdir(folder,{recursive:true});
const data=await fs.mkdtemp(path.join(folder,'master-ui-'));
const python=process.env.NEXQORI_LAB_PYTHON||path.resolve(process.platform==='win32'?'.local/intent-lab-venv/Scripts/python.exe':'.local/intent-lab-venv/bin/python');
// Refuse to attach to a running development server or to test the live provider keys.
const occupied=await fetch(base+'/lab-api/health').then(()=>true).catch(()=>false);
assert.equal(occupied,false,'Port 5191 must be free for the isolated verification server.');
const server=spawn(python,['experiments/intent-lab/tests/master_ui_server.py'],{env:{...process.env,PYTHONPATH:[path.resolve('.'),path.resolve('experiments/intent-lab')].join(path.delimiter),NEXQORI_LAB_DATA:data,NEXQORI_MASTER_UI_CHECK:'1'},windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverOutput='';server.stderr.on('data',chunk=>{serverOutput+=chunk.toString();});
let browser,page;
const checks=[],errors=[],results=[],inspections=[],executionRequests=[];
async function api(route){const response=await fetch(base+'/lab-api/editor/'+route);assert.ok(response.ok);return response.json();}
const words={full:['Flujo completo','Full workflow','Fluxo completo'],step:['Paso a paso','Step by step','Passo a passo'],close:['Cerrar','Close','Fechar'],fit:['Ajustar vista','Fit view','Ajustar vista'],chat:['Conversación','Conversation','Conversa'],clear:['Nueva conversación','New conversation','Nova conversa'],save:['Guardar borrador','Save draft','Salvar rascunho'],restore:['Restaurar reglas de la ejecución','Restore execution rules','Restaurar regras da execução'],instructions:['Instrucciones del bloque','Block instructions','Instruções do bloco']};
try{
 for(let i=0;i<100;i++){if(await fetch(base+'/lab-api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error(serverOutput);await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1700,height:1000}});page=await context.newPage();
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{if(request.method()==='POST'&&/\/(run-stream|advance|replay)$/.test(new URL(request.url()).pathname))executionRequests.push(request.url());});
 const editor=page.locator('.workflow-editor');
 const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))));
 for(const [i,language] of ['es','en','pt'].entries()){
  for(const scenario of ['charge','app','human']){
   await page.goto(base+'/?view=flows&mode=editor&lang='+language);
   await expect(editor.locator('[data-block-kind]')).toHaveCount(26);
   const masterId=new URL(page.url()).searchParams.get('workflow'),before=await api('workflows/'+masterId);
   assert.equal(before.graph.nodes.filter(n=>n.kind==='contract').length,6);
   assert.equal(before.graph.edges.filter(e=>e.source==='case_route').length,7);
   await editor.locator('#editor-message').fill({charge:'[charge] No reconozco un cargo de Comercio Alfa.',app:'[app] La app se cierra al pagar. Ya reinicié.',human:'[human] La atención no resuelve mi problema. Necesito una persona.'}[scenario]);
   if(scenario==='charge'){
    for(let step=1;step<=4;step++){
     await editor.locator('.editor-toolbar').getByRole('button',{name:words.step[i],exact:true}).click();
     await expect(editor.locator('.editor-trace li')).toHaveCount(step);
     await expect(editor.locator('[data-execution-phase="paused"]')).toBeVisible();
    }
    const checkpoint=new URL(page.url()).searchParams.get('execution');assert.ok(checkpoint);
    const paused=await api('executions/'+checkpoint);
    assert.equal(paused.execution.next_node_id,'case_route');
    if(await editor.locator('.editor-palette').count())await editor.locator('.editor-palette').getByRole('button',{name:words.close[i],exact:true}).click();
    const executionsBeforeInspection=executionRequests.length;
    for(const id of ['context','jev','contract_0']){
     await settle();await editor.getByRole('button',{name:words.fit[i],exact:true}).click();await settle();
     await editor.locator('.react-flow__node[data-id="'+id+'"] .editor-node-tile').click();
     assert.equal(new URL(page.url()).searchParams.get('execution'),checkpoint,'Selecting '+id+' must retain the execution');
     await expect(editor.locator('.editor-trace li')).toHaveCount(4);
    }
    // A tiny pointer movement while clicking must also preserve the paused run.
    const tile=editor.locator('.react-flow__node[data-id="contract_0"] .editor-node-tile'),box=await tile.boundingBox();
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+3,box.y+box.height/2+2,{steps:3});await page.mouse.up();await settle();
    assert.equal(new URL(page.url()).searchParams.get('execution'),checkpoint,'Pointer movement must retain the execution');
    assert.deepEqual(await api('executions/'+checkpoint),paused);
    await editor.locator('.editor-toolbar').getByRole('button',{name:words.save[i],exact:true}).click();
    await expect(editor.locator('.editor-save-state.is-dirty')).toHaveCount(0);
    await page.reload();await expect(editor.locator('.editor-trace li')).toHaveCount(4);
    assert.equal(new URL(page.url()).searchParams.get('execution'),checkpoint);
    if(await editor.locator('.editor-palette').count())await editor.locator('.editor-palette').getByRole('button',{name:words.close[i],exact:true}).click();
    await settle();await editor.getByRole('button',{name:words.fit[i],exact:true}).click();await settle();
    await editor.locator('.react-flow__node[data-id="jev"] .editor-node-tile').click();
    const catalog=editor.locator('.case-taxonomy');
    await expect(catalog.locator('[data-classification-case]')).toHaveCount(24);
    for(const [family,count] of Object.entries({problem:6,query:8,service:7,clarification:3}))await expect(catalog.locator('[data-case-family="'+family+'"] [data-classification-case]')).toHaveCount(count);
    await expect(catalog.locator('.is-classified')).toHaveAttribute('data-classification-case','unrecognized-charge');
    await catalog.locator('.catalog-filters button').nth(1).click();await expect(catalog.locator('[data-classification-case]')).toHaveCount(9);
    await catalog.locator('[data-classification-case="unrecognized-charge"] summary').click();
    const app=(await api('cases?language='+language)).cases.find(c=>c.intent==='app-support');
    await catalog.getByRole('textbox').fill(app.title);await expect(catalog.locator('[data-classification-case]')).toHaveCount(1);
    await catalog.getByRole('textbox').fill('');await catalog.locator('.catalog-filters button').first().click();
    await catalog.locator('h3').scrollIntoViewIfNeeded();
    const axe=await new AxeBuilder({page}).analyze();checks.push({language,view:'classification',violations:axe.violations.map(v=>v.id)});assert.deepEqual(axe.violations.map(v=>v.id),[]);
    await page.screenshot({path:path.join(folder,'master-classification-'+language+'.png'),fullPage:true});
    assert.equal(executionRequests.length,executionsBeforeInspection,'Inspecting, moving, saving and reloading must not run any block');
    assert.deepEqual(await api('executions/'+checkpoint),paused);
    // A rule edit keeps outputs but blocks continuation until the original rules are restored.
    const instructions=editor.locator('.editor-config textarea').first(),oldInstructions=await instructions.inputValue();
    await instructions.fill(oldInstructions+' [verification]');await expect(editor.locator('.rules-changed')).toBeVisible();
    assert.equal(new URL(page.url()).searchParams.get('execution'),checkpoint);await expect(editor.locator('.editor-trace li')).toHaveCount(4);
    await expect(editor.locator('[data-inspector-step="jev"]')).toBeDisabled();
    await editor.locator('.rules-changed button').first().click();await expect(editor.locator('.rules-changed')).toHaveCount(0);
    assert.equal(executionRequests.length,executionsBeforeInspection);
    // Explicit play repeats only Jev with saved upstream inputs; viewing it never did.
    await editor.locator('[data-inspector-step="jev"]').click();
    await expect.poll(()=>new URL(page.url()).searchParams.get('execution')).not.toBe(checkpoint);
    await expect(editor.locator('[data-execution-phase="paused"]')).toBeVisible();
    await expect(editor.locator('.editor-trace li')).toHaveCount(4);
    await expect(editor.locator('.editor-trace li[data-reused="true"]')).toHaveCount(3);
    const childId=new URL(page.url()).searchParams.get('execution'),child=await api('executions/'+childId);
    assert.equal(child.replayed_from.execution_id,checkpoint);assert.equal(child.execution.next_node_id,'case_route');
    assert.equal(executionRequests.length,executionsBeforeInspection+1);assert.ok(executionRequests.at(-1).endsWith('/replay'));
    assert.deepEqual(await api('executions/'+checkpoint),paused);
    await page.reload();await expect(editor.locator('.editor-trace li')).toHaveCount(4);assert.equal(new URL(page.url()).searchParams.get('execution'),childId);
    assert.equal(executionRequests.length,executionsBeforeInspection+1);
    inspections.push({language,checkpoint:'preserved',steps:4,categories:24,cachedSteps:3,explicitReplay:1});
   }
   await editor.locator('.editor-toolbar').getByRole('button',{name:words.full[i],exact:true}).click();
   const stateSelector=scenario==='charge'?'waiting_reply':'completed';
   await expect(editor.locator('[data-execution-phase="'+stateSelector+'"]')).toBeVisible();
   let value=await api('executions/'+new URL(page.url()).searchParams.get('execution'));
   assert.equal(value.contract.intent||value.jev.intent,{charge:'unrecognized-charge',app:'app-support',human:'service-feedback'}[scenario]);
   if(scenario==='charge'){
    const id=value.execution.id;
    assert.equal(value.execution.next_node_id,'context');
    await page.reload();await expect(editor.locator('[data-execution-phase="waiting_reply"]')).toBeVisible();
    assert.equal(new URL(page.url()).searchParams.get('execution'),id);
    await editor.locator('#editor-message').fill('Comercio Alfa, 1 de octubre de 2026, 100 MXN.');
    await editor.locator('.editor-toolbar').getByRole('button',{name:words.full[i],exact:true}).click();
    await expect(editor.locator('[data-execution-phase="completed"]')).toBeVisible();
    value=await api('executions/'+id);
    assert.equal(value.trace.filter(r=>r.kind==='triage').length,1);assert.equal(value.trace.filter(r=>r.kind==='jev').length,1);
    assert.equal(value.trace.filter(r=>r.kind==='context').length,2);
   }
   assert.equal(value.state,scenario==='human'?'human_review':'review_in_bank');
   assert.equal(value.activation_plan.every(a=>a.executed===false),true);
   assert.equal(value.notification,null);assert.deepEqual(value.executed_operations,[]);assert.deepEqual(value.executed_tools,[]);
   assert.equal((await api('notifications')).notifications.length,0);
   const required={charge:'prepare-refund-review',app:'notify-confirmed-incident',human:'prepare-handoff'}[scenario];
   await expect(editor.locator('[data-activation="'+required+'"]')).toBeVisible();
   assert.equal(value.workflow_id,masterId);assert.deepEqual(value.workflow,before.graph);
   results.push({language,scenario,state:value.state,activation:required,steps:value.trace.length});
   if(scenario==='charge'){
    for(const size of [{width:1700,height:1000},{width:390,height:1000}]){
     await page.setViewportSize(size);await settle();const axe=await new AxeBuilder({page}).analyze();
     checks.push({language,width:size.width,violations:axe.violations.map(v=>v.id)});assert.deepEqual(axe.violations.map(v=>v.id),[]);
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    }
    await page.setViewportSize({width:1700,height:1000});
   }
  }
  // Inspect the complete diagram with the inspector and result dock closed.
  for(const selector of ['.editor-config','.editor-palette'])if(await editor.locator(selector).count())await editor.locator(selector).getByRole('button',{name:words.close[i],exact:true}).click();
  await editor.locator('.editor-dock-tabs').getByRole('button',{name:words.close[i],exact:true}).click();
  await settle();await editor.getByRole('button',{name:words.fit[i],exact:true}).click();await settle();
  await expect(editor.locator('.react-flow__edge')).toHaveCount(36);
  await page.screenshot({path:path.join(folder,'master-diagram-'+language+'.png'),fullPage:true});
 }
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(folder,'master-ui.json'),JSON.stringify({results,inspections,checks,errors},null,2));
 console.log(JSON.stringify({results,inspections,checks,errors}));
}catch(error){if(page)await page.screenshot({path:path.join(folder,'master-failure.png'),fullPage:true});console.error(serverOutput);throw error;}finally{if(browser)await browser.close();server.kill();}
