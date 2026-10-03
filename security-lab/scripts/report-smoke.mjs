import {execFileSync} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium,request} from '@playwright/test';
import assert from 'node:assert/strict';
const cwd=fileURLToPath(new URL('../',import.meta.url));
const out=new URL('../.local/verification/',import.meta.url);await mkdir(out,{recursive:true});
const username='verification-report-'+randomBytes(4).toString('hex'),password=randomBytes(24).toString('hex');
const script=`import sys,json
from lab.db import *
from lab.security import HASHER
p=json.load(sys.stdin)
with sessions(engine_for())() as db:
 u=User(username=p['username'],password_hash=HASHER.hash(p['password']),role='reader');db.add(u);db.flush();audit(db,'verification','temporary_reader_created',u.id);db.commit();print(u.id)`;
const id=execFileSync('docker',['compose','exec','-T','lab-api','python','-c',script],{cwd,input:JSON.stringify({username,password}),encoding:'utf8'}).trim();
let browser,client;
try{
 client=await request.newContext({baseURL:'http://localhost:5200'});
 const login=await client.post('/api/login',{headers:{Origin:'http://localhost:5200'},data:{username,password}});assert.equal(login.status(),200);
 const runs=await(await client.get('/api/runs')).json();const run=runs.find(r=>r.mode==='real'&&r.spec.cases.length===66);assert.ok(run);
 const response=await client.get(`/api/runs/${run.id}/export/html`);assert.equal(response.status(),200);
 const html=await response.text();assert.ok(html.includes('Informe de evaluación'));assert.ok(!html.includes('<script>'));assert.ok(response.headers()['content-security-policy'].includes("default-src 'none'"));
 await writeFile(new URL('report-print.html',out),html);
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:960}});await page.setContent(html);await page.getByRole('heading',{name:'Informe de evaluación'}).waitFor();
 await page.screenshot({path:fileURLToPath(new URL('report-print.png',out))});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 console.log(JSON.stringify({report:run.id,html:true,readerExport:true,screenshot:'report-print.png'}));
}finally{
 if(browser)await browser.close();if(client)await client.dispose();
 execFileSync('docker',['compose','exec','-T','lab-api','python','-c',`import sys
from sqlalchemy import delete
from lab.db import *
with sessions(engine_for())() as db:
 u=db.get(User,sys.stdin.read().strip());u.active=False;db.execute(delete(Session).where(Session.user_id==u.id));audit(db,'verification','temporary_reader_disabled',u.id);db.commit()`],{cwd,input:id,stdio:['pipe','pipe','pipe']});
}
