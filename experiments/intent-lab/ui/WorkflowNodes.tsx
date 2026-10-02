import {Handle,Position,BaseEdge,EdgeLabelRenderer,getBezierPath,type Node,type NodeProps,type Edge,type EdgeProps} from '@xyflow/react';
import {Play,Shapes,BrainCircuit,Split,MessageCircle,MessageSquare,UserRound,FileSearch,BellRing,Plus,Check,AlertCircle,LoaderCircle} from 'lucide-react';
import {et} from './editorLocales';
import type {Language} from './locales';
import {ports,type Kind,type Port} from './workflowGraph';

export const blockIcons={start:Play,jev:Shapes,context:BrainCircuit,condition:Split,question:MessageCircle,response:MessageSquare,escalate:UserRound,diagnostic:FileSearch,notify:BellRing};
type BlockData={label:string;kind:Kind;language:Language;status?:string;connectedPorts:Port[];busy:boolean;addAfter:(id:string,port:Port)=>void};
export type CanvasNode=Node<BlockData,'block'>;
type EdgeData={language:Language;insert:(id:string)=>void;busy:boolean};
export type CanvasEdge=Edge<EdgeData,'insertable'>;

export function BlockNode({id,data,selected}:NodeProps<CanvasNode>){
  const Icon=blockIcons[data.kind];
  return <div className={'editor-block '+(selected?'is-selected ':'')+(data.status?'visited':'')} data-block-kind={data.kind} data-stage-status={data.status}>
    <div className={'editor-node-tile kind-'+data.kind}>
      {data.kind!=='start'&&<Handle type="target" position={Position.Left} title={et(data.language,'connectInput')+' · '+data.label}/>}
      <Icon size={32} strokeWidth={1.6} aria-hidden="true"/>
      {data.status&&<span role="img" className={'editor-node-status '+(data.status==='running'?'running':data.status==='ok'?'ok':'failed')} aria-label={et(data.language,data.status==='running'?'running':data.status==='ok'?'completed':'error')}>{data.status==='running'?<LoaderCircle className="spin" size={13}/>:data.status==='ok'?<Check size={13}/>:<AlertCircle size={13}/>}</span>}
      {ports(data.kind).map((port,i)=><div key={port}>
        <Handle type="source" id={port} position={Position.Right} style={{top:data.kind==='condition'?(i?'72%':'28%'):'50%'}} title={et(data.language,'connectOutput')+' · '+et(data.language,port)+' · '+data.label}/>
        {data.kind==='condition'&&<span className={'port-label port-'+port}>{et(data.language,port)}</span>}
        {!data.connectedPorts.includes(port)&&<button className={'node-add nodrag nopan port-'+port} data-add-source={id} data-add-port={port} disabled={data.busy} style={{top:data.kind==='condition'?(i?'72%':'28%'):'50%'}} aria-label={et(data.language,'addAfter')+' '+data.label+' · '+et(data.language,port)} title={et(data.language,'addAfter')+' '+data.label} onClick={event=>{event.stopPropagation();data.addAfter(id,port);}}><Plus size={15}/></button>}
      </div>)}
    </div>
    <strong>{data.label}</strong><span className="editor-node-kind">{et(data.language,data.kind)}</span>
  </div>;
}

export function InsertableEdge(props:EdgeProps<CanvasEdge>){
  const [path,x,y]=getBezierPath(props);
  return <>
    <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} interactionWidth={22} label={props.label} labelX={x} labelY={y-27} labelStyle={{fill:'#65574e',fontSize:12,fontWeight:600}} labelBgStyle={{fill:'#f7f5f1'}}/>
    <EdgeLabelRenderer><button className="edge-insert nodrag nopan" data-insert-edge={props.id} disabled={props.data?.busy} style={{transform:`translate(-50%, -50%) translate(${x}px,${y}px)`}} title={et(props.data!.language,'insert')} aria-label={et(props.data!.language,'insert')} onClick={event=>{event.stopPropagation();props.data?.insert(props.id);}}><Plus size={13}/></button></EdgeLabelRenderer>
  </>;
}

export const nodeTypes={block:BlockNode};
export const edgeTypes={insertable:InsertableEdge};
