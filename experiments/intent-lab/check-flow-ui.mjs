// UI contract checks use controlled provider outputs. No paid provider or bank calls.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const base='http://127.0.0.1:5190';
const maps=Object.fromEntries(await Promise.all(['es','en','pt'].map(async lang=>[lang,await(await fetch(base+'/lab-api/flow-map?language='+lang)).json()])));
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1100}});
const page=await context.newPage();
const errors=[],checks=[];let calls=0, forbiddenCalls=0, edits=0;
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(/:5180|api\.typesafe|api\.openai|live|audio/.test(r.url()))forbiddenCalls++;});
await page.route('**/lab-api/conversations',route=>route.fulfill({json:{version:1,conversations:[]}}));
await page.route('**/lab-api/flow-map**',route=>{
  const req=route.request();
  if(req.method()==='GET')return route.fulfill({json:maps[new URL(req.url()).searchParams.get('language')]});
  const body=req.postDataJSON(),intent=new URL(req.url()).pathname.split('/').at(-1),map=maps[body.language];
  assert.equal(body.revision,map.revision);assert.ok(body.questions);
  Object.assign(map.definitions.find(d=>d.intent===intent),{questions:body.questions,instructions:body.instructions});map.revision++;edits++;
  return route.fulfill({json:map});
});
await page.route('**/lab-api/flow-run',route=>{
  calls++;const body=route.request().postDataJSON(),last=body.messages.at(-1).content;
  const mode=last.includes('QUERY')?'query':last.includes('HUMAN')?'human':last.includes('ERROR')?'error':last.includes('COMPLETE')?'complete':'ask';
  const intent=mode==='query'?'account-balance':'incorrect-charge';
  const definition=maps[body.language].definitions.find(d=>d.intent===intent),state=({query:'review_in_bank',human:'human_review',error:'provider_unavailable',complete:'review_in_bank',ask:'ask_customer'})[mode];
  const questions=mode==='ask'?[{field:'amount',text:definition.questions.amount},{field:'difference',text:definition.questions.difference}]:[];
  return route.fulfill({json:{id:'00000000-0000-4000-8000-'+String(calls).padStart(12,'0'),thread_id:'22222222-2222-4222-8222-222222222222',created_at:new Date().toISOString(),config_revision:maps[body.language].revision,definition,route_family:definition.family,jev:{status:'ok',intent,model:'jev-verification',latency_ms:20,probabilities:{[intent]:.94}},llm:{status:mode==='error'?'error':'ok',model:'luna-verification',latency_ms:35,assessment:mode==='human'?'human_review':'continue'},state,reply:questions.length?questions.map(q=>q.text).join(' '):'Verificación / Verification / Verificação: '+state,missing_fields:questions.map(q=>q.field),questions,observations:mode==='ask'?[{field:'movement',message_index:0,quote:'Verificación'}]:[],tool_plan:{...definition.tool_plan,source:'jev'},latency_ms:55,stages:[],executed_operations:[],authorizes_execution:false}});
});
await fs.mkdir('.local/intent-lab/verification',{recursive:true});
try {
  for (const [i,lang] of ['es','en','pt'].entries()) {
    await page.addInitScript(value=>localStorage.setItem('nexqori-lab-language',value),lang);
    await page.setViewportSize({width:i===2?390:1440,height:1100});
    await page.goto(base+'/?view=flows');
    await page.locator('#flow-case').waitFor();
    assert.equal(await page.locator('#flow-intent option').count(),24);
    assert.equal(await page.locator('[data-flow-node]').count(),12);
    assert.equal(calls,i*5,'Loading does not call providers');
    await page.locator('#flow-case').selectOption('custom');
    await page.locator('#flow-intent').selectOption('incorrect-charge');
    const question=page.locator('.flow-editor label').filter({hasText:['Pregunta · Importe y moneda','Question · Amount and currency','Pergunta · Valor e moeda'][i]}).locator('textarea');
    await question.fill('Verificación / Verification / Verificação: importe?');
    await page.getByRole('button',{name:['Guardar cambios','Save changes','Salvar alterações'][i],exact:true}).click();
    await page.getByRole('status').filter({hasText:['Guardado','Saved','Salvo'][i]}).waitFor();
    const play=page.getByRole('button',{name:['Ejecutar turno','Run turn','Executar turno'][i],exact:true});
    for(const [j,message] of ['ASK','COMPLETE','QUERY','HUMAN','ERROR'].entries()) {
      await page.locator('#flow-input').fill('Verificación '+message);
      await play.click();
      await expect(page.locator('.flow-history button')).toHaveCount(j+1);
      const expected=['ask_customer','review_in_bank','review_in_bank','human_review','provider_unavailable'][j];
      await page.locator(`[data-flow-state="${expected}"]`).waitFor();
      if(j===0)assert.match(await page.locator('.flow-next').innerText(),/importe\?/);
      if(j===2){assert.equal(await page.locator('.flow-history button').count(),3);assert.match(await page.locator('.flow-next').innerText(),new RegExp(maps[lang].definitions.find(d=>d.intent==='account-balance').title));}
      assert.equal(calls,i*5+j+1);
    }
    const scan=await new AxeBuilder({page}).analyze();checks.push({language:lang,violations:scan.violations.map(v=>({id:v.id,nodes:v.nodes.length}))});
    assert.equal(scan.violations.length,0,JSON.stringify(scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow');
    await page.screenshot({path:`.local/intent-lab/verification/flow-${lang}.png`,fullPage:true});
    await page.getByRole('button',{name:['Nueva conversación','New conversation','Nova conversa'][i],exact:true}).click();
    assert.equal(await page.locator('.flow-history button').count(),0);
    assert.equal(await page.locator('[data-flow-state]').count(),0);
  }
  assert.equal(edits,3);assert.equal(forbiddenCalls,0);assert.deepEqual(errors,[]);
  await fs.writeFile('.local/intent-lab/verification/flow-ui.json',JSON.stringify({calls,edits,checks,errors,forbiddenCalls},null,2));
  console.log(JSON.stringify({calls,edits,checks,errors,forbiddenCalls}));
} finally {await browser.close();}
