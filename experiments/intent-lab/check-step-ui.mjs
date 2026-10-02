// Real API and browser. Only the local incident flow runs; no model calls are allowed.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const base='http://127.0.0.1:5190',folder='.local/intent-lab/verification';
await fs.mkdir(folder,{recursive:true});
async function api(path,body,method='POST'){
 const r=await fetch(base+'/lab-api/editor/'+path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 assert.ok(r.ok,path+': '+r.status);return r.json();
}
const fixtures=JSON.parse(await fs.readFile(folder+'/step-fixtures.json','utf8').catch(()=>'{}'));
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1500,height:1000}}),page=await context.newPage();
const errors=[],checks=[];let writes=0,blocked=0;
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.route('**/lab-api/editor/**',async route=>{
 const r=route.request(),url=new URL(r.url());
 if(r.method()==='POST'&&/\/(run|run-stream|advance)$/.test(url.pathname)){
  let record;
  if(url.pathname.endsWith('/advance')){const state=await api('executions/'+url.pathname.split('/').at(-2));record={graph:state.workflow};}
  else record=await api('workflows/'+url.pathname.split('/').at(-2));
  if(record.graph.nodes.some(n=>['triage','jev','context'].includes(n.kind))){blocked++;await route.abort();return;}
  writes++;
 }
 await route.continue();
});
const labels={
 step:['Paso a paso','Step by step','Passo a passo'],full:['Flujo completo','Full workflow','Fluxo completo'],
 close:['Cerrar','Close','Fechar'],fit:['Ajustar vista','Fit view','Ajustar vista'],
 reproduce:['Reproducir error de acceso','Reproduce access error','Reproduzir erro de acesso'],
 name:['Nombre del bloque','Block name','Nome do bloco'],connections:['Conexiones de salida · Siguiente','Output connections · Next','Conexões de saída · Próximo'],
};
let i=0;const editor=page.locator('.workflow-editor');
const button=(key,scope=editor)=>scope.getByRole('button',{name:labels[key][i],exact:true});
const node=id=>editor.locator('.react-flow__node[data-id="'+id+'"]');
async function settle(){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))));}
async function closeSide(){for(const side of ['.editor-config','.editor-palette'])if(await editor.locator(side).count())await button('close',editor.locator(side)).click();}
async function fit(){await settle();await button('fit').click();await settle();}
async function scan(lang,viewport){const result=await new AxeBuilder({page}).analyze();checks.push({lang,viewport,violations:result.violations.map(v=>v.id)});assert.deepEqual(result.violations.map(v=>v.id),[]);}
try{
 for(const [index,lang] of ['es','en','pt'].entries()){
  i=index;await page.setViewportSize({width:1500,height:1000});
  const {graph}=await api('template?kind=app');graph.name={es:'Verificación · Pasos '+lang,en:'Verification · Steps '+lang,pt:'Verificação · Passos '+lang};
  const old=fixtures[lang]?await api('workflows/'+fixtures[lang]):null;
  const saved=await api('workflows'+(old?'/'+old.id:''),{graph,revision:old?.revision},old?'PUT':'POST');fixtures[lang]=saved.id;
  await fs.writeFile(folder+'/step-fixtures.json',JSON.stringify(fixtures,null,2));
  await page.goto(base+'/?view=flows&mode=editor&lang='+lang+'&workflow='+saved.id);
  await expect(editor.locator('[data-block-kind]')).toHaveCount(6);
  await button('reproduce').click();
  await closeSide();await fit();await node('logs').locator('.editor-node-tile').click();
  await editor.getByLabel(labels.name[i],{exact:true}).fill('Lectura verificada · '+lang);
  // The first Step click saves the edited graph and runs Start only.
  await button('step',editor.locator('.editor-toolbar')).click();
  await expect(editor.locator('.editor-trace li')).toHaveCount(1);
  await expect(editor.locator('[data-execution-phase="paused"]')).toBeVisible();
  let state=await api('executions/'+new URL(page.url()).searchParams.get('execution'));
  assert.equal(state.execution.next_node_id,'logs');assert.equal(state.workflow_revision,saved.revision+1);
  assert.equal((await api('workflows/'+saved.id)).graph.nodes.find(n=>n.id==='logs').label[lang],'Lectura verificada · '+lang);
  await fit();await expect(editor.locator('[data-step-edge="e0"]')).toBeEnabled();
  await expect(editor.locator('[data-step-node="notify"]')).toBeDisabled();
  await editor.locator('[data-step-edge="e0"]').click();
  await expect(editor.locator('.editor-trace li')).toHaveCount(2);
  const beforeReload=writes,url=page.url();await page.reload();
  await expect(editor.locator('.editor-trace li')).toHaveCount(2);assert.equal(page.url(),url);assert.equal(writes,beforeReload);
  await closeSide();await fit();await editor.locator('[data-step-node="failed"]').click();
  await expect(editor.locator('.editor-trace li')).toHaveCount(3);
  await expect(editor.locator('.editor-trace b.yes')).toHaveCount(1);
  await expect(editor.locator('[data-step-edge="e2"]')).toBeEnabled();await expect(editor.locator('[data-step-edge="e3"]')).toBeDisabled();
  await button('full',editor.locator('.editor-toolbar')).click();
  await expect(editor.locator('.editor-trace li')).toHaveCount(5);
  state=await api('executions/'+new URL(page.url()).searchParams.get('execution'));
  assert.equal(state.execution.phase,'completed');assert.ok(state.notification);assert.deepEqual(state.trace.map(r=>r.node_id),['start','logs','failed','notify','result']);
  await scan(lang,'desktop');await page.screenshot({path:folder+'/steps-'+lang+'.png',fullPage:true});
  await page.setViewportSize({width:390,height:1000});await scan(lang,'mobile');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1500,height:1000});await fit();
  // Invalid drafts show concrete missing connections, never a silently disabled Play.
  await node('start').locator('.editor-node-tile').click();await editor.locator('#editor-message').fill('Verificar las conexiones');
  await editor.getByLabel(labels.connections[i],{exact:true}).selectOption('');
  const beforeInvalid=writes;await button('full',editor.locator('.editor-toolbar')).click();
  await expect(editor.locator('.editor-errors')).toBeVisible();assert.equal(writes,beforeInvalid);
 }
 assert.equal(blocked,0);assert.equal(writes,12);assert.deepEqual(errors,[]);
 await fs.writeFile(folder+'/step-ui.json',JSON.stringify({writes,checks,errors,blocked},null,2));console.log(JSON.stringify({writes,checks,errors,blocked}));
}catch(error){await page.screenshot({path:folder+'/steps-failure.png',fullPage:true});console.error(JSON.stringify({errors,body:(await page.locator('body').innerText()).slice(-3500)}));throw error;}finally{await browser.close();}
