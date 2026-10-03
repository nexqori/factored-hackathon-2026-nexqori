// Compiled UI + isolated bank. Voice transport and media are fakes; no microphone or paid API.
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const origin='http://127.0.0.1:5192',root=path.resolve('.local/verification');await fs.mkdir(root,{recursive:true});
const folder=await fs.mkdtemp(path.join(root,'voice-ui-'));
assert.equal(await fetch(origin+'/api/health').then(()=>true).catch(()=>false),false,'Port 5192 must be free');
const python=process.env.NEXQORI_BANK_PYTHON||path.resolve(process.platform==='win32'?'.venv-app/Scripts/python.exe':'.venv-app/bin/python');
const server=spawn(python,['-m','backend.tests.chat_ui_server'],{env:{...process.env,BANK_VOICE_ENABLED:'false',NEXQORI_CHAT_UI_CHECK:'1',NEXQORI_CHAT_UI_DATA:folder},windowsHide:true,stdio:['ignore','pipe','pipe']});
let diagnostics='',browser,page;server.stderr.on('data',b=>diagnostics+=b.toString());const report={checks:[],accessibility:[],errors:[]};
async function axe(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();report.accessibility.push({name,violations:r.violations.map(v=>v.id)});assert.equal(r.violations.length,0,JSON.stringify(r.violations));}
try{
 for(let i=0;i<100;i++){if(await fetch(origin+'/api/health').then(r=>r.ok).catch(()=>false))break;if(server.exitCode!==null)throw new Error(diagnostics);await new Promise(r=>setTimeout(r,150));}
 const people=JSON.parse(await fs.readFile(path.join(folder,'credentials.private.json'),'utf8'));
 browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
 for(const locale of ['es','en','pt']){
  const person=people.find(p=>p.locale===locale&&p.intent==='incorrect-charge'),copy=JSON.parse(await fs.readFile('src/locales/'+locale+'.json','utf8'));
  const context=await browser.newContext({viewport:{width:1512,height:1050}});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await page.addInitScript(()=>{
   window.__voiceCheck={microphones:0,stopped:0,controls:[]};
   const track={enabled:true,stop(){window.__voiceCheck.stopped++;}};
   Object.defineProperty(navigator,'mediaDevices',{value:{async getUserMedia(){window.__voiceCheck.microphones++;return{getAudioTracks:()=>[track],getTracks:()=>[track]};}}});
   window.RTCPeerConnection=class{
    iceGatheringState='complete';localDescription={sdp:'v=0'};connectionState='connected';
    addTrack(){} async createOffer(){return{type:'offer',sdp:'v=0'};}async setLocalDescription(){}async setRemoteDescription(){}close(){}
    createDataChannel(){return{readyState:'open',onmessage:null,onclose:null,close(){},send(v){window.__voiceCheck.controls.push(JSON.parse(v));}};}
   };
  });
  const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
  const auth=await login.json();
  const result=await context.request.post(origin+'/api/assistant/flow',{headers:{Origin:origin,'X-CSRF-Token':auth.csrfToken},data:{requestKey:crypto.randomUUID(),locale,transactionId:person.transactionId,message:'Verificación [incorrect-charge] me cobraron de más'}});
  assert.equal(result.status(),200);const reply=await result.json();
  await page.goto(origin);await page.locator('.language-trigger').click();await page.locator('[data-locale="'+locale+'"]').click();
  await page.getByRole('button',{name:copy.startVoice,exact:true}).click();const call=page.locator('.voice-call');
  await expect(call).toContainText(copy['voiceCall.unavailable']);await expect(call.getByRole('button',{name:copy['voiceCall.start'],exact:true})).toBeDisabled();
  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),0);await axe('disabled-'+locale);
  await call.getByRole('button',{name:copy.voiceContinue,exact:true}).click();
  let pendingSessionId='previous-call';
  await page.route('**/api/voice/capabilities',route=>route.fulfill({json:{enabled:true,maxSeconds:300,voices:['marin','cedar','bossa'],pendingSessionId}}));
  await page.route('**/api/voice/sessions',route=>route.fulfill({json:{id:'fake-voice',conversationId:reply.conversation.id,status:'active',sdp:'v=0',expiresAt:Math.floor(Date.now()/1000)+300}}));
  await page.route('**/api/voice/sessions/*/heartbeat',route=>route.fulfill({json:{status:'active',revision:1,reply}}));
  let closed=0;await page.route('**/api/voice/sessions/*/close',route=>{closed++;pendingSessionId=null;return route.fulfill({json:{status:'closed',remoteClosed:true}});});
  await page.getByRole('button',{name:copy.startVoice,exact:true}).click();
  await expect(call.getByRole('button',{name:copy['voiceCall.start'],exact:true})).toBeDisabled();
  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),0);
  await call.getByRole('button',{name:copy['voiceCall.closePrevious'],exact:true}).click();
  await call.getByRole('button',{name:copy['voiceCall.start'],exact:true}).click();
  await expect(call).toContainText(copy['voiceCall.active']);await expect(page.locator('.chat-bubble.assistant').last()).toHaveText(reply.text);
  await expect(page.locator('.chat-details-button')).toBeDisabled();
  await expect(page.locator('.paste-composer textarea')).toBeDisabled();await call.getByRole('button',{name:copy['voiceCall.mute'],exact:true}).click();
  await expect(call.getByRole('button',{name:copy['voiceCall.unmute'],exact:true})).toHaveAttribute('aria-pressed','true');
  await axe('active-'+locale);await call.screenshot({path:path.join(folder,'call-'+locale+'.png')});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('mobile-'+locale);
  await call.getByRole('button',{name:copy['voiceCall.end'],exact:true}).click();await expect(call).toHaveCount(0);await expect(page.locator('.paste-composer textarea')).toBeEnabled();
  await expect(page.locator('.chat-details-button')).toBeEnabled();
  await expect.poll(()=>closed).toBeGreaterThan(1);assert((await page.evaluate(()=>window.__voiceCheck.stopped))>0);
  report.checks.push({locale,disabledWithoutMicrophone:true,recoverPreviousCall:true,fakeCall:true,bankReply:true,closed:true});await context.close();
 }
 assert.deepEqual(report.errors,[]);await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({folder,...report},null,2));
}catch(error){if(page)await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});throw error;}
finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
