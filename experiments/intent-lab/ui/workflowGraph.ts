import type {Language} from './locales';
import {allText, type EditorKey} from './editorLocales';

export type Kind='start'|'triage'|'jev'|'case_router'|'contract'|'preview'|'context'|'condition'|'question'|'response'|'escalate'|'diagnostic'|'notify';
export type Localized=Record<Language,string>;
export type Config={instructions?:Localized;scope?:string;intent?:string;stage?:string;notes?:Localized;mode?:string;fields?:string[];predicate?:string;value?:string;text?:Localized;outcome?:string};
export type Point={x:number;y:number};
export type Block={id:string;kind:Kind;label:Localized;position:Point;config:Config};
export const problemPorts=['unrecognized-charge','incorrect-charge','payment-status','app-support','branch-support','service-feedback'] as const;
export type Port='next'|'yes'|'no'|'reply'|'otherwise'|typeof problemPorts[number];
export type Link={id:string;source:string;target:string;port:Port};
export type Graph={schema_version:1;name:Localized;nodes:Block[];edges:Link[]};
export type Validation={valid:boolean;errors:{code:EditorKey;node_id:string|null;port:string|null}[]};
export type Workflow={id:string;revision:number;graph:Graph;validation:Validation};
export type Summary={id:string;revision:number;name:Localized};
export type Incident={id:string;reference:string;events:Record<string,unknown>[];source:string};
export type Notice={id:string;reference:string;created_at:string;reused?:boolean};
export type Trace={node_id:string;kind:Kind;label:Localized;status:string;output:unknown;latency_ms:number;step_index?:number;turn?:number;reused?:boolean};
export type ToolPlan={tools:{id:string;titles:Localized;status:string}[]};
export type Activation={id:string;node_id:string;stage:string;titles:Localized;requirements:string[];status:'would_activate';executed:false};
export type Execution={id:string;phase:'paused'|'waiting_reply'|'running'|'completed'|'interrupted';version:number;next_node_id:string|null;awaiting_node_id:string|null;last_edge_id:string|null;turn:number};
export type Result={id:string;thread_id:string;language:Language;workflow_id:string;workflow:Graph;state:EditorKey;reply:string;trace:Trace[];visited_edges:string[];latency_ms:number;notification:Notice|null;incident:Incident|null;workflow_revision:number;triage:{family?:string};jev:{intent?:string};contract:{title?:string;steps:string[]}|null;tool_plan:ToolPlan;activation_plan?:Activation[];execution:Execution;replayable_nodes?:string[];replayed_from?:{execution_id:string;node_id:string};messages:{role:'user'|'assistant';content:string}[]};
export type CaseDefinition={intent:string;title:string;summary:string;family:string;fields:string[];example:string;contract:null|{steps:string[]};tool_plan:ToolPlan;evidence:null|{records:number;denominator:number;source:string}};
export type InsertAt={source:string;port:Port;position?:Point};
export const kinds:Kind[]=['triage','jev','case_router','contract','preview','context','condition','question','response','escalate','diagnostic','notify'];
export const terminals=new Set<Kind>(['question','response','escalate']);
export const emptyText=()=>({es:'',en:'',pt:''});
export const ports=(kind:Kind):Port[]=>kind==='question'?['reply']:terminals.has(kind)?[]:kind==='case_router'?[...problemPorts,'otherwise']:kind==='condition'?['yes','no']:['next'];
export const uid=()=> 'n'+crypto.randomUUID().replaceAll('-','').slice(0,12);
const edge=(source:string,port:Port,target:string):Link=>({id:'e'+uid(),source,port,target});

function canonical(value:unknown):unknown {
  if(Array.isArray(value))return value.map(canonical);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)]));
  return value;
}
export function sameExecutionRules(a:Graph,b:Graph):boolean {
  const rules=(g:Graph)=>({schema_version:g.schema_version,nodes:g.nodes.map(({id,kind,config})=>({id,kind,config})).sort((a,b)=>a.id.localeCompare(b.id)),edges:[...g.edges].sort((a,b)=>a.id.localeCompare(b.id))});
  return JSON.stringify(canonical(rules(a)))===JSON.stringify(canonical(rules(b)));
}

export function moveBlocks(graph:Graph,moves:{id:string;position?:Point}[]):Graph {
  let changed=false;
  const nodes=graph.nodes.map(node=>{
    const position=moves.find(move=>move.id===node.id)?.position;
    if(!position||(position.x===node.position.x&&position.y===node.position.y))return node;
    changed=true;return {...node,position};
  });
  return changed?{...graph,nodes}:graph;
}

export function caseInScope(item:CaseDefinition,scope:string):boolean {
  return scope==='all'||item.family==='clarification'||(item.family==='problem')===(scope==='problem');
}

export function configFor(kind:Kind):Config {
  if(kind==='triage')return {instructions:emptyText()};
  if(kind==='jev')return {instructions:emptyText(),scope:'all'};
  if(kind==='contract')return {intent:''};
  if(kind==='preview')return {stage:'action'};
  if(kind==='context')return {mode:'case',fields:[],instructions:emptyText(),notes:emptyText()};
  if(kind==='condition')return {predicate:'has_missing',value:''};
  if(kind==='question')return {mode:'custom',text:allText('defaultQuestion')};
  if(kind==='response')return {outcome:'information',text:allText('defaultResponse')};
  if(kind==='escalate')return {text:emptyText()};
  return {};
}

export function connectGraph(graph:Graph,source:string,port:Port,target:string,replacedId?:string):Graph {
  const edges=graph.edges.filter(e=>e.id!==replacedId&&!(e.source===source&&e.port===port));
  return {...graph,edges:target?[...edges,edge(source,port,target)]:edges};
}

export function canAdd(graph:Graph,kind:Kind,pending:InsertAt|null):boolean {
  if(graph.nodes.length>=40)return false;
  if(pending?.port==='reply')return false;
  const maximum=kind==='jev'?2:kind==='contract'?6:['triage','case_router','context','diagnostic'].includes(kind)?1:40;
  if(graph.nodes.filter(n=>n.kind===kind).length>=maximum)return false;
  // A terminal cannot replace an existing connection without losing its continuation.
  return !(pending&&graph.edges.some(e=>e.source===pending.source&&e.port===pending.port)&&terminals.has(kind));
}

export function insertBlock(graph:Graph,kind:Kind,position:Point,pending:InsertAt|null):{graph:Graph;id:string}|null {
  if(!canAdd(graph,kind,pending))return null;
  const id=uid(),source=pending&&graph.nodes.find(n=>n.id===pending.source);
  if(pending&&!source)return null;
  const old=pending&&graph.edges.find(e=>e.source===pending.source&&e.port===pending.port);
  let nodes=graph.nodes;
  if(old){
    const target=nodes.find(n=>n.id===old.target)!;
    const shift=Math.max(240,position.x+240-target.position.x);
    const downstream=new Set<string>(),queue=[old.target];
    while(queue.length){const next=queue.shift()!;if(downstream.has(next))continue;downstream.add(next);queue.push(...graph.edges.filter(e=>e.source===next&&e.port!=='reply').map(e=>e.target));}
    nodes=nodes.map(n=>downstream.has(n.id)?{...n,position:{...n.position,x:Math.min(9900,n.position.x+shift)}}:n);
  }
  let next:Graph={...graph,nodes:[...nodes,{id,kind,label:allText(kind),position,config:configFor(kind)}]};
  if(pending)next=connectGraph(next,pending.source,pending.port,id);
  if(old)next=connectGraph(next,id,kind==='condition'?'yes':kind==='case_router'?'otherwise':'next',old.target);
  return {graph:next,id};
}

export function arrangeGraph(graph:Graph):Graph {
  const incoming=new Map(graph.nodes.map(n=>[n.id,graph.edges.filter(e=>e.target===n.id&&e.port!=='reply').length]));
  const level=new Map<string,number>(),queue=graph.nodes.filter(n=>incoming.get(n.id)===0).map(n=>n.id);
  for(const id of queue)level.set(id,0);
  for(let i=0;i<queue.length;i++){
    const id=queue[i];
    for(const e of graph.edges.filter(e=>e.source===id&&e.port!=='reply')){
      level.set(e.target,Math.max(level.get(e.target)||0,(level.get(id)||0)+1));
      incoming.set(e.target,(incoming.get(e.target)||0)-1);
      if(incoming.get(e.target)===0)queue.push(e.target);
    }
  }
  const rows=new Map<number,number>();
  return {...graph,nodes:graph.nodes.map(n=>{
    const column=level.get(n.id)||0,row=rows.get(column)||0;rows.set(column,row+1);
    return {...n,position:{x:column*260,y:100+row*200}};
  })};
}
