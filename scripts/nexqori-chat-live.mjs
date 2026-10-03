// Explicit opt-in: exercises configured Jev/Luna through the authenticated bank API.
// Only new conversations on verification fixtures; never confirms claims or payments.
import { request } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import assert from 'node:assert/strict';

if (!process.argv.includes('--live')) throw new Error('Use --live to authorize provider calls for this test run.');
const origin='http://localhost:5180';
const definitions=JSON.parse(readFileSync('tests/scenarios/banking-cases.json','utf8')).cases;
const fixture=spawnSync('docker',['compose','exec','-T','-e','NEXQORI_LOCAL_VERIFY=1','-e','NEXQORI_CASES_INPUT='+Buffer.from(JSON.stringify({mode:'prepare',languages:['es'],definitions,phoneCharge:true})).toString('base64'),'api','python','-'],{input:readFileSync('scripts/banking-cases-fixtures.py','utf8'),encoding:'utf8',windowsHide:true,timeout:120000});
assert.equal(fixture.status,0,'Fixture creation failed (private output suppressed)');
const pack=JSON.parse(fixture.stdout),folder='.local/verification/chat-live/'+pack.runId;
mkdirSync(folder,{recursive:true});writeFileSync(folder+'/credentials.private.json',JSON.stringify(pack),{mode:0o600});
const client=await request.newContext({baseURL:origin,timeout:180000});
const login=await client.post('/api/auth/login',{headers:{Origin:origin},data:{identifier:pack.cases[0].email,password:pack.cases[0].password}});
assert.equal(login.status(),200);const session=await login.json();
const headers={Origin:origin,'X-CSRF-Token':session.csrfToken};
const capabilities=await(await client.get('/api/assistant/capabilities')).json();
assert(capabilities.connected && Object.values(capabilities.providers).every(value=>value==='configured'),'Connect the providers before running this opt-in check.');
const before=await(await client.get('/api/bootstrap')).json();
const report={runId:pack.runId,scope:'Real configured providers, authored scenarios, read-only banking actions',cases:[],errors:[]};
const only=process.argv.find(arg=>arg.startsWith('--only='))?.slice(7).split(',');
const scenarios=JSON.parse(readFileSync('tests/scenarios/conversation-basics.json','utf8')).cases.filter(s=>!only||only.includes(s.id));
assert(scenarios.length && (!only||only.every(id=>scenarios.some(s=>s.id===id))),'Unknown or empty scenario selection');
try {
 for(const scenario of scenarios){
  let conversationId=null;const result={id:scenario.id,locale:scenario.locale,turns:[],passed:true};
  for(const [index,turn] of scenario.turns.entries()){
   const body={message:turn.text,locale:scenario.locale,currentPage:'complaints',conversationId,requestKey:randomUUID()};
   const started=Date.now();const response=await client.post('/api/assistant/flow',{headers,data:body});
   if(!response.ok()){result.passed=false;report.errors.push(scenario.id+': HTTP '+response.status());break;}
   const value=await response.json();conversationId=value.conversation.id;
   const errors=[];const family=value.flow.triage.family,intent=value.flow.jev.intent||null;
   if(family!==turn.family) errors.push('family: '+family+' expected '+turn.family);
   if(intent!==turn.intent) errors.push('intent: '+intent+' expected '+turn.intent);
   if(turn.contains&&!value.text.toLowerCase().includes(turn.contains.toLowerCase())) errors.push('Missing targeted clarification');
   if(turn.route&&value.navigation?.route!==turn.route) errors.push('Unexpected navigation');
   if(value.flow.state==='provider_unavailable') errors.push('Provider unavailable');
   if(/consultar información o reportar|information or to report|informações ou relatar/.test(value.text)) errors.push('Generic family question repeated');
   if(value.flow.canRegister && !value.conversation.transactionId && ['unrecognized-charge','incorrect-charge','payment-status'].includes(intent)) errors.push('Missing bank reference must not permit claim registration');
   if(turn.suggestion && (value.flow.suggestedTransaction?.id!==pack.cases[0].transactionId || value.conversation.transactionId)) errors.push('Expected unconfirmed own phone charge suggestion');
   if(turn.confirmed && (value.conversation.transactionId!==pack.cases[0].transactionId || !value.flow.canRegister || value.flow.suggestedTransaction)) errors.push('Expected selected movement and complaint review');
   const restored=await(await client.get('/api/conversations/'+conversationId+'/flow')).json();
   if(!isDeepStrictEqual(restored.flow,value.flow)) errors.push('Restored result differs from the saved turn');
   if(index===0){const retry=await(await client.post('/api/assistant/flow',{headers,data:body})).json();if(!isDeepStrictEqual(retry,value)) errors.push('Retry differs from original response');}
   if(intent==='account-balance'&&!value.text.includes('MXN')) errors.push('Balance inquiry did not answer with the available amount');
   result.turns.push({text:turn.text,family,intent,state:value.flow.state,reply:value.text,elapsedMs:Date.now()-started,providerMs:value.flow.latency_ms,errors});
   if(errors.length){result.passed=false;report.errors.push(scenario.id+': '+errors.join('; '));}
  }
  report.cases.push(result);console.log((result.passed?'OK ':'FAIL ')+scenario.id);
 }
 const after=await(await client.get('/api/bootstrap')).json();
 for(const key of ['products','transactions','requests']) assert.deepEqual(after[key],before[key],key+' changed');
 report.financialDataUnchanged=true;
} finally {
 writeFileSync(folder+'/report.json',JSON.stringify(report,null,2));console.log('Informe privado: '+folder+'/report.json');await client.dispose();
}
assert.equal(report.errors.length,0,report.errors.join('\n'));
