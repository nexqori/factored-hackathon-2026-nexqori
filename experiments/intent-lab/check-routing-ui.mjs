// Controlled provider responses; server-authored plans, no bank/provider calls.
import {chromium} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const base = 'http://127.0.0.1:5190';
const plans = (await (await fetch(base+'/lab-api/tool-routes')).json()).plans;
const langs = ['es','en','pt'];
const saved = langs.map((language, i)=>({id:`22222222-2222-4222-8222-22222222222${i}`,title:'Verificación de rutas '+language,language,messages:[{role:'user',content:'Consultar mi folio.'}],expected:'request-status',instructions:'Classify the active intent.'}));
const contracts = Object.fromEntries(await Promise.all(langs.map(async lang=>[lang,(await (await fetch(base+'/lab-api/workflows?language='+lang)).json()).contracts])));
const browser = await chromium.launch({channel:'msedge',headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1100}});
const page = await context.newPage();
const errors=[], checks=[];let calls=0, bankCalls=0;
page.on('pageerror', e=>errors.push(e.message));
page.on('request',req=>{if(req.url().includes(':5180'))bankCalls++;});
await page.route('**/lab-api/conversations',route=>route.fulfill({json:{version:1,conversations:saved}}));
await page.route('**/lab-api/dialogue',route=>{
  calls++;
  const body=route.request().postDataJSON(), problem=body.messages.at(-1).content === 'Verificación: problema con cargo.';
  const intent=problem?'incorrect-charge':'request-status', family=problem?'problem':'query';
  const contract=problem?contracts[body.language].find(c=>c.id===intent):null;
  return route.fulfill({json:{id:'routing-verification',thread_id:'22222222-2222-4222-8222-222222222229',contract,route_family:family,tool_plan:{...plans[intent],source:'jev'},jev:{status:'ok',intent},llm:problem?{status:'ok',reply:'Verificación: ¿qué importe esperabas?',next_step:'collect_context'}:{status:'skipped',reason:'separate_flow'},routing:problem?null:{family,reply:'Verificación: consulta de seguimiento.',proposal:{route:'/requests'}},executed_operations:[]}});
});
await page.route('**/lab-api/classify',route=>route.fulfill({json:{id:'routing-provider-error',jev:{status:'error',error:'timeout'},llm:{status:'error'},decision:{status:'pending',reason:'provider_unavailable'},tool_plan:{...plans['needs-clarification'],source:'jev',intent:null,status:'unavailable'}}}));
await fs.mkdir('.local/intent-lab/verification',{recursive:true});
try {
  for(const [i,lang] of langs.entries()){
    await page.setViewportSize({width:i===2?390:1440,height:1100});
    await page.goto(base+'/?case='+saved[i].id);
    await page.locator('#conversation-title').waitFor();
    assert.equal(await page.locator('.compact-decision [data-tool-family="query"]').count(),1);
    assert.equal(calls, i*3,'Opening a case must not run a provider');
    await page.getByRole('button',{name:['Probar respuesta de este caso','Test reply for this case','Testar resposta deste caso'][i],exact:true}).click();
    const panel=page.locator('.dialogue-panel');
    await panel.locator('[data-tool-family="query"]').waitFor();
    assert.equal(await panel.locator('[data-tool-id="read-request-status"]').count(),1);
    assert.equal(await panel.locator('[data-tool-id^="prepare-"]').count(),0);
    await page.screenshot({path:`.local/intent-lab/verification/routing-${lang}-query.png`,fullPage:true});
    for(const [text, family] of [['Verificación: problema con cargo.','problem'],['Verificación: ahora sólo consultar el folio.','query']]){
      await panel.locator('[data-assistant-input]').fill(text);
      await panel.getByRole('button',{name:['Enviar mensaje','Send message','Enviar mensagem'][i],exact:true}).click();
      await panel.locator(`[data-tool-family="${family}"]`).waitFor();
      assert.equal(await panel.locator('[data-tool-id="prepare-refund-review"]').count(),family==='problem'?1:0);
      assert.equal(await panel.locator('[data-tool-id="prepare-card-block"]').count(),0);
      const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      checks.push({lang,family,violations:a.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1));
      if(family==='problem') await panel.locator('.tool-plan').screenshot({path:`.local/intent-lab/verification/routing-${lang}-problem.png`});
    }
    await page.getByRole('button',{name:['Ejecutar caso','Run case','Executar caso'][i],exact:true}).click();
    await page.locator('.compact-decision [data-tool-family="clarification"]').waitFor();
    assert.equal(await page.locator('.compact-decision [data-tool-id]').count(),0);
  }
  assert.equal(bankCalls,0);assert.equal(calls,9);assert.deepEqual(errors,[]);
  assert.equal(checks.flatMap(c=>c.violations).length,0,JSON.stringify(checks));
  console.log(JSON.stringify({passed:true,checks,dialogueCalls:'9 controlled',bankCalls,automaticProviderCalls:0}));
} finally {await browser.close();}
