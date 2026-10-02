// Real local API and saved graphs; no model calls. Reuses named verification fixtures.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const base='http://127.0.0.1:5190', folder='.local/intent-lab/verification';
await fs.mkdir(folder,{recursive:true});
async function api(path,body,method='POST') {
  const response=await fetch(base+'/lab-api/editor/'+path,body?{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  assert.ok(response.ok,`${path}: ${response.status}`);return response.json();
}
const fixtures=JSON.parse(await fs.readFile(folder+'/editor-fixtures.json','utf8').catch(()=>'{}'));
for(const language of ['es','en','pt']) {
  const {graph}=await api('template?kind=app');
  graph.name={es:'Verificación · Incidencia '+language,en:'Verification · Incident '+language,pt:'Verificação · Incidência '+language};
  let existing;
  if(fixtures[language])existing=await api('workflows/'+fixtures[language]);
  const record=await api('workflows'+(existing?'/'+existing.id:''),{graph,revision:existing?.revision},existing?'PUT':'POST');
  fixtures[language]=record.id;
}
await fs.writeFile(folder+'/editor-fixtures.json',JSON.stringify(fixtures,null,2));
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1500,height:1100},acceptDownloads:true});
const page=await context.newPage(),errors=[],checks=[];
let runs=0,blocked=0;
page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',dialog=>dialog.accept());
await page.route('**/lab-api/editor/workflows/*/run',async route=>{
  const request=route.request(),id=new URL(request.url()).pathname.split('/').at(-2);
  const {graph}=await api('workflows/'+id);
  if(graph.nodes.some(n=>n.kind==='jev'||n.kind==='context')) {blocked++;await route.abort();return;}
  runs++;await route.continue();
});
try {
  for(const [i,lang] of ['es','en','pt'].entries()) {
    await page.setViewportSize({width:1500,height:1100});
    await page.goto(`${base}/?view=flows&mode=editor&lang=${lang}&workflow=${fixtures[lang]}`);
    const editor=page.locator('.workflow-editor');
    await expect(editor.locator('[data-block-kind]')).toHaveCount(6);
    assert.equal(runs,i*3,'Opening a saved workflow must not run it');
    const play=editor.getByRole('button',{name:['Probar flujo','Test flow','Testar fluxo'][i],exact:true});
    await play.click();
    await editor.locator('[data-editor-state="missing_incident"]').waitFor();
    await editor.getByRole('button',{name:['Reproducir error de acceso','Reproduce access error','Reproduzir erro de acesso'][i],exact:true}).click();
    const reference=await editor.locator('.editor-incident code').innerText();
    assert.match(reference,/^APP-[A-F0-9]{8}$/);
    await play.click();
    await editor.locator('[data-editor-state="information"]').waitFor();
    await expect(editor.locator('.editor-trace li')).toHaveCount(5);
    assert.match(await editor.locator('.editor-result').innerText(),new RegExp(reference));

    // Add a real response, connect it, remove the old terminal and persist the changed graph.
    await editor.locator('.editor-palette').getByRole('button',{name:['Respuesta','Response','Resposta'][i],exact:true}).click();
    const newId=await editor.locator('.editor-config-heading code').innerText();
    await editor.getByLabel(['Nombre del bloque','Block name','Nome do bloco'][i],{exact:true}).fill('Verificación · '+lang);
    await editor.getByLabel(['Texto de respuesta','Response text','Texto de resposta'][i],{exact:true}).fill('Verificación de conexión guardada · '+lang);
    await editor.getByRole('button',{name:['Ajustar vista','Fit view','Ajustar vista'][i],exact:true}).click();
    await editor.locator('.react-flow__node[data-id="notify"]').click();
    await editor.getByLabel(['Conexiones de salida · Siguiente','Output connections · Next','Conexões de saída · Próximo'][i],{exact:true}).selectOption(newId);
    await editor.locator('.react-flow__node[data-id="result"]').click();
    await editor.getByRole('button',{name:['Eliminar bloque','Delete block','Excluir bloco'][i],exact:true}).click();
    await expect(play).toBeDisabled();
    await editor.getByRole('button',{name:['Guardar borrador','Save draft','Salvar rascunho'][i],exact:true}).click();
    await expect(editor.locator('.editor-validation')).toContainText(['Listo para probar','Ready to test','Pronto para testar'][i]);
    const saved=await api('workflows/'+fixtures[lang]);
    assert.equal(saved.graph.edges.find(e=>e.source==='notify').target,newId);
    assert.equal(saved.graph.nodes.find(n=>n.id===newId).config.text[lang],'Verificación de conexión guardada · '+lang);
    await editor.locator('#editor-message').fill('Verificación de repetición');
    await play.click();
    await expect(editor.locator('.editor-result')).toContainText('Verificación de conexión guardada · '+lang);
    await expect(editor.locator('.editor-result')).toContainText(['Aviso existente; no se duplicó','Existing notification; no duplicate','Aviso existente; não foi duplicado'][i]);
    assert.equal((await api('notifications')).notifications.filter(n=>n.reference===reference).length,1);

    // JSON export is the same graph the server executed.
    const downloadPromise=page.waitForEvent('download');
    await editor.locator('.editor-library').getByRole('button',{name:['Exportar JSON','Export JSON','Exportar JSON'][i],exact:true}).click();
    const download=await downloadPromise;
    const exported=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.deepEqual(exported,saved.graph);
    await editor.locator('.editor-trace li').nth(1).getByRole('button').click();
    await editor.locator('.editor-inbox summary').click();
    const scan=await new AxeBuilder({page}).analyze();
    checks.push({language:lang,viewport:'desktop',violations:scan.violations.map(v=>v.id)});
    assert.equal(scan.violations.length,0,JSON.stringify(scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))));
    await page.screenshot({path:`${folder}/editor-${lang}.png`,fullPage:true});
    await page.setViewportSize({width:390,height:1000});
    await editor.getByRole('button',{name:['Ajustar vista','Fit view','Ajustar vista'][i],exact:true}).click();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow');
    const mobile=await new AxeBuilder({page}).analyze();
    checks.push({language:lang,viewport:'mobile',violations:mobile.violations.map(v=>v.id)});
    assert.equal(mobile.violations.length,0,JSON.stringify(mobile.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))));
    await page.screenshot({path:`${folder}/editor-${lang}-mobile.png`,fullPage:true});
    await page.reload();
    await expect(editor.getByLabel(['Nombre del flujo','Flow name','Nome do fluxo'][i],{exact:true})).toHaveValue(saved.graph.name[lang]);
    assert.equal(runs,(i+1)*3,'Reloading does not execute');
    assert.equal(await editor.locator('.editor-result').count(),0);
    // Duplicating and importing preserve the graph while creating an unsaved variant.
    await editor.getByRole('button',{name:['Duplicar','Duplicate','Duplicar'][i],exact:true}).click();
    await expect(editor.getByLabel(['Nombre del flujo','Flow name','Nome do fluxo'][i],{exact:true})).toHaveValue(saved.graph.name[lang]+' · 2');
    await expect(play).toBeDisabled();
    await editor.locator('input[type=file]').setInputFiles({name:'verification.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});
    await expect(editor.getByLabel(['Nombre del flujo','Flow name','Nome do fluxo'][i],{exact:true})).toHaveValue(saved.graph.name[lang]);
    await expect(editor.locator('.editor-validation')).toContainText(['Listo para probar','Ready to test','Pronto para testar'][i]);
    assert.equal((await api('workflows/'+fixtures[lang])).revision,saved.revision,'Draft import does not overwrite the saved flow');
    // Banking context and country instructions can be edited in all languages without any model call.
    await editor.getByLabel(['Nuevo flujo','New flow','Novo fluxo'][i],{exact:true}).selectOption('banking');
    await editor.getByRole('button',{name:['Nuevo flujo','New flow','Novo fluxo'][i],exact:true}).click();
    await expect(editor.locator('[data-block-kind]')).toHaveCount(10);
    await editor.locator('.editor-config select').first().selectOption('context');
    await editor.getByLabel(['Instrucciones adicionales','Additional instructions','Instruções adicionais'][i],{exact:true}).fill('Verificación · instrucciones '+lang);
    await editor.getByLabel(['Contexto de referencia','Reference context','Contexto de referência'][i],{exact:true}).fill('Verificación · contexto '+lang);
    const contextExportPromise=page.waitForEvent('download');
    await editor.locator('.editor-library').getByRole('button',{name:['Exportar JSON','Export JSON','Exportar JSON'][i],exact:true}).click();
    const contextExport=JSON.parse(await fs.readFile(await(await contextExportPromise).path(),'utf8'));
    assert.equal(contextExport.nodes.find(n=>n.id==='context').config.instructions[lang],'Verificación · instrucciones '+lang);
    assert.equal(runs,(i+1)*3);
  }
  assert.equal(blocked,0);assert.deepEqual(errors,[]);
  await fs.writeFile(folder+'/editor-ui.json',JSON.stringify({runs,checks,errors,blocked},null,2));
  console.log(JSON.stringify({runs,checks,errors,blocked}));
} catch(error) {
  await page.screenshot({path:folder+'/editor-failure.png',fullPage:true});
  console.error(JSON.stringify({errors,body:(await page.locator('body').innerText()).slice(-5000)}));
  throw error;
} finally {await browser.close();}
