import type {Language} from './locales';
import {allText, type EditorKey} from './editorLocales';

export type Kind='start'|'jev'|'context'|'condition'|'question'|'response'|'escalate'|'diagnostic'|'notify';
export type Localized=Record<Language,string>;
export type Config={instructions?:Localized;notes?:Localized;mode?:string;fields?:string[];predicate?:string;value?:string;text?:Localized;outcome?:string};
export type Point={x:number;y:number};
export type Block={id:string;kind:Kind;label:Localized;position:Point;config:Config};
export type Port='next'|'yes'|'no';
export type Link={id:string;source:string;target:string;port:Port};
export type Graph={schema_version:1;name:Localized;nodes:Block[];edges:Link[]};
export type Validation={valid:boolean;errors:{code:EditorKey;node_id:string|null;port:string|null}[]};
export type Workflow={id:string;revision:number;graph:Graph;validation:Validation};
export type Summary={id:string;revision:number;name:Localized};
export type Incident={id:string;reference:string;events:Record<string,unknown>[];source:string};
export type Notice={id:string;reference:string;created_at:string;reused?:boolean};
export type Trace={node_id:string;kind:Kind;label:Localized;status:string;output:unknown;latency_ms:number};
export type ToolPlan={tools:{id:string;titles:Localized;status:string}[]};
export type Result={id:string;thread_id:string;state:EditorKey;reply:string;trace:Trace[];visited_edges:string[];latency_ms:number;notification:Notice|null;workflow_revision:number;jev:{intent?:string};tool_plan:ToolPlan};
export type CaseDefinition={intent:string;title:string;summary:string;family:string;fields:string[];example:string;contract:null|{steps:string[]};tool_plan:ToolPlan;evidence:null|{records:number;denominator:number;source:string}};
export type InsertAt={source:string;port:Port;position?:Point};
export const kinds:Kind[]=['jev','context','condition','question','response','escalate','diagnostic','notify'];
export const terminals=new Set<Kind>(['question','response','escalate']);
export const emptyText=()=>({es:'',en:'',pt:''});
export const ports=(kind:Kind):Port[]=>terminals.has(kind)?[]:kind==='condition'?['yes','no']:['next'];
export const uid=()=> 'n'+crypto.randomUUID().replaceAll('-','').slice(0,12);
const edge=(source:string,port:Port,target:string):Link=>({id:'e'+uid(),source,port,target});

export function configFor(kind:Kind):Config {
  if(kind==='jev')return {instructions:emptyText()};
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
  if(graph.nodes.length>=24)return false;
  if(['jev','context','diagnostic'].includes(kind)&&graph.nodes.some(n=>n.kind===kind))return false;
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
    while(queue.length){const next=queue.shift()!;if(downstream.has(next))continue;downstream.add(next);queue.push(...graph.edges.filter(e=>e.source===next).map(e=>e.target));}
    nodes=nodes.map(n=>downstream.has(n.id)?{...n,position:{...n.position,x:Math.min(9900,n.position.x+shift)}}:n);
  }
  let next:Graph={...graph,nodes:[...nodes,{id,kind,label:allText(kind),position,config:configFor(kind)}]};
  if(pending)next=connectGraph(next,pending.source,pending.port,id);
  if(old)next=connectGraph(next,id,kind==='condition'?'yes':'next',old.target);
  return {graph:next,id};
}

export function arrangeGraph(graph:Graph):Graph {
  const incoming=new Map(graph.nodes.map(n=>[n.id,graph.edges.filter(e=>e.target===n.id).length]));
  const level=new Map<string,number>(),queue=graph.nodes.filter(n=>incoming.get(n.id)===0).map(n=>n.id);
  for(const id of queue)level.set(id,0);
  for(let i=0;i<queue.length;i++){
    const id=queue[i];
    for(const e of graph.edges.filter(e=>e.source===id)){
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
