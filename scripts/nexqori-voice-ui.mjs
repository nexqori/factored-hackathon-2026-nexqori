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
   window.__voiceCheck={microphones:0,stopped:0,controls:[],rms:0,analysersClosed:0};
   window.AudioContext=class{
    state='running';
    createMediaStreamSource(){return{connect(){},disconnect(){}};}
    createAnalyser(){return{fftSize:256,getFloatTimeDomainData(values){values.fill(window.__voiceCheck.rms);},disconnect(){}};}
    async resume(){}async close(){this.state='closed';window.__voiceCheck.analysersClosed++;}
   };
   const track={enabled:true,stop(){window.__voiceCheck.stopped++;}};
   Object.defineProperty(navigator,'mediaDevices',{value:{async getUserMedia(){window.__voiceCheck.microphones++;return{getAudioTracks:()=>[track],getTracks:()=>[track]};}}});
   window.RTCPeerConnection=class{
    iceGatheringState='complete';localDescription={sdp:'v=0'};connectionState='connected';
    addTrack(){} async createOffer(){return{type:'offer',sdp:'v=0'};}async setLocalDescription(){}async setRemoteDescription(){}close(){}
    createDataChannel(){const channel={readyState:'open',onmessage:null,onclose:null,close(){},send(v){window.__voiceCheck.controls.push(JSON.parse(v));}};window.__voiceCheck.channel=channel;return channel;}
   };
  });
  const login=await context.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{identifier:person.email,password:person.password}});assert.equal(login.status(),200);
  const auth=await login.json();
  const result=await context.request.post(origin+'/api/assistant/flow',{headers:{Origin:origin,'X-CSRF-Token':auth.csrfToken},data:{requestKey:crypto.randomUUID(),locale,transactionId:person.transactionId,message:{es:'Verificación [CASE-2] me cobraron de más',en:'Verification [CASE-2] I was charged too much',pt:'Verificação [CASE-2] cobraram a mais'}[locale]}});
  assert.equal(result.status(),200);const first=await result.json();
  const next=await context.request.post(origin+'/api/assistant/flow',{headers:{Origin:origin,'X-CSRF-Token':auth.csrfToken},data:{requestKey:crypto.randomUUID(),locale,conversationId:first.conversation.id,message:{es:'Esperaba 100 MXN',en:'I expected 100 MXN',pt:'Esperava 100 MXN'}[locale]}});
  assert.equal(next.status(),200);const reply=await next.json();assert(reply.flow.canRegister);
  reply.voiceSummary={summary:copy['voiceCall.verdict.unusual'],transactionId:person.transactionId,comparison:{basis:'history',baselineMinor:10000,currentMinor:18500,differenceMinor:8500,currency:'MXN',count:3,verdict:'unusual'}};
  await page.goto(origin);await page.locator('.language-trigger').click();await page.locator('[data-locale="'+locale+'"]').click();
  await page.locator('.paste-composer textarea').fill('Borrador conservado');
  await page.getByRole('button',{name:copy.startVoice,exact:true}).click();const call=page.locator('.voice-call');
  await expect(call).toContainText(copy['voiceCall.unavailable']);await expect(call.getByRole('button',{name:copy['voiceCall.start'],exact:true})).toBeDisabled();
  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),0);
  await expect(call.getByLabel(copy['voiceCall.agent'],{exact:true})).toHaveValue('marin');
  await expect(call.locator('.voice-agent-description')).toHaveText(copy['voiceCall.agent.marin']);
  await expect(call.getByText(copy['voiceCall.intro'],{exact:true})).not.toBeVisible();
  await call.locator('.voice-call-info summary').click();await expect(call.getByText(copy['voiceCall.intro'],{exact:true})).toBeVisible();
  await call.locator('.voice-call-info summary').click();
  await axe('disabled-'+locale);await page.locator('.assistant-panel').screenshot({path:path.join(folder,'agents-'+locale+'.png')});
  await call.getByRole('button',{name:copy.voiceContinue,exact:true}).click();
  await expect(page.locator('.paste-composer textarea')).toHaveValue('Borrador conservado');
  await expect(page.getByRole('button',{name:copy.startVoice,exact:true})).toBeFocused();
  let pendingSessionId='previous-call';
  await page.route('**/api/voice/capabilities',route=>route.fulfill({json:{enabled:true,maxSeconds:300,voices:['marin','cedar','bossa'],pendingSessionId}}));
  let chosenVoice;await page.route('**/api/voice/sessions',route=>{chosenVoice=route.request().postDataJSON().voice;return route.fulfill({json:{id:'fake-voice',conversationId:reply.conversation.id,status:'active',sdp:'v=0',expiresAt:Math.floor(Date.now()/1000)+300}});});
  await page.route('**/api/voice/sessions/*/heartbeat',route=>route.fulfill({json:{status:'active',revision:1,reply}}));
  let closed=0;await page.route('**/api/voice/sessions/*/close',route=>{closed++;pendingSessionId=null;return route.fulfill({json:{status:'closed',remoteClosed:true}});});
  await page.getByRole('button',{name:copy.startVoice,exact:true}).click();
  await expect(call.getByRole('button',{name:copy['voiceCall.start'],exact:true})).toBeDisabled();
  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),0);
  await call.getByRole('button',{name:copy['voiceCall.closePrevious'],exact:true}).click();
  await call.getByLabel(copy['voiceCall.agent'],{exact:true}).selectOption('cedar');
  await expect(call.locator('.voice-agent-description')).toHaveText(copy['voiceCall.agent.cedar']);
  await call.getByRole('button',{name:copy['voiceCall.start'],exact:true}).click();
  await expect(call).toContainText(copy['voiceCall.active']);assert.equal(chosenVoice,'cedar');
  await expect(page).toHaveURL(new RegExp('/movements\\?transaction='+person.transactionId+'$'));
  await expect(page.locator('.transaction-panel [data-transaction-id]')).toHaveCount(1);
  await expect(page.locator('.transaction-panel [data-transaction-id]')).toHaveAttribute('data-transaction-id',person.transactionId);
  await expect(page.locator('.transaction-panel [data-transaction-id]')).toBeInViewport();
  await expect(page.getByRole('heading',{name:copy.movements,exact:true})).toBeVisible();
  await page.setViewportSize({width:1366,height:768});
  await expect(page.locator('.spending-overview')).not.toHaveAttribute('open');
  await expect(page.locator('.movements-page')).not.toContainText(copy.activityNote);
  await expect(page.locator('.movements-page a[href="/documents"]')).toHaveCount(0);
  const patternsBox=await page.locator('.spending-overview').boundingBox();assert(patternsBox.height<65);
  assert.equal(await page.locator('.movement-highlighted').evaluate(el=>getComputedStyle(el).animationDuration),'2s');
  await expect(page.locator('.movement-extra-filters')).not.toHaveAttribute('open');
  const movementBounds=await page.locator('.transaction-panel').boundingBox();
  assert(movementBounds.y>=0&&movementBounds.y+movementBounds.height<=768,JSON.stringify(movementBounds));
  await expect(page.locator('.sidebar nav a[href="/complaints"]')).toBeInViewport();
  await page.screenshot({path:path.join(folder,'movement-visible-'+locale+'.png')});
  await page.setViewportSize({width:1512,height:1050});

  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),1,'Navigation must keep the same microphone/session');
  await expect(page.locator('.assistant-panel > .voice-call')).toHaveCount(1);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.chat-details-button')).not.toBeVisible();
  await expect(page.locator('.conversation-toolbar')).not.toBeVisible();
  await expect(page.locator('.chat-messages')).not.toBeVisible();
  await expect(page.locator('.paste-composer textarea')).not.toBeVisible();
  await expect(call.locator('select')).toHaveCount(0);
  const spoken={es:['No reconozco',' este cobro.','Vamos a revisarlo.','Sí, es ese.'],en:['I do not recognize',' this charge.','Let’s review it.','Yes, that one.'],pt:['Não reconheço',' esta cobrança.','Vamos verificar.','Sim, é essa.']}[locale];
  await page.evaluate(parts=>{
   const events=[['user',parts[0],100],['assistant',parts[2],500],['user',parts[1],200],['user',parts[3],1500]];
   for(const [i,[speaker,delta,start]]of events.entries()){
    const data=JSON.stringify({type:speaker==='user'?'session.input_transcript.delta':'session.output_transcript.delta',event_id:'caption-'+i,delta,start_ms:start,end_ms:start+100});
    window.__voiceCheck.channel.onmessage({data});window.__voiceCheck.channel.onmessage({data});
   }
  },spoken);
  await expect(call.locator('.voice-transcript-row')).toHaveCount(3);
  await expect(call.locator('.voice-transcript-row.user p').first()).toHaveText(spoken[0]+spoken[1]);
  await expect(call.locator('.voice-transcript-row.assistant p')).toHaveText(spoken[2]);
  await expect(call).toHaveAttribute('data-speaking','false'); // Captions alone are not playing audio.
  await page.evaluate(()=>{
   const audio=document.querySelector('.voice-call audio');audio.srcObject=new MediaStream();
   audio.dispatchEvent(new Event('playing'));
  });
  await expect(call).toHaveAttribute('data-speaking','false');
  await page.evaluate(()=>window.__voiceCheck.rms=.08);
  await expect(call).toHaveAttribute('data-speaking','true');
  await expect(call.locator('.voice-call-status')).toHaveText(copy['voiceCall.speaking']);
  assert.notEqual(await call.locator('.voice-agent-wave span').first().evaluate(el=>getComputedStyle(el).animationName),'none');
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await call.locator('.voice-agent-wave span').first().evaluate(el=>getComputedStyle(el).animationName),'none');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator('.assistant-panel').screenshot({path:path.join(folder,'speaking-'+locale+'.png')});
  await page.evaluate(()=>window.__voiceCheck.rms=0);
  await expect(call).toHaveAttribute('data-speaking','false');
  await expect(page.locator('.voice-bank-text')).toHaveCount(0);
  await call.getByRole('button',{name:copy['voiceCall.fullDetail'],exact:true}).click();
  await expect(page.locator('.voice-bank-text')).toHaveText(reply.text);
  await expect(page.locator('.voice-comparison-row')).toHaveCount(2);
  await axe('comparison-'+locale);
  await page.getByRole('dialog').screenshot({path:path.join(folder,'comparison-'+locale+'.png')});
  await page.getByRole('dialog').getByRole('button',{name:copy.close,exact:true}).click();
  await expect(call.getByRole('button',{name:copy['voiceCall.fullDetail'],exact:true})).toBeFocused();
  await call.getByRole('button',{name:copy['voiceCall.mute'],exact:true}).click();
  await expect(call.getByRole('button',{name:copy['voiceCall.unmute'],exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(call).toContainText(copy['voiceCall.muted']);
  await page.evaluate(()=>window.__voiceCheck.rms=.08);
  await expect(call).toHaveAttribute('data-speaking','true'); // Muting the client does not mute the agent.
  await page.evaluate(()=>document.querySelector('.voice-call audio').dispatchEvent(new Event('pause')));
  await expect(call).toHaveAttribute('data-speaking','false');
  assert.equal(await page.evaluate(()=>window.__voiceCheck.analysersClosed),1);
  await page.evaluate(()=>{window.__voiceCheck.rms=0;document.querySelector('.voice-call audio').dispatchEvent(new Event('playing'));});
  await call.getByRole('button',{name:copy['voiceCall.unmute'],exact:true}).click();
  await axe('active-'+locale);await page.locator('.assistant-panel').screenshot({path:path.join(folder,'call-'+locale+'.png')});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await axe('mobile-'+locale);
  await page.locator('.assistant-panel').scrollIntoViewIfNeeded();
  const panelBounds=await page.locator('.assistant-panel').boundingBox(),endBounds=await call.getByRole('button',{name:copy['voiceCall.end'],exact:true}).boundingBox();
  assert(endBounds.y>=panelBounds.y&&endBounds.y+endBounds.height<=panelBounds.y+panelBounds.height,'End button must stay inside the panel');
  assert(endBounds.y+endBounds.height<=844,'End button must fit on a phone screen');
  await page.locator('.assistant-panel').screenshot({path:path.join(folder,'mobile-'+locale+'.png')});
  // A long call must scroll its transcript, never grow over the bank page or hide controls.
  await page.evaluate(parts=>{
   for(let i=0;i<100;i++)window.__voiceCheck.channel.onmessage({data:JSON.stringify({
    type:i%2?'session.output_transcript.delta':'session.input_transcript.delta',event_id:'long-'+i,
    delta:parts[i%2?2:3],start_ms:10000+i*3000,end_ms:10100+i*3000})});
  },spoken);
  await expect(call.locator('.voice-transcript-row')).toHaveCount(103);
  for(const viewport of [{width:1512,height:1050},{width:390,height:844},{width:844,height:390}]){
   await page.setViewportSize(viewport);await call.scrollIntoViewIfNeeded();
   const layout=await call.evaluate(el=>{
    const bounds=selector=>{const b=el.querySelector(selector).getBoundingClientRect();return{top:b.top,bottom:b.bottom};};
    const body=el.querySelector('.voice-call-body'),panel=el.parentElement;
    return{header:bounds('.voice-call-heading'),body:bounds('.voice-call-body'),footer:bounds('.voice-call-footer'),
     inside:el.scrollHeight<=el.clientHeight+1&&panel.scrollHeight<=panel.clientHeight+1,
     scrollable:body.scrollHeight>body.clientHeight,atBottom:body.scrollHeight-body.clientHeight-body.scrollTop<5,
     panel:panel.getBoundingClientRect().toJSON(),width:document.documentElement.scrollWidth<=innerWidth+1};
   });
   assert(layout.inside&&layout.scrollable&&layout.width,JSON.stringify({viewport,layout}));
   assert(layout.body.top>=layout.header.bottom-1&&layout.body.bottom<=layout.footer.top+1);
   assert(layout.footer.bottom<=layout.panel.bottom+1&&layout.panel.height<=viewport.height);
  }
  await page.setViewportSize({width:390,height:844});await call.scrollIntoViewIfNeeded();
  await call.locator('.voice-call-body').focus();await page.keyboard.press('Control+Home');
  await expect.poll(()=>call.locator('.voice-call-body').evaluate(el=>el.scrollTop)).toBe(0);
  await page.evaluate(()=>window.__voiceCheck.channel.onmessage({data:JSON.stringify({type:'session.input_transcript.delta',event_id:'while-reading',delta:' Mensaje nuevo.',start_ms:500000,end_ms:500100})}));
  await expect(call.locator('.voice-transcript-row')).toHaveCount(104);
  assert.equal(await call.locator('.voice-call-body').evaluate(el=>el.scrollTop),0,'New captions must not interrupt reading older text');
  await call.locator('.voice-call-body').evaluate(el=>{el.scrollTop=el.scrollHeight;});
  await page.locator('.assistant-panel').screenshot({path:path.join(folder,'long-call-'+locale+'.png')});
  await page.setViewportSize({width:1512,height:1050});
  await call.getByRole('button',{name:copy['chatFlow.prepareClaim'],exact:true}).click();
  const review=page.locator('.chat-claim-review');
  await expect(review.locator('.chat-claim-summary')).not.toHaveText('');
  await expect(review.getByRole('checkbox')).toHaveCount(0);
  const unchanged=await(await context.request.get(origin+'/api/bootstrap')).json();
  assert.equal(unchanged.requests.filter(r=>r.kind==='claim').length,0,'Opening review does not register a claim');
  await review.getByRole('button',{name:copy['chatClaim.edit'],exact:true}).click();
  const summary=await review.locator('textarea').inputValue();assert(summary.length>=10);
  await review.locator('textarea').fill(summary+' '+{es:'Solicito revisión.',en:'Please review.',pt:'Solicito análise.'}[locale]);
  await review.getByRole('button',{name:copy['chatClaim.doneEditing'],exact:true}).click();
  await expect(review.locator('textarea')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});
  await expect(review.getByRole('button',{name:copy['chatClaim.register'],exact:true})).toBeInViewport();
  await review.screenshot({path:path.join(folder,'review-summary-'+locale+'.png')});
  await page.setViewportSize({width:1512,height:1050});

  await review.getByRole('button',{name:copy['chatClaim.register'],exact:true}).click();
  await expect(page).toHaveURL(/\/complaints\?case=NQ-/);
  await expect(call).toContainText('NQ-');
  await expect(page.locator('.claims-detail')).toBeInViewport();
  await page.screenshot({path:path.join(folder,'registered-case-'+locale+'.png')});
  assert.equal(await page.evaluate(()=>window.__voiceCheck.microphones),1);
  await expect(call).toContainText(copy['voiceCall.active']);
  await call.getByRole('button',{name:copy['voiceCall.end'],exact:true}).click();await expect(call).toHaveCount(0);await expect(page.locator('.paste-composer textarea')).toBeEnabled();
  await expect(page.locator('.paste-composer textarea')).toHaveValue('Borrador conservado');
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('NQ-');
  await expect(page.getByRole('button',{name:copy.startVoice,exact:true})).toBeFocused();
  await expect(page.locator('.chat-details-button')).toBeEnabled();
  await expect.poll(()=>closed).toBeGreaterThan(1);assert((await page.evaluate(()=>window.__voiceCheck.stopped))>0);
  assert.equal(await page.evaluate(()=>window.__voiceCheck.analysersClosed),2);
  report.checks.push({locale,disabledWithoutMicrophone:true,recoverPreviousCall:true,inlineVoiceOnly:true,chosenVoice,orderedTranscripts:true,audioDrivenAnimation:true,reducedMotion:true,longCallContained:true,keyboardScroll:true,bankResultSeparated:true,filteredMovementNavigation:true,microphonePreservedDuringNavigation:true,draftPreserved:true,closed:true});await context.close();
 }
 assert.deepEqual(report.errors,[]);await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({folder,...report},null,2));
}catch(error){if(page)await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});throw error;}
finally{await browser?.close();server.kill();await fs.writeFile(path.join(folder,'server.private.log'),diagnostics);}
