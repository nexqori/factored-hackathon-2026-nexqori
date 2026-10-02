"""Checkpointed execution. Only the server chooses the next node or feedback route."""
import hashlib
import copy
import json
import time
import uuid
from datetime import datetime, timezone

from backend.agent_routing import route_family, route_plan
from . import storage, app_diagnostics, flow_engine as flow, workflow_editor as editor
from .decision import INSTRUCTIONS
from .providers import save_run
from .workflow_previews import activation_plan, QUERY_REPLY

BOOT_ID = str(uuid.uuid4())
MAX_REPLIES = 10


def path_for(id):
    return storage.DATA_DIR/'workflow-executions'/f'{uuid.UUID(str(id))}.json'


def write(state):
    path = path_for(state['id'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def read(id):
    path = path_for(id)
    if not path.exists(): raise FileNotFoundError()
    state = json.loads(path.read_text(encoding='utf-8'))
    if state['phase'] == 'running' and state.get('worker') != BOOT_ID:
        state.update(phase='interrupted', next_node_id=None)
        write(state)
    return state


def create(record, messages, language, thread_id=None, incident_id=None):
    if not editor.validate_graph(record['graph'])['valid']: raise ValueError('invalid_graph')
    state = {'id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4()), 'record': copy.deepcopy(record),
             'messages': copy.deepcopy(messages), 'language': language, 'thread_id': thread_id or str(uuid.uuid4()),
             'incident_id': incident_id, 'created_at': datetime.now(timezone.utc).isoformat(),
             'phase': 'paused', 'version': 0, 'turn': 0, 'worker': BOOT_ID,
             'next_node_id': next(n['id'] for n in record['graph']['nodes'] if n['kind'] == 'start'),
             'awaiting_node_id': None, 'feedback_edge_id': None, 'last_edge_id': None,
             'trace': [], 'visited_edges': [], 'requests': [], 'latency_ms': 0,
             'node_inputs': {}, 'replays': {},
             'context': {'triage': {'status': 'skipped'}, 'jev': {'status': 'skipped'},
                         'llm': {'status': 'skipped'}, 'missing': [], 'observations': [],
                         'questions': [], 'intent': None, 'fields': [], 'incident': None,
                         'notice': None, 'contract': None, 'case_definition': None, 'activation_plan': [], 'state': 'information', 'reply': ''}}
    write(state)
    return state


def view(state):
    cfg, graph, record = state['context'], state['record']['graph'], state['record']
    return copy.deepcopy({'id': state['run_id'], 'thread_id': state['thread_id'], 'created_at': state['created_at'],
            'language': state['language'], 'workflow_id': record['id'], 'workflow_revision': record['revision'],
            'workflow': graph, 'graph_sha256': hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest(),
            'extraction_prompt_sha256': hashlib.sha256(flow.EXTRACT_INSTRUCTIONS.encode()).hexdigest(),
            'triage': cfg['triage'], 'jev': cfg['jev'], 'llm': cfg['llm'], 'contract': cfg['contract'],
            'state': cfg['state'], 'reply': cfg['reply'], 'questions': cfg['questions'],
            'missing_fields': cfg['missing'], 'observations': cfg['observations'],
            'trace': state['trace'], 'visited_edges': state['visited_edges'], 'latency_ms': round(state['latency_ms'], 1),
            'reused_latency_ms': round(sum(row['latency_ms'] for row in state['trace'] if row.get('reused')), 1),
            'tool_plan': route_plan(cfg['jev']), 'incident': cfg['incident'], 'notification': cfg['notice'],
            'activation_plan': cfg.get('activation_plan', []),
            'executed_operations': [], 'executed_tools': [], 'authorizes_execution': False, 'verified_facts': [],
            'messages': state['messages'],
            'replayable_nodes': list(state.get('node_inputs', {})),
            'replayed_from': state.get('replayed_from'),
            'execution': {key: state[key] for key in ('id', 'phase', 'version', 'next_node_id', 'awaiting_node_id', 'last_edge_id', 'turn')}})


def preflight(state, version, node_id, reply=None):
    if state['version'] != version: raise RuntimeError('stale_step')
    if state['phase'] not in ('paused', 'waiting_reply'): raise RuntimeError('execution_not_paused')
    if state['next_node_id'] != node_id: raise RuntimeError('wrong_next_node')
    current = editor.read_workflow(state['record']['id'])
    if editor.execution_rules(current['graph']) != editor.execution_rules(state['record']['graph']):
        raise RuntimeError('revision_conflict')
    if state['phase'] == 'waiting_reply':
        if not reply or not reply.strip(): raise ValueError('reply_required')
        if state['turn'] >= MAX_REPLIES or len(state['messages']) >= 30: raise ValueError('conversation_limit')
    elif reply is not None: raise ValueError('unexpected_reply')


def replay(state, version, node_id):
    """Fork a reached block from its saved inputs, retaining the original run.

    Downstream results never become inputs of the replay. Only the chosen block
    runs; its newly selected route becomes the next paused step.
    """
    if state['version'] != version: raise RuntimeError('stale_step')
    if state['phase'] not in ('paused','waiting_reply','completed'): raise RuntimeError('execution_not_paused')
    snapshot=state.get('node_inputs', {}).get(node_id)
    if not snapshot: raise ValueError('block_inputs_unavailable')
    current=editor.read_workflow(state['record']['id'])
    if editor.execution_rules(current['graph']) != editor.execution_rules(state['record']['graph']):
        raise RuntimeError('revision_conflict')
    key=f'{version}:{node_id}'
    existing=state.get('replays', {}).get(key)
    if existing: return read(existing), True
    child=copy.deepcopy(state)
    child.update(id=str(uuid.uuid4()),run_id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),
                 phase='paused',version=0,worker=BOOT_ID,next_node_id=node_id,awaiting_node_id=None,feedback_edge_id=None,
                 context=copy.deepcopy(snapshot['context']),messages=copy.deepcopy(snapshot['messages']),turn=snapshot['turn'],
                 latency_ms=0,last_edge_id=snapshot['last_edge_id'],replays={},
                 replayed_from={'execution_id':state['id'],'node_id':node_id,'step_index':snapshot['trace_length']})
    for keyname, length in [('trace','trace_length'),('visited_edges','edges_length'),('requests','requests_length')]:
        child[keyname]=child[keyname][:snapshot[length]]
    child['trace']=[{**row,'reused':True} for row in child['trace']]
    child['node_inputs']={id:value for id,value in child['node_inputs'].items() if value['trace_length']<snapshot['trace_length']}
    write(child)
    state.setdefault('replays', {})[key]=child['id']
    write(state)
    return child, False


def advance(state, mode='step', reply=None, on_event=None):
    def emit(event):
        if on_event: on_event(event)
    if state['phase'] == 'waiting_reply':
        if not reply or not reply.strip(): raise ValueError('reply_required')
        if state['turn'] >= MAX_REPLIES or len(state['messages']) >= 30: raise ValueError('conversation_limit')
        state['messages'].append({'role': 'user', 'content': reply.strip()})
        state['turn'] += 1
        state['run_id'] = str(uuid.uuid4())
        state['visited_edges'].append(state['feedback_edge_id'])
        emit({'event': 'edge_taken', 'edge_id': state['feedback_edge_id'], 'port': 'reply'})
        state['awaiting_node_id'] = None
        state['context']['reply'] = ''
        state['context']['questions'] = []
    state.update(phase='running', worker=BOOT_ID)
    write(state)  # A process crash cannot silently retry a provider or notification.
    try:
        for _ in range(1 if mode == 'step' else 40):
            _one(state, emit)
            state['version'] += 1
            write(state)
            if state['phase'] in ('completed', 'waiting_reply'): break
        if state['phase'] == 'running': state['phase'] = 'paused'
        write(state)
        result = view(state)
        if state['phase'] in ('completed', 'waiting_reply'):
            save_run({'kind': 'workflow', 'actor': 'local_operator', 'messages': state['messages'],
                      'request': state['requests'][-1] if state['requests'] else None,
                      'requests': state['requests'], 'result': result})
        return result
    except Exception:
        state.update(phase='interrupted', next_node_id=None)
        write(state)
        raise


def _one(state, emit):
    graph, ctx, language = state['record']['graph'], state['context'], state['language']
    current = state['next_node_id']
    node = next(n for n in graph['nodes'] if n['id'] == current)
    kind, cfg, messages = node['kind'], node['config'], state['messages']
    state.setdefault('node_inputs', {})[current] = {
        'context':copy.deepcopy(ctx),'messages':copy.deepcopy(messages),'turn':state['turn'],
        'trace_length':len(state['trace']),'edges_length':len(state['visited_edges']),'requests_length':len(state['requests']),
        'latency_ms':state['latency_ms'],'last_edge_id':state['last_edge_id']}
    write(state)
    tick = time.perf_counter()
    emit({'event': 'node_started', 'node_id': current, 'kind': kind})
    output, status, port = {}, 'ok', 'next'
    if kind == 'start': output = {'message_count': len(messages), 'language': language, 'messages': copy.deepcopy(messages)}
    elif kind == 'triage':
        ctx['triage'], request = editor.classify_triage(messages, language, cfg['instructions'][language])
        state['requests'].append(request)
        output, status = ctx['triage'], ctx['triage']['status']
    elif kind == 'jev':
        scope = cfg.get('scope', 'all')
        family = ctx['triage'].get('family')
        if scope != 'all' and family != scope:
            output, status = {'error': 'route_mismatch'}, 'route_mismatch'
            ctx['jev'] = {'status': 'error', 'error': 'route_mismatch'}
        else:
            args = (messages, language, INSTRUCTIONS+'\n'+cfg['instructions'][language])
            ctx['jev'], request = editor.classify_jev(*args, **({'criteria': editor.case_criteria(scope, language)} if scope != 'all' else {}))
            state['requests'].append(request)
            output, status = ctx['jev'], ctx['jev']['status']
            ctx['intent'] = ctx['jev'].get('intent')
    elif kind == 'case_router':
        port = ctx['intent'] if ctx['intent'] in editor.PROBLEM_PORTS else 'otherwise'
        output = {'intent': ctx['intent'], 'port': port}
    elif kind == 'contract':
        if ctx['intent'] not in editor.PROBLEM_PORTS or (cfg.get('intent') and cfg['intent'] != ctx['intent']):
            output, status = {'error': 'problem_contract_required'}, 'route_mismatch'
        else:
            ctx['case_definition'] = flow.definition(ctx['intent'], language)
            ctx['contract'] = ctx['case_definition']['contract']
            planned = activation_plan('evidence', ctx['jev'])
            ctx.setdefault('activation_plan', []).extend({**item, 'node_id': current, 'stage': 'evidence'} for item in planned)
            output = {'intent': ctx['intent'], 'contract': ctx['contract'], 'required_fields': flow.REQUIREMENTS[ctx['intent']],
                      'would_activate': planned, 'executed': False, 'verified_facts': []}
    elif kind == 'preview':
        stage=cfg['stage']
        planned=activation_plan(stage, ctx['jev'])
        ctx.setdefault('activation_plan', []).extend({**item, 'node_id': current, 'stage': stage} for item in planned)
        if stage=='action': ctx.update(state='review_in_bank', reply=flow.COPY['review_in_bank'][flow.LANGS.index(language)])
        elif stage=='handoff': ctx.update(state='human_review', reply=flow.COPY['human_review'][flow.LANGS.index(language)])
        elif stage=='query': ctx.update(state='information', reply=QUERY_REPLY[language])
        output = {'stage':stage, 'would_activate':planned, 'executed':False, 'authorizes_execution':False}
    elif kind == 'diagnostic':
        try:
            if not state['incident_id']: raise FileNotFoundError()
            ctx['incident'] = app_diagnostics.read(state['incident_id'])
            output = ctx['incident']
        except FileNotFoundError: output, status = {'error': 'missing_incident'}, 'missing_incident'
    elif kind == 'notify':
        ctx['notice'] = app_diagnostics.notify(ctx['incident']['id'], state['record']['id'], current)
        output = ctx['notice']
    elif kind == 'context':
        ctx['fields'] = flow.REQUIREMENTS[ctx['intent']] if cfg['mode'] == 'case' else cfg['fields']
        notes = cfg['notes'][language]
        if ctx['contract']: notes = '\n'.join(ctx['contract']['steps'])+'\n'+notes
        instructions=cfg['instructions'][language]
        if ctx['contract']:
            instructions+='\n'+ctx['contract'].get('custom_instructions','')+'\n'+ctx['case_definition']['instructions']
        ctx['llm'] = editor.extract(messages, language, ctx['fields'], instructions, notes, ctx['intent'], ctx['incident'])
        output, status = ctx['llm'], ctx['llm']['status']
        if status == 'ok':
            ctx['observations'] = [{**o, 'status': 'declared', 'source': 'customer_message'} for o in ctx['llm']['observations']]
            ctx['missing'] = [f for f in ctx['fields'] if f not in {o['field'] for o in ctx['observations']}]
            output = {**ctx['llm'], 'missing_fields': ctx['missing'], 'verified_facts': []}
    elif kind == 'condition':
        checks = {'triage_is': ctx['triage'].get('family') == cfg['value'],
                  'intent_is': ctx['intent'] == cfg['value'],
                  'family_is': route_family(ctx['intent']) == cfg['value'] if ctx['intent'] else False,
                  'has_missing': bool(ctx['missing']), 'field_missing': cfg['value'] in ctx['missing'],
                  'needs_human': ctx['llm'].get('assessment') in ('conflicting', 'human_review') or bool(ctx['missing'] and (state['turn'] >= MAX_REPLIES or len(messages) >= 29)),
                  'diagnostic_failed': bool(ctx['incident'] and ctx['incident']['state'] == 'failed')}
        matched = checks[cfg['predicate']]
        port = 'yes' if matched else 'no'
        output = {'predicate': cfg['predicate'], 'value': cfg['value'], 'matched': matched, 'port': port}
    elif kind == 'question':
        if cfg['mode'] == 'missing':
            questions=(ctx.get('case_definition') or {}).get('questions',{})
            ctx['questions'] = [{'field': f, 'text': questions.get(f,flow.QUESTIONS[f][flow.LANGS.index(language)])} for f in ctx['missing'][:2]]
            ctx['state'] = 'ask_customer' if ctx['questions'] else 'review_in_bank'
            ctx['reply'] = ' '.join([flow.COPY[ctx['state']][flow.LANGS.index(language)]]+[q['text'] for q in ctx['questions']])
        else:
            ctx.update(reply=cfg['text'][language], questions=[{'field': None, 'text': cfg['text'][language]}], state='ask_customer')
        if ctx['questions'] and (state['turn'] >= MAX_REPLIES or len(messages) >= 29):
            ctx.update(state='human_review', reply=flow.COPY['human_review'][flow.LANGS.index(language)], questions=[])
        output = {key: ctx[key] for key in ('state', 'reply', 'questions')}
    elif kind == 'response':
        if cfg['outcome'] != 'current':
            ctx['state'] = cfg['outcome']
            ctx['reply'] = cfg['text'][language] or flow.COPY['review_in_bank'][flow.LANGS.index(language)]
        elif not ctx['reply']:
            ctx.update(state='information', reply=QUERY_REPLY[language])
        output = {'state': ctx['state'], 'reply': ctx['reply'], 'authorizes_execution': False}
    elif kind == 'escalate':
        ctx['state'] = 'human_review'
        ctx['reply'] = cfg['text'][language] or flow.COPY['human_review'][flow.LANGS.index(language)]
        output = {'state': ctx['state'], 'reply': ctx['reply'], 'handoff_sent': False}
    latency = round((time.perf_counter()-tick)*1000, 1)
    row = {'node_id': current, 'kind': kind, 'label': node['label'], 'status': status, 'output': output,
           'latency_ms': latency, 'step_index': len(state['trace']), 'turn': state['turn']}
    state['trace'].append(row);state['latency_ms'] += latency
    emit({'event': 'node_finished', 'trace': row})
    if status != 'ok':
        ctx['state'] = 'missing_incident' if status == 'missing_incident' else 'provider_unavailable'
        ctx['reply'] = editor.text('Primero reproduce el error de acceso y vincula su incidencia.', 'First reproduce the access error and link its incident.', 'Primeiro reproduza o erro de acesso e vincule sua incidência.')[language] if status == 'missing_incident' else flow.COPY['provider_unavailable'][flow.LANGS.index(language)]
        state.update(phase='completed', next_node_id=None)
        return
    if kind in editor.TERMINALS:
        state['messages'].append({'role': 'assistant', 'content': ctx['reply']})
        feedback = next((e for e in graph['edges'] if e['source'] == current and e['port'] == 'reply'), None)
        if kind == 'question' and feedback and ctx['questions'] and state['turn'] < MAX_REPLIES and len(state['messages']) < 30:
            state.update(phase='waiting_reply', next_node_id=feedback['target'], awaiting_node_id=current, feedback_edge_id=feedback['id'])
        else: state.update(phase='completed', next_node_id=None)
        return
    edge = next(e for e in graph['edges'] if e['source'] == current and e['port'] == port)
    state['visited_edges'].append(edge['id'])
    state.update(next_node_id=edge['target'], last_edge_id=edge['id'])
    emit({'event': 'edge_taken', 'edge_id': edge['id'], 'port': port})
