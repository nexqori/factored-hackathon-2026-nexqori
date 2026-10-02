import {useEffect,useState,useRef,useMemo,type DragEvent} from 'react';
import {ReactFlow,Background,Handle,Position,MarkerType,type Node,type NodeProps,type Edge,type Connection,type ReactFlowInstance} from '@xyflow/react';
import {Plus,Save,Play,Copy,Download,Upload,Trash2,CheckCircle2} from 'lucide-react';
import type {Language} from './locales';
import {fieldTitle,ft} from './flowLocales';
import {et,allText,type EditorKey} from './editorLocales';
import type {Message} from './scenarios';
import '@xyflow/react/dist/style.css';
import './editor.css';

type Kind='start'|'jev'|'context'|'condition'|'question'|'response'|'escalate'|'diagnostic'|'notify';
type Localized=Record<Language,string>;
type Config={instructions?:Localized;notes?:Localized;mode?:string;fields?:string[];predicate?:string;value?:string;text?:Localized;outcome?:string};
type Block={id:string;kind:Kind;label:Localized;position:{x:number;y:number};config:Config};
type Link={id:string;source:string;target:string;port:'next'|'yes'|'no'};
type Graph={schema_version:1;name:Localized;nodes:Block[];edges:Link[]};
type Validation={valid:boolean;errors:{code:EditorKey;node_id:string|null;port:string|null}[]};
type Workflow={id:string;revision:number;graph:Graph;validation:Validation};
type Summary={id:string;revision:number;name:Localized};
type Incident={id:string;reference:string;events:Record<string,unknown>[];source:string};
type Notice={id:string;reference:string;created_at:string;reused?:boolean};
type Trace={node_id:string;kind:Kind;label:Localized;status:string;output:unknown;latency_ms:number};
type Result={id:string;thread_id:string;state:EditorKey;reply:string;trace:Trace[];visited_edges:string[];latency_ms:number;notification:Notice|null;workflow_revision:number};
type BlockData={label:string;kind:Kind;language:Language;status?:string};
type CanvasNode=Node<BlockData,'block'>;
const kinds:Kind[]=['jev','context','condition','question','response','escalate','diagnostic','notify'];
const terminals=new Set<Kind>(['question','response','escalate']);
const emptyText=()=>({es:'',en:'',pt:''});
const ports=(kind:Kind)=>terminals.has(kind)?[]:kind==='condition'?['yes','no'] as const:['next'] as const;
function BlockNode({data}:NodeProps<CanvasNode>){
 return <div className={'editor-block '+(data.status?'visited':'')} data-block-kind={data.kind}>
  {data.kind!=='start'&&<Handle type="target" position={Position.Left} isConnectable/>}
  <span>{et(data.language,data.kind)}</span><strong>{data.label}</strong>{data.status&&<small>{data.status==='ok'?'✓':et(data.language,'error')}</small>}
  {ports(data.kind).map((p,i)=><div key={p}><Handle type="source" id={p} position={Position.Right} style={{top:data.kind==='condition'?(i?78:38)+'%':'50%'}}/>{data.kind==='condition'&&<b className={'port-label port-'+p}>{et(data.language,p)}</b>}</div>)}
 </div>;
}
const nodeTypes={block:BlockNode};
async function api<T>(path:string,body?:unknown,method='POST'):Promise<T>{
 const res=await fetch('/lab-api/'+path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!res.ok)throw new Error(String(res.status));return res.json();
}
function exportJson(name:string,value:unknown){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);}
function configFor(kind:Kind):Config{
 if(kind==='jev')return{instructions:emptyText()};
 if(kind==='context')return{mode:'case',fields:[],instructions:emptyText(),notes:emptyText()};
 if(kind==='condition')return{predicate:'has_missing',value:''};
 if(kind==='question')return{mode:'custom',text:allText('defaultQuestion')};
 if(kind==='response')return{outcome:'information',text:allText('defaultResponse')};
 if(kind==='escalate')return{text:emptyText()};return{};
}

export function WorkflowEditor({language}:{language:Language}){
 const t=(key:EditorKey)=>et(language,key);
 const [graph,setGraph]=useState<Graph|null>(null),[saved,setSaved]=useState<Workflow|null>(null),[library,setLibrary]=useState<Summary[]>([]);
 const [fields,setFields]=useState<string[]>([]),[taxonomy,setTaxonomy]=useState<{id:string;copy:Record<Language,{title:string}>}[]>([]);
 const [selected,setSelected]=useState('context'),[dirty,setDirty]=useState(false),[validation,setValidation]=useState<Validation|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(false),[message,setMessage]=useState<EditorKey|null>(null),[templateKind,setTemplateKind]=useState('banking');
 const [instance,setInstance]=useState<ReactFlowInstance<CanvasNode>|null>(null),[result,setResult]=useState<Result|null>(null);
 const [input,setInput]=useState<string>(t('defaultMessage')),[history,setHistory]=useState<Message[]>([]);
 const [incident,setIncident]=useState<Incident|null>(null),[notices,setNotices]=useState<Notice[]>([]);
 const [measurements,setMeasurements]=useState<Record<string,{width:number;height:number}>>({});
 const fileInput=useRef<HTMLInputElement>(null);
 const block=graph?.nodes.find(n=>n.id===selected);
 const limits={jev:1,context:1,diagnostic:1};
 async function refresh(){setLibrary((await api<{workflows:Summary[]}>('editor/workflows')).workflows);setNotices((await api<{notifications:Notice[]}>('editor/notifications')).notifications);}
 async function getTemplate(kind:string){const data=await api<{graph:Graph;fields:string[];taxonomy:typeof taxonomy}>('editor/template?kind='+kind);setFields(data.fields);setTaxonomy(data.taxonomy);return data.graph;}
 useEffect(()=>{void getTemplate('banking').then(async g=>{const id=new URLSearchParams(location.search).get('workflow');if(id){const record=await api<Workflow>('editor/workflows/'+encodeURIComponent(id));reset(record.graph,record);}else setGraph(g);}).catch(()=>setError(true));void refresh().catch(()=>setError(true));},[]);
 useEffect(()=>{const handler=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue='';}};addEventListener('beforeunload',handler);return()=>removeEventListener('beforeunload',handler);},[dirty]);
 function edited(g:Graph){setGraph(g);setDirty(true);setValidation(null);setResult(null);setMessage(null);setError(false);}
 function reset(g:Graph,record:Workflow|null){setGraph(g);setSaved(record);setDirty(!record);setValidation(record?.validation||null);setSelected(g.nodes[0].id);setHistory([]);setResult(null);setIncident(null);setError(false);setMessage(null);setInput(t('defaultMessage'));setTimeout(()=>void instance?.fitView({padding:.08}),80);}
 function mayDiscard(){return !dirty||confirm(t('discard'));}
 async function create(){if(!mayDiscard())return;setBusy(true);try{reset(await getTemplate(templateKind),null);}catch{setError(true);}finally{setBusy(false);}}
 async function load(id:string){if(!id||!mayDiscard())return;setBusy(true);try{const record=await api<Workflow>('editor/workflows/'+id);reset(record.graph,record);}catch{setError(true);}finally{setBusy(false);}}
 async function save(){if(!graph)return;setBusy(true);setError(false);try{const record=await api<Workflow>('editor/workflows'+(saved?'/'+saved.id:''),{graph,revision:saved?.revision},saved?'PUT':'POST');setSaved(record);setGraph(record.graph);setValidation(record.validation);setDirty(false);setMessage('saved');await refresh();}catch{setError(true);}finally{setBusy(false);}}
 async function validate(){if(!graph)return;setBusy(true);setError(false);try{setValidation(await api<Validation>('editor/validate',{graph}));}catch{setError(true);}finally{setBusy(false);}}
 function editBlock(patch:Partial<Block>){if(graph&&block)edited({...graph,nodes:graph.nodes.map(n=>n.id===block.id?{...n,...patch}:n)});}
 function editConfig(patch:Config){if(block)editBlock({config:{...block.config,...patch}});}
 function add(kind:Kind,position?:{x:number;y:number}){if(!graph||graph.nodes.length>=24||busy)return;if(kind in limits&&graph.nodes.some(n=>n.kind===kind))return;const id='n'+crypto.randomUUID().replaceAll('-','').slice(0,10);edited({...graph,nodes:[...graph.nodes,{id,kind,label:allText(kind),position:position||{x:300,y:480+graph.nodes.length%3*135},config:configFor(kind)}]});setSelected(id);setTimeout(()=>void instance?.fitView({padding:.08}),80);}
 function connect(source:string,port:Link['port'],target:string){if(!graph||busy)return;const rest=graph.edges.filter(e=>!(e.source===source&&e.port===port));edited({...graph,edges:target?[...rest,{id:'e_'+source+'_'+port,source,target,port}]:rest});}
 function onConnect(c:Connection){if(c.source&&c.target)connect(c.source,(c.sourceHandle||'next') as Link['port'],c.target);}
 function drop(event:DragEvent){event.preventDefault();const kind=event.dataTransfer.getData('application/nexqori-block') as Kind;if(kinds.includes(kind))add(kind,instance?.screenToFlowPosition({x:event.clientX,y:event.clientY}));}
 async function importFile(file?:File){if(!file||!mayDiscard())return;if(file.size>96000){setError(true);return;}setBusy(true);try{const incoming=JSON.parse(await file.text());const checked=await api<Validation&{graph:Graph}>('editor/validate',{graph:incoming});reset(checked.graph,null);setValidation(checked);}catch{setError(true);}finally{setBusy(false);if(fileInput.current)fileInput.current.value='';}}
 async function run(){if(!saved||dirty||!validation?.valid||!input.trim())return;const messages:Message[]=[...history,{role:'user',content:input.trim()}];if(messages.length>10){setMessage('limit');return;}setBusy(true);setError(false);setMessage(null);try{const value=await api<Result>('editor/workflows/'+saved.id+'/run',{language,messages,revision:saved.revision,thread_id:result?.thread_id,incident_id:incident?.id});setResult(value);if(value.state!=='provider_unavailable'&&value.state!=='missing_incident'){setHistory([...messages,{role:'assistant',content:value.reply}]);setInput('');}await refresh();}catch{setError(true);}finally{setBusy(false);}}
 async function reproduce(){setBusy(true);setError(false);try{const value=await api<Incident>('editor/app-check',{});setIncident(value);setResult(null);setMessage('linked');}catch{setError(true);}finally{setBusy(false);}}
 const canvasNodes:CanvasNode[]=useMemo(()=>graph?.nodes.map(n=>({id:n.id,type:'block',position:n.position,measured:measurements[n.id],selected:n.id===selected,ariaLabel:n.label[language],deletable:n.kind!=='start',data:{label:n.label[language],kind:n.kind,language,status:result?.trace.find(row=>row.node_id===n.id)?.status}}))||[],[graph,measurements,selected,language,result]);
 const canvasEdges:Edge[]=graph?.edges.map(e=>({id:e.id,source:e.source,target:e.target,sourceHandle:e.port,type:'smoothstep',label:e.port==='next'?undefined:t(e.port),markerEnd:{type:MarkerType.ArrowClosed},style:{stroke:result?.visited_edges.includes(e.id)?'#9a4b32':'#ac9180',strokeWidth:result?.visited_edges.includes(e.id)?3:1.5}}))||[];
 const output=result?.trace.find(row=>row.node_id===selected);
 return <div className="workflow-editor">
  <div className="simple-heading"><div><h1>{t('editor')}</h1><p>{t('intro')}</p></div><span className={'editor-badge '+(dirty?'is-dirty':'')}>{t(dirty?'dirty':saved?'saved':'unsaved')}{saved&&' · '+t('revision')+' '+saved.revision}</span></div>
  {error&&<p role="alert" className="error">{t('error')}</p>}{message&&<p role="status" className="save-notice">{t(message)}</p>}
  {!graph?<p>…</p>:<>
   <div className="editor-library panel"><label>{t('library')}<select aria-label={t('library')} value={saved?.id||''} disabled={busy} onChange={e=>void load(e.target.value)}><option value="">{t('unsaved')}</option>{library.map(row=><option value={row.id} key={row.id}>{row.name[language]} · {row.revision}</option>)}</select></label><label>{t('new')}<select aria-label={t('new')} value={templateKind} disabled={busy} onChange={e=>setTemplateKind(e.target.value)}><option value="banking">{t('banking')}</option><option value="app">{t('app')}</option></select></label><div className="button-row"><button disabled={busy} onClick={()=>void create()}><Plus size={16}/>{t('new')}</button><button disabled={busy} onClick={()=>{reset({...structuredClone(graph),name:Object.fromEntries(Object.entries(graph.name).map(([k,v])=>[k,v.slice(0,96)+' · 2'])) as Localized},null);}}><Copy size={16}/>{t('duplicate')}</button><button disabled={busy} onClick={()=>fileInput.current?.click()}><Upload size={16}/>{t('import')}</button><button onClick={()=>exportJson('nexqori-workflow.json',graph)}><Download size={16}/>{t('export')}</button><input type="file" hidden ref={fileInput} accept="application/json,.json" onChange={e=>void importFile(e.target.files?.[0])}/></div></div>
   <div className="editor-toolbar"><label>{t('name')}<input aria-label={t('name')} value={graph.name[language]} disabled={busy} maxLength={100} onChange={e=>edited({...graph,name:{...graph.name,[language]:e.target.value}})}/></label><div className="button-row"><button disabled={busy} onClick={()=>void validate()}>{t('validate')}</button><button className="primary" disabled={busy} onClick={()=>void save()}><Save size={16}/>{t('save')}</button>{saved&&<button disabled={busy} onClick={()=>void load(saved.id)}>{t('reload')}</button>}</div></div>
   <section className="editor-palette" aria-label={t('add')}><strong>{t('add')}</strong>{kinds.map(kind=><button key={kind} draggable={!busy} onDragStart={e=>e.dataTransfer.setData('application/nexqori-block',kind)} disabled={busy||graph.nodes.length>=24||(kind in limits&&graph.nodes.some(n=>n.kind===kind))} onClick={()=>add(kind)}><Plus size={13}/>{t(kind)}</button>)}</section><p className="editor-help">{t('paletteHint')}</p>
   <div className="editor-canvas" onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='move';}} onDrop={drop}>
    <ReactFlow<CanvasNode> nodes={canvasNodes} edges={canvasEdges} nodeTypes={nodeTypes} onInit={setInstance} onConnect={onConnect} onNodeClick={(_,node)=>setSelected(node.id)} nodesDraggable={!busy} nodesConnectable={!busy} deleteKeyCode={null} fitView fitViewOptions={{padding:.08}} minZoom={.2} maxZoom={1.6}
     onNodesChange={changes=>{const sizes=changes.filter(c=>c.type==='dimensions');if(sizes.length)setMeasurements(previous=>{let next=previous;for(const c of sizes){if(c.dimensions&&(previous[c.id]?.width!==c.dimensions.width||previous[c.id]?.height!==c.dimensions.height))next={...next,[c.id]:c.dimensions};}return next;});const moves=changes.filter(c=>c.type==='position');if(moves.some(c=>c.position)&&!busy)edited({...graph,nodes:graph.nodes.map(n=>{const move=moves.find(c=>c.id===n.id);return move?.position?{...n,position:move.position}:n;})});}}
     ariaLabelConfig={{'node.a11yDescription.default':t('paletteHint'),'node.a11yDescription.keyboardDisabled':t('paletteHint'),'node.a11yDescription.ariaLiveMessage':({x,y})=>`${x}, ${y}`,'edge.a11yDescription.default':t('connections'),'handle.ariaLabel':t('connections')}}><Background gap={22} color="#dac9bc"/></ReactFlow>
   </div><div className="editor-canvas-footer"><span>{graph.nodes.length}/24 · {t('add')}</span><div className="button-row"><button aria-label={t('zoomOut')} onClick={()=>void instance?.zoomOut()}>−</button><button aria-label={t('zoomIn')} onClick={()=>void instance?.zoomIn()}>+</button><button onClick={()=>void instance?.fitView({padding:.08})}>{t('fit')}</button></div></div>
   {validation&&<div className={'editor-validation '+(validation.valid?'valid':'invalid')} role="status">{validation.valid?<strong><CheckCircle2 size={17}/>{t('ready')}</strong>:<><strong>{t('invalid')}</strong><ul>{validation.errors.map((e,i)=><li key={i}><button onClick={()=>{if(e.node_id)setSelected(e.node_id);}}>{e.node_id&&(graph.nodes.find(n=>n.id===e.node_id)?.label[language]||t(e.node_id as EditorKey))+' · '}{t(e.code)}{e.port&&' ('+t(e.port as EditorKey)+')'}</button></li>)}</ul></>}</div>}
   <div className="editor-lower"><section className="panel editor-config"><h2>{t('config')}</h2><label>{t('selection')}<select value={selected} onChange={e=>setSelected(e.target.value)}>{graph.nodes.map(n=><option key={n.id} value={n.id}>{n.label[language]}</option>)}</select></label>{block?<>
    <div className="editor-config-heading"><span>{t(block.kind)} · <code>{block.id}</code></span><button aria-label={t('remove')} disabled={busy||block.kind==='start'} onClick={()=>{edited({...graph,nodes:graph.nodes.filter(n=>n.id!==block.id),edges:graph.edges.filter(e=>e.source!==block.id&&e.target!==block.id)});setSelected(graph.nodes[0].id);}}><Trash2 size={16}/>{t('remove')}</button></div>
    <label>{t('nodeName')}<input value={block.label[language]} maxLength={90} disabled={busy} onChange={e=>editBlock({label:{...block.label,[language]:e.target.value}})}/></label>
    {(block.kind==='jev'||block.kind==='context')&&<label>{t('instructions')}<textarea aria-label={t('instructions')} value={block.config.instructions?.[language]||''} rows={3} maxLength={1200} disabled={busy} onChange={e=>editConfig({instructions:{...(block.config.instructions||emptyText()),[language]:e.target.value}})}/></label>}
    {block.kind==='context'&&<><label>{t('notes')}<textarea aria-label={t('notes')} value={block.config.notes?.[language]||''} rows={3} maxLength={1200} disabled={busy} onChange={e=>editConfig({notes:{...(block.config.notes||emptyText()),[language]:e.target.value}})}/></label><p className="editor-help">{t('notesHint')}</p><label>{t('fields')}<select value={block.config.mode} disabled={busy} onChange={e=>editConfig({mode:e.target.value,fields:e.target.value==='selected'?(block.config.fields?.length?block.config.fields:['symptom']):[]})}><option value="case">{t('caseFields')}</option><option value="selected">{t('selectedFields')}</option></select></label>{block.config.mode==='selected'&&<div className="editor-fields">{fields.map(field=><label key={field}><input type="checkbox" checked={block.config.fields?.includes(field)||false} disabled={busy} onChange={e=>editConfig({fields:e.target.checked?[...(block.config.fields||[]),field]:block.config.fields?.filter(f=>f!==field)})}/>{fieldTitle(language,field)}</label>)}</div>}</>}
    {block.kind==='condition'&&<><label>{t('predicate')}<select value={block.config.predicate} disabled={busy} onChange={e=>editConfig({predicate:e.target.value,value:e.target.value==='intent_is'?'app-support':e.target.value==='family_is'?'problem':e.target.value==='field_missing'?'symptom':''})}>{(['has_missing','needs_human','intent_is','family_is','field_missing','diagnostic_failed'] as const).map(p=><option key={p} value={p}>{t(p)}</option>)}</select></label>{['intent_is','family_is','field_missing'].includes(block.config.predicate||'')&&<label>{t('value')}<select value={block.config.value} disabled={busy} onChange={e=>editConfig({value:e.target.value})}>{block.config.predicate==='intent_is'?taxonomy.map(item=><option key={item.id} value={item.id}>{item.copy[language].title}</option>):block.config.predicate==='family_is'?['query','problem','service','clarification'].map(f=><option key={f} value={f}>{ft(language,f as 'query')}</option>):fields.map(f=><option key={f} value={f}>{fieldTitle(language,f)}</option>)}</select></label>}</>}
    {block.kind==='question'&&<label>{t('mode')}<select value={block.config.mode} disabled={busy} onChange={e=>editConfig({mode:e.target.value,text:block.config.text&&Object.values(block.config.text).every(v=>v.trim())?block.config.text:allText('defaultQuestion')})}><option value="missing">{t('missing')}</option><option value="custom">{t('custom')}</option></select></label>}
    {block.kind==='response'&&<label>{t('outcome')}<select value={block.config.outcome} disabled={busy} onChange={e=>editConfig({outcome:e.target.value,text:block.config.text&&Object.values(block.config.text).every(v=>v.trim())?block.config.text:allText('defaultResponse')})}><option value="review_in_bank">{t('review_in_bank')}</option><option value="information">{t('information')}</option></select></label>}
    {(block.kind==='response'||block.kind==='escalate'||(block.kind==='question'&&block.config.mode==='custom'))&&<label>{t('message')}<textarea aria-label={t('message')} value={block.config.text?.[language]||''} rows={4} maxLength={block.kind==='question'?600:1200} disabled={busy} onChange={e=>editConfig({text:{...(block.config.text||emptyText()),[language]:e.target.value}})}/>{(block.kind==='escalate'||block.config.outcome==='review_in_bank')&&<small>{t('emptyDefault')}</small>}</label>}
    {['start','diagnostic','notify'].includes(block.kind)&&<p>{t('locked')}</p>}
    {!!ports(block.kind).length&&<fieldset className="editor-connections"><legend>{t('connections')}</legend>{ports(block.kind).map(port=><label key={port}>{t(port)}<select aria-label={t('connections')+' · '+t(port)} value={graph.edges.find(e=>e.source===block.id&&e.port===port)?.target||''} disabled={busy} onChange={e=>connect(block.id,port,e.target.value)}><option value="">{t('disconnected')}</option>{graph.nodes.filter(n=>n.id!==block.id&&n.kind!=='start').map(n=><option key={n.id} value={n.id}>{n.label[language]} · {n.id}</option>)}</select></label>)}</fieldset>}
    {output&&<details open><summary>{t('output')} · {new Intl.NumberFormat(language,{maximumFractionDigits:1}).format(output.latency_ms)} ms</summary><pre tabIndex={0}>{JSON.stringify(output.output,null,2)}</pre></details>}
   </>:<p>{t('selection')}</p>}</section>
   <section className="panel editor-testing"><h2>{t('chat')}</h2>{history.length>0&&<div className="editor-chat" role="log" aria-label={t('chat')} tabIndex={0}>{history.map((m,i)=><p key={i} className={m.role}>{m.content}</p>)}</div>}<label>{t('input')}<textarea id="editor-message" rows={3} maxLength={2000} disabled={busy} value={input} onChange={e=>setInput(e.target.value)}/></label><div className="button-row"><button className="primary" disabled={busy||dirty||!validation?.valid||!saved||!input.trim()||history.length>=10} onClick={()=>void run()}><Play size={16}/>{t(busy?'running':'run')}</button><button disabled={busy} onClick={()=>{setHistory([]);setResult(null);setInput('');}}>{t('clear')}</button></div><p className="editor-help">{t(dirty||!saved?'saveFirst':'noAuto')}</p>{history.length>=10&&<p>{t('limit')}</p>}
    {result&&<><div className="editor-result" data-editor-state={result.state}><strong>{t(result.state)}</strong><p>{result.reply}</p><small>{new Intl.NumberFormat(language,{maximumFractionDigits:1}).format(result.latency_ms)} ms · {t('revision')} {result.workflow_revision}</small>{result.notification&&<p>{t(result.notification.reused?'reused':'notification')}: <b>{result.notification.reference}</b></p>}</div><h3>{t('trace')}</h3><ol className="editor-trace">{result.trace.map(row=><li key={row.node_id}><button onClick={()=>setSelected(row.node_id)}><span>{row.status==='ok'?'✓':'!'} {row.label[language]}</span><small>{new Intl.NumberFormat(language,{maximumFractionDigits:1}).format(row.latency_ms)} ms</small></button></li>)}</ol><button onClick={()=>exportJson('nexqori-workflow-run.json',result)}>{t('export')}</button></>}
    <details className="editor-probe" open={graph.nodes.some(n=>n.kind==='diagnostic')}><summary>{t('probe')}</summary><p className="editor-help">{t('probeHint')}</p><button disabled={busy} onClick={()=>void reproduce()}>{t('reproduce')}</button>{incident&&<div className="editor-incident" role="status"><strong>{t('accessFailed')}</strong><p><code>{incident.reference}</code> · {t('linked')}</p><details><summary>{t('evidence')}</summary><pre tabIndex={0}>{JSON.stringify(incident.events,null,2)}</pre></details></div>}</details>
    <details className="editor-inbox"><summary>{t('inbox')} · {notices.length}</summary><p className="editor-help">{t('notificationHint')}</p>{notices.map(n=><p key={n.id}><strong>{n.reference}</strong> · {t('notification')}<small>{new Date(n.created_at).toLocaleString(language)}</small></p>)}</details>
   </section></div><p className="editor-help">{t('boundary')}</p>
  </>}
 </div>;
}
