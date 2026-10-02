"""Bounded graph editor and interpreter for the local LAB. No executable code or bank tools."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.agent_routing import route_family, route_plan
from . import flow_engine as flow, storage, app_diagnostics
from .decision import INSTRUCTIONS, LABELS
from .providers import classify_jev, openai_response, save_run

KINDS = ('start', 'jev', 'context', 'condition', 'question', 'response', 'escalate', 'diagnostic', 'notify')
TERMINALS = {'question', 'response', 'escalate'}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Text(Strict):
    es: str = Field(default='', max_length=1200)
    en: str = Field(default='', max_length=1200)
    pt: str = Field(default='', max_length=1200)


class Position(Strict):
    x: float = Field(ge=-10000, le=10000, allow_inf_nan=False)
    y: float = Field(ge=-10000, le=10000, allow_inf_nan=False)


class JevConfig(Strict):
    instructions: Text = Field(default_factory=Text)


class ContextConfig(JevConfig):
    mode: Literal['case', 'selected'] = 'case'
    fields: list[str] = Field(default_factory=list, max_length=12)
    notes: Text = Field(default_factory=Text)

    @model_validator(mode='after')
    def allowed_fields(self):
        if len(self.fields) != len(set(self.fields)) or any(f not in flow.QUESTIONS for f in self.fields):
            raise ValueError('invalid_fields')
        if self.mode == 'selected' and not self.fields: raise ValueError('select_fields')
        return self


class ConditionConfig(Strict):
    predicate: Literal['intent_is', 'family_is', 'has_missing', 'field_missing', 'needs_human', 'diagnostic_failed'] = 'has_missing'
    value: str = Field(default='', max_length=80)

    @model_validator(mode='after')
    def allowed_value(self):
        allowed = {'intent_is': LABELS, 'family_is': {'query','problem','service','clarification'},
                   'field_missing': set(flow.QUESTIONS), 'has_missing': {''}, 'needs_human': {''}, 'diagnostic_failed': {''}}
        if self.value not in allowed[self.predicate]: raise ValueError('invalid_condition')
        return self


class QuestionConfig(Strict):
    mode: Literal['missing', 'custom'] = 'missing'
    text: Text = Field(default_factory=Text)

    @model_validator(mode='after')
    def custom_has_text(self):
        if self.mode == 'custom' and any(not s.strip() or len(s) > 600 for s in self.text.model_dump().values()):
            raise ValueError('question_needs_three_languages')
        return self


class ResponseConfig(Strict):
    outcome: Literal['information', 'review_in_bank'] = 'review_in_bank'
    text: Text = Field(default_factory=Text)

    @model_validator(mode='after')
    def information_has_text(self):
        if self.outcome == 'information' and any(not s.strip() for s in self.text.model_dump().values()):
            raise ValueError('response_needs_three_languages')
        return self


class EscalateConfig(Strict):
    text: Text = Field(default_factory=Text)


CONFIGS = {'start': Strict, 'diagnostic': Strict, 'notify': Strict, 'jev': JevConfig, 'context': ContextConfig, 'condition': ConditionConfig,
           'question': QuestionConfig, 'response': ResponseConfig, 'escalate': EscalateConfig}


class Node(Strict):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,49}$')
    kind: Literal['start','jev','context','condition','question','response','escalate','diagnostic','notify']
    label: Text
    position: Position
    config: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def known_configuration(self):
        if any(not s.strip() or len(s) > 90 for s in self.label.model_dump().values()): raise ValueError('invalid_label')
        self.config = CONFIGS[self.kind].model_validate(self.config).model_dump()
        return self


class Edge(Strict):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,99}$')
    source: str = Field(max_length=50)
    target: str = Field(max_length=50)
    port: Literal['next', 'yes', 'no'] = 'next'


class Graph(Strict):
    schema_version: Literal[1] = 1
    name: Text
    nodes: list[Node] = Field(min_length=1, max_length=24)
    edges: list[Edge] = Field(default_factory=list, max_length=36)

    @model_validator(mode='after')
    def bounded_name(self):
        if any(not s.strip() or len(s) > 100 for s in self.name.model_dump().values()): raise ValueError('invalid_name')
        return self


def text(es, en, pt): return dict(zip(flow.LANGS, (es, en, pt)))


def template(kind='banking'):
    def node(id, kind, label, x, y, config=None):
        return {'id':id,'kind':kind,'label':text(*label),'position':{'x':x,'y':y},'config':config or {}}
    if kind=='app':
        nodes=[node('start','start',('Inicio','Start','Início'),0,100),
               node('logs','diagnostic',('Recoger logs de la incidencia','Read incident logs','Ler logs da incidência'),230,100),
               node('failed','condition',('¿Se confirmó el error?','Was an error recorded?','O erro foi registrado?'),460,100,{'predicate':'diagnostic_failed'}),
               node('notify','notify',('Registrar aviso de incidencia','Register incident notification','Registrar aviso de incidência'),690,0),
               node('result','response',('Confirmar el aviso','Confirm notification','Confirmar o aviso'),920,0,
                    {'outcome':'information','text':text('El flujo terminó. Revisa el aviso local y su referencia en la traza.', 'The flow finished. Review the local notification and its reference in the trace.', 'O fluxo terminou. Confira o aviso local e sua referência no rastro.')}),
               node('noerror','response',('Revisar el resultado','Review result','Revisar o resultado'),690,220,
                    {'outcome':'information','text':text('No hay un error registrado en esta comprobación.', 'No error was recorded in this check.', 'Não há erro registrado nesta verificação.')}),
              ]
        links=[('start','logs','next'),('logs','failed','next'),('failed','notify','yes'),('failed','noerror','no'),('notify','result','next')]
        return Graph.model_validate({'name':text('Incidencia de acceso a la app','App access incident','Incidência de acesso ao app'),'nodes':nodes,
                    'edges':[{'id':f'e{i}','source':a,'target':b,'port':p} for i,(a,b,p) in enumerate(links)]}).model_dump()
    nodes = [
        node('start','start',('Mensaje del cliente','Customer message','Mensagem do cliente'),0,100),
        node('jev','jev',('Clasificar el caso','Classify the case','Classificar o caso'),210,100),
        node('scope','condition',('¿Fuera de alcance?','Out of scope?','Fora do escopo?'),420,100,{'predicate':'intent_is','value':'out-of-scope'}),
        node('outside','response',('Orientar al cliente','Guide the customer','Orientar o cliente'),420,300,{'outcome':'information','text':text(*flow.COPY['stop'])}),
        node('context','context',('Contexto e instrucciones','Context and instructions','Contexto e instruções'),630,100),
        node('human','condition',('¿Requiere una persona?','Needs a person?','Precisa de uma pessoa?'),840,100,{'predicate':'needs_human'}),
        node('escalate','escalate',('Proponer revisión humana','Propose human review','Propor revisão humana'),840,300),
        node('missing','condition',('¿Faltan datos?','Missing information?','Faltam dados?'),1050,100),
        node('ask','question',('Preguntar lo que falta','Ask for missing details','Perguntar o que falta'),1260,0),
        node('review','response',('Revisar en el banco','Review in the bank','Revisar no banco'),1260,210),
    ]
    links=[('start','jev','next'),('jev','scope','next'),('scope','outside','yes'),('scope','context','no'),
           ('context','human','next'),('human','escalate','yes'),('human','missing','no'),('missing','ask','yes'),('missing','review','no')]
    return Graph.model_validate({'name':text('Atención bancaria','Banking support','Atendimento bancário'), 'nodes':nodes,
                                 'edges':[{'id':f'e{i}','source':a,'target':b,'port':p} for i,(a,b,p) in enumerate(links)]}).model_dump()


def validate_graph(graph):
    """Validate ports, reachability, acyclicity and required predecessors on every path."""
    graph = Graph.model_validate(graph).model_dump()
    nodes = {n['id']:n for n in graph['nodes']}
    errors=[]
    def error(code, node=None, port=None): errors.append({'code':code,'node_id':node,'port':port})
    if len(nodes)!=len(graph['nodes']): error('duplicate_node')
    if len({e['id'] for e in graph['edges']})!=len(graph['edges']): error('duplicate_edge')
    starts=[n['id'] for n in graph['nodes'] if n['kind']=='start']
    if len(starts)!=1: error('one_start')
    for kind in ('jev','context','diagnostic'):
        if sum(n['kind']==kind for n in graph['nodes'])>1: error('one_provider_node',kind)
    outgoing={id:{} for id in nodes}; incoming={id:[] for id in nodes}
    for edge in graph['edges']:
        a,b,p=edge['source'],edge['target'],edge['port']
        if a not in nodes or b not in nodes: error('missing_node'); continue
        ports=() if nodes[a]['kind'] in TERMINALS else ('yes','no') if nodes[a]['kind']=='condition' else ('next',)
        if p not in ports: error('invalid_port',a,p)
        if p in outgoing[a]: error('duplicate_port',a,p)
        if nodes[b]['kind']=='start': error('start_has_input',b)
        outgoing[a][p]=b;incoming[b].append(a)
    for id,node in nodes.items():
        ports=() if node['kind'] in TERMINALS else ('yes','no') if node['kind']=='condition' else ('next',)
        for port in ports:
            if port not in outgoing[id]: error('unconnected_port',id,port)
    if errors: return {'valid':False,'errors':errors}
    seen=set();active=set();order=[]
    def visit(id):
        if id in active: error('cycle',id); return
        if id in seen: return
        seen.add(id);active.add(id)
        for target in outgoing[id].values(): visit(target)
        active.remove(id);order.append(id)
    visit(starts[0])
    for id in nodes.keys()-seen: error('unreachable',id)
    if errors: return {'valid':False,'errors':errors}
    known={}
    for id in reversed(order):
        node=nodes[id]; parents=incoming[id]
        before=set.intersection(*(known[p] for p in parents)) if parents else set()
        needs=None
        if node['kind']=='context' and node['config']['mode']=='case': needs='jev'
        if node['kind']=='condition': needs='diagnostic' if node['config']['predicate']=='diagnostic_failed' else 'jev' if node['config']['predicate'] in ('intent_is','family_is') else 'context'
        if node['kind']=='question' and node['config']['mode']=='missing': needs='context'
        if node['kind']=='notify': needs='diagnostic'
        if needs and needs not in before: error('requires_'+needs,id)
        known[id]=before|{node['kind']}
    return {'valid':not errors,'errors':errors}


def workflow_path(id): return storage.DATA_DIR/'workflows'/f'{uuid.UUID(str(id))}.json'


def read_workflow(id):
    path=workflow_path(id)
    if not path.exists(): raise FileNotFoundError()
    return json.loads(path.read_text(encoding='utf-8'))


def list_workflows():
    rows=[]
    for path in (storage.DATA_DIR/'workflows').glob('*.json'):
        row=json.loads(path.read_text(encoding='utf-8'))
        rows.append({key:row[key] for key in ('id','revision','updated_at','validation')}|{'name':row['graph']['name']})
    return sorted(rows,key=lambda row:row['updated_at'],reverse=True)


def save_workflow(graph, id=None, revision=None):
    graph=Graph.model_validate(graph).model_dump()
    if id:
        current=read_workflow(id)
        if current['revision']!=revision: raise RuntimeError('revision_conflict')
    else:
        if len(list_workflows())>=50: raise RuntimeError('workflow_limit')
        id=str(uuid.uuid4());current={'revision':0}
    record={'id':str(id),'revision':current['revision']+1,'updated_at':datetime.now(timezone.utc).isoformat(),
            'graph':graph,'validation':validate_graph(graph)}
    path=workflow_path(id);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    return record


def extract(messages,language,fields,instructions,notes,intent,incident=None):
    schema={'type':'object','additionalProperties':False,'required':['assessment','observations'],'properties':{
        'assessment':{'type':'string','enum':['continue','conflicting','human_review']},
        'observations':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['field','message_index','quote'],
            'properties':{'field':{'type':'string',**({'enum':fields} if fields else {})},'message_index':{'type':'integer'},'quote':{'type':'string','maxLength':240}}}}}}
    return openai_response({'language':language,'messages':messages,'required_fields':fields,'intent':intent,
                            'custom_instructions':instructions,'unverified_reference_notes':notes,'controlled_lab_incident':incident,
                            'field_questions':{f:flow.QUESTIONS[f][flow.LANGS.index(language)] for f in fields}},
                           flow.EXTRACT_INSTRUCTIONS,schema,'workflow_context',lambda value:flow.validate_observations(value,fields,messages))


def run_workflow(record,messages,language,thread_id=None,incident_id=None,on_event=None):
    graph=Graph.model_validate(record['graph']).model_dump()
    validation=validate_graph(graph)
    if not validation['valid']: raise ValueError('invalid_graph')
    started=time.perf_counter();nodes={n['id']:n for n in graph['nodes']}
    outgoing={(e['source'],e['port']):e for e in graph['edges']}
    current=next(n['id'] for n in graph['nodes'] if n['kind']=='start')
    jev={'status':'skipped'};llm={'status':'skipped'};missing=[];observations=[];questions=[];intent=None
    traces=[];edges=[];state='information';reply='';request=None;fields=[];incident=None;notice=None
    for _ in range(24):
        node=nodes[current];kind=node['kind'];cfg=node['config'];port='next';tick=time.perf_counter();output={};status='ok'
        if on_event: on_event({'event':'node_started','node_id':current,'kind':kind})
        if kind=='start': output={'message_count':len(messages),'language':language}
        elif kind=='diagnostic':
            try:
                if not incident_id: raise FileNotFoundError()
                incident=app_diagnostics.read(incident_id);output=incident
            except FileNotFoundError:
                status='missing_incident';output={'error':'missing_incident'}
        elif kind=='notify':
            notice=app_diagnostics.notify(incident['id'],record['id'],current);output=notice
        elif kind=='jev':
            jev,request=classify_jev(messages,language,INSTRUCTIONS+'\n'+cfg['instructions'][language])
            output=jev;intent=jev.get('intent');status=jev['status']
        elif kind=='context':
            fields=flow.REQUIREMENTS[intent] if cfg['mode']=='case' else cfg['fields']
            llm=extract(messages,language,fields,cfg['instructions'][language],cfg['notes'][language],intent,incident)
            status=llm['status'];output=llm
            if status=='ok':
                observations=[{**o,'status':'declared','source':'customer_message'} for o in llm['observations']]
                missing=[f for f in fields if f not in {o['field'] for o in observations}]
                output={**llm,'missing_fields':missing,'verified_facts':[]}
        elif kind=='condition':
            checks={'intent_is':intent==cfg['value'],'family_is':route_family(intent)==cfg['value'] if intent else False,
                    'has_missing':bool(missing),'field_missing':cfg['value'] in missing,'needs_human':llm.get('assessment') in ('conflicting','human_review'),
                    'diagnostic_failed': bool(incident and incident['state']=='failed')}
            passed=checks[cfg['predicate']];port='yes' if passed else 'no';output={'predicate':cfg['predicate'],'value':cfg['value'],'matched':passed,'port':port}
        elif kind=='question':
            if cfg['mode']=='missing':
                questions=[{'field':f,'text':flow.QUESTIONS[f][flow.LANGS.index(language)]} for f in missing[:2]]
                state='ask_customer' if questions else 'review_in_bank'
                reply=' '.join([flow.COPY[state][flow.LANGS.index(language)]]+[q['text'] for q in questions])
            else:
                reply=cfg['text'][language];questions=[{'field':None,'text':reply}];state='ask_customer'
            output={'state':state,'reply':reply,'questions':questions}
        elif kind=='response':
            state=cfg['outcome'];reply=cfg['text'][language] or flow.COPY['review_in_bank'][flow.LANGS.index(language)]
            output={'state':state,'reply':reply,'authorizes_execution':False}
        elif kind=='escalate':
            state='human_review';reply=cfg['text'][language] or flow.COPY['human_review'][flow.LANGS.index(language)]
            output={'state':state,'reply':reply,'handoff_sent':False}
        traces.append({'node_id':current,'kind':kind,'label':node['label'],'status':status,'output':output,'latency_ms':round((time.perf_counter()-tick)*1000,1)})
        if on_event: on_event({'event':'node_finished','trace':traces[-1]})
        if status!='ok':
            state='missing_incident' if status=='missing_incident' else 'provider_unavailable'
            reply=text('Primero ejecuta la comprobación de acceso y vincula su incidencia.', 'Run the access check first and link its incident.', 'Primeiro execute a verificação de acesso e vincule sua incidência.')[language] if state=='missing_incident' else flow.COPY[state][flow.LANGS.index(language)]
            break
        if kind in TERMINALS: break
        edge=outgoing[(current,port)];edges.append(edge['id']);current=edge['target']
        if on_event: on_event({'event':'edge_taken','edge_id':edge['id'],'port':port})
    result={'id':str(uuid.uuid4()),'thread_id':thread_id or str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
            'language':language,'workflow_id':record['id'],'workflow_revision':record['revision'],'workflow':graph,
            'graph_sha256':hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest(),
            'extraction_prompt_sha256':hashlib.sha256(flow.EXTRACT_INSTRUCTIONS.encode()).hexdigest(),
            'jev':jev,'llm':llm,'state':state,'reply':reply,'questions':questions,'missing_fields':missing,'observations':observations,
            'trace':traces,'visited_edges':edges,'latency_ms':round((time.perf_counter()-started)*1000,1),
            'tool_plan':route_plan(jev),'incident':incident,'notification':notice,'executed_operations':[],'executed_tools':[],'authorizes_execution':False,'verified_facts':[]}
    save_run({'kind':'workflow','actor':'local_operator','messages':messages,'request':request,'result':result})
    return result
