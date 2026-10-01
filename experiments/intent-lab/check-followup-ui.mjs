// UI regression only: no provider calls and no stored conversation mutations.
import {chromium} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const fixture=JSON.parse(await fs.readFile('experiments/intent-lab/evaluations/recurrent-fee.json','utf8'));
const saved=Object.entries(fixture.variants).map(([language,v],i)=>({id:`11111111-1111-4111-8111-11111111111${i}`,title:v.title,language,messages:[{role:'user',content:v.status_only}],expected:'request-status',instructions:'Classify the active banking intent.'}));
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1100}});const page=await context.newPage();let calls=0;const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/lab-api/conversations',route=>route.fulfill({json:{version:1,conversations:saved}}));
await page.route('**/lab-api/classify',()=>{throw new Error('Unexpected provider execution');});
await page.route('**/lab-api/dialogue',async route=>{
 calls++;const body=route.request().postDataJSON();assert.equal(body.language,saved.find(s=>s.messages[0].content===body.messages[0].content).language);
 await route.fulfill({json:{id:'verification-query',thread_id:'11111111-1111-4111-8111-111111111119',contract:null,jev:{status:'ok',intent:'request-status'},llm:{status:'skipped',reason:'separate_flow'},route_family:'query',routing:{family:'query',reply:'Verificación · consulta de seguimiento.',proposal:{route:'/requests'}},executed_operations:[]}});
});
try {
 for(const [i,entry] of saved.entries()){
  await page.setViewportSize({width:i===2?390:1440,height:1100});
  await page.goto('http://127.0.0.1:5190/?case='+entry.id);
  await page.locator('#conversation-title').waitFor();
  assert.equal(await page.locator('#conversation-title').inputValue(),entry.title);
  assert.equal(await page.locator('html').getAttribute('lang'),entry.language);
  assert.equal(calls,i,'Loading a saved case must not call a provider');
  await page.getByRole('button',{name:['Probar respuesta de este caso','Test reply for this case','Testar resposta deste caso'][i],exact:true}).click();
  await page.locator('.dialogue-chat .assistant').waitFor();
  assert.equal(await page.getByRole('link',{name:['Abrir Mis solicitudes','Open My requests','Abrir Minhas solicitações'][i],exact:true}).getAttribute('href'),'http://localhost:5180/requests');
  assert.equal(await page.locator('.problem-actions').count(),0);
  assert.equal(await page.locator('#workflow-select option').count(),6);
  const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();checks.push({language:entry.language,violations:a.violations.map(v=>v.id)});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 }
 await page.goto('http://127.0.0.1:5190/?case=not-a-saved-case');
 await page.locator('#case').waitFor();assert.equal(await page.locator('#case').inputValue(),'unknown');
 assert.equal(calls,3);assert.deepEqual(errors,[]);assert.equal(checks.flatMap(c=>c.violations).length,0,JSON.stringify(checks));
 console.log(JSON.stringify({passed:true,checks,calls:'3 mocked',noAutomaticExecution:true}));
}finally{await browser.close();}
