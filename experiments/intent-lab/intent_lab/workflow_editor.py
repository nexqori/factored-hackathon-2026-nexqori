"""Bounded graph editor and interpreter for the local LAB. No executable code or bank tools."""
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from . import flow_engine as flow, storage
from .decision import LABELS
from .providers import classify_jev, openai_response
from .workflow_routing import classify_triage, case_criteria

PROBLEM_PORTS = ('unrecognized-charge', 'incorrect-charge', 'payment-status', 'app-support', 'branch-support', 'service-feedback')
KINDS = ('start', 'triage', 'jev', 'case_router', 'contract', 'preview', 'context', 'condition', 'question', 'response', 'escalate', 'diagnostic', 'notify')
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


class ModelConfig(Strict):
    instructions: Text = Field(default_factory=Text)


class JevConfig(ModelConfig):
    scope: Literal['all', 'problem', 'query'] = 'all'


class ContextConfig(ModelConfig):
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
    predicate: Literal['triage_is', 'intent_is', 'family_is', 'has_missing', 'field_missing', 'needs_human', 'diagnostic_failed'] = 'has_missing'
    value: str = Field(default='', max_length=80)

    @model_validator(mode='after')
    def allowed_value(self):
        allowed = {'triage_is': {'query','problem','clarification'}, 'intent_is': LABELS, 'family_is': {'query','problem','service','clarification'},
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
    outcome: Literal['information', 'review_in_bank', 'current'] = 'review_in_bank'
    text: Text = Field(default_factory=Text)

    @model_validator(mode='after')
    def information_has_text(self):
        if self.outcome == 'information' and any(not s.strip() for s in self.text.model_dump().values()):
            raise ValueError('response_needs_three_languages')
        return self


class EscalateConfig(Strict):
    text: Text = Field(default_factory=Text)


class ContractConfig(Strict):
    intent: Literal['', 'unrecognized-charge', 'incorrect-charge', 'payment-status', 'app-support', 'branch-support', 'service-feedback'] = ''


class PreviewConfig(Strict):
    stage: Literal['query', 'action', 'handoff', 'delivery', 'closure'] = 'action'


CONFIGS = {'start': Strict, 'case_router': Strict, 'contract': ContractConfig, 'preview': PreviewConfig, 'diagnostic': Strict, 'notify': Strict, 'triage': ModelConfig, 'jev': JevConfig, 'context': ContextConfig, 'condition': ConditionConfig,
           'question': QuestionConfig, 'response': ResponseConfig, 'escalate': EscalateConfig}


class Node(Strict):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,49}$')
    kind: Literal['start','triage','jev','case_router','contract','preview','context','condition','question','response','escalate','diagnostic','notify']
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
    port: Literal['next', 'yes', 'no', 'reply', 'unrecognized-charge', 'incorrect-charge', 'payment-status', 'app-support', 'branch-support', 'service-feedback', 'otherwise'] = 'next'


class Graph(Strict):
    schema_version: Literal[1] = 1
    name: Text
    nodes: list[Node] = Field(min_length=1, max_length=40)
    edges: list[Edge] = Field(default_factory=list, max_length=64)

    @model_validator(mode='after')
    def bounded_name(self):
        if any(not s.strip() or len(s) > 100 for s in self.name.model_dump().values()): raise ValueError('invalid_name')
        return self


def text(es, en, pt): return dict(zip(flow.LANGS, (es, en, pt)))


def execution_rules(graph):
    """Presentation edits do not invalidate a paused execution's frozen rules."""
    return {'schema_version': graph['schema_version'],
            'nodes': sorted(({key:n[key] for key in ('id','kind','config')} for n in graph['nodes']), key=lambda n:n['id']),
            'edges': sorted(graph['edges'], key=lambda e:e['id'])}


def legacy_template(kind='banking'):
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


def with_initial_route(graph):
    """Create a new draft with routing and a customer-controlled feedback connection."""
    import copy
    graph=copy.deepcopy(graph)
    def node(id,kind,labels,x,y,config=None):
        return {'id':id,'kind':kind,'label':text(*labels),'position':{'x':x,'y':y},'config':config or {}}
    for n in graph['nodes']:
        if n['kind']!='start': n['position']['x']+=780
        if n['kind']=='jev': n['config']['scope']='problem'
    graph['nodes'] += [
        node('triage','triage',('¿Consulta o queja?','Inquiry or complaint?','Consulta ou reclamação?'),260,100),
        node('complaint_route','condition',('¿Es una queja o problema?','Is it a complaint or problem?','É uma reclamação ou problema?'),520,100,{'predicate':'triage_is','value':'problem'}),
        node('query_route','condition',('¿Es una consulta o gestión?','Is it an inquiry or request?','É uma consulta ou solicitação?'),520,450,{'predicate':'triage_is','value':'query'}),
        node('query_case','jev',('Identificar la consulta','Identify the inquiry','Identificar a consulta'),780,450,{'scope':'query'}),
        node('query_result','response',('Orientar la consulta','Guide the inquiry','Orientar a consulta'),1040,450,{'outcome':'information','text':text('La consulta tiene su propia ruta. Revisa las herramientas propuestas y los datos que necesitan antes de consultar el banco.','The inquiry has its own route. Review the proposed tools and their required information before checking bank records.','A consulta tem seu próprio percurso. Confira as ferramentas propostas e os dados necessários antes de consultar o banco.')}),
        node('clarify','question',('Precisar la necesidad','Clarify the need','Esclarecer a necessidade'),780,680,{'mode':'custom','text':text('¿Quieres consultar información o reportar un problema? Cuéntame qué necesitas revisar primero.','Would you like information or to report a problem? Tell me what you need to review first.','Quer consultar informações ou relatar um problema? Conte o que precisa revisar primeiro.')}),
    ]
    first=next(n['id'] for n in graph['nodes'] if n['kind']=='start')
    initial=next(e for e in graph['edges'] if e['source']==first)
    previous=initial['target'];initial['target']='triage'
    links=[('triage','complaint_route','next'),('complaint_route',previous,'yes'),('complaint_route','query_route','no'),
           ('query_route','query_case','yes'),('query_route','clarify','no'),('query_case','query_result','next')]
    context=next(n['id'] for n in graph['nodes'] if n['kind']=='context')
    question=next(n['id'] for n in graph['nodes'] if n['kind']=='question' and n['config'].get('mode')=='missing')
    links.append((question,context,'reply'))
    graph['edges'] += [{'id':'routing_'+str(i),'source':a,'target':b,'port':port} for i,(a,b,port) in enumerate(links)]
    return Graph.model_validate(graph).model_dump()


def legacy_master_template(kind='banking'):
    if kind=='app': return legacy_template('app')
    graph=legacy_template()
    def node(id,kind,labels,x,y,config=None):
        return {'id':id,'kind':kind,'label':text(*labels),'position':{'x':x,'y':y},'config':config or {}}
    # One graph: the classified intent selects the contract and its requirements at runtime.
    graph['name']=text('Flujo de atención','Support workflow','Fluxo de atendimento')
    graph['nodes'] += [
        node('contract','contract',('Cargar contrato del caso','Load case procedure','Carregar procedimento do caso'),630,100),
        node('app_case','condition',('¿Problema de la app?','App issue?','Problema no app?'),890,100,{'predicate':'intent_is','value':'app-support'}),
        node('logs','diagnostic',('Recoger logs de la incidencia','Read incident logs','Ler logs da incidência'),1150,-160),
        node('failed','condition',('¿Se confirmó el error?','Was an error recorded?','O erro foi registrado?'),1410,-160,{'predicate':'diagnostic_failed'}),
        node('notify','notify',('Registrar aviso de incidencia','Register incident notification','Registrar aviso de incidência'),1670,-160),
    ]
    scope=next(n for n in graph['nodes'] if n['id']=='scope')
    scope.update(label=text('¿Problema identificado?','Problem identified?','Problema identificado?'),config={'predicate':'family_is','value':'problem'})
    for n in graph['nodes']:
        if n['id'] in ('context','human','escalate','missing','ask','review'):n['position']['x']+=1300
    for e in graph['edges']:
        if e['source']=='scope':
            e['port']='no' if e['target']=='outside' else 'yes'
            if e['target']=='context':e['target']='contract'
    links=[('contract','app_case','next'),('app_case','logs','yes'),('app_case','context','no'),
           ('logs','failed','next'),('failed','notify','yes'),('failed','context','no'),('notify','context','next')]
    graph['edges'] += [{'id':'case_'+str(i),'source':a,'target':b,'port':p} for i,(a,b,p) in enumerate(links)]
    return with_initial_route(Graph.model_validate(graph).model_dump())


def template(kind='banking'):
    if kind == 'app': return legacy_template('app')
    from .workflow_templates import support_workflow
    return support_workflow()


def master_workflow():
    """Keep one saved default graph, preserving user edits and other saved workflows."""
    path=storage.DATA_DIR/'master-workflow.json'
    if path.exists():
        try:
            pointer = json.loads(path.read_text(encoding='utf-8'))
            record = read_workflow(pointer['id'])
            # Only upgrade the untouched generated graph. Preserve custom edits and
            # the original snapshot for old execution links and local recovery.
            if pointer.get('template_version', 1) < 2 and Graph.model_validate(record['graph']).model_dump() == legacy_master_template():
                archive = storage.DATA_DIR/'workflow-revisions'/f"{record['id']}-v{record['revision']}.json"
                archive.parent.mkdir(parents=True, exist_ok=True)
                archive.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
                record = save_workflow(template(), record['id'], record['revision'])
                temp=path.with_suffix('.tmp');temp.write_text(json.dumps({'id':record['id'], 'template_version':2}),encoding='utf-8');temp.replace(path)
            return record
        except FileNotFoundError:pass
    record=save_workflow(template())
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps({'id':record['id'], 'template_version':2}),encoding='utf-8');temp.replace(path)
    return record


def validate_graph(graph):
    """Automatic paths are acyclic. Feedback must wait for new customer input."""
    graph=Graph.model_validate(graph).model_dump()
    nodes={n['id']:n for n in graph['nodes']};errors=[]
    def error(code,node=None,port=None): errors.append({'code':code,'node_id':node,'port':port})
    if len(nodes)!=len(graph['nodes']): error('duplicate_node')
    if len({e['id'] for e in graph['edges']})!=len(graph['edges']): error('duplicate_edge')
    starts=[n['id'] for n in graph['nodes'] if n['kind']=='start']
    if len(starts)!=1: error('one_start')
    for kind,limit in [('jev',2),('triage',1),('case_router',1),('contract',6),('context',1),('diagnostic',1)]:
        if sum(n['kind']==kind for n in graph['nodes'])>limit: error('one_provider_node',kind)
    outgoing={id:{} for id in nodes};incoming={id:[] for id in nodes};feedback=[]
    for edge in graph['edges']:
        a,b,port=edge['source'],edge['target'],edge['port']
        if a not in nodes or b not in nodes: error('missing_node');continue
        kind=nodes[a]['kind']
        ports=('reply',) if kind=='question' else () if kind in TERMINALS else (*PROBLEM_PORTS,'otherwise') if kind=='case_router' else ('yes','no') if kind=='condition' else ('next',)
        if port not in ports: error('invalid_port',a,port)
        if port in outgoing[a]: error('duplicate_port',a,port)
        if nodes[b]['kind']=='start': error('start_has_input',b)
        outgoing[a][port]=b
        if port=='reply':
            feedback.append(edge)
            if kind!='question' or nodes[b]['kind']!='context': error('invalid_feedback',a,port)
        else: incoming[b].append(a)
    for id,node in nodes.items():
        ports=() if node['kind'] in TERMINALS else (*PROBLEM_PORTS,'otherwise') if node['kind']=='case_router' else ('yes','no') if node['kind']=='condition' else ('next',)
        for port in ports:
            if port not in outgoing[id]: error('unconnected_port',id,port)
    if errors:return {'valid':False,'errors':errors}
    seen=set();active=set();order=[]
    def visit(id):
        if id in active:error('cycle',id);return
        if id in seen:return
        seen.add(id);active.add(id)
        for port,target in outgoing[id].items():
            if port!='reply':visit(target)
        active.remove(id);order.append(id)
    visit(starts[0])
    for id in nodes.keys()-seen:error('unreachable',id)
    if errors:return {'valid':False,'errors':errors}
    known={};ancestors={};any_provider={}
    for id in reversed(order):
        node=nodes[id];parents=incoming[id]
        before=set.intersection(*(known[p] for p in parents)) if parents else set()
        ancestors[id]=set.intersection(*(ancestors[p]|{p} for p in parents)) if parents else set()
        prior=set.union(*(any_provider[p] for p in parents)) if parents else set()
        if node['kind']=='jev' and 'jev' in prior:error('one_provider_node',id)
        if node['kind']=='contract' and 'contract' in prior:error('one_provider_node',id)
        needs=None
        if node['kind']=='jev' and node['config']['scope']!='all':needs='triage'
        if node['kind'] in ('contract','case_router'):needs='jev'
        if node['kind']=='preview' and node['config']['stage'] in ('action','handoff'):needs='context'
        if node['kind']=='preview' and node['config']['stage']=='query':needs='jev'
        if node['kind']=='context' and node['config']['mode']=='case':needs='jev'
        if node['kind']=='condition':
            pred=node['config']['predicate']
            needs='triage' if pred=='triage_is' else 'diagnostic' if pred=='diagnostic_failed' else 'jev' if pred in ('intent_is','family_is') else 'context'
        if node['kind']=='question' and node['config']['mode']=='missing':needs='context'
        if node['kind']=='notify':needs='diagnostic'
        if needs and needs not in before:error('requires_'+needs,id)
        known[id]=before|{node['kind']};any_provider[id]=prior|{node['kind']}
    for edge in feedback:
        if edge['target'] not in ancestors[edge['source']]:error('invalid_feedback',edge['source'],'reply')
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
    from . import workflow_execution as execution
    state=execution.create(record,messages,language,thread_id,incident_id)
    return execution.advance(state,mode='full',on_event=on_event)
