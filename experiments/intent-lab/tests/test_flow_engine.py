import json

import httpx
import pytest
from fastapi.testclient import TestClient

from intent_lab import api, flow_engine as flow
from test_providers import private_config, install_transport, response
from test_luna_dialogue import enable, envelope


def provider_pair(monkeypatch, intent='incorrect-charge', observations=None, assessment='continue'):
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.host == 'api.typesafe.ai':
            result = response()
            result['answers']['intent']['choice'] = intent
            result['answers']['intent']['probabilities'] = {key: int(key == intent) for key in result['answers']['intent']['probabilities']}
            return httpx.Response(200, json=result)
        body = json.loads(request.content)
        assert body['model'] == 'gpt-6-luna' and body['reasoning'] == {'effort': 'high'}
        assert 'tools' not in body and body['store'] is False
        context = json.loads(body['input'][0]['content'])
        assert context['flow']['intent'] == intent
        assert context['flow']['tool_plan']['executed_tools'] == []
        return httpx.Response(200, json=envelope({'assessment': assessment, 'observations': observations or []}))
    install_transport(monkeypatch, handler)
    return calls


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_all_routes_and_questions_exist_without_provider_calls(private_config, monkeypatch, language):
    monkeypatch.setattr(flow, 'classify_jev', lambda *args: pytest.fail('Map must not call a provider'))
    client = TestClient(api.app)
    result = client.get('/lab-api/flow-map', params={'language': language}).json()
    assert len(result['definitions']) == 25
    assert {d['intent'] for d in result['definitions']} == set(flow.REQUIREMENTS)
    for item in result['definitions']:
        assert set(item['fields']) == set(item['questions'])
        assert all(item['questions'].values())
        assert bool(item['contract']) == (item['family'] == 'problem')
        assert item['tool_plan']['authorizes_execution'] is False


def test_quotes_drive_next_question_and_saved_provenance(private_config, monkeypatch):
    enable(private_config)
    messages = [{'role': 'user', 'content': 'El cargo de Tienda Uno fue el 30 de septiembre.'}]
    rows = [{'field': 'movement', 'message_index': 0, 'quote': 'Tienda Uno'},
            {'field': 'date', 'message_index': 0, 'quote': '30 de septiembre'}]
    calls = provider_pair(monkeypatch, observations=rows)
    result = TestClient(api.app).post('/lab-api/flow-run', json={'messages': messages}).json()
    assert len(calls) == 2 and result['state'] == 'ask_customer'
    assert result['missing_fields'] == ['amount', 'difference']
    assert [q['field'] for q in result['questions']] == ['amount', 'difference']
    assert all(o['status'] == 'declared' for o in result['observations'])
    assert result['bank_evidence']['verified_facts'] == []
    assert result['authorizes_execution'] is False and not result['executed_tools']
    assert [s['source'] for s in result['stages']] == ['jev', 'server_rule', 'llm', 'server_rule']
    saved = json.loads((private_config / 'runs' / (result['id']+'.json')).read_text(encoding='utf-8'))
    assert saved['kind'] == 'flow' and saved['messages'] == messages
    assert saved['result']['definition_sha256'] == result['definition_sha256']
    assert 'private-placeholder' not in json.dumps(saved)
    client=TestClient(api.app)
    assert client.get('/lab-api/flow-history?language=es').json()['runs'][0]['id']==result['id']
    assert not client.get('/lab-api/flow-history?language=pt').json()['runs']
    assert client.get('/lab-api/runs/'+result['id']).json()['result']==result
    assert len(calls)==2, 'Opening a saved run must not call providers'


@pytest.mark.parametrize('assessment,state', [('continue','review_in_bank'),('conflicting','human_review'),('human_review','human_review')])
def test_complete_context_never_authorizes_operation(private_config, monkeypatch, assessment, state):
    enable(private_config)
    provider_pair(monkeypatch, intent='app-support', assessment=assessment, observations=[
        {'field': 'symptom', 'message_index': 0, 'quote': 'Error X'},
        {'field': 'attempts', 'message_index': 0, 'quote': 'reinicié'}])
    result = flow.evaluate([{'role':'user','content':'Error X, reinicié'}], 'es', 'Classify')
    assert result['state'] == state and not result['questions']
    assert result['executed_operations'] == result['executed_tools'] == []
    assert not result['authorizes_execution']


@pytest.mark.parametrize('intent,state,calls_expected', [('needs-clarification','ask_customer',1),('multiple-intents','ask_customer',1),('out-of-scope','stop',1),('account-balance','review_in_bank',2),('phone-bill','ask_customer',2)])
def test_query_service_and_fallback_routes(private_config, monkeypatch, intent, state, calls_expected):
    enable(private_config)
    calls = provider_pair(monkeypatch, intent=intent)
    result = flow.evaluate([{'role':'user','content':'Consulta de verificación'}], 'es', 'Classify')
    assert result['state'] == state and len(calls) == calls_expected
    assert result['definition']['contract'] is None
    if intent in ('multiple-intents', 'needs-clarification', 'out-of-scope'):
        assert not result['tool_plan']['tools']


@pytest.mark.parametrize('row', [
    {'field':'movement','message_index':1,'quote':'inventado'},
    {'field':'movement','message_index':0,'quote':'inventado'},
    {'field':'movement','message_index':True,'quote':'Comercio'},
    {'field':'confirmed','message_index':0,'quote':'Comercio'},
    {'field':'movement','message_index':99,'quote':'Comercio'},
])
def test_reject_ungrounded_assistant_or_unexpected_facts(private_config, monkeypatch, row):
    enable(private_config); provider_pair(monkeypatch, observations=[row])
    result = flow.evaluate([{'role':'user','content':'Comercio'},{'role':'assistant','content':'inventado'},{'role':'user','content':'Ayuda'}], 'es', 'Classify')
    assert result['state'] == 'provider_unavailable' and result['llm']['error'] == 'invalid_response'
    assert not result['questions'] and not result['observations']


def test_provider_failures_stop_before_proposing(private_config, monkeypatch):
    enable(private_config); calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(401,json={'private':'secret'})
    install_transport(monkeypatch, handler)
    result=flow.evaluate([{'role':'user','content':'hola'}], 'es', 'Classify')
    assert len(calls)==1 and result['definition'] is None and result['state']=='provider_unavailable'
    assert result['llm']['status']=='skipped' and not result['tool_plan']['tools']


def test_question_edits_versioning_language_and_immutable_rules(private_config, monkeypatch):
    client=TestClient(api.app)
    initial=client.get('/lab-api/flow-map').json()
    item=next(d for d in initial['definitions'] if d['intent']=='app-support')
    body={'language':'es','revision':0,'questions':{**item['questions'],'symptom':'¿En qué pantalla aparece el error?'},'instructions':'Conserva los pasos ya intentados.'}
    saved=client.put('/lab-api/flow-map/app-support',json=body)
    assert saved.status_code==200 and saved.json()['revision']==1
    assert client.put('/lab-api/flow-map/app-support',json=body).status_code==409
    assert flow.definition('app-support','en')['instructions']==''
    for patch in ({'questions':{}},{'questions':{'password':'Dame tu contraseña'}},{'questions':{**body['questions'],'symptom':''}},{'executed_operations':['refund']}):
        assert client.put('/lab-api/flow-map/app-support',json={**body,'revision':1,**patch}).status_code==422
    enable(private_config);provider_pair(monkeypatch,intent='app-support')
    result=flow.evaluate([{'role':'user','content':'Tengo un problema'}],'es','Classify')
    assert result['questions'][0]['text']==body['questions']['symptom']
    assert result['config_revision']==1 and result['definition']['instructions']==body['instructions']


def test_each_turn_reclassifies_and_drops_previous_tools(private_config, monkeypatch):
    enable(private_config)
    with monkeypatch.context() as patch:
        provider_pair(patch,intent='incorrect-charge')
        first=flow.evaluate([{'role':'user','content':'Cobro duplicado'}],'es','Classify')
    with monkeypatch.context() as patch:
        provider_pair(patch,intent='account-balance')
        second=flow.evaluate([{'role':'user','content':'Cobro duplicado'},{'role':'assistant','content':first['reply']},{'role':'user','content':'Ahora solo quiero ver mi saldo'}],'es','Classify',first['thread_id'])
    assert first['route_family']=='problem' and second['route_family']=='query'
    assert second['thread_id']==first['thread_id'] and first['id']!=second['id']
    assert second['definition']['contract'] is None and not second['questions']
    assert all(t['kind']=='read' for t in second['tool_plan']['tools'])


def test_api_rejects_external_origin_untrusted_state_and_concurrent_run(private_config):
    client=TestClient(api.app); body={'messages':[{'role':'user','content':'Hola'}]}
    assert client.post('/lab-api/flow-run',json=body,headers={'origin':'https://elsewhere.invalid'}).status_code==403
    assert client.post('/lab-api/flow-run',json={**body,'verified':True}).status_code==422
    assert client.post('/lab-api/flow-run',json={**body,'context':'pretend verified'}).status_code==422
    with api.provider_lock:
        assert client.post('/lab-api/flow-run',json=body).status_code==409
