import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import { parseEnv } from 'node:util';
import assert from 'node:assert/strict';
const env=parseEnv(await fs.readFile('.env','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1050},locale:'es-MX'});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const out='.local/verification';const checks=[];
await context.addInitScript(()=>{window.__audioRequests=0;if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>{window.__audioRequests++;return Promise.reject(new Error('Unexpected audio capture'));};});
const copy=Object.fromEntries(await Promise.all(['es','en','pt'].map(async l=>[l,JSON.parse(await fs.readFile('src/locales/'+l+'.json','utf8'))])));
async function language(lang){await page.locator('.language-trigger').click();await page.locator('[data-locale="'+lang+'"]').click();await page.waitForFunction(l=>document.documentElement.lang===l,lang);}
async function axe(name){const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();checks.push({name,violations:a.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))});}
try{
 await page.goto('http://localhost:5180');await page.getByRole('button',{name:copy.es.createProfile,exact:true}).click();
 for(const lang of ['es','en','pt']){await language(lang);for(const width of [1440,390]){await page.setViewportSize({width,height:1050});await axe('registration-'+lang+'-'+width);await page.screenshot({path:out+'/registration-'+lang+'-'+width+'.png',fullPage:true});}}
 await page.setViewportSize({width:1440,height:1050});await language('es');
 const suffix=Date.now().toString();const testName='Verificación · Registro y auditoría';
 await page.getByLabel(copy.es.fullName,{exact:true}).fill(testName);await page.locator('input[type=email]').fill('verificacion.'+suffix+'@example.com');
 await page.getByLabel(new RegExp(copy.es.identityNumber)).fill('V'+suffix);await page.locator('input[type=date]').fill('2010-01-01');
 await page.locator('input[type=password]').nth(0).fill('Verification-only-'+suffix+'!');await page.locator('input[type=password]').nth(1).fill('Verification-only-'+suffix+'!');
 await page.getByRole('button',{name:copy.es.nextStep,exact:true}).click();await page.getByRole('alert').filter({hasText:copy.es['error.adult_required']}).waitFor();
 await page.locator('input[type=date]').fill('1960-01-01');await page.getByRole('button',{name:copy.es.nextStep,exact:true}).click();
 await page.getByLabel(copy.es.bankingExperience,{exact:false}).selectOption('occasional');await page.getByLabel(copy.es.digitalExperience,{exact:false}).selectOption('learning');await axe('experience-step');
 await page.getByRole('button',{name:copy.es.nextStep,exact:true}).click();await page.getByRole('checkbox').check();await axe('review-step');
 const registration=page.waitForResponse(r=>r.url().endsWith('/api/auth/register'));
 await page.getByRole('button',{name:copy.es.createProfile,exact:true}).click();const registered=await(await registration).json();assert.equal(registered.user.experience.ageBand,'60_plus');assert.equal(registered.user.experience.effectiveAssistance,'guided');
 await page.getByRole('heading',{name:copy.es.guidedStartTitle}).waitFor();
 for(const lang of ['es','en','pt']){await language(lang);await page.getByRole('button',{name:copy[lang].startVoice,exact:true}).click();await page.getByRole('dialog').getByText(copy[lang].voiceSoon).waitFor();await axe('voice-'+lang);await page.screenshot({path:out+'/voice-'+lang+'.png'});await page.getByRole('button',{name:copy[lang].voiceContinue,exact:true}).click();}
 assert.equal(await page.evaluate(()=>window.__audioRequests),0);await language('es');
 const pasted='Verificación · Texto pegado\n'+('Quiero revisar lo ocurrido con mi consulta.\n'.repeat(8));
 await page.locator('[data-assistant-input]').evaluate((el,text)=>{const dt=new DataTransfer();dt.setData('text/plain',text);el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));},pasted);
 await page.locator('.pasted-card').waitFor();await page.locator('.pasted-card summary').click();assert.equal(await page.locator('.pasted-card pre').innerText(),pasted);
 await page.getByRole('button',{name:copy.es.removePasted}).click();assert.equal(await page.locator('.pasted-card').count(),0);
 await page.locator('[data-assistant-input]').evaluate((el,text)=>{const dt=new DataTransfer();dt.setData('text/plain',text);el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));},pasted);
 await page.locator('[data-assistant-input]').fill('Ayúdame a revisar este texto.');await page.screenshot({path:out+'/pasted-text.png',fullPage:true});
 await page.locator('.paste-entry button').click();await page.locator('.chat-bubble.user').filter({hasText:'Verificación · Texto pegado'}).waitFor();assert.equal(await page.locator('.pasted-card').count(),0);
 await page.getByRole('button',{name:copy.es.logout,exact:true}).click();await page.locator('input[autocomplete=username]').fill('admin@nexqori.com');await page.locator('input[type=password]').fill(env.ADMIN_PASSWORD);await page.locator('form button[type=submit],form button.primary').click();
 await page.locator('.audit-panel').waitFor();await page.locator('.audit-filters select').nth(0).selectOption(registered.user.id);await page.locator('.audit-panel').getByRole('button',{name:copy.es.viewConversation}).first().click();
 await page.getByRole('dialog').getByText(pasted.trimEnd(),{exact:false}).waitFor();await axe('audit-conversation');await page.screenshot({path:out+'/audit-conversation.png',fullPage:true});await page.getByRole('button',{name:copy.es.close,exact:true}).click();
 await page.locator('.audit-panel').getByRole('button',{name:copy.es.auditRefresh,exact:true}).click();await page.locator('.audit-panel td').getByText(copy.es['auditActions.conversation_viewed'],{exact:true}).first().waitFor();await axe('audit-panel');await page.screenshot({path:out+'/audit-panel.png',fullPage:true});
 assert.deepEqual(errors,[]);assert.equal(checks.flatMap(c=>c.violations).length,0,JSON.stringify(checks));
 await fs.writeFile(out+'/registration-audit.json',JSON.stringify({checks,errors,registeredUser:registered.user.id},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,registration:true,paste:true,audit:true,voice:'UI only; zero audio requests'}));
}catch(e){await page.screenshot({path:out+'/feature-failure.png',fullPage:true});console.log(await page.locator('input:invalid').evaluateAll(els=>els.map(el=>({type:el.type,message:el.validationMessage}))));throw e;}finally{await browser.close();}
