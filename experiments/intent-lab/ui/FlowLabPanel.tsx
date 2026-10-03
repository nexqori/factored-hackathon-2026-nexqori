import { useEffect, useMemo, useState } from 'react';
import { ReactFlow, Background, applyNodeChanges, Position, MarkerType, type Node, type Edge, type ReactFlowInstance } from '@xyflow/react';
import { Download, GitBranch, Play, Save } from 'lucide-react';
import { translate, type Language } from './locales';
import { ft, fieldTitle, type FlowKey } from './flowLocales';
import { messagesFor, prompts, scenarios, type Message } from './scenarios';
import { ToolPlanPanel, type ToolPlan } from './ToolPlanPanel';
import '@xyflow/react/dist/style.css';
import './flow.css';

type Definition = {intent:string;title:string;summary:string;family:string;fields:string[];questions:Record<string,string>;instructions:string;tool_plan:ToolPlan};
type FlowMap = {version:string;revision:number;definitions:Definition[]};
type SavedCase = {id:string;title:string;language:Language;messages:Message[]};
type Provider = {status:string;intent?:string;model?:string;latency_ms?:number;probabilities?:Record<string,number>;assessment?:string;error?:string};
type Result = {id:string;thread_id:string;created_at:string;language:Language;config_revision:number;definition:Definition|null;jev:Provider;llm:Provider;route_family:string|null;state:FlowKey;reply:string;missing_fields:string[];observations:{field:string;quote:string;message_index:number}[];questions:{field:string;text:string}[];tool_plan:ToolPlan;latency_ms:number;stages:{id:string;source:string;status:string;value:string|null}[];input_messages?:Message[]};
type RunSummary = {id:string;created_at:string;state:FlowKey;title:string};
async function api<T>(path:string, body?:unknown, method='POST'):Promise<T> {
  const response = await fetch('/lab-api/'+path, body === undefined ? {} : {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}
function download(value:unknown) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='nexqori-flow-traces.json';link.click();URL.revokeObjectURL(url);
}

export function FlowLabPanel({language}:{language:Language}) {
  const t=(key:FlowKey)=>ft(language,key);
  const ms=(value?:number)=>value===undefined?'—':new Intl.NumberFormat(language,{maximumFractionDigits:1}).format(value);
  const [map,setMap]=useState<FlowMap|null>(null), [selected,setSelected]=useState('unrecognized-charge');
  const [caseId,setCaseId]=useState('unknown'), [savedCases,setSavedCases]=useState<SavedCase[]>([]);
  const [history,setHistory]=useState<Message[]>([]),[results,setResults]=useState<Result[]>([]),[view,setView]=useState(0);
  const [text,setText]=useState(messagesFor(scenarios[0],language).at(-1)!.content),[caseTitle,setCaseTitle]=useState('');
  const [questions,setQuestions]=useState<Record<string,string>>({}),[instructions,setInstructions]=useState('');
  const [busy,setBusy]=useState(false),[saving,setSaving]=useState(false),[notice,setNotice]=useState<FlowKey|null>(null),[error,setError]=useState<FlowKey|null>(null);
  const [stage,setStage]=useState('decision'), [instance,setInstance]=useState<ReactFlowInstance|null>(null);
  const [lastInput,setLastInput]=useState<Message[]>([]);
  const [savedRuns,setSavedRuns]=useState<RunSummary[]>([]);
  const result=results[view];
  const definition=map?.definitions.find(d=>d.intent===selected);
  const activeDefinition=result?result.definition:definition;
  const preset=scenarios.find(s=>s.id===caseId);
  const seed=preset?messagesFor(preset,language):(savedCases.find(s=>s.id===caseId)?.messages||[]);
  async function load() {
    try {setMap(await api<FlowMap>('flow-map?language='+language));setError(null);} catch {setError('loadError');}
  }
  async function refreshRuns() {setSavedRuns((await api<{runs:RunSummary[]}>('flow-history?language='+language)).runs);}
  async function restore(id:string) {
    if(!id)return;setBusy(true);setError(null);
    try {
      const record=await api<{kind:string;messages:Message[];result:Result}>('runs/'+id);
      if(record.kind!=='flow')throw new Error('invalid_run');
      if(record.result.language!==language)return;
      const value={...record.result,input_messages:record.messages};
      setResults([value]);setView(0);setLastInput(record.messages);setCaseId('custom');setText('');setNotice(null);
      setHistory(value.state==='provider_unavailable'?record.messages.slice(0,-1):[...record.messages,{role:'assistant',content:value.reply}]);
      if(value.state==='provider_unavailable')setText(record.messages.at(-1)?.content||'');
      if(value.definition)setSelected(value.definition.intent);
    } catch {setError('loadError');} finally {setBusy(false);}
  }
  useEffect(()=>{void load();void refreshRuns().catch(()=>setError('loadError'));void api<{conversations:SavedCase[]}>('conversations').then(v=>setSavedCases(v.conversations)).catch(()=>setError('loadError'));const runId=new URLSearchParams(location.search).get('run');if(runId)void restore(runId);},[language]);
  useEffect(()=>{if(definition){setQuestions({...definition.questions});setInstructions(definition.instructions);}},[definition]);
  function chooseCase(id:string) {
    setCaseId(id);setHistory([]);setResults([]);setView(0);setLastInput([]);setNotice(null);setError(null);setCaseTitle('');
    const scenario=scenarios.find(s=>s.id===id), saved=savedCases.find(s=>s.id===id);
    setText((scenario?messagesFor(scenario,language):saved?.messages)?.at(-1)?.content||'');
    if(scenario)setSelected(scenario.intent);
  }
  async function execute() {
    const prefix=history.length?history:seed.slice(0,-1);
    const input:Message[]=[...prefix,{role:'user',content:text.trim()}];
    if(input.length>10){setError('limit');return;}
    setBusy(true);setError(null);setNotice(null);
    try {
      const value=await api<Result>('flow-run',{language,messages:input,instructions:prompts.banking,thread_id:results.at(-1)?.thread_id});
      setResults(previous=>[...previous,{...value,input_messages:input}]);setView(results.length);setStage('decision');setLastInput(input);
      if(value.state!=='provider_unavailable'){setHistory([...input,{role:'assistant',content:value.reply}]);setText('');}
      if(value.definition)setSelected(value.definition.intent);
      void refreshRuns().catch(()=>setError('loadError'));
    } catch {setError('runError');} finally {setBusy(false);}
  }
  async function saveRules() {
    if(!map)return;setSaving(true);setNotice(null);setError(null);
    try {setMap(await api<FlowMap>('flow-map/'+selected,{language,revision:map.revision,questions,instructions},'PUT'));setNotice('saved');}
    catch {setError('saveError');} finally {setSaving(false);}
  }
  async function saveCase() {
    const messages=lastInput.length?lastInput:[...seed.slice(0,-1),{role:'user' as const,content:text.trim()}];
    setSaving(true);setError(null);
    try {await api('conversations',{language,title:caseTitle.trim(),messages,expected:null,instructions:prompts.banking});setSavedCases((await api<{conversations:SavedCase[]}>('conversations')).conversations);setNotice('caseSaved');}
    catch {setError('saveError');} finally {setSaving(false);}
  }
  const graph=useMemo(()=>{
    const entries:[string,number,number,string,string][]=[
      ['conversation',0,155,t('conversation'),''],['intent',230,155,t('intent'),'Jev'],
      ...(['query','problem','service','clarification'] as const).map((key,i):[string,number,number,string,string]=>[key,470,i*106,t(key),t('rule')]),
      ['context',700,155,t('context'),'Luna'],['decision',930,155,t('decision'),t('rule')],
      ...(['ask_customer','review_in_bank','human_review','stop'] as const).map((key,i):[string,number,number,string,string]=>[key,1160,i*106,t(key),t('rule')]),
    ];
    const visited=new Set(result?['conversation','intent',...(result.definition?[result.route_family!,'decision',result.state,...(result.llm.status==='skipped'?[]:['context'])]:[])]:[]);
    const nodes:Node[]=entries.map(([id,x,y,label,source])=>({id,position:{x,y},sourcePosition:Position.Right,targetPosition:Position.Left,
      className:'flow-node '+(visited.has(id)?'is-visited':'')+(result?.state==='provider_unavailable'&&id===(result.jev.status==='ok'?'context':'intent')?' is-error':''),
      ariaLabel:label, data:{label:<div data-flow-node={id}><span>{source||'Nexqori'}</span><strong>{label}</strong>{id==='intent'&&<small>{result?.definition?.title||(!result?definition?.title:'—')}</small>}{id==='context'&&<small>{result?t(result.llm.status==='ok'?'declared':result.llm.status==='skipped'?'skipped':'error'):t('noRun')}</small>}</div>}}));
    const links:[string,string][]=[['conversation','intent'],...['query','problem','service','clarification'].map((id):[string,string]=>['intent',id]),...['query','problem','service'].map((id):[string,string]=>[id,'context']),['clarification','decision'],['context','decision'],...['ask_customer','review_in_bank','human_review','stop'].map((id):[string,string]=>['decision',id])];
    const edges:Edge[]=links.map(([source,target])=>({id:source+'-'+target,source,target,type:'smoothstep',markerEnd:{type:MarkerType.ArrowClosed,color:visited.has(source)&&visited.has(target)?'#9A4B32':'#beaca1'},style:{stroke:visited.has(source)&&visited.has(target)?'#9A4B32':'#beaca1',strokeWidth:visited.has(source)&&visited.has(target)?3:1.3}}));
    return {nodes,edges};
  },[result,definition,language]);
  const [nodes,setNodes]=useState<Node[]>([]);
  useEffect(()=>setNodes(graph.nodes),[graph]);
  const nodeOutput=result?(stage==='conversation'?result.input_messages:stage==='intent'?result.jev:stage==='context'?{...result.llm,observations:result.observations,missing_fields:result.missing_fields}:['query','problem','service','clarification'].includes(stage)?{family:result.route_family,source:'server_rule',tool_plan:result.tool_plan}:{state:result.state,questions:result.questions,authorizes_execution:false}):null;
  return <div className="flow-lab">
    <div className="simple-heading"><div><p className="eyebrow">JEV · LUNA · REACT FLOW</p><h1>{t('title')}</h1><p>{t('intro')}</p></div>{results.length>0&&<button className="secondary" onClick={()=>download({version:1,language,messages:history,runs:results})}><Download size={16}/>{t('export')}</button>}</div>
    {error&&<div className="error" role="alert">{t(error)} <button onClick={()=>void load()}>{t('reload')}</button></div>}
    {notice&&<p role="status" className="save-notice">{t(notice)}</p>}
    {!map?<p role="status">{translate(language,'loading')}</p>:<>
      <section className="flow-canvas-panel" aria-label={t('map')}>
        <div className="flow-map-heading"><span className="flow-chip"><GitBranch size={15}/>{t(result?'actual':'reference')}</span><span>{result?t('turn')+' '+(view+1)+' · '+t('latency')+': '+ms(result.latency_ms)+' ms':map.definitions.length+' '+t('flows').toLowerCase()} · {t('revision')} {result?.config_revision??map.revision}</span></div>
        <div className="flow-canvas">
          <ReactFlow nodes={nodes} edges={graph.edges} onNodesChange={changes=>setNodes(current=>applyNodeChanges(changes,current))} onInit={setInstance} onNodeClick={(_,node)=>setStage(node.id)} onSelectionChange={({nodes:selection})=>{if(selection[0])setStage(selection[0].id);}} nodesConnectable={false} edgesFocusable={false} deleteKeyCode={null} fitView minZoom={.2} maxZoom={1.5} fitViewOptions={{padding:.08}} ariaLabelConfig={{'node.a11yDescription.default':t('stageHint'),'node.a11yDescription.keyboardDisabled':t('stageHint'),'node.a11yDescription.ariaLiveMessage':({x,y})=>`${t('map')}: ${x}, ${y}`}}><Background color="#dac9bc" gap={22}/></ReactFlow>
        </div>
        <div className="flow-map-footer"><p>{t('stageHint')}</p><div className="button-row"><button onClick={()=>void instance?.zoomOut()} aria-label={t('zoomOut')}>−</button><button onClick={()=>void instance?.zoomIn()} aria-label={t('zoomIn')}>+</button><button onClick={()=>void instance?.fitView({padding:.08})}>{t('resetView')}</button></div></div>
        <ol className="flow-compact-path"><li><strong>Jev · {t('intent')}</strong><span>{activeDefinition?.title||t('noRun')}</span></li><li><strong>{t('family')}</strong><span>{result?.route_family?t(result.route_family as FlowKey):definition?t(definition.family as FlowKey):'—'}</span></li><li><strong>Luna · {t('context')}</strong><span>{result?t(result.llm.status==='ok'?'declared':result.llm.status==='skipped'?'skipped':'error'):t('noRun')}</span></li><li><strong>{t('decision')}</strong><span>{result?t(result.state):t('noRun')}</span></li></ol>
      </section>
      <div className="flow-workspace">
        <section className="panel flow-conversation"><h2>{t('conversation')}</h2>
          <label htmlFor="flow-case">{t('case')}</label><select id="flow-case" value={caseId} disabled={busy} onChange={e=>chooseCase(e.target.value)}>{scenarios.map(s=><option key={s.id} value={s.id}>{translate(language,s.id)}</option>)}<option value="custom">{t('newChat')}</option>{savedCases.filter(c=>c.language===language).map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>
          <p className="small-note">{t('authored')}</p>
          {!history.length&&seed.length>1&&<details><summary>{t('seed')}</summary><div className="flow-transcript" tabIndex={0} role="region" aria-label={t('seed')}>{seed.slice(0,-1).map((m,i)=><p key={i}><strong>{t(m.role==='user'?'client':'assistant')}</strong>{m.content}</p>)}</div></details>}
          {history.length>0&&<div className="flow-transcript" tabIndex={0} role="log" aria-label={t('conversation')}>{history.map((m,i)=><p key={i} className={m.role}><strong>{t(m.role==='user'?'client':'assistant')}</strong>{m.content}</p>)}</div>}
          <label htmlFor="flow-input">{t('input')}</label><textarea id="flow-input" value={text} maxLength={2000} disabled={busy} onChange={e=>setText(e.target.value)} rows={3}/>
          <div className="button-row"><button className="primary" disabled={busy||!text.trim()||history.length>=10} onClick={()=>void execute()}><Play size={17}/>{t(busy?'running':'play')}</button><button className="secondary" disabled={busy} onClick={()=>chooseCase('custom')}>{t('restart')}</button></div>
          {history.length>=10&&<p role="status">{t('limit')}</p>}<p className="small-note">{t('runHint')}</p>
          <details className="flow-save-case"><summary>{t('saveCase')}</summary><label htmlFor="flow-case-title">{t('titleCase')}</label><input id="flow-case-title" maxLength={120} value={caseTitle} onChange={e=>setCaseTitle(e.target.value)}/><button className="secondary" onClick={()=>void saveCase()} disabled={saving||busy||!caseTitle.trim()||(!lastInput.length&&!text.trim())}>{t('saveCase')}</button></details>
          <label htmlFor="flow-saved-run">{t('savedRuns')}</label><select id="flow-saved-run" value="" disabled={busy} onChange={e=>void restore(e.target.value)}><option value="">{t('chooseRun')}</option>{savedRuns.map(r=><option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString(language)} · {r.title||t(r.state)}</option>)}</select><p className="small-note">{t('savedRunsHint')}</p>
        </section>
        <section className="panel flow-inspector"><h2>{t('next')}</h2>
          {result?<><div className="flow-next" data-flow-state={result.state}><span>{activeDefinition?.title||t('provider_unavailable')}</span><h3>{t(result.state)}</h3><p>{result.reply}</p></div><p className="small-note">{t('boundary')}</p></>:<p>{t('reference')}</p>}
          <div className="flow-inspector-tabs" role="group" aria-label={t('output')}>{(['intent','context','decision'] as const).map(id=><button aria-pressed={stage===id} key={id} onClick={()=>setStage(id)}>{t(id)}</button>)}</div>
          {stage==='intent'&&result&&<><p>Jev · {result.jev.model||'—'} · {ms(result.jev.latency_ms)} ms</p><p>{t('probability')}: {result.jev.intent&&result.jev.probabilities?new Intl.NumberFormat(language,{style:'percent',maximumFractionDigits:1}).format(result.jev.probabilities[result.jev.intent]):'—'}</p><p className="small-note">{t('confidenceHint')}</p></>}
          <h3>{t('observations')}</h3>{result?.observations.length?<ul className="flow-facts">{result.observations.map(row=><li key={row.field}><strong>{fieldTitle(language,row.field)}</strong><span>{t('declared')} · {t('client')} #{row.message_index+1}</span><q>{row.quote}</q></li>)}</ul>:<p className="small-note">{t('noFacts')}</p>}
          {!!result?.missing_fields.length&&<p>{t('missing')}: {result.missing_fields.map(f=>fieldTitle(language,f)).join(' · ')}</p>}
          <div className="flow-bank-boundary"><strong>{t('notVerified')}</strong><p>{t('bankHint')}</p></div>
          {results.length>0&&<div className="flow-history"><h3>{t('history')}</h3>{results.map((r,i)=><button key={r.id} className={view===i?'selected':''} onClick={()=>setView(i)} aria-pressed={view===i}>{t('turn')} {i+1} · {r.definition?.title||t('error')}<span>{t(r.state)} · {ms(r.latency_ms)} ms</span></button>)}</div>}
          {nodeOutput&&<details><summary>{t('raw')}</summary><pre>{JSON.stringify(nodeOutput,null,2)}</pre></details>}
        </section>
      </div>
      <details className="panel flow-editor" open={!result}>
        <summary>{t('edit')} · {t('revision')} {map.revision}</summary><p>{t('editHint')}</p>
        <label htmlFor="flow-intent">{t('intentSelect')}</label><select id="flow-intent" value={selected} disabled={busy||saving} onChange={e=>{setSelected(e.target.value);setNotice(null);}}>{(['problem','query','service','clarification'] as const).map(f=><optgroup key={f} label={t(f)}>{map.definitions.filter(d=>d.family===f).map(d=><option key={d.intent} value={d.intent}>{d.title}</option>)}</optgroup>)}</select>
        <p>{definition?.summary}</p><div className="flow-editor-grid"><div>{Object.entries(questions).map(([key,value])=><label key={key}>{t('question')} · {fieldTitle(language,key)}<textarea rows={2} value={value} maxLength={300} onChange={e=>setQuestions(current=>({...current,[key]:e.target.value}))}/></label>)}{!Object.keys(questions).length&&<p>{t(selected==='out-of-scope'?'stopQuestions':'noQuestions')}</p>}<label>{t('instructions')}<textarea rows={3} maxLength={2000} value={instructions} onChange={e=>setInstructions(e.target.value)}/></label><div className="button-row"><button className="primary" disabled={saving||busy||Object.values(questions).some(q=>!q.trim())} onClick={()=>void saveRules()}><Save size={16}/>{t('save')}</button><button className="secondary" disabled={saving||busy} onClick={()=>void load()}>{t('reload')}</button></div></div><div>{definition&&<ToolPlanPanel plan={definition.tool_plan} language={language}/>}</div></div>
      </details>
    </>}
  </div>;
}
