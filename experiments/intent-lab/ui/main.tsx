import { DialoguePanel } from './DialoguePanel';
import { ToolPlanPanel, type ToolPlan } from './ToolPlanPanel';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowRight, Bot, Check, ChevronDown, Download, FlaskConical, GitBranch, Globe2, MessageCircle, Play, Plus, Save, Settings2, ShieldCheck } from 'lucide-react';
import { translate, type CopyKey, type Language } from './locales';
import { messagesFor, prompts, scenarios, type Message } from './scenarios';
import '../../../src/tokens.css';
import './style.css';
import './simple.css';
import { safeNavigation } from '../../../src/navigation';

type Label = { id: string; copy: Record<Language, { title: string; summary: string }> };
type Action = { intent: string; kind: string; route: string | null; executes_operation: boolean };
type Problem = { source_label: string; intent: string; records: number; denominator: number };
type Meta = { providers: {jev:string;llm:string}; taxonomy: Label[]; actions: Record<string, Action>; tool_plans: Record<string, ToolPlan>; splits: Record<string, number>; corpus_sha256: string; evidence: { transcripts: number; distinct_texts: number; text_families: number; problems: Problem[]; contact_reasons: {source_label:string;records:number;unresolved:number}[]; digital_errors: {action:string;events:number;errors:number}[] } };
type Conversation = { id?: string; title: string; language: Language; messages: Message[]; expected: string | null; instructions: string };
type ProviderResult = {status:string;intent?:string;error?:string;provider_confidence?:number|null;probabilities?:Record<string,number>;latency_ms?:number;proposal?:Action;model?:string};
type LiveRun = {id:string;jev:ProviderResult;llm:ProviderResult;decision:{status:string;reason?:string};tool_plan?:ToolPlan;signature?:string};
type Original = {id:string;language:Language;occurrences:number;messages:Message[]};
type Measurement = { n: number; accuracy: number; macro_f1: number; p50_ms: number; p95_ms: number };
type Prediction = { id: string; text: string; language: Language; expected: string; intent: string; correct: boolean; slice: string };
type Method = Measurement & { method: string; api_cost_usd: number; by_language: Record<Language, Measurement>; predictions: Prediction[] };
type Report = { created_at: string; corpus_sha256: string; methods: Method[]; protocol: Record<string, unknown> };
type Condition = 'agreement' | 'disagreement' | 'unavailable' | 'uncertainty';
const languageNames = { es: 'Español', en: 'English', pt: 'Português' };

async function request<T>(path: string, body?: unknown, method = 'POST'): Promise<T> {
  const response = await fetch('/lab-api/' + path, body === undefined ? undefined : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error('request_failed');
  return response.json() as Promise<T>;
}
function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}

function App() {
  const [language, setLanguage] = useState<Language>(() => { try { const saved = localStorage.getItem('nexqori-lab-language'); return saved === 'pt' || saved === 'en' ? saved : 'es'; } catch { return 'es'; } });
  const [page, setPage] = useState<'walkthrough' | 'benchmark' | 'evidence'>('walkthrough');
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState(false);
  const [scenarioId, setScenarioId] = useState<CopyKey>('unknown');
  const [draft, setDraft] = useState<Conversation | null>(null);
  const [savedConversations, setSavedConversations] = useState<Conversation[]>([]);
  const [savedNotice, setSavedNotice] = useState(false);
  const [liveRun,setLiveRun]=useState<LiveRun|null>(null);
  const [executing,setExecuting]=useState(false);
  const [originals,setOriginals]=useState<Original[]>([]);
  const [editedText, setEditedText] = useState<string | null>(null);
  const [condition, setCondition] = useState<Condition>('agreement');
  const [prompt, setPrompt] = useState<string>(prompts.banking);
  const [preview, setPreview] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [filter, setFilter] = useState<Language | 'all'>('all');
  const [methodFilter, setMethodFilter] = useState('nlp-linear');
  const t = (key: CopyKey) => translate(language, key);
  const pct = (value: number) => new Intl.NumberFormat(language, { style: 'percent', maximumFractionDigits: 1 }).format(value);
  const num = (value: number) => new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(value);
  const title = (id: string) => meta?.taxonomy.find(item => item.id === id)?.copy[language].title || id;
  const scenario = scenarios.find(item => item.id === scenarioId)!;
  const messages = draft ? draft.messages.map(message => ({ ...message })) : messagesFor(scenario, language);
  if (!draft && editedText !== null) messages[messages.length - 1].content = editedText;
  const edited = !draft && editedText !== null && editedText !== messagesFor(scenario, language).at(-1)!.content;
  const expectedIntent = draft ? draft.expected : edited ? null : scenario.intent;
  const signature=JSON.stringify({messages,language:draft?.language||language,instructions:prompt});
  const shownRun=liveRun?.signature===signature?liveRun:null;
  const resultIntent=shownRun?shownRun.jev.intent||null:expectedIntent;
  const isFallback = !resultIntent || ['needs-clarification', 'multiple-intents', 'out-of-scope'].includes(resultIntent);
  const proposes = (shownRun?shownRun.jev.status==='ok':condition === 'agreement') && !isFallback;
  const action = resultIntent ? meta?.actions[resultIntent] : undefined;
  const toolPlan = shownRun ? shownRun.tool_plan : meta?.tool_plans?.[condition === 'agreement' && resultIntent ? resultIntent : 'needs-clarification'];
  const destination = resultIntent === 'account-balance' ? 'accounts' : resultIntent === 'account-activity' ? 'movements' : resultIntent === 'my-cards' ? 'cards' : resultIntent === 'request-status' ? 'requests' : 'services';
  const bankRoute = action?.route ? safeNavigation({tool:'navigate_in_app',destination,route:action.route,...(destination==='services'?{serviceId:resultIntent}:{})}) : null;
  const selectedMethod = report?.methods.find(m => m.method === methodFilter);
  const mistakes = selectedMethod?.predictions.filter(p => !p.correct && (filter === 'all' || p.language === filter)) || [];

  async function load() { setError(false); try { const [metadata, last, conversations,originalData] = await Promise.all([request<Meta>('meta'), request<Report | null>('results'), request<{conversations:Conversation[]}>('conversations'),request<{conversations:Original[]}>('originals')]); setMeta(metadata); setReport(last); setSavedConversations(conversations.conversations);setOriginals(originalData.conversations);
    const caseId = new URLSearchParams(window.location.search).get('case');
    const selected = conversations.conversations.find(item => item.id === caseId);
    if (selected) { setDraft(structuredClone(selected)); setPrompt(selected.instructions); setLanguage(selected.language); }
  } catch { setError(true); } }
  useEffect(() => { void load(); }, []);
  useEffect(() => { document.documentElement.lang = language; document.title = 'Nexqori · ' + translate(language, 'lab'); try { localStorage.setItem('nexqori-lab-language', language); } catch { /* preference is optional */ } setEditedText(null); setPreview(null); }, [language]);
  function choose(id: CopyKey) { setScenarioId(id); setDraft(null); setEditedText(null); setPreview(null); setCondition('agreement'); setSavedNotice(false); }
  function startConversation(customize = false) { setDraft({ title: customize ? t(scenario.id) : '', language, messages: customize ? messages : [{role:'user',content:''}], expected: customize && !edited ? scenario.intent : null, instructions: prompt }); setSavedNotice(false); setPreview(null); }
  function selectConversation(id: string) { const saved = savedConversations.find(item => item.id === id); if (saved) { setDraft(structuredClone(saved)); setPrompt(saved.instructions); setSavedNotice(false); setPreview(null); } else choose(id as CopyKey); }
  function changeMessage(index: number, patch: Partial<Message>) { if (!draft) return; setDraft({...draft, expected:null, messages:draft.messages.map((message,i) => i===index ? {...message,...patch} : message)}); setPreview(null); setSavedNotice(false); }
  async function saveConversation() { if (!draft) return; setError(false); try { const {id,title,language,messages,expected}=draft; const saved=await request<Conversation>('conversations'+(id?'/'+id:''), {title,language,messages,expected,instructions:prompt},id?'PUT':'POST'); setDraft(saved); setSavedConversations(old => [...old.filter(item=>item.id!==saved.id),saved]); setSavedNotice(true); } catch {setError(true);} }
  async function inspect() { setError(false); try { setPreview(await request('preview', { messages, language: draft?.language || language, instructions: prompt })); } catch { setError(true); } }
  async function run() { setBusy(true); setError(false); try { setReport(await request<Report>('benchmark', {})); } catch { setError(true); } finally { setBusy(false); } }
  async function executeCase(){setExecuting(true);setError(false);try{const result=await request<LiveRun>('classify',{messages,language:draft?.language||language,instructions:prompt});setLiveRun({...result,signature});}catch{setError(true);}finally{setExecuting(false);}}
  const providerError=(code:string|undefined)=>t(code==='missing_key'?'missingKey':code==='auth_error'?'authError':code==='rate_limited'?'rateError':code==='timeout'?'timeError':'apiFailure');
  function exportVariant() { download('nexqori-prompt-variant.json', { version: 1, instructions: prompt, language: draft?.language || language, conversation: messages, source: 'authored_walkthrough_not_model_output', expected: expectedIntent, corpus_sha256: meta?.corpus_sha256, created_at: new Date().toISOString(), providers_run: false }); }
  function exportConversations() {download('nexqori-conversations.json',{version:1,conversations:[...scenarios.map(s=>({id:s.id,title:t(s.id),language,messages:messagesFor(s,language),expected:s.intent,source:'authored_from_dataset_categories',instructions:prompts.banking})),...savedConversations]});}
  const validInput = messages.every(message=>message.content.trim()) && !!prompt.trim();
  const canSave = !!draft?.title.trim() && validInput && messages.at(-1)?.role==='user';

  return <>
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); setPage('walkthrough'); }}><span className="brand-mark">n</span>nexqori<span className="lab-tag">LAB</span></a>
      <nav aria-label={t('lab')}>{(['walkthrough', 'benchmark', 'evidence'] as const).map(tab => <button key={tab} className={page === tab ? 'nav-active' : ''} aria-current={page === tab ? 'page' : undefined} onClick={() => setPage(tab)}>{t(tab)}</button>)}</nav>
      <div className="header-tools"><span className="local-badge"><span />{t('local')}</span><details className="language"><summary><Globe2 size={17} />{languageNames[language]}<ChevronDown size={15} /></summary><div>{(Object.keys(languageNames) as Language[]).map(lang => <button key={lang} lang={lang} aria-pressed={lang === language} onClick={e => { setLanguage(lang); e.currentTarget.closest('details')!.open = false; }}>{languageNames[lang]}{lang === language && <Check size={15} />}</button>)}</div></details></div>
    </header>
    <main>
      {error && <div role="alert" className="error">{t('loadError')} <button onClick={() => void load()}>{t('retry')}</button></div>}
      {!meta ? <p role="status">{t('loading')}</p> : <>
        {page === 'walkthrough' && <>
          <div className="simple-heading"><div><h1>{t('simpleTitle')}</h1><p>{t('simpleIntro')}</p></div><div className="button-row"><button className="primary" onClick={() => startConversation()}><Plus size={17}/>{t('newConversation')}</button><button className="secondary" onClick={exportConversations}><Download size={16}/>{t('downloadConversations')}</button></div></div>
          <p className="reference-line"><FlaskConical size={16}/>{t('authored')} {t('referenceVsRun')}</p>
          <div className="workspace simple-workspace">
            <section className="panel conversation-panel"><div className="panel-heading"><MessageCircle size={20}/><h2>{t('conversation')}</h2></div>
              <label className="field-label" htmlFor="case">{t('caseLabel')}</label><select id="case" value={draft ? draft.id || 'draft' : scenarioId} onChange={e => selectConversation(e.target.value)}><optgroup label={t('builtIn')}>{scenarios.map(item => <option value={item.id} key={item.id}>{t(item.id)}</option>)}</optgroup>{savedConversations.length>0 && <optgroup label={t('mine')}>{savedConversations.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</optgroup>}{draft&&!draft.id&&<option value="draft">{t('draft')}</option>}</select>
              {!draft && <div className="case-source"><span>{num(meta.evidence.problems.find(p=>p.intent===scenario.intent)?.records || 0)} {t('casesCount')} · {t('sourceNote')}</span><button className="text-button" onClick={()=>startConversation(true)}>{t('customize')}</button></div>}
              {draft ? <div className="custom-editor">
                <label className="field-label" htmlFor="conversation-title">{t('conversationTitle')}</label><input id="conversation-title" value={draft.title} maxLength={120} onChange={e=>{setDraft({...draft,title:e.target.value});setSavedNotice(false);}}/>
                <label className="field-label" htmlFor="conversation-language">{t('conversationLanguage')}</label><select id="conversation-language" value={draft.language} onChange={e=>{setDraft({...draft,language:e.target.value as Language});setSavedNotice(false);}}>{(Object.keys(languageNames) as Language[]).map(lang=><option key={lang} value={lang}>{languageNames[lang]}</option>)}</select>
                {draft.messages.map((message,i)=><div className="edit-message" key={i}><div><label className="field-label" htmlFor={'role-'+i}>{t('role')} {i+1}</label><select id={'role-'+i} value={message.role} onChange={e=>changeMessage(i,{role:e.target.value as Message['role']})}><option value="user">{t('client')}</option><option value="assistant">{t('assistant')}</option></select><button className="text-button" disabled={draft.messages.length===1} onClick={()=>{setDraft({...draft,expected:null,messages:draft.messages.filter((_,index)=>index!==i)});setSavedNotice(false);setPreview(null);}}>{t('removeMessage')}</button></div><label className="field-label" htmlFor={'message-'+i}>{t('messageText')} {i+1}</label><textarea id={'message-'+i} lang={draft.language} value={message.content} maxLength={2000} onChange={e=>changeMessage(i,{content:e.target.value})}/></div>)}
                <button className="secondary" disabled={draft.messages.length>=10} onClick={()=>{setDraft({...draft,expected:null,messages:[...draft.messages,{role:draft.messages.at(-1)?.role==='user'?'assistant':'user',content:''}]});setSavedNotice(false);}}><Plus size={15}/>{t('addMessage')}</button>
                <label className="field-label" htmlFor="expected-intent">{t('goldLabel')}</label><select id="expected-intent" value={draft.expected||''} onChange={e=>{setDraft({...draft,expected:e.target.value||null});setSavedNotice(false);}}><option value="">{t('unlabelled')}</option>{meta.taxonomy.map(item=><option key={item.id} value={item.id}>{item.copy[language].title}</option>)}</select>
                {messages.at(-1)?.role!=='user'&&<p className="small-note">{t('endCustomer')}</p>}<p className="small-note">{t('localJson')}</p><button className="primary" disabled={!canSave} onClick={()=>void saveConversation()}><Save size={16}/>{t('save')}</button>{savedNotice&&<p className="save-notice" role="status"><Check size={15}/>{t('saved')}</p>}
              </div> : <div className="chat">{messages.map((message,i)=><div className={'message '+message.role} key={i}><span className="message-role">{t(message.role==='user'?'client':'assistant')}</span>{i===messages.length-1?<><label className="sr-only" htmlFor="customer-message">{t('lastMessage')}</label><textarea id="customer-message" value={message.content} maxLength={2000} onChange={e=>{setEditedText(e.target.value);setPreview(null);}}/></>:<p>{message.content}</p>}</div>)}</div>}
              {edited&&<p className="small-note">{t('custom')}</p>}
              <p className="small-note">{t('runHint')}</p><div className="button-row"><button className="primary" disabled={!validInput||executing} onClick={()=>void executeCase()}><Play size={17}/>{t(executing?'executing':'executeCase')}</button><button className="secondary" disabled={!validInput} onClick={()=>void inspect()}>{t('inspect')}<ArrowRight size={16}/></button>{!draft&&<button className="text-button" onClick={()=>choose(scenarioId)}>{t('restore')}</button>}</div>
              <details className="prompt-editor"><summary><Settings2 size={17}/>{t('prompt')}<ChevronDown size={16}/></summary><p>{t('promptHint')}</p><label className="field-label" htmlFor="prompt-version">{t('promptRevision')}</label><select id="prompt-version" value={prompt===prompts.general?'general':prompt===prompts.banking?'banking':'custom'} onChange={e=>{if(e.target.value!=='custom')setPrompt(prompts[e.target.value as keyof typeof prompts]);setPreview(null);setSavedNotice(false);}}><option value="general">{t('basePrompt')}</option><option value="banking">{t('bankingPrompt')}</option><option value="custom" disabled>—</option></select><label className="field-label" htmlFor="instructions">{t('instructionsLimit')}</label><textarea id="instructions" className="instructions" value={prompt} maxLength={4000} onChange={e=>{setPrompt(e.target.value);setPreview(null);setSavedNotice(false);}}/><p className="small-note">{t('promptNote')}</p><button className="secondary" onClick={exportVariant} disabled={!prompt.trim()}><Download size={16}/>{t('saveVariant')}</button></details>
              {preview!==null&&<details className="payload" open><summary>{t('inspect')}</summary><pre>{JSON.stringify(preview,null,2)}</pre></details>}
            </section>
            <div className="decision-side"><section className="comparison"><div className="comparison-header"><h2>Jev + LLM</h2><p>{t('promptHint')}</p></div><div className="model-grid">{(['Jev','LLM'] as const).map((model,i)=>{
              const live=shownRun?(i?shownRun.llm:shownRun.jev):null;
              const referenceIntent=!expectedIntent||(condition==='unavailable'&&i===1)?null:condition==='disagreement'&&i===1?(expectedIntent==='incorrect-charge'?'unrecognized-charge':'needs-clarification'):condition==='uncertainty'?'needs-clarification':expectedIntent;
              const displayedIntent=live?live.intent:referenceIntent;
              return <article className="model-card compact-model" key={model}><div className="model-heading"><span className={'model-logo model-'+i}>{i?<Bot size={21}/>:'J'}</span><div><h3>{model}</h3><span className="status-pill">{t(live?.status==='ok'?'actualResult':(i?meta.providers.llm:meta.providers.jev)==='configured'?'ready':'pending')}</span></div></div><div className="model-intent"><span>{t(live?'reportedIntent':'expected')}</span><strong>{displayedIntent?title(displayedIntent):t('noResult')}</strong><code>{displayedIntent||'—'}</code></div><p className="stat-note">{t('confidence')}: {live?.provider_confidence!=null?pct(live.provider_confidence):'—'} · {t('latency')}: {live?.latency_ms!==undefined&&live.latency_ms!==null?num(live.latency_ms)+' ms':'—'}</p>{live?.intent&&live.probabilities&&<p className="stat-note">{t('probability')}: {pct(live.probabilities[live.intent])}</p>}{live?.status==='error'&&<p className="small-note" role="alert">{providerError(live.error)}</p>}<details className="contract"><summary>{t('output')}</summary><pre>{JSON.stringify(live||{status:'not_run',intent:null,probabilities:null,provider_confidence:null,latency_ms:null},null,2)}</pre></details></article>;
            })}</div></section>
              <section className="decision-panel compact-decision"><h2>{t('routing')}</h2>{shownRun?<button className="text-button" onClick={()=>setLiveRun(null)}>{t('expectedView')}</button>:<div className="condition-tabs" role="group" aria-label={t('exploreState')}>{(['agreement','disagreement','unavailable','uncertainty'] as const).map(c=><button key={c} aria-pressed={condition===c} className={condition===c?'selected':''} onClick={()=>setCondition(c)}>{t(c)}</button>)}</div>}<p>{shownRun?(shownRun.jev.status==='ok'&&shownRun.llm.status==='ok'?t(shownRun.jev.intent===shownRun.llm.intent?'comparisonAgreement':'disagreementText'):shownRun.jev.status==='ok'?t('singleReading'):providerError(shownRun.jev.error)):t(condition==='agreement'&&!isFallback?'agreementText':condition==='disagreement'?'disagreementText':condition==='unavailable'?'unavailableText':'uncertainText')}</p>
                <div className="next-action"><div><span className="step-label">{t('flow')}</span><h3>{proposes&&resultIntent?title(resultIntent):t('noAction')}</h3><p>{t('action')}: {proposes?t(action?.kind==='view'?'view':'prepare'):t('followup')}</p>{proposes&&<><code>{action?.route}</code>{bankRoute&&<a className="button secondary" href={'http://localhost:5180'+bankRoute} target="_blank" rel="noopener noreferrer">{t('openBankFlow')}<ArrowRight size={16}/></a>}<p className="small-note">{t('bankFlowHint')}</p></>}</div><GitBranch size={25} aria-hidden="true"/></div>
                {toolPlan && <ToolPlanPanel plan={toolPlan} language={language}/>}
                <details className="next-details"><summary>{t('formPreview')}</summary><div className="form-preview">{(proposes?(resultIntent==='unrecognized-charge'||resultIntent==='incorrect-charge'?['movement','details','proof','review']:['details','review']):['followup']).map((field,i)=><span key={field}><b>{i+1}</b>{t(field as CopyKey)}</span>)}</div></details><p className="small-note"><ShieldCheck size={15}/>{t('noExecute')}</p>
              </section><p className="small-note">{t('pendingText')}</p>
            </div>
          </div>
          <DialoguePanel key={(draft?.id||scenarioId)+language} language={draft?.language||language} messages={messages} instructions={prompt}/><details className="panel evidence-section originals"><summary>{t('originalTexts')}</summary><p>{t('originalsHint')} {t('originalsLanguage')}</p>{!originals.length&&<p>{t('originalEmpty')}</p>}{originals.map((item,i)=><article key={item.id}><h3>{i+1}. <code>{item.id}</code></h3><p>{num(item.occurrences)} · {t('records')}</p>{item.messages.map((message,index)=><div key={index} className={'message '+message.role}><span className="message-role">{t(message.role==='user'?'client':'assistant')}</span><p lang="es">{message.content}</p></div>)}</article>)}</details>
        </>}
        {page === 'benchmark'  && <>
          <div className="hero"><div><p className="eyebrow">NLP · JEV · LLM · JEV + LLM</p><h1>{t('benchmarkTitle')}</h1><p className="intro">{t('benchmarkIntro')}</p></div><Activity className="hero-icon" size={50} /></div>
          <div className="metric-strip">{(['train', 'validation', 'test'] as const).map(split => <article key={split}><span>{t(split)}</span><strong>{num(meta.splits[split])}</strong></article>)}<article><span>ES / EN / PT</span><strong>23 <small>{t('expectedLabel').toLowerCase()}</small></strong></article></div>
          <div className="reference-notice"><FlaskConical size={20} /><p>{t('seedWarning')}</p></div><div className="button-row benchmark-actions"><button className="primary" onClick={() => void run()} disabled={busy}><Play size={17} />{t(busy ? 'running' : 'run')}</button>{report && <button className="secondary" onClick={() => download('nexqori-intent-benchmark.json', report)}><Download size={17} />{t('export')}</button>}<span role="status">{busy ? t('running') : report ? new Date(report.created_at).toLocaleString(language) : ''}</span></div>
          <div className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>{t('method')}</th><th>{t('accuracy')}</th><th>{t('macro')}</th><th>p95 · ms</th><th>{t('cost')}</th></tr></thead><tbody>{['nlp-centroid', 'nlp-linear', 'jev', 'llm', 'jev+llm'].map(id => { const m = report?.methods.find(method => method.method === id); return <tr key={id}><th>{({ 'nlp-centroid': 'NLP · TF-IDF / cosine', 'nlp-linear': 'NLP · TF-IDF / logistic', jev: 'Jev', llm: 'LLM', 'jev+llm': 'Jev + LLM' })[id]}<small>{t(m ? 'measured' : 'notMeasured')}</small></th><td>{m ? pct(m.accuracy) : '—'}</td><td>{m ? pct(m.macro_f1) : '—'}</td><td>{m ? num(m.p95_ms) : '—'}</td><td>{m ? '$0' : '—'}</td></tr>; })}</tbody></table></div></div>
          <p className="small-note">{t('costNote')}</p>{!report && <p className="empty-state">{t('noBenchmark')}</p>}
          {report && <section className="panel errors-panel"><div className="panel-heading"><Activity size={22} /><h2>{t('errorReview')}</h2></div><div className="filters"><label>{t('method')}<select value={methodFilter} onChange={e => setMethodFilter(e.target.value)}>{report.methods.map(m => <option key={m.method} value={m.method}>{m.method}</option>)}</select></label><label>Idioma / Language<select value={filter} onChange={e => setFilter(e.target.value as Language | 'all')}><option value="all">{t('all')}</option>{(Object.keys(languageNames) as Language[]).map(l => <option key={l} value={l}>{languageNames[l]}</option>)}</select></label></div><div className="language-metrics">{selectedMethod && (Object.keys(languageNames) as Language[]).map(lang => <span key={lang}>{languageNames[lang]} <strong>{pct(selectedMethod.by_language[lang].macro_f1)}</strong> F1</span>)}</div><div className="table-scroll"><table><thead><tr><th>{t('phrase')}</th><th>{t('expectedLabel')}</th><th>{t('predicted')}</th></tr></thead><tbody>{mistakes.map(row => <tr key={row.id}><td lang={row.language}><small>{row.language.toUpperCase()} · {row.id}</small>{row.text}</td><td>{title(row.expected)}</td><td>{title(row.intent)}</td></tr>)}</tbody></table>{!mistakes.length && <p>{t('noErrors')}</p>}</div></section>}
          <p className="connection-note"><GitBranch size={20} />{t('compareNext')}</p>
        </>}
        {page === 'evidence' && <>
          <div className="simple-heading"><div><h1>{t('evidence')}</h1><p>{t('complaintScope')}</p></div></div><p className="reference-line">{t('mappingNote')}</p>
          <section className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>{t('problem')}</th><th>{t('records')}</th><th>{t('share')}</th><th>{t('flow')}</th><th>{t('conversation')}</th></tr></thead><tbody>{meta.evidence.problems.map(problem=><tr key={problem.intent}><th>{problem.intent==='needs-clarification'?t('noSubcategory'):t(scenarios.find(s=>s.intent===problem.intent)!.id)}<small lang="es">{problem.source_label}</small></th><td>{num(problem.records)}</td><td>{pct(problem.records/problem.denominator)}</td><td><code>{meta.actions[problem.intent].route||t('noAction')}</code></td><td>{scenarios.find(s=>s.intent===problem.intent)&&<button className="text-button" onClick={()=>{choose(scenarios.find(s=>s.intent===problem.intent)!.id);setPage('walkthrough');}}>{t('inspectCase')}</button>}</td></tr>)}</tbody></table></div></section><p className="small-note">Fuente / Source: notebooks/servicios_nexqori/complaint_needs.csv</p>
          <details className="panel evidence-section"><summary>{t('contactReasons')}</summary><p>{t('contactScope')}</p><div className="table-scroll"><table><thead><tr><th>{t('problem')}</th><th>{t('records')}</th><th>{t('unresolved')}</th><th>{t('action')}</th></tr></thead><tbody>{meta.evidence.contact_reasons.map(row=><tr key={row.source_label}><th lang="es">{row.source_label}</th><td>{num(row.records)}</td><td>{num(row.unresolved)}</td><td>{t('noAction')}</td></tr>)}</tbody></table></div></details>
          <details className="panel evidence-section"><summary>{t('digitalProblems')}</summary><p>{t('digitalScope')}</p><div className="table-scroll"><table><thead><tr><th>{t('action')}</th><th>{t('eventCount')}</th><th>{t('errorCount')}</th><th>{t('flow')}</th></tr></thead><tbody>{meta.evidence.digital_errors.map((row,i)=><tr key={i}><th><code>{row.action==='Sin acción'?t('noActionLabel'):row.action}</code></th><td>{num(row.events)}</td><td>{num(row.errors)}</td><td>{title('app-support')}</td></tr>)}</tbody></table></div></details>
          <details className="panel evidence-section"><summary>{t('allServices')}</summary><div className="table-scroll"><table><thead><tr><th>{t('flow')}</th><th>{t('action')}</th></tr></thead><tbody>{meta.taxonomy.map(item=><tr key={item.id}><th>{item.copy[language].title}</th><td><code>{meta.actions[item.id].route||t('noAction')}</code></td></tr>)}</tbody></table></div></details>
          <details className="panel evidence-section protocol"><summary>{t('protocol')}</summary><p>{t('coverage')}</p><p>{num(meta.evidence.transcripts)} · {t('transcripts')} / {num(meta.evidence.distinct_texts)} · {t('distinct')} / {num(meta.evidence.text_families)} · {t('families')}</p><ol>{(['rule1','rule2','rule3','rule4'] as const).map(key=><li key={key}>{t(key)}</li>)}</ol><p>{t('seedWarning')}</p><code>SHA-256 {meta.corpus_sha256}</code><p><a href="https://docs.typesafe.ai/models" target="_blank" rel="noreferrer">{t('source')} ↗</a></p></details>
        </>}
      </>}
    </main><footer>nexqori <span>·</span> {t('lab')} <span>·</span> ES / EN / PT</footer>
  </>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
