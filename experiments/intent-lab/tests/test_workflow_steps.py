"""One master graph, real provider-envelope validation and checkpointed customer feedback."""
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from intent_lab import api, workflow_editor as editor, workflow_execution as execution, flow_engine as flow
from intent_lab.dialogue import problem_intents, contract_for
from test_providers import private_config, install_transport, response
from test_luna_dialogue import enable, envelope


def models(monkeypatch, family='problem', intent='unrecognized-charge', assessments=None):
    calls=[]
    extraction=iter(assessments or [{'assessment':'continue','observations':[]}])
    def handler(request):
        body=json.loads(request.content)
        if request.url.host=='api.typesafe.ai':
            criteria=body['questions']['intent']['criteria']
            is_triage='problem' in criteria
            choice=family if is_triage else (intent() if callable(intent) else intent)
            assert choice in criteria
            if not is_triage:
                assert (set(criteria)&problem_intents()==problem_intents()) if family=='problem' else not(set(criteria)&problem_intents())
            value=response();value['answers']['intent'].update(choice=choice,probabilities={k:int(k==choice) for k in criteria})
            calls.append(('triage' if is_triage else 'case',body))
            return httpx.Response(200,json=value)
        assert body['model']=='gpt-6-luna' and body['reasoning']=={'effort':'high'} and body['store'] is False
        calls.append(('context',json.loads(body['input'][0]['content'])))
        return httpx.Response(200,json=envelope(next(extraction)))
    install_transport(monkeypatch,handler)
    return calls


def master(client):
    r=client.post('/lab-api/editor/master-workflow',json={})
    assert r.status_code==200
    return r.json()


def start(client,record,mode='full',content='No reconozco un cargo',**extra):
    r=client.post('/lab-api/editor/workflows/'+record['id']+'/run-stream',json={
        'revision':record['revision'],'mode':mode,'messages':[{'role':'user','content':content}],**extra})
    assert r.status_code==200,r.text
    events=[json.loads(line) for line in r.text.splitlines()]
    assert events[0]['event']=='execution_created'
    return events[-1]['result']


def advance(client,result,mode='step',**extra):
    state=result['execution']
    return client.post('/lab-api/editor/executions/'+state['id']+'/advance',json={
        'version':state['version'],'node_id':state['next_node_id'],'mode':mode,**extra})


def result_of(response):
    assert response.status_code==200,response.text
    return json.loads(response.text.splitlines()[-1])['result']


def test_master_is_one_saved_graph_and_keeps_edits(private_config):
    client=TestClient(api.app);record=master(client)
    assert record['validation']['valid'] and len(record['graph']['nodes'])==26
    graph=copy.deepcopy(record['graph']);graph['name']['es']='Atención configurada'
    updated=client.put('/lab-api/editor/workflows/'+record['id'],json={'revision':1,'graph':graph}).json()
    assert master(client)==updated
    assert len(editor.list_workflows())==1
    for row in client.get('/lab-api/editor/cases').json()['cases']:
        assert client.get('/lab-api/editor/case-template/'+row['intent']).json()==editor.template()
    assert len(editor.list_workflows())==1


@pytest.mark.parametrize('language',['es','en','pt'])
@pytest.mark.parametrize('intent',sorted(problem_intents()))
def test_same_graph_selects_each_problem_contract_from_actual_jev(private_config,monkeypatch,language,intent):
    enable(private_config);calls=models(monkeypatch,intent=intent)
    client=TestClient(api.app);record=master(client)
    result=start(client,record,language=language)
    assert result['triage']['family']=='problem' and result['jev']['intent']==intent
    assert [c[0] for c in calls]==['triage','case','context']
    assert result['contract']==contract_for(intent,language)
    assert result['missing_fields']==flow.REQUIREMENTS[intent]
    assert result['execution']['phase']=='waiting_reply' and result['execution']['next_node_id']=='context'
    assert all(step in calls[-1][1]['unverified_reference_notes'] for step in result['contract']['steps'])
    assert calls[-1][1]['required_fields']==flow.REQUIREMENTS[intent]
    assert not result['authorizes_execution'] and result['executed_operations']==result['verified_facts']==[]
    assert result['workflow']==record['graph']
    assert result['notification'] is None and result['incident'] is None
    assert len([r for r in result['trace'] if r['kind']=='contract'])==1
    assert all(item['executed'] is False for item in result['activation_plan'])
    assert bool([item for item in result['activation_plan'] if item['id']=='notify-confirmed-incident'])==(intent=='app-support')
    assert client.get('/lab-api/editor/notifications').json()['notifications']==[]


@pytest.mark.parametrize('language',['es','en','pt'])
@pytest.mark.parametrize('intent',['account-balance','request-status','phone-bill'])
def test_queries_and_requests_skip_problem_contracts_and_luna(private_config,monkeypatch,language,intent):
    enable(private_config);calls=models(monkeypatch,family='query',intent=intent)
    client=TestClient(api.app);result=start(client,master(client),language=language)
    assert [c[0] for c in calls]==['triage','case']
    assert result['trace'][-1]['node_id']=='result'
    assert any(row['node_id']=='query_plan' for row in result['trace'])
    assert result['contract'] is None and result['llm']['status']=='skipped'
    assert result['tool_plan']['tools'] and result['executed_tools']==[]
    assert result['execution']['phase']=='completed'


def test_unclear_initial_intent_asks_before_loading_any_contract(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch,family='clarification')
    client=TestClient(api.app);result=start(client,master(client))
    assert len(calls)==1 and result['trace'][-1]['node_id']=='clarify'
    assert result['contract'] is None and result['state']=='ask_customer'


def test_step_reload_and_full_resume_never_repeat_completed_providers(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch)
    client=TestClient(api.app);record=master(client);value=start(client,record,mode='step')
    assert len(value['trace'])==1 and value['execution']['phase']=='paused' and not calls
    url='/lab-api/editor/executions/'+value['execution']['id']
    assert client.get(url).json()==value and not calls
    # A client cannot force the other branch or jump to a contract/operation.
    assert advance(client,value,node_id='contract').status_code==409
    first=advance(client,value);done=result_of(first)
    assert [c[0] for c in calls]==['triage']
    assert advance(client,value).status_code==409 and len(calls)==1
    with api.provider_lock: assert advance(client,done).status_code==409
    done=result_of(advance(client,done,mode='full'))
    assert [c[0] for c in calls]==['triage','case','context']
    assert done['execution']['phase']=='waiting_reply'
    assert client.get(url).json()==done and len(calls)==3
    assert done['trace'][0]['output']['messages']==[{'role':'user','content':'No reconozco un cargo'}]


def test_customer_feedback_loops_until_complete_without_reclassifying(private_config,monkeypatch):
    enable(private_config)
    row=lambda field,index,quote:{'field':field,'message_index':index,'quote':quote}
    observations=[row('movement',0,'Comercio Alfa')]
    calls=models(monkeypatch,assessments=[{'assessment':'continue','observations':observations},
        {'assessment':'continue','observations':observations+[row('date',2,'1 de octubre de 2026')]},
        {'assessment':'continue','observations':observations+[row('date',2,'1 de octubre de 2026'),row('amount',4,'100 MXN')]}])
    client=TestClient(api.app);value=start(client,master(client),content='No reconozco el cargo de Comercio Alfa')
    assert value['missing_fields']==['date','amount'] and len(value['messages'])==2
    assert advance(client,value,mode='full').status_code==422 and len(calls)==3
    feedback=next(e['id'] for e in value['workflow']['edges'] if e['port']=='reply')
    assert feedback not in value['visited_edges']
    first_run=value['id']
    value=result_of(advance(client,value,mode='full',reply='Fue el 1 de octubre de 2026'))
    assert value['missing_fields']==['amount'] and value['execution']['phase']=='waiting_reply'
    assert value['visited_edges'].count(feedback)==1
    assert client.get('/lab-api/runs/'+first_run).json()['result']['missing_fields']==['date','amount']
    value=result_of(advance(client,value,mode='full',reply='El importe es 100 MXN'))
    assert not value['missing_fields'] and value['execution']['phase']=='completed'
    assert value['state']=='review_in_bank' and value['execution']['turn']==2
    assert value['visited_edges'].count(feedback)==2
    assert [c[0] for c in calls]==['triage','case','context','context','context']
    assert [r['node_id'] for r in value['trace']].count('context')==3
    assert len({r['step_index'] for r in value['trace']})==len(value['trace'])
    assert advance(client,value).status_code==422  # completed has no next node
    assert not value['verified_facts'] and not value['authorizes_execution']


def test_graph_revision_change_blocks_resume_and_worker_restart_does_not_retry(private_config,monkeypatch):
    client=TestClient(api.app);record=master(client);value=start(client,record,mode='step')
    next(n for n in record['graph']['nodes'] if n['kind']=='triage')['config']['instructions']['es']='Cambiar reglas de clasificación'
    client.put('/lab-api/editor/workflows/'+record['id'],json={'revision':1,'graph':record['graph']})
    assert advance(client,value).json()['detail']=='revision_conflict'
    state=execution.read(value['execution']['id']);state.update(phase='running',worker='previous-process');execution.write(state)
    restored=client.get('/lab-api/editor/executions/'+state['id']).json()
    assert restored['execution']['phase']=='interrupted' and restored['execution']['next_node_id'] is None


def test_saved_layout_and_labels_preserve_checkpoint_inputs_and_progress(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch)
    client=TestClient(api.app);record=master(client);value=start(client,record,mode='step')
    original=copy.deepcopy(value)
    record['graph']['name']['es']='Nombre visual'
    for node in record['graph']['nodes']:
        node['position']['x']+=3
        node['label']['es']+=' · vista'
    updated=client.put('/lab-api/editor/workflows/'+record['id'],json={'revision':1,'graph':record['graph']}).json()
    assert updated['revision']==2
    assert client.get('/lab-api/editor/executions/'+value['execution']['id']).json()==original
    result=result_of(advance(client,value))
    assert result['execution']['id']==value['execution']['id'] and result['execution']['version']==value['execution']['version']+1
    assert result['workflow']==original['workflow'] and result['messages']==value['messages']
    assert [r['node_id'] for r in result['trace']]==['start','triage'] and len(calls)==1


@pytest.mark.parametrize('target',['jev','missing','query_case'])
def test_feedback_cannot_cycle_models_or_jump_to_unrelated_route(private_config,target):
    graph=editor.template();next(e for e in graph['edges'] if e['port']=='reply')['target']=target
    assert not editor.validate_graph(graph)['valid']


def test_branch_context_dominates_feedback_and_automatic_cycles_rejected(private_config):
    graph=editor.template();next(e for e in graph['edges'] if e['source']=='missing' and e['port']=='yes')['target']='context'
    assert 'cycle' in {e['code'] for e in editor.validate_graph(graph)['errors']}
    graph=editor.template();next(e for e in graph['edges'] if e['source']=='query_case')['target']='ask'
    errors={e['code'] for e in editor.validate_graph(graph)['errors']}
    assert 'requires_context' in errors or 'unreachable' in errors


def test_wrong_provider_taxonomy_stops_before_case_and_contract(private_config,monkeypatch):
    install_transport(monkeypatch,lambda req:httpx.Response(200,json=response()))
    client=TestClient(api.app);value=start(client,master(client))
    assert value['triage']['error']=='invalid_response'
    assert len(value['trace'])==2 and value['contract'] is None


def test_full_and_steps_have_identical_local_effect_and_branch(private_config):
    client=TestClient(api.app)
    record=client.post('/lab-api/editor/workflows',json={'graph':editor.template('app')}).json()
    incident=client.post('/lab-api/editor/app-check',json={}).json()
    stepped=start(client,record,mode='step',incident_id=incident['id'])
    while stepped['execution']['phase']=='paused':stepped=result_of(advance(client,stepped))
    full=start(client,record,incident_id=incident['id'])
    assert [r['node_id'] for r in stepped['trace']]==[r['node_id'] for r in full['trace']]
    assert full['notification']['id']==stepped['notification']['id'] and full['notification']['reused']
    assert len(client.get('/lab-api/editor/notifications').json()['notifications'])==1


def test_feedback_is_bounded_and_can_escalate_without_fabricating_data(private_config,monkeypatch):
    enable(private_config)
    calls=models(monkeypatch,assessments=[{'assessment':'continue','observations':[]}]*(execution.MAX_REPLIES+1))
    client=TestClient(api.app);value=start(client,master(client))
    for _ in range(execution.MAX_REPLIES):
        value=result_of(advance(client,value,mode='full',reply='No tengo ese dato'))
    assert value['execution']['phase']=='completed' and value['state']=='human_review'
    assert value['missing_fields']==flow.REQUIREMENTS['unrecognized-charge']
    assert len(calls)==execution.MAX_REPLIES+3
    assert not value['questions'] and not value['executed_operations']


def test_reply_can_request_human_and_stops_asking(private_config,monkeypatch):
    enable(private_config)
    calls=models(monkeypatch,assessments=[{'assessment':'continue','observations':[]},
        {'assessment':'human_review','observations':[]}])
    client=TestClient(api.app);value=start(client,master(client))
    value=result_of(advance(client,value,mode='full',reply='Quiero hablar con una persona'))
    assert value['execution']['phase']=='completed' and value['state']=='human_review'
    handoff=next(row for row in value['trace'] if row['node_id']=='handoff')
    assert handoff['output']['executed'] is False and len(calls)==4
    assert not any(row['node_id']=='action' for row in value['trace'])


@pytest.mark.parametrize('family',['query','problem'])
@pytest.mark.parametrize('intent',['needs-clarification','multiple-intents','out-of-scope'])
def test_case_fallbacks_do_not_propose_action_or_closure(private_config,monkeypatch,family,intent):
    enable(private_config);calls=models(monkeypatch,family=family,intent=intent)
    client=TestClient(api.app);value=start(client,master(client))
    assert value['trace'][-1]['node_id']=='clarify' and len(calls)==2
    assert not value['activation_plan'] and not value['contract']


def test_refund_proposal_keeps_bank_evidence_and_administrator_gates(private_config,monkeypatch):
    enable(private_config)
    observations=[{'field':f,'message_index':0,'quote':'cargo'} for f in flow.REQUIREMENTS['unrecognized-charge']]
    models(monkeypatch,assessments=[{'assessment':'continue','observations':observations}])
    client=TestClient(api.app);value=start(client,master(client))
    assert value['state']=='review_in_bank' and value['execution']['phase']=='completed'
    refund=next(a for a in value['activation_plan'] if a['id']=='prepare-refund-review')
    assert set(('administrator_approval','ownership','confirmation','verified_bank_evidence'))<=set(refund['requirements'])
    assert all(a['status']=='would_activate' and not a['executed'] for a in value['activation_plan'])
    assert not value['executed_operations'] and not value['executed_tools'] and not value['verified_facts']
    assert [r['node_id'] for r in value['trace']][-4:]==['action','delivery','closure','result']


def test_rewiring_to_wrong_contract_fails_closed(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch)
    client=TestClient(api.app);record=master(client);graph=record['graph']
    next(e for e in graph['edges'] if e['port']=='unrecognized-charge')['target']='contract_1'
    # Retain reachability while deliberately reversing the two branch targets.
    next(e for e in graph['edges'] if e['port']=='incorrect-charge')['target']='contract_0'
    updated=client.put('/lab-api/editor/workflows/'+record['id'],json={'revision':record['revision'],'graph':graph}).json()
    value=start(client,updated)
    assert value['state']=='provider_unavailable' and value['trace'][-1]['status']=='route_mismatch'
    assert len(calls)==2 and not value['activation_plan'] and value['contract'] is None


@pytest.mark.parametrize('edited',[False,True])
def test_upgrade_preserves_custom_graph_and_previous_snapshot(private_config,edited):
    graph=editor.legacy_master_template()
    if edited:graph['nodes'][0]['label']['es']='Entrada personalizada'
    record=editor.save_workflow(graph)
    (private_config/'master-workflow.json').write_text(json.dumps({'id':record['id']}),encoding='utf-8')
    result=editor.master_workflow()
    assert result['id']==record['id'] and editor.master_workflow()==result
    if edited:assert result==record
    else:
        assert result['revision']==2 and result['graph']==editor.template()
        original=json.loads((private_config/'workflow-revisions'/f"{record['id']}-v1.json").read_text(encoding='utf-8'))
        assert original==record


def test_execution_created_is_an_immutable_empty_checkpoint(private_config):
    client=TestClient(api.app);record=master(client)
    response=client.post('/lab-api/editor/workflows/'+record['id']+'/run-stream',json={
        'revision':1,'mode':'step','messages':[{'role':'user','content':'Pregunta'}]})
    events=[json.loads(line) for line in response.text.splitlines()]
    assert events[0]['result']['trace']==[] and events[0]['result']['execution']['version']==0
    assert len(events[-1]['result']['trace'])==1 and events[-1]['result']['execution']['version']==1


def test_selected_contract_keeps_its_custom_questions_and_instructions(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch)
    def config(word):
        (private_config/'workflow-instructions.json').write_text(json.dumps({'unrecognized-charge':{'es':'Contrato '+word}}),encoding='utf-8')
        (private_config/'flow-config.json').write_text(json.dumps({'version':'1','revision':1,'overrides':{
            'unrecognized-charge':{'es':{'instructions':'Contexto '+word,'questions':{'movement':'Movimiento '+word+'?'}}}}}),encoding='utf-8')
    config('original')
    client=TestClient(api.app);value=start(client,master(client),mode='step')
    while value['execution']['next_node_id']!='context':value=result_of(advance(client,value))
    assert [c[0] for c in calls]==['triage','case']
    config('cambiado')
    value=result_of(advance(client,value,mode='full'))
    assert value['questions'][0]['text']=='Movimiento original?'
    assert 'Contrato original' in calls[-1][1]['custom_instructions']
    assert 'Contexto original' in calls[-1][1]['custom_instructions']
    assert 'cambiado' not in calls[-1][1]['custom_instructions']


def replay(client,value,node_id):
    return client.post('/lab-api/editor/executions/'+value['execution']['id']+'/replay',json={'version':value['execution']['version'],'node_id':node_id})


def test_replay_reuses_upstream_inputs_and_recalculates_branch_without_stale_results(private_config,monkeypatch):
    enable(private_config);choice={'intent':'unrecognized-charge'}
    calls=models(monkeypatch,intent=lambda:choice['intent'],assessments=[{'assessment':'continue','observations':[]}] * 2)
    client=TestClient(api.app);parent=start(client,master(client))
    assert parent['execution']['phase']=='waiting_reply' and len(calls)==3
    choice['intent']='app-support';calls.clear()
    child=result_of(replay(client,parent,'jev'))
    assert child['execution']['id']!=parent['execution']['id']
    assert child['replayed_from']['execution_id']==parent['execution']['id']
    assert child['execution']['phase']=='paused' and child['execution']['next_node_id']=='case_route'
    assert child['jev']['intent']=='app-support' and child['contract'] is None
    assert child['llm']['status']=='skipped' and not child['activation_plan'] and not child['questions']
    assert child['trace'][:-1]==[{**row,'reused':True} for row in parent['trace'][:3]] and child['messages']==[{'role':'user','content':'No reconozco un cargo'}]
    assert child['latency_ms']==child['trace'][-1]['latency_ms']
    assert [c[0] for c in calls]==['case']
    assert client.get('/lab-api/editor/executions/'+parent['execution']['id']).json()==parent
    duplicate=replay(client,parent,'jev')
    assert duplicate.status_code==409 and duplicate.json()['execution_id']==child['execution']['id'] and len(calls)==1
    assert replay(client,child,'contract_0').status_code==422  # no cached input on the new path
    child=result_of(advance(client,child,mode='full'))
    assert child['contract']==contract_for('app-support','es') and child['execution']['phase']=='waiting_reply'
    assert [c[0] for c in calls]==['case','context']
    assert not child['executed_operations'] and child['notification'] is None


def test_replay_uses_last_iteration_inputs_after_customer_reply(private_config,monkeypatch):
    enable(private_config)
    calls=models(monkeypatch,assessments=[{'assessment':'continue','observations':[]}] * 3)
    client=TestClient(api.app);parent=start(client,master(client))
    parent=result_of(advance(client,parent,mode='full',reply='Todavía no encuentro el dato'))
    snapshot=list(parent['messages'][:-1])
    child=result_of(replay(client,parent,'context'))
    assert child['messages']==snapshot and child['execution']['turn']==1
    assert calls[-1][1]['messages']==snapshot
    assert [c[0] for c in calls]==['triage','case','context','context','context']
    assert child['execution']['next_node_id']=='human' and child['execution']['phase']=='paused'


def test_replay_rejects_unreached_nodes_stale_versions_and_changed_rules(private_config,monkeypatch):
    enable(private_config);calls=models(monkeypatch)
    client=TestClient(api.app);record=master(client);parent=start(client,record,mode='step')
    assert replay(client,parent,'context').status_code==422 and not calls
    stale=copy.deepcopy(parent);stale['execution']['version']-=1
    assert replay(client,stale,'start').status_code==409
    with api.provider_lock:assert replay(client,parent,'start').status_code==409
    next(n for n in record['graph']['nodes'] if n['kind']=='triage')['config']['instructions']['es']='Reglas nuevas'
    client.put('/lab-api/editor/workflows/'+record['id'],json={'revision':record['revision'],'graph':record['graph']})
    assert replay(client,parent,'start').json()['detail']=='revision_conflict' and not calls
