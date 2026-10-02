// Real local API, native pointer gestures and persistent verification fixtures. No model calls.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const base='http://127.0.0.1:5190',folder='.local/intent-lab/verification';
await fs.mkdir(folder,{recursive:true});
async function api(path,body,method='POST'){
 const r=await fetch(base+'/lab-api/editor/'+path,body?{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 assert.ok(r.ok,path+': '+r.status);return r.json();
}
const fixtures=JSON.parse(await fs.readFile(folder+'/editor-fixtures.json','utf8').catch(()=>'{}'));
for(const lang of ['es','en','pt']){
 const {graph}=await api('template?kind=app');
 graph.name={es:'Verificación · Incidencia '+lang,en:'Verification · Incident '+lang,pt:'Verificação · Incidência '+lang};
 const old=fixtures[lang]?await api('workflows/'+fixtures[lang]):null;
 const saved=await api('workflows'+(old?'/'+old.id:''),{graph,revision:old?.revision},old?'PUT':'POST');fixtures[lang]=saved.id;
}
await fs.writeFile(folder+'/editor-fixtures.json',JSON.stringify(fixtures,null,2));
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1500,height:1000},acceptDownloads:true});
const page=await context.newPage(),errors=[],checks=[];
let runs=0,blocked=0;
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.route('**/lab-api/editor/workflows/*/run-stream',async route=>{
 const id=new URL(route.request().url()).pathname.split('/').at(-2),{graph}=await api('workflows/'+id);
 if(graph.nodes.some(n=>['triage','jev','context'].includes(n.kind))){blocked++;await route.abort();return;}
 runs++;await route.continue();
});
const labels={
 fit:['Ajustar vista','Fit view','Ajustar vista'],play:['Flujo completo','Full workflow','Fluxo completo'],
 save:['Guardar borrador','Save draft','Salvar rascunho'],close:['Cerrar','Close','Fechar'],
 files:['Mis flujos','My flows','Meus fluxos'],add:['Agregar bloque','Add block','Adicionar bloco'],
 nodeName:['Nombre del bloque','Block name','Nome do bloco'],message:['Texto de respuesta','Response text','Texto de resposta'],
 name:['Nombre del flujo','Flow name','Nome do fluxo'],ready:['Listo para probar','Ready to test','Pronto para testar'],
 remove:['Eliminar bloque','Delete block','Excluir bloco'],export:['Exportar JSON','Export JSON','Exportar JSON'],
 reproduce:['Reproducir error de acceso','Reproduce access error','Reproduzir erro de acesso'],
 undo:['Deshacer','Undo','Desfazer'],redo:['Rehacer','Redo','Refazer'],
};
let i=0;const editor=page.locator('.workflow-editor');
const button=(key,scope=editor)=>scope.getByRole('button',{name:labels[key][i],exact:true});
const node=id=>editor.locator('.react-flow__node[data-id="'+id+'"]');
async function settle(){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))));}
async function fit(){await settle();await button('fit').click();await settle();}
async function closeSide(){for(const side of ['.editor-config','.editor-palette']){if(await editor.locator(side).count())await button('close',editor.locator(side)).click();}}
async function select(id){await node(id).locator('.editor-node-tile').click();}
async function exportGraph(){
 await button('files').click();
 const promise=page.waitForEvent('download');await button('export',editor.locator('dialog')).click();
 const value=JSON.parse(await fs.readFile(await(await promise).path(),'utf8'));
 await button('close',editor.locator('dialog')).click();return value;
}
async function drag(source,target){
 await source.click({trial:true});await target.click({trial:true});await settle();
 const a=await source.boundingBox(),b=await target.boundingBox();assert.ok(a&&b);
 await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();
 await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:16});await page.mouse.up();
}
async function scan(viewport){
 const result=await new AxeBuilder({page}).analyze();checks.push({language:['es','en','pt'][i],viewport,violations:result.violations.map(v=>v.id)});
 assert.equal(result.violations.length,0,JSON.stringify(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))));
}
try{
 for(const [index,lang] of ['es','en','pt'].entries()){
  i=index;await page.setViewportSize({width:1500,height:1000});
  await page.goto(base+'/?view=flows&mode=editor&lang='+lang+'&workflow='+fixtures[lang]);
  await expect(editor.locator('[data-block-kind]')).toHaveCount(6);
  await expect(editor.locator('.editor-case-card:visible')).toHaveCount(6);
  assert.equal(runs,i*3);
  assert.ok(!/\bLAB\b/.test(await editor.innerText()));
  // Start contains the customer question and the same guarded Play action as the toolbar.
  await select('start');await expect(editor.locator('#editor-message')).toBeVisible();
  await button('play',editor.locator('.editor-config')).click();
  await expect(editor.locator('[data-editor-state="missing_incident"]')).toBeVisible();
  await select('start');await button('reproduce').click();
  await editor.locator('#editor-message').fill('Verificación de acceso');
  const reference=await editor.locator('.editor-incident code').innerText();assert.match(reference,/^APP-[A-F0-9]{8}$/);
  await button('play',editor.locator('.editor-toolbar')).click();
  await expect(editor.locator('[data-editor-state="information"]')).toBeVisible();
  await expect(editor.locator('.editor-trace li')).toHaveCount(5);
  await expect(node('failed').locator('[data-stage-status]')).toHaveAttribute('data-stage-status','ok');
  await expect(editor.locator('.editor-trace b.yes')).toHaveCount(1);
  assert.ok((await editor.locator('.editor-result').innerText()).includes(reference));
  assert.equal(await editor.locator('.react-flow__edge path[style*="stroke: rgb(57, 116, 91)"]').count(),4);
  // Inserting + on an existing edge preserves the following step.
  await closeSide();await fit();
  await editor.locator('[data-insert-edge="e4"]').click();
  await editor.locator('[data-palette-kind="notify"]').click();
  const addedNotify=await editor.locator('.editor-config-heading code').innerText();
  let draft=await exportGraph();
  assert.equal(draft.edges.find(e=>e.source==='notify').target,addedNotify);
  assert.equal(draft.edges.find(e=>e.source===addedNotify).target,'result');
  // Native drag/drop from the palette to empty canvas, then configure by clicking the node.
  await closeSide();await button('add').click();
  const paletteItem=editor.locator('[data-palette-kind="response"]'),box=await editor.locator('.editor-canvas').boundingBox();
  await paletteItem.scrollIntoViewIfNeeded();const a=await paletteItem.boundingBox();
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();
  await page.mouse.move(a.x+a.width/2+12,a.y+a.height/2,{steps:4});
  await page.mouse.move(box.x+box.width*.53,box.y+box.height*.73,{steps:18});await page.mouse.up();
  await expect(editor.locator('[data-block-kind]')).toHaveCount(8);
  const added=await editor.locator('.editor-config-heading code').innerText();
  await editor.getByLabel(labels.nodeName[i],{exact:true}).fill('Verificación · '+lang);
  await editor.getByLabel(labels.message[i],{exact:true}).fill('Conexión y respuesta comprobadas · '+lang);
  await closeSide();await fit();
  // A pointer connection replaces the output's old target, as in the visual editor.
  await drag(node(addedNotify).locator('.source'),node(added).locator('.target'));
  draft=await exportGraph();assert.equal(draft.edges.find(e=>e.source===addedNotify).target,added);
  await select('result');await button('remove').click();await closeSide();await fit();
  // Real movement, grouped undo/redo and saved coordinates.
  const before=(await exportGraph()).nodes.find(n=>n.id===added).position;
  const tile=await node(added).locator('.editor-node-tile').boundingBox();
  await page.mouse.move(tile.x+tile.width/2,tile.y+tile.height/2);await page.mouse.down();
  await page.mouse.move(tile.x+tile.width/2+75,tile.y+tile.height/2-45,{steps:12});await page.mouse.up();
  const moved=(await exportGraph()).nodes.find(n=>n.id===added).position;assert.notDeepEqual(moved,before);
  await button('undo').click();assert.deepEqual((await exportGraph()).nodes.find(n=>n.id===added).position,before);
  await button('redo').click();assert.deepEqual((await exportGraph()).nodes.find(n=>n.id===added).position,moved);
  await button('save').click();await expect(editor.locator('.editor-validation')).toContainText(labels.ready[i]);
  const saved=await api('workflows/'+fixtures[lang]);assert.deepEqual(saved.graph.nodes.find(n=>n.id===added).position,moved);
  await fit();await select('start');await editor.locator('#editor-message').fill('Verificación de repetición');
  await button('play',editor.locator('.editor-config')).click();
  await expect(editor.locator('.editor-result')).toContainText('Conexión y respuesta comprobadas · '+lang);
  await expect(editor.locator('.editor-trace li')).toHaveCount(6);
  assert.equal((await api('notifications')).notifications.filter(n=>n.reference===reference).length,2);
  assert.deepEqual(await exportGraph(),saved.graph);
  await closeSide();await fit();
  await editor.locator('.editor-trace li').nth(1).getByRole('button').click();
  await scan('desktop');
  await page.screenshot({path:folder+'/studio-'+lang+'.png',fullPage:true});
  await page.setViewportSize({width:390,height:1000});await scan('mobile');await closeSide();await fit();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:folder+'/studio-'+lang+'-mobile.png',fullPage:true});
  await page.reload();await expect(editor.getByLabel(labels.name[i],{exact:true})).toHaveValue(saved.graph.name[lang]);
  assert.equal(runs,(i+1)*3,'Reload must not call providers or execute');
  await page.setViewportSize({width:1500,height:1000});
  // Choosing a case changes conversation/parameters, preserving every saved block and edge.
  const beforeCase=await exportGraph();
  await editor.locator('[data-case-intent="unrecognized-charge"]').click();
  await expect(editor.locator('.editor-prior')).toBeVisible();
  await expect(editor.locator('#editor-message')).not.toHaveValue('');
  await editor.locator('.editor-case-detail summary').click();
  await expect(editor.locator('.editor-case-detail ol li')).not.toHaveCount(0);
  assert.deepEqual(await exportGraph(),beforeCase);
  // Open the shared master for model instructions; merely reading it does not run providers.
  await page.goto(base+'/?view=flows&mode=editor&lang='+lang);
  await expect(editor.locator('[data-block-kind]')).toHaveCount(26);
  await closeSide();await fit();await select('context');
  await editor.getByLabel(['Instrucciones adicionales','Additional instructions','Instruções adicionais'][i],{exact:true}).fill('Verificación de instrucciones '+lang);
  await editor.getByLabel(['Contexto de referencia','Reference context','Contexto de referência'][i],{exact:true}).fill('Verificación de contexto '+lang);
  const configured=await exportGraph();assert.equal(configured.nodes.find(n=>n.id==='context').config.instructions[lang],'Verificación de instrucciones '+lang);
  assert.equal(runs,(i+1)*3);
 }
 assert.equal(blocked,0);assert.deepEqual(errors,[]);
 await fs.writeFile(folder+'/editor-ui.json',JSON.stringify({runs,checks,errors,blocked},null,2));
 console.log(JSON.stringify({runs,checks,errors,blocked}));
}catch(error){await page.screenshot({path:folder+'/studio-failure.png',fullPage:true});console.error(JSON.stringify({errors,body:(await page.locator('body').innerText()).slice(-4000)}));throw error;}finally{await browser.close();}
