import {useEffect} from 'react';
import {Handle,Position,BaseEdge,EdgeLabelRenderer,getBezierPath,useUpdateNodeInternals,type Node,type NodeProps,type Edge,type EdgeProps} from '@xyflow/react';
import {Play,Shapes,BrainCircuit,Split,MessageCircle,MessageSquare,UserRound,FileSearch,BellRing,Plus,Check,AlertCircle,LoaderCircle,Route,ClipboardList,GitBranch,Zap} from 'lucide-react';
import {et} from './editorLocales';
import type {Language} from './locales';
import {ports,type Kind,type Port} from './workflowGraph';

export const blockIcons={start:Play,triage:Route,jev:Shapes,case_router:GitBranch,contract:ClipboardList,preview:Zap,context:BrainCircuit,condition:Split,question:MessageCircle,response:MessageSquare,escalate:UserRound,diagnostic:FileSearch,notify:BellRing};
type BlockData={label:string;kind:Kind;language:Language;status?:string;connectedPorts:Port[];busy:boolean;canStep:boolean;step:(id:string)=>void;addAfter:(id:string,port:Port)=>void};
export type CanvasNode=Node<BlockData,'block'>;
type EdgeData={language:Language;insert:(id:string)=>void;busy:boolean;port:Port;canStep:boolean;step:()=>void};
export type CanvasEdge=Edge<EdgeData,'insertable'>;

export function BlockNode({id,data,selected}:NodeProps<CanvasNode>){
  const Icon=blockIcons[data.kind];
  const top=(i:number)=>data.kind==='case_router'?(10+i*13)+'%':data.kind==='condition'?(i?'72%':'28%'):'50%';
  const updateInternals=useUpdateNodeInternals();
  // Restoring a checkpoint changes controlled node data before ResizeObserver can run.
  // Refresh handles after that render even when the tile's dimensions stayed identical.
  useEffect(()=>{updateInternals(id);},[id,data.kind,data.label,data.busy,data.status,updateInternals]);
  return <div className={'editor-block '+(selected?'is-selected ':'')+(data.status?'visited':'')} data-block-kind={data.kind} data-stage-status={data.status}>
    <div className={'editor-node-tile kind-'+data.kind}>
      {data.kind!=='start'&&<Handle type="target" position={Position.Left} title={et(data.language,'connectInput')+' · '+data.label}/>}
      <Icon size={32} strokeWidth={1.6} aria-hidden="true"/>
      {data.status&&<span role="img" className={'editor-node-status '+(data.status==='running'?'running':data.status==='ok'?'ok':'failed')} aria-label={et(data.language,data.status==='running'?'running':data.status==='ok'?(data.kind==='preview'?'planReady':'completed'):'error')}>{data.status==='running'?<LoaderCircle className="spin" size={13}/>:data.status==='ok'?(data.kind==='preview'?<Zap size={13}/>:<Check size={13}/>):<AlertCircle size={13}/>}</span>}
      {ports(data.kind).map((port,i)=><div key={port}>
        <Handle type="source" id={port} position={Position.Right} style={{top:top(i)}} title={et(data.language,'connectOutput')+' · '+et(data.language,port)+' · '+data.label}/>
        {data.kind==='condition'&&<span className={'port-label port-'+port}>{et(data.language,port)}</span>}
        {data.kind==='case_router'&&<span className="router-port-label" style={{top:top(i)}}>{et(data.language,port)}</span>}
        {port!=='reply'&&!data.connectedPorts.includes(port)&&<button className={'node-add nodrag nopan port-'+port} data-add-source={id} data-add-port={port} disabled={data.busy} style={{top:top(i)}} aria-label={et(data.language,'addAfter')+' '+data.label+' · '+et(data.language,port)} title={et(data.language,'addAfter')+' '+data.label} onClick={event=>{event.stopPropagation();data.addAfter(id,port);}}><Plus size={15}/></button>}
      </div>)}
    </div>
    <strong>{data.label}</strong><span className="editor-node-kind">{et(data.language,data.kind)}</span>
    {data.kind==='preview'&&<span className="node-preview-badge">{et(data.language,'wouldActivate')}</span>}
    <button className="node-step nodrag nopan" data-step-node={id} disabled={!data.canStep} title={et(data.language,data.canStep?'stepBlock':'stepUnavailable')} aria-label={et(data.language,'stepBlock')+' · '+data.label} onClick={event=>{event.stopPropagation();data.step(id);}}><Play size={12}/></button>
  </div>;
}

export function InsertableEdge(props:EdgeProps<CanvasEdge>){
  const feedback=props.data?.port==='reply';
  const [curve,cx,cy]=getBezierPath(props);
  const bottom=Math.max(props.sourceY,props.targetY)+180;
  const path=feedback?`M ${props.sourceX} ${props.sourceY} C ${props.sourceX+90} ${bottom}, ${props.targetX-90} ${bottom}, ${props.targetX} ${props.targetY}`:curve;
  const x=feedback?(props.sourceX+props.targetX)/2:cx,y=feedback?(props.sourceY+props.targetY)/8+bottom*.75:cy;
  return <>
    <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} interactionWidth={22} label={props.label} labelX={x} labelY={y-27} labelStyle={{fill:'#65574e',fontSize:12,fontWeight:600}} labelBgStyle={{fill:'#f7f5f1'}}/>
    <EdgeLabelRenderer>{!feedback&&<button className="edge-insert nodrag nopan" data-insert-edge={props.id} disabled={props.data?.busy} style={{transform:`translate(-50%, -50%) translate(${x-18}px,${y}px)`}} title={et(props.data!.language,'insert')} aria-label={et(props.data!.language,'insert')} onClick={event=>{event.stopPropagation();props.data?.insert(props.id);}}><Plus size={13}/></button>}<button className="edge-step nodrag nopan" data-step-edge={props.id} disabled={!props.data?.canStep} style={{transform:`translate(-50%, -50%) translate(${x+(feedback?0:18)}px,${y}px)`}} title={et(props.data!.language,props.data?.canStep?'stepNext':'stepUnavailable')} aria-label={et(props.data!.language,'stepNext')+' · '+et(props.data!.language,props.data!.port)+' · '+props.target} onClick={event=>{event.stopPropagation();props.data?.step();}}><Play size={12}/></button></EdgeLabelRenderer>
  </>;
}

export const nodeTypes={block:BlockNode};
export const edgeTypes={insertable:InsertableEdge};
