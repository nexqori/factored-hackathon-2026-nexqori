import json
import httpx
import pytest
from fastapi.testclient import TestClient

from intent_lab import api, dialogue
from intent_lab.data import taxonomy, corpus
from test_providers import private_config, install_transport, response
from test_luna_dialogue import enable, envelope


def test_full_mapping_and_reference_provenance():
    client = TestClient(api.app)
    plans = client.get('/lab-api/tool-routes').json()['plans']
    assert set(plans) == {row['id'] for row in taxonomy()}
    assert client.get('/lab-api/meta').json()['tool_plans'] == plans
    assert len(corpus()) == 345 and len({row['expected'] for row in corpus()}) == 23
    assert all(p['source'] == 'reference' and p['executed_tools'] == [] for p in plans.values())
    assert plans['request-status']['family'] == 'query'
    assert plans['phone-bill']['family'] == 'service'


def test_conversation_recomputes_tool_allowlist_each_turn(private_config, monkeypatch):
    enable(private_config)
    chosen = ['request-status','incorrect-charge','account-balance','multiple-intents']
    current = {'intent': None}
    calls = []
    def handler(req):
        calls.append(req.url.host)
        if req.url.host == 'api.typesafe.ai':
            current['intent'] = chosen.pop(0)
            value = response(); answer = value['answers']['intent']
            answer['choice'] = current['intent']
            answer['probabilities'] = {key: int(key == current['intent']) for key in answer['probabilities']}
            return httpx.Response(200,json=value)
        payload = json.loads(req.content)
        context = json.loads(payload['input'][0]['content'])
        assert context['tool_plan']['intent'] == 'incorrect-charge'
        assert context['tool_plan']['source'] == 'jev'
        assert context['tool_plan']['executed_tools'] == []
        assert 'tools' not in payload  # The LLM receives descriptions, never executable calls.
        return httpx.Response(200,json=envelope({'reply':'¿Cuál es el importe que esperabas?','next_step':'collect_context','missing_information':['importe esperado']}))
    install_transport(monkeypatch,handler)
    history = []; thread = None
    for message, expected in [('Quiero ver el folio.','query'),('La comisión sigue mal.','problem'),('Ahora sólo quiero ver mi saldo.','query'),('Varias cosas a la vez.','clarification')]:
        history.append({'role':'user','content':message})
        result = dialogue.respond(history,'es','Clasifica la necesidad activa.',thread_id=thread)
        thread = result['thread_id']
        plan = result['tool_plan']
        assert plan['family'] == expected and plan['source'] == 'jev'
        assert plan['executed_tools'] == result['executed_operations'] == []
        if expected == 'query':
            assert all(t['kind'] == 'read' for t in plan['tools'])
            assert result['contract'] is None and result['llm']['status'] == 'skipped'
        if expected == 'clarification':
            assert plan['tools'] == []
        history.append({'role':'assistant','content':result['routing']['reply'] if result['routing'] else result['llm']['reply']})
    assert calls.count('api.typesafe.ai') == 4 and calls.count('api.openai.com') == 1
    records = [json.loads(p.read_text()) for p in (private_config/'runs').glob('*.json')]
    assert len(records) == 4 and {r['result']['thread_id'] for r in records} == {thread}


def test_failed_jev_cannot_reuse_previous_problem_tools(private_config, monkeypatch):
    install_transport(monkeypatch,lambda request: httpx.Response(401,json={}))
    result = dialogue.respond([{'role':'user','content':'Continúa con el bloqueo.'}],'es','Classify')
    assert result['tool_plan']['status'] == 'unavailable'
    assert result['tool_plan']['tools'] == [] and result['contract'] is None
