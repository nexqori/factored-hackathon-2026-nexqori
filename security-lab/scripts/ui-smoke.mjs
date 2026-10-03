import {chromium, request} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {randomBytes} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const cwd=fileURLToPath(new URL('../',import.meta.url));
const out=new URL('../.local/verification/',import.meta.url);
await mkdir(out,{recursive:true});
const username='verification-'+randomBytes(5).toString('hex'),password=randomBytes(24).toString('hex');
function sqlScript(script,input=''){return execFileSync('docker',['compose','exec','-T','lab-api','python','-c',script],{cwd,input,encoding:'utf8',stdio:['pipe','pipe','pipe']})}
const id=sqlScript(`import sys,json
from lab.db import *
from lab.security import HASHER
p=json.load(sys.stdin)
with sessions(engine_for())() as db:
 u=User(username=p['username'],password_hash=HASHER.hash(p['password']),role='admin');db.add(u);db.flush();audit(db,'verification','temporary_user_created',u.id);db.commit();print(u.id)`,JSON.stringify({username,password})).trim();
let browser;
const errors=[];
let results={screens:[],axe:[],runs:[]};
try{
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://localhost:5200');
 await page.getByLabel('Usuario',{exact:true}).fill(username);await page.getByLabel('Contraseña',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Ingresar',exact:true}).click();
 await page.getByRole('heading',{name:'Resumen',exact:true}).waitFor();
 const session=await (await context.request.get('http://localhost:5200/api/session')).json();
 const headers={Origin:'http://localhost:5200','X-CSRF-Token':session.csrf};
 async function get(path){const r=await context.request.get('http://localhost:5200/api'+path);assert.equal(r.status(),200,await r.text());return r.json()}
 async function post(path,body){const r=await context.request.post('http://localhost:5200/api'+path,{data:body,headers});assert.ok(r.ok(),await r.text());return r.json()}
 const catalog=await get('/catalog'),targets=await get('/targets');
 async function run(target,cases,parent_id=null){
  const spec={target_id:target.id,cases,locale:'es',case_seconds:20,run_seconds:300,requests_per_case:30,parent_id};
  const preview=await post('/runs/preview',spec);
  const created=await post('/runs',{...preview.spec,catalog_hash:preview.catalog_hash,confirmed:true,request_key:randomBytes(16).toString('hex')});
  const deadline=Date.now()+330000;let r;
  do {r=await get('/runs/'+created.id);if(!['pending','running'].includes(r.status))break;await new Promise(r=>setTimeout(r,600));}while(Date.now()<deadline);
  assert.ok(!['pending','running'].includes(r.status),'worker timeout');
  results.runs.push(r);return r;
 }
 const real=await run(targets.find(t=>t.adapter==='nexqori-local'),catalog.cases.map(c=>c.id));
 await writeFile(new URL('real-results.json',out),JSON.stringify(real,null,2));
 console.log(JSON.stringify({realStatus:real.status,verdicts:real.metrics.verdicts,errors:real.results.filter(r=>r.status==='error').map(r=>({case:r.case_id,evidence:r.evidence}))}));
 assert.equal(real.status,'completed','real run infrastructure error');
 assert.ok(real.results.filter(r=>r.applicability==='automated').every(r=>r.verdict==='passed'),'real contract assertion failed');
 // Simulated findings remain exclusively in DEMO metrics.
 const lifecycle=await run(targets.find(t=>t.adapter==='demo'),['NQ-auth']);
 const original=lifecycle.results.find(r=>r.case_id==='NQ-auth');
 await post('/results/'+original.id+'/reviews',{verdict:'failed',criteria:'Verification fixture: demonstrate finding lifecycle, not a real vulnerability.',evidence:'Synthetic workflow verification only. <script>window.labInjected=true</script> token=canary',severity:'low',impact:'Synthetic finding for verifying review, persistence and retest.',recommendation:'Run the unchanged registered contract to verify the workflow.'});
 let fs=await get('/findings');const finding=fs.find(f=>f.case_id==='NQ-auth'&&f.mode==='demo');
 const updated=await context.request.patch('http://localhost:5200/api/findings/'+finding.id,{headers,data:{status:'fixed',assignee:username,note:'Synthetic verification: ready for linked contract retest.'}});assert.equal(updated.status(),200);
 const retest=await run(targets.find(t=>t.adapter==='demo'),['NQ-auth'],lifecycle.id);
 fs=await get('/findings');assert.equal(fs.find(f=>f.id===finding.id).status,'verified');
 const demo=await run(targets.find(t=>t.adapter==='demo'),['LLM06-05']);
 assert.equal(demo.results[0].verdict,'failed');
 for(const format of ['json','csv','html']){const r=await context.request.get(`http://localhost:5200/api/runs/${lifecycle.id}/export/${format}`);assert.equal(r.status(),200);const text=await r.text();if(format==='html'){assert.ok(!text.includes('<script>'));assert.ok(!text.includes('token=canary'));}await writeFile(new URL('report.'+format,out),text)}
 // Verify persistence across API/worker restart without changing the main stack.
 execFileSync('docker',['compose','restart','lab-api','lab-worker'],{cwd,stdio:'pipe'});
 for(let n=0;n<30;n++){try{const r=await context.request.get('http://localhost:5200/api/health');if(r.ok())break}catch{}await new Promise(r=>setTimeout(r,500));}
 assert.equal((await get('/runs/'+real.id)).results.length,catalog.cases.length);
 await page.reload();await page.getByRole('heading',{name:'Resumen',exact:true}).waitFor();
 for(const [lang,label] of [['es','Resumen'],['en','Overview'],['pt','Resumo']]){
  await page.getByLabel(/Idioma|Language/).selectOption(lang);await page.getByRole('heading',{name:label,exact:true}).waitFor();
  const axe=await new AxeBuilder({page}).analyze();results.axe.push({page:'dashboard',lang,violations:axe.violations});
  await page.screenshot({path:fileURLToPath(new URL('dashboard-'+lang+'.png',out)),fullPage:true});results.screens.push('dashboard-'+lang+'.png');
 }
 await page.getByLabel('Idioma').selectOption('es');
 await page.getByRole('button',{name:'Catálogo',exact:true}).click();
 await page.getByLabel('Buscar caso').fill('NQ-auth');
 await page.getByRole('checkbox',{name:/NQ-auth/}).check();
 await page.getByRole('button',{name:'Revisar alcance',exact:true}).click();
 await page.getByRole('checkbox',{name:/Confirmo ejecutar/}).check();
 await page.getByRole('button',{name:'Ejecutar evaluación',exact:true}).click();
 await page.getByRole('heading',{name:'HTTP real · rules',exact:true}).waitFor();
 await page.getByText('Aprobado',{exact:true}).waitFor({timeout:45000});
 await page.screenshot({path:fileURLToPath(new URL('run-detail.png',out)),fullPage:true});
 results.axe.push({page:'run',violations:(await new AxeBuilder({page}).analyze()).violations});
 await page.getByRole('button',{name:'Registrar revisión',exact:true}).click();
 await page.getByLabel('Criterio concreto y justificación').fill('Synthetic verification criterion: expected contract status codes.');
 await page.getByLabel('Impacto observado').fill('Synthetic verification only; no real vulnerability asserted.');
 await page.getByLabel('Recomendación').fill('Retain original HTTP evidence and compare future runs.');
 await page.getByLabel('Evidencia',{exact:true}).fill('<script>window.labInjected=true</script> Synthetic inert UI verification.');
 await page.getByRole('button',{name:'Guardar',exact:true}).click();
 await page.locator('details').first().locator('summary').click();
 assert.equal(await page.evaluate(()=>window.labInjected),undefined);
 for(const tab of ['Hallazgos','Administración','Auditoría']){
  await page.getByRole('button',{name:tab,exact:true}).click();await page.getByRole('heading',{name:tab,exact:true}).waitFor();
  results.axe.push({page:tab,violations:(await new AxeBuilder({page}).analyze()).violations});
 }
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Resumen',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:fileURLToPath(new URL('mobile.png',out)),fullPage:true});
 results.axe.push({page:'mobile',violations:(await new AxeBuilder({page}).analyze()).violations});
 assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage)),['nexqori-lab-locale']);
 assert.deepEqual(errors,[]);
 await writeFile(new URL('ui-results.json',out),JSON.stringify({...results,pageErrors:errors},null,2));
 assert.ok(results.axe.every(a=>a.violations.length===0),'accessibility violations');
 console.log(JSON.stringify({ok:true,realRun:real.id,retest:retest.id,demo:demo.id,axe:results.axe.length,screens:results.screens,pageErrors:errors}));
}finally{
 if(browser)await browser.close();
 sqlScript(`import sys
from sqlalchemy import delete
from lab.db import *
with sessions(engine_for())() as db:
 u=db.get(User,sys.stdin.read().strip());u.active=False;db.execute(delete(Session).where(Session.user_id==u.id));audit(db,'verification','temporary_user_disabled',u.id);db.commit()`,id);
}
