import {useEffect,useState,useRef,useMemo,type DragEvent} from 'react';
import {ReactFlow,Background,MiniMap,MarkerType,type Connection,type ReactFlowInstance} from '@xyflow/react';
import {Plus,Save,Play,Copy,Download,Upload,Trash2,CheckCircle2,X,Search,GripVertical,FolderOpen,Maximize,LayoutGrid,Undo2,Redo2,ChevronDown,ChevronUp,ArrowRight,Workflow as WorkflowIcon,ListChecks,LoaderCircle,BellRing,MessageCircle} from 'lucide-react';
import type {Language} from './locales';
import {fieldTitle} from './flowLocales';
import {et,allText,type EditorKey} from './editorLocales';
import {scenarios,messagesFor,type Message} from './scenarios';
import {BlockSettings} from './BlockSettings';
import {nodeTypes,edgeTypes,blockIcons,type CanvasNode,type CanvasEdge} from './WorkflowNodes';
import {kinds,canAdd,insertBlock,connectGraph,arrangeGraph,type Graph,type Workflow,type Summary,type Kind,type Point,type Port,type InsertAt,type Validation,type Block,type Config,type Incident,type Notice,type Trace,type Result,type CaseDefinition} from './workflowGraph';
import '@xyflow/react/dist/style.css';
import './editor.css';

async function api<T>(path:string,body?:unknown,method='POST'):Promise<T>{
 const r=await fetch('/lab-api/'+path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok)throw new Error(String(r.status));return r.json();
}
function exportJson(name:string,value:unknown){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);}
type Progress={event:string;node_id?:string;trace?:Trace;edge_id?:string;result?:Result};

export function WorkflowEditor({language}:{language:Language}){
 const t=(key:EditorKey)=>et(language,key);
 const [graph,setGraph]=useState<Graph|null>(null),[saved,setSaved]=useState<Workflow|null>(null),[library,setLibrary]=useState<Summary[]>([]);
 const [fields,setFields]=useState<string[]>([]),[taxonomy,setTaxonomy]=useState<{id:string;copy:Record<Language,{title:string}>}[]>([]),[cases,setCases]=useState<CaseDefinition[]>([]);
 const [selected,setSelected]=useState(''),[dirty,setDirty]=useState(false),[validation,setValidation]=useState<Validation|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(false),[message,setMessage]=useState<EditorKey|null>(null);
 const [instance,setInstance]=useState<ReactFlowInstance<CanvasNode,CanvasEdge>|null>(null),[result,setResult]=useState<Result|null>(null);
 const [input,setInput]=useState<string>(t('defaultMessage')),[history,setHistory]=useState<Message[]>([]);
 const [incident,setIncident]=useState<Incident|null>(null),[notices,setNotices]=useState<Notice[]>([]);
 const [measurements,setMeasurements]=useState<Record<string,{width:number;height:number}>>({});
 const [palette,setPalette]=useState<'cases'|'blocks'|null>('cases'),[search,setSearch]=useState(''),[pending,setPending]=useState<InsertAt|null>(null);
 const [selectedCase,setSelectedCase]=useState<string|null>(null),[dock,setDock]=useState<'conversation'|'execution'|'notifications'|null>(null);
 const [inspectorTab,setInspectorTab]=useState<'parameters'|'output'>('parameters'),[filesOpen,setFilesOpen]=useState(false);
 const [trace,setTrace]=useState<Trace[]>([]),[activeNode,setActiveNode]=useState<string|null>(null),[taken,setTaken]=useState<string[]>([]),[zoom,setZoom]=useState(90);
 const undo=useRef<Graph[]>([]),redo=useRef<Graph[]>([]),dragBefore=useRef<Graph|null>(null),[,redraw]=useState(0);
 const fileInput=useRef<HTMLInputElement>(null),canvas=useRef<HTMLDivElement>(null),filesDialog=useRef<HTMLDialogElement>(null),thread=useRef<string|undefined>(undefined);
 const block=graph?.nodes.find(n=>n.id===selected),output=trace.find(n=>n.node_id===selected),chosen=cases.find(c=>c.intent===selectedCase);
 const classified=(trace.find(row=>row.kind==='jev')?.output as {intent?:string}|undefined)?.intent;
 const actualCase=cases.find(c=>c.intent===(result?.jev.intent||classified));
 const runnable=!!saved&&!dirty&&!!validation?.valid&&!!input.trim()&&history.length<10&&!busy;

 async function refresh(){setLibrary((await api<{workflows:Summary[]}>('editor/workflows')).workflows);setNotices((await api<{notifications:Notice[]}>('editor/notifications')).notifications);}
 async function getTemplate(kind:string){const data=await api<{graph:Graph;fields:string[];taxonomy:typeof taxonomy}>('editor/template?kind='+kind);setFields(data.fields);setTaxonomy(data.taxonomy);return arrangeGraph(data.graph);}
 useEffect(()=>{void getTemplate('banking').then(async template=>{const id=new URLSearchParams(location.search).get('workflow');if(id){const record=await api<Workflow>('editor/workflows/'+encodeURIComponent(id));reset(record.graph,record);}else setGraph(template);}).catch(()=>setError(true));void refresh().catch(()=>setError(true));},[]);
 useEffect(()=>{let disposed=false;void api<{cases:CaseDefinition[]}>('editor/cases?language='+language).then(data=>{if(!disposed)setCases(data.cases);}).catch(()=>{if(!disposed)setError(true);});return()=>{disposed=true;};},[language]);
 useEffect(()=>{const handler=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue='';}};addEventListener('beforeunload',handler);return()=>removeEventListener('beforeunload',handler);},[dirty]);
 useEffect(()=>{if(activeNode&&instance&&graph){const point=graph.nodes.find(n=>n.id===activeNode)?.position;if(point)void instance.setCenter(point.x+76,point.y+60,{zoom:Math.max(.7,instance.getZoom()),duration:180});}},[activeNode,instance]);
 useEffect(()=>{if(filesOpen)filesDialog.current?.showModal();else filesDialog.current?.close();},[filesOpen]);
 function edited(next:Graph,remember=true){if(remember&&graph){undo.current=[...undo.current.slice(-39),graph];redo.current=[];}setGraph(next);setDirty(true);setValidation(null);setResult(null);setTrace([]);setTaken([]);setMessage(null);setError(false);}
 function syncUrl(record:Workflow|null){const url=new URL(location.href);url.searchParams.set('view','flows');url.searchParams.set('mode','editor');url.searchParams.delete('run');if(record)url.searchParams.set('workflow',record.id);else url.searchParams.delete('workflow');window.history.replaceState(null,'',url);}
 function reset(next:Graph,record:Workflow|null){syncUrl(record);setGraph(next);setSaved(record);setDirty(!record);setValidation(record?.validation||null);setSelected('');setHistory([]);setResult(null);setTrace([]);setTaken([]);setIncident(null);setError(false);setMessage(null);setInput(t('defaultMessage'));setPending(null);setDock(null);setSelectedCase(null);undo.current=[];redo.current=[];thread.current=undefined;void instance?.setViewport({x:70,y:90,zoom:.9});}
 function mayDiscard(){return !dirty||confirm(t('discard'));}
 function selectNode(id:string,tab:'parameters'|'output'='parameters'){if(graph?.nodes.find(n=>n.id===id)?.kind==='start'&&dock==='conversation')setDock(null);setSelected(id);setInspectorTab(tab);setPending(null);if(innerWidth<1100)setPalette(null);}
 function openPalette(source?:string,port?:Port,position?:Point){setDock(null);setPalette('blocks');setSearch('');setPending(source&&port?{source,port,position}:null);setSelected('');}
 async function create(kind:string){if(!mayDiscard())return;setBusy(true);try{const template=await getTemplate(kind==='app'?'app':'banking');reset(kind==='blank'?{...template,name:allText('blankName'),nodes:[{...template.nodes[0],position:{x:0,y:100}}],edges:[]}:template,null);setFilesOpen(false);setPalette('blocks');}catch{setError(true);}finally{setBusy(false);}}
 async function load(id:string){if(!id||!mayDiscard())return;setBusy(true);try{const record=await api<Workflow>('editor/workflows/'+id);reset(record.graph,record);setFilesOpen(false);}catch{setError(true);}finally{setBusy(false);}}
 async function chooseCase(item:CaseDefinition){
  if(!mayDiscard())return;setBusy(true);try{const next=await api<Graph>('editor/case-template/'+item.intent);reset(arrangeGraph(next),null);setSelectedCase(item.intent);
   const scenario=scenarios.find(s=>s.intent===item.intent),messages=scenario?messagesFor(scenario,language):[{role:'user' as const,content:item.example}];
   setHistory(messages.slice(0,-1));setInput(messages.at(-1)!.content);setSelected(next.nodes.find(n=>n.kind==='start')!.id);setPalette(null);setInspectorTab('parameters');
  }catch{setError(true);}finally{setBusy(false);}
 }
 async function save(){if(!graph)return;setBusy(true);setError(false);try{const record=await api<Workflow>('editor/workflows'+(saved?'/'+saved.id:''),{graph,revision:saved?.revision},saved?'PUT':'POST');syncUrl(record);setSaved(record);setGraph(record.graph);setValidation(record.validation);setDirty(false);setMessage('saved');await refresh();}catch{setError(true);}finally{setBusy(false);}}
 async function validate(){if(!graph)return;setBusy(true);try{setValidation(await api<Validation>('editor/validate',{graph}));}catch{setError(true);}finally{setBusy(false);}}
 function editBlock(patch:Partial<Block>){if(graph&&block)edited({...graph,nodes:graph.nodes.map(n=>n.id===block.id?{...n,...patch}:n)});}
 function editConfig(patch:Config){if(block)editBlock({config:{...block.config,...patch}});}
 function removeBlock(){if(!graph||!block||block.kind==='start')return;edited({...graph,nodes:graph.nodes.filter(n=>n.id!==block.id),edges:graph.edges.filter(e=>e.source!==block.id&&e.target!==block.id)});setSelected('');}
 function add(kind:Kind,point?:Point){
  if(!graph||busy)return;const source=graph.nodes.find(n=>n.id===pending?.source),old=graph.edges.find(e=>e.source===pending?.source&&e.port===pending?.port),target=graph.nodes.find(n=>n.id===old?.target),rect=canvas.current?.getBoundingClientRect();
  const position=point||pending?.position||(source?{x:source.position.x+260,y:target?.position.y??source.position.y+(pending?.port==='no'?180:0)}:instance?.screenToFlowPosition({x:(rect?.left||0)+(rect?.width||700)/2,y:(rect?.top||0)+(rect?.height||500)/2})||{x:260,y:100});
  const added=insertBlock(graph,kind,position,pending);if(!added)return;edited(added.graph);selectNode(added.id);setPending(null);if(innerWidth<1300)setPalette(null);
 }
 function connect(source:string,port:Port,target:string,replacedId?:string){if(graph&&!busy)edited(connectGraph(graph,source,port,target,replacedId));}
 function onConnect(c:Connection,replacedId?:string){if(c.source&&c.target)connect(c.source,(c.sourceHandle||'next') as Port,c.target,replacedId);}
 function drop(event:DragEvent){event.preventDefault();const kind=event.dataTransfer.getData('application/nexqori-block') as Kind;if(kinds.includes(kind))add(kind,instance?.screenToFlowPosition({x:event.clientX,y:event.clientY}));}
 function stepHistory(back:boolean){if(!graph)return;const from=back?undo:redo,to=back?redo:undo,next=from.current.pop();if(!next)return;to.current.push(graph);edited(next,false);setSelected('');redraw(n=>n+1);}
 async function importFile(file?:File){if(!file||!mayDiscard())return;if(file.size>96000){setError(true);return;}setBusy(true);try{const incoming=JSON.parse(await file.text()),checked=await api<Validation&{graph:Graph}>('editor/validate',{graph:incoming});reset(checked.graph,null);setValidation(checked);setFilesOpen(false);}catch{setError(true);}finally{setBusy(false);if(fileInput.current)fileInput.current.value='';}}
 async function run(){
  if(!runnable||!saved)return;const messages:Message[]=[...history,{role:'user',content:input.trim()}];
  setBusy(true);setError(false);setMessage(null);setResult(null);setTrace([]);setTaken([]);setDock('execution');setSelected('');let complete=false;
  try{
   const r=await fetch('/lab-api/editor/workflows/'+saved.id+'/run-stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({language,messages,revision:saved.revision,thread_id:thread.current,incident_id:incident?.id})});
   if(!r.ok||!r.body)throw new Error('execution_failed');const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';
   function consume(row:string){if(!row.trim())return;const event=JSON.parse(row) as Progress;
    if(event.event==='error')throw new Error('execution_failed');
    if(event.event==='node_started')setActiveNode(event.node_id!);
    if(event.event==='node_finished'){setTrace(previous=>[...previous,event.trace!]);setActiveNode(null);}
    if(event.event==='edge_taken')setTaken(previous=>[...previous,event.edge_id!]);
    if(event.event==='complete'&&event.result){const value=event.result;complete=true;setResult(value);setTrace(value.trace);setTaken(value.visited_edges);thread.current=value.thread_id;if(!['provider_unavailable','missing_incident'].includes(value.state)){setHistory([...messages,{role:'assistant',content:value.reply}]);setInput('');}}
   }
   while(true){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop()!;for(const line of lines)consume(line);}
   buffer+=decoder.decode();consume(buffer);if(!complete)throw new Error('incomplete_stream');await refresh();
  }catch{setError(true);}finally{setBusy(false);setActiveNode(null);}
 }
 async function reproduce(){setBusy(true);setError(false);try{setIncident(await api<Incident>('editor/app-check',{}));setResult(null);setTrace([]);setTaken([]);setMessage('linked');}catch{setError(true);}finally{setBusy(false);}}
 const canvasNodes:CanvasNode[]=useMemo(()=>graph?.nodes.map(n=>({id:n.id,type:'block',position:n.position,measured:measurements[n.id],selected:n.id===selected,ariaLabel:n.label[language],deletable:false,data:{label:n.label[language],kind:n.kind,connectedPorts:graph.edges.filter(e=>e.source===n.id).map(e=>e.port),language,busy,addAfter:openPalette,status:activeNode===n.id?'running':trace.find(row=>row.node_id===n.id)?.status}}))||[],[graph,measurements,selected,language,busy,trace,activeNode]);
 const canvasEdges:CanvasEdge[]=graph?.edges.map(e=>({id:e.id,source:e.source,target:e.target,sourceHandle:e.port,type:'insertable',data:{language,busy,insert:()=>openPalette(e.source,e.port)},markerEnd:{type:MarkerType.ArrowClosed},animated:taken.includes(e.id)&&busy,style:{stroke:taken.includes(e.id)?(e.port==='no'?'#9b6626':'#39745b'):'#b7b1a9',strokeWidth:taken.includes(e.id)?2.8:1.5},label:e.port==='next'?undefined:t(e.port)}))||[];
 const visibleCases=cases.filter(c=>(c.title+' '+c.summary).toLocaleLowerCase(language).includes(search.toLocaleLowerCase(language)));
 const visibleKinds=kinds.filter(k=>(t(k)+' '+t((k+'Hint') as EditorKey)).toLocaleLowerCase(language).includes(search.toLocaleLowerCase(language)));
 const number=(value:number)=>new Intl.NumberFormat(language,{maximumFractionDigits:1}).format(value);

 function questionPanel(){return <div className="editor-start-form">
  <h3>{t('questionStart')}</h3>{chosen&&<p className="case-selected"><ListChecks size={16}/>{chosen.title}</p>}
  {history.length>0&&<details className="editor-prior"><summary>{t('chat')} · {history.length}</summary><div className="editor-chat" role="log" aria-label={t('chat')} tabIndex={0}>{history.map((m,i)=><p key={i} className={m.role}>{m.content}</p>)}</div></details>}
  <label>{t('input')}<textarea aria-label={t('input')} id="editor-message" rows={4} maxLength={2000} disabled={busy} value={input} onChange={e=>setInput(e.target.value)}/></label>
  <div className="button-row"><button className="primary" aria-label={t(busy?'running':'run')} disabled={!runnable} onClick={()=>void run()}><Play size={15}/>{t('run')}</button><button disabled={busy} onClick={()=>{setHistory([]);setInput('');setResult(null);setTrace([]);setTaken([]);thread.current=undefined;}}>{t('clear')}</button></div>
  <p className="editor-help">{t(dirty||!saved?'saveFirst':'noAuto')}</p>
  {graph?.nodes.some(n=>n.kind==='diagnostic')&&<div className="editor-probe"><button disabled={busy} onClick={()=>void reproduce()}><ListChecks size={16}/>{t('reproduce')}</button>{incident&&<div className="editor-incident" role="status"><CheckCircle2 size={15}/><code>{incident.reference}</code><details><summary>{t('evidence')}</summary><pre tabIndex={0}>{JSON.stringify(incident.events,null,2)}</pre></details></div>}</div>}
  {chosen&&<details className="editor-case-detail"><summary>{t('procedure')}</summary><p>{chosen.summary}</p>{chosen.contract&&<ol>{chosen.contract.steps.map((step,i)=><li key={i}>{step}</li>)}</ol>}<h4>{t('needed')}</h4><p>{chosen.fields.map(f=>fieldTitle(language,f)).join(' · ')||'—'}</p><small>{t('caseOrigin')}</small></details>}
 </div>;}
 return <div className="workflow-editor">
  <h1 className="editor-screen-reader">{t('editor')}</h1>
  <div className="editor-toolbar">
   <button className="files-button" onClick={()=>setFilesOpen(true)} disabled={busy} aria-label={t('library')} title={t('library')}><FolderOpen size={19}/><ChevronDown size={13}/></button>
   <div className="editor-title"><input aria-label={t('name')} value={graph?.name[language]||t('editor')} disabled={busy||!graph} maxLength={100} onChange={e=>graph&&edited({...graph,name:{...graph.name,[language]:e.target.value}})}/><span className={'editor-save-state '+(dirty?'is-dirty':'')}>{t(dirty?'dirty':saved?'saved':'unsaved')}{saved&&' · v'+saved.revision}</span></div>
   <div className="editor-toolbar-actions"><button className="icon-button" title={t('undo')} aria-label={t('undo')} disabled={busy||!undo.current.length} onClick={()=>stepHistory(true)}><Undo2 size={17}/></button><button className="icon-button" title={t('redo')} aria-label={t('redo')} disabled={busy||!redo.current.length} onClick={()=>stepHistory(false)}><Redo2 size={17}/></button><button className="editor-validate" aria-label={t('validate')} disabled={busy||!graph} onClick={()=>void validate()}><CheckCircle2 size={16}/><span>{t('validate')}</span></button><button aria-label={t('save')} disabled={busy||!graph} onClick={()=>void save()}><Save size={16}/><span>{t('save')}</span></button><button className="primary" aria-label={t(busy?'running':'run')} disabled={!runnable} onClick={()=>void run()}>{busy?<LoaderCircle size={16} className="spin"/>:<Play size={16}/>}<span>{t(busy?'running':'run')}</span></button></div>
  </div>
  {error&&<div role="alert" className="editor-banner error">{t('error')}<button aria-label={t('close')} onClick={()=>setError(false)}><X size={15}/></button></div>}
  {message&&<div className="editor-toast" role="status">{t(message)}<button aria-label={t('close')} onClick={()=>setMessage(null)}><X size={14}/></button></div>}
  <div className="editor-workarea">
   {palette&&<aside className="editor-palette" aria-label={t('chooseBlock')}>
    <div className="editor-side-heading"><div className="editor-side-tabs"><button aria-pressed={palette==='cases'} onClick={()=>{setPalette('cases');setPending(null);setSearch('');}}>{t('cases')}</button><button aria-pressed={palette==='blocks'} onClick={()=>{setPalette('blocks');setSearch('');}}>{t('blocks')}</button></div><button className="icon-button" aria-label={t('close')} onClick={()=>{setPalette(null);setPending(null);}}><X size={17}/></button></div>
    <label className="editor-search"><Search size={16}/><input aria-label={t('search')} placeholder={t('search')} value={search} onChange={e=>setSearch(e.target.value)}/></label>
    {pending&&<div className="editor-insert-hint"><strong>{t('addAfter')} {graph?.nodes.find(n=>n.id===pending.source)?.label[language]}</strong><p>{t('insertHint')}</p></div>}
    <div className="editor-palette-scroll" tabIndex={0}>{palette==='blocks'?<><p className="editor-help">{t('dragHint')}</p>{visibleKinds.map(kind=>{const Icon=blockIcons[kind],allowed=!!graph&&canAdd(graph,kind,pending);return <button className="block-palette-card" data-palette-kind={kind} key={kind} draggable={!busy&&allowed} onDragStart={e=>{e.dataTransfer.setData('application/nexqori-block',kind);e.dataTransfer.effectAllowed='copy';}} disabled={busy||!allowed} title={!allowed?t('terminalHint'):t(kind)} onClick={()=>add(kind)}><span className="palette-icon"><Icon size={21}/></span><span><strong>{t(kind)}</strong><small>{t((kind+'Hint') as EditorKey)}</small></span><GripVertical size={14}/></button>;})}{!visibleKinds.length&&<p>{t('noneFound')}</p>}</>:<>
     <h3>{t('problems')} <span>{cases.filter(c=>c.family==='problem').length}</span></h3>
     {visibleCases.filter(c=>c.family==='problem').map(item=><button className="editor-case-card" data-case-intent={item.intent} key={item.intent} disabled={busy} onClick={()=>void chooseCase(item)}><span><strong>{item.title}</strong><small>{item.evidence?number(item.evidence.records)+' '+t('records'):t('scopeCase')}</small></span><ArrowRight size={15}/></button>)}
     <details className="other-cases" open={!!search}><summary>{t('otherCases')} · {cases.filter(c=>c.family!=='problem').length}</summary>{visibleCases.filter(c=>c.family!=='problem').map(item=><button className="editor-case-card" data-case-intent={item.intent} key={item.intent} disabled={busy} onClick={()=>void chooseCase(item)}><strong>{item.title}</strong><ArrowRight size={14}/></button>)}</details>
    </>}</div>
   </aside>}
   <div className="editor-canvas" ref={canvas} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}} onDrop={drop}>
    <div className="editor-canvas-tools"><button aria-label={t('cases')} title={t('cases')} aria-pressed={palette==='cases'} onClick={()=>{setPalette(palette==='cases'?null:'cases');setPending(null);}}><ListChecks size={18}/></button><button aria-label={t('add')} title={t('add')} onClick={()=>openPalette()}><Plus size={20}/></button></div>
    {graph&&<ReactFlow<CanvasNode,CanvasEdge> nodes={canvasNodes} edges={canvasEdges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onInit={setInstance} onConnect={c=>onConnect(c)} onReconnect={(old,c)=>onConnect(c,old.id)} onNodeClick={(_,node)=>selectNode(node.id)} onNodeDoubleClick={(_,node)=>selectNode(node.id)} onPaneClick={()=>{setSelected('');setPending(null);}} onPaneContextMenu={event=>{event.preventDefault();openPalette();}} nodesDraggable={!busy} nodesConnectable={!busy} edgesReconnectable={!busy} deleteKeyCode={null} defaultViewport={{x:70,y:90,zoom:.9}} minZoom={.25} maxZoom={1.8} onMove={(_,viewport)=>setZoom(Math.round(viewport.zoom*100))}
     onConnectEnd={(event,state)=>{if(!state.isValid&&!state.toNode&&state.fromNode&&state.fromHandle?.type==='source'){const point='changedTouches' in event?event.changedTouches[0]:event;openPalette(state.fromNode.id,(state.fromHandle.id||'next') as Port,instance?.screenToFlowPosition({x:point.clientX,y:point.clientY}));}}}
     onNodeDragStart={()=>{dragBefore.current=graph;}} onNodeDragStop={()=>{if(dragBefore.current){undo.current=[...undo.current.slice(-39),dragBefore.current];redo.current=[];dragBefore.current=null;redraw(n=>n+1);}}}
     onNodesChange={changes=>{const picked=changes.find(c=>c.type==='select'&&c.selected);if(picked?.type==='select'&&picked.id!==selected)selectNode(picked.id);const sizes=changes.filter(c=>c.type==='dimensions');if(sizes.length)setMeasurements(previous=>{let next=previous;for(const c of sizes)if(c.dimensions&&(previous[c.id]?.width!==c.dimensions.width||previous[c.id]?.height!==c.dimensions.height))next={...next,[c.id]:c.dimensions};return next;});const moves=changes.filter(c=>c.type==='position');if(moves.some(c=>c.position)&&!busy)edited({...graph,nodes:graph.nodes.map(n=>{const change=moves.find(c=>c.id===n.id);return change?.position?{...n,position:change.position}:n;})},!dragBefore.current);}}
     ariaLabelConfig={{'node.a11yDescription.default':t('canvasHint'),'node.a11yDescription.keyboardDisabled':t('canvasHint'),'node.a11yDescription.ariaLiveMessage':({x,y})=>String(x)+', '+y,'edge.a11yDescription.default':t('connections'),'handle.ariaLabel':t('connections')}}>
     <Background gap={24} size={1} color="#d3cbc1"/><MiniMap pannable zoomable nodeColor={n=>n.id===activeNode?'#9a4b32':taken.length&&trace.some(row=>row.node_id===n.id)?'#81a38c':'#ddd1c6'} maskColor="#f9f7f280" ariaLabel={t('mapView')}/>
    </ReactFlow>}
    <div className="editor-canvas-bottom"><div className="canvas-zoom"><button aria-label={t('zoomOut')} onClick={()=>void instance?.zoomOut()}>−</button><span>{zoom}%</span><button aria-label={t('zoomIn')} onClick={()=>void instance?.zoomIn()}>+</button><button aria-label={t('fit')} title={t('fit')} onClick={()=>void instance?.fitView({padding:.18,maxZoom:1})}><Maximize size={16}/></button><button disabled={busy||!graph} aria-label={t('arrange')} title={t('arrange')} onClick={()=>{if(graph){edited(arrangeGraph(graph));setTimeout(()=>void instance?.fitView({padding:.18,maxZoom:1}),60);}}}><LayoutGrid size={16}/></button></div><span className="canvas-hint">{t('canvasHint')}</span></div>
   </div>
   {block&&graph&&<aside className="editor-config" aria-label={t('config')}>
    <div className="editor-side-heading"><div><span className="editor-eyebrow">{t(block.kind)}</span><h2>{block.label[language]}</h2></div><button className="icon-button" aria-label={t('close')} onClick={()=>setSelected('')}><X size={19}/></button></div>
    <div className="editor-inspector-tabs"><button aria-pressed={inspectorTab==='parameters'} onClick={()=>setInspectorTab('parameters')}>{t('parameters')}</button><button aria-pressed={inspectorTab==='output'} disabled={!output} onClick={()=>setInspectorTab('output')}>{t('output')}</button></div>
    <div className="editor-inspector-scroll" tabIndex={0}>{inspectorTab==='output'&&output?<><p className="editor-help">{number(output.latency_ms)} ms · {t(output.status==='ok'?'completed':'error')}</p><pre tabIndex={0}>{JSON.stringify(output.output,null,2)}</pre></>:<>
     {block.kind==='start'&&questionPanel()}<div className="editor-config-heading"><span><code>{block.id}</code></span><button aria-label={t('remove')} disabled={busy||block.kind==='start'} onClick={removeBlock}><Trash2 size={15}/></button></div>
     <BlockSettings language={language} graph={graph} block={block} busy={busy} fields={fields} taxonomy={taxonomy} editBlock={editBlock} editConfig={editConfig} connect={connect}/>
    </>}</div>
   </aside>}
  </div>
  <div className="editor-dock">
   <div className="editor-dock-tabs"><button aria-pressed={dock==='conversation'} onClick={()=>{setDock(dock==='conversation'?null:'conversation');if(block?.kind==='start')setSelected('');}}><MessageCircle size={16}/>{t('chat')}</button><button aria-pressed={dock==='execution'} onClick={()=>setDock(dock==='execution'?null:'execution')}><ListChecks size={16}/>{t('execution')}{trace.length>0&&<span>{trace.length}</span>}</button><button aria-pressed={dock==='notifications'} onClick={()=>setDock(dock==='notifications'?null:'notifications')}><BellRing size={16}/>{t('inbox')}{notices.length>0&&<span>{notices.length}</span>}</button><div className="editor-dock-spacer"/>{validation&&<span className={'editor-validation '+(validation.valid?'valid':'invalid')} role="status">{t(validation.valid?'ready':'invalid')}</span>}<button className="icon-button" aria-label={t(dock?'close':'execution')} onClick={()=>setDock(dock?null:'execution')}>{dock?<ChevronDown size={16}/>:<ChevronUp size={16}/>}</button></div>
   {validation&&!validation.valid&&<div className="editor-errors" role="alert">{validation.errors.map((e,i)=><button key={i} onClick={()=>e.node_id&&selectNode(e.node_id)}>{e.node_id&&graph?.nodes.find(n=>n.id===e.node_id)?.label[language]} · {t(e.code)}{e.port&&' ('+t(e.port as EditorKey)+')'}</button>)}</div>}
   {dock&&<div className={'editor-dock-content dock-'+dock} tabIndex={0}>
    {dock==='conversation'&&<section className="editor-testing">{questionPanel()}</section>}
    {dock==='execution'&&<><section className="editor-run-summary"><span className="editor-eyebrow">{t('identified')}</span><h3>{actualCase?.title||(busy?t('running'):result?graph?.name[language]:t('noRun'))}</h3>{actualCase&&<p className="editor-help">{actualCase.summary}</p>}{result&&<div className="editor-result" data-editor-state={result.state}><strong>{t(result.state)}</strong><p>{result.reply}</p><small>{number(result.latency_ms)} ms · {t('revision')} {result.workflow_revision}</small>{result.notification&&<p>{t(result.notification.reused?'reused':'notification')} · <b>{result.notification.reference}</b></p>}</div>}{result&&<button onClick={()=>exportJson('nexqori-workflow-run.json',result)}><Download size={14}/>{t('export')}</button>}</section>
     <section><h3>{t('actionsTaken')}</h3>{!trace.length&&!busy&&<p className="editor-help">{t('noActions')}</p>}<ol className="editor-trace">{trace.map(row=><li key={row.node_id}><button onClick={()=>selectNode(row.node_id,'output')}><span>{row.status==='ok'?<CheckCircle2 size={15}/>:<X size={15}/>} {row.label[language]}{row.kind==='condition'&&<b className={(row.output as {port:string}).port}>{t((row.output as {port:string}).port==='yes'?'branchYes':'branchNo')}</b>}</span><small>{number(row.latency_ms)} ms</small></button></li>)}{activeNode&&<li className="trace-running"><LoaderCircle className="spin" size={15}/>{graph?.nodes.find(n=>n.id===activeNode)?.label[language]}</li>}</ol></section>
     <section className="editor-action-plan"><h3>{t('pendingActions')}</h3>{(result?.tool_plan||actualCase?.tool_plan)?.tools.map(tool=><div key={tool.id}><strong>{tool.titles[language]}</strong><small>{t('actionPending')}</small></div>)}{!(result?.tool_plan||actualCase?.tool_plan)?.tools.length&&<p className="editor-help">{t('noPending')}</p>}</section></>}
    {dock==='notifications'&&<section className="editor-inbox"><h3>{t('inbox')}</h3><p className="editor-help">{t('notificationHint')}</p>{notices.map(n=><p key={n.id}><BellRing size={16}/><strong>{n.reference}</strong><span>{t('notification')}</span><small>{new Date(n.created_at).toLocaleString(language)}</small></p>)}</section>}
   </div>}
  </div>
  <dialog ref={filesDialog} className="editor-files" aria-label={t('library')} onCancel={()=>setFilesOpen(false)} onClose={()=>setFilesOpen(false)}>
   <div className="editor-side-heading"><h2>{t('library')}</h2><button aria-label={t('close')} onClick={()=>setFilesOpen(false)}><X size={20}/></button></div>
   <div className="editor-new-options">{(['blank','banking','app'] as const).map(kind=><button key={kind} disabled={busy} data-new-kind={kind} onClick={()=>void create(kind)}><Plus size={20}/><span>{t(kind)}</span></button>)}</div>
   <div className="editor-library-list">{library.map(row=><button key={row.id} disabled={busy} onClick={()=>void load(row.id)}><WorkflowIcon size={20}/><strong>{row.name[language]}</strong><small>v{row.revision}</small><ArrowRight size={16}/></button>)}</div>
   <div className="button-row">{saved&&<button disabled={busy} onClick={()=>void load(saved.id)}>{t('reload')}</button>}<button disabled={busy||!graph} onClick={()=>{if(graph){reset({...structuredClone(graph),name:Object.fromEntries(Object.entries(graph.name).map(([k,v])=>[k,v.slice(0,96)+' · 2'])) as Graph['name']},null);setFilesOpen(false);}}}><Copy size={15}/>{t('duplicate')}</button><button disabled={busy} onClick={()=>fileInput.current?.click()}><Upload size={15}/>{t('import')}</button><button disabled={!graph} onClick={()=>graph&&exportJson('nexqori-workflow.json',graph)}><Download size={15}/>{t('export')}</button></div>
  </dialog>
  <input type="file" hidden ref={fileInput} accept="application/json,.json" onChange={e=>void importFile(e.target.files?.[0])}/>
 </div>;
}
