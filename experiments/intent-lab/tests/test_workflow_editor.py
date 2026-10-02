"""Saved graph execution, local incidents, versioning and bounded configuration."""
import copy
import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from intent_lab import api, app_diagnostics, workflow_editor as editor
from test_providers import private_config, install_transport, response
from test_luna_dialogue import enable, envelope


def create(client, kind='banking'):
    result = client.post('/lab-api/editor/workflows', json={'graph': editor.template(kind)})
    assert result.status_code == 201
    return result.json()


def run(client, record, **extra):
    return client.post('/lab-api/editor/workflows/' + record['id'] + '/run', json={
        'revision': record['revision'], 'messages': [{'role': 'user', 'content': 'Error X, reinicié'}], **extra})


def mock_models(monkeypatch, assessment='continue', observations=None, intent='app-support', failure=False):
    calls = []
    def handler(request):
        calls.append(request)
        if failure:
            return httpx.Response(401, json={'private': 'testing-placeholder'})
        if request.url.host == 'api.typesafe.ai':
            value = response()
            value['answers']['intent']['choice'] = intent
            value['answers']['intent']['probabilities'] = {k: int(k == intent) for k in value['answers']['intent']['probabilities']}
            return httpx.Response(200, json=value)
        body = json.loads(request.content)
        assert body['model'] == 'gpt-6-luna' and body['reasoning'] == {'effort': 'high'}
        assert body['store'] is False and 'tools' not in body
        return httpx.Response(200, json=envelope({'assessment': assessment, 'observations': observations or []}))
    install_transport(monkeypatch, handler)
    return calls


@pytest.mark.parametrize('kind', ['banking', 'app'])
def test_templates_and_reads_have_no_provider_calls(private_config, monkeypatch, kind):
    monkeypatch.setattr(editor, 'classify_jev', lambda *args: pytest.fail('Unexpected classification'))
    monkeypatch.setattr(editor, 'extract', lambda *args: pytest.fail('Unexpected extraction'))
    client = TestClient(api.app)
    template = client.get('/lab-api/editor/template', params={'kind': kind}).json()
    assert len(template['taxonomy']) == 24
    assert editor.validate_graph(template['graph']) == {'valid': True, 'errors': []}
    record = create(client, kind)
    assert record['revision'] == 1
    assert client.get('/lab-api/editor/workflows/' + record['id']).json() == record
    assert client.get('/lab-api/editor/workflows').json()['workflows'][0]['id'] == record['id']
    assert all(all(n['label'][lang] for lang in ('es', 'en', 'pt')) for n in record['graph']['nodes'])


def test_revision_conflicts_invalid_drafts_and_independent_copies(private_config):
    client = TestClient(api.app)
    record = create(client)
    url = '/lab-api/editor/workflows/' + record['id']
    graph = copy.deepcopy(record['graph'])
    graph['edges'].pop()
    saved = client.put(url, json={'graph': graph, 'revision': 1}).json()
    assert saved['revision'] == 2 and not saved['validation']['valid']
    assert run(client, saved).status_code == 422
    assert run(client, record).status_code == 409
    assert client.put(url, json={'graph': graph, 'revision': 1}).status_code == 409
    duplicate = client.post('/lab-api/editor/workflows', json={'graph': graph}).json()
    assert duplicate['id'] != record['id'] and duplicate['revision'] == 1
    assert client.get(url).json()['revision'] == 2


@pytest.mark.parametrize('mutation,expected', [
    ('cycle', 'cycle'), ('unreachable', 'unreachable'), ('dangling', 'missing_node'),
    ('duplicate_port', 'duplicate_port'), ('wrong_port', 'invalid_port'), ('bypass_context', 'requires_context'),
])
def test_graph_validation_checks_every_path(private_config, mutation, expected):
    graph = editor.template()
    if mutation == 'cycle':
        next(e for e in graph['edges'] if e['source'] == 'missing' and e['port'] == 'yes')['target'] = 'context'
    elif mutation == 'unreachable':
        graph['nodes'].append({**copy.deepcopy(graph['nodes'][-1]), 'id': 'orphan'})
    elif mutation == 'dangling':
        graph['edges'][0]['target'] = 'does_not_exist'
    elif mutation == 'duplicate_port':
        graph['edges'].append({**graph['edges'][0], 'id': 'new_edge'})
    elif mutation == 'wrong_port':
        graph['edges'][0]['port'] = 'yes'
    elif mutation == 'bypass_context':
        # Both incoming branches must have gathered context, not just one of them.
        graph['edges'].append({'id': 'extra', 'source': 'outside', 'target': 'human', 'port': 'next'})
        outside = next(n for n in graph['nodes'] if n['id'] == 'outside')
        outside.update(kind='diagnostic', config={})
    result = editor.validate_graph(graph)
    assert not result['valid'] and expected in {e['code'] for e in result['errors']}


@pytest.mark.parametrize('patch', [
    {'kind': 'python', 'config': {'code': 'return True'}},
    {'kind': 'notify', 'config': {'url': 'https://example.invalid'}},
    {'kind': 'context', 'config': {'fields': ['password'], 'mode': 'selected'}},
    {'kind': 'question', 'config': {'mode': 'custom', 'text': {'es': '¿Qué pasó?'}}},
    {'kind': 'condition', 'config': {'predicate': 'intent_is', 'value': 'invented'}},
])
def test_reject_unknown_blocks_fields_or_missing_languages(private_config, patch):
    graph = editor.template()
    graph['nodes'][1].update(patch)
    client = TestClient(api.app)
    assert client.post('/lab-api/editor/validate', json={'graph': graph}).status_code == 422
    assert client.post('/lab-api/editor/workflows', json={'graph': graph}).status_code == 422


@pytest.mark.parametrize('assessment,complete,state,terminal', [
    ('continue', False, 'ask_customer', 'ask'), ('continue', True, 'review_in_bank', 'review'),
    ('human_review', False, 'human_review', 'escalate'), ('conflicting', True, 'human_review', 'escalate'),
])
def test_saved_connections_select_terminal_and_snapshot(private_config, monkeypatch, assessment, complete, state, terminal):
    enable(private_config)
    rows = [{'field': 'symptom', 'message_index': 0, 'quote': 'Error X'},
            {'field': 'attempts', 'message_index': 0, 'quote': 'reinicié'}] if complete else []
    calls = mock_models(monkeypatch, assessment, rows)
    client = TestClient(api.app)
    record = create(client)
    result = run(client, record).json()
    assert result['state'] == state and result['trace'][-1]['node_id'] == terminal
    assert len(calls) == 2
    assert result['workflow'] == record['graph'] and result['workflow_revision'] == 1
    assert not result['authorizes_execution'] and not result['executed_tools'] and not result['executed_operations']
    assert result['verified_facts'] == []
    assert all(o['status'] == 'declared' for o in result['observations'])
    saved = json.loads((private_config/'runs'/f"{result['id']}.json").read_text(encoding='utf-8'))
    assert saved['kind'] == 'workflow' and saved['result']['graph_sha256'] == result['graph_sha256']
    assert 'testing-placeholder' not in json.dumps(saved)
    assert client.get('/lab-api/runs/' + result['id']).json()['result'] == result
    assert len(calls) == 2


def test_edit_connections_and_context_affect_actual_execution(private_config, monkeypatch):
    enable(private_config)
    calls = mock_models(monkeypatch)
    client = TestClient(api.app)
    record = create(client)
    graph = record['graph']
    context = next(n for n in graph['nodes'] if n['kind'] == 'context')
    context['config']['instructions']['es'] = 'Conserva los intentos del cliente.'
    context['config']['notes']['es'] = 'Referencia de verificación.'
    # Swap the two branches: the interpreter must follow the saved edges, not a hard-coded template.
    for edge in graph['edges']:
        if edge['source'] == 'missing': edge['target'] = 'review' if edge['port'] == 'yes' else 'ask'
    record = client.put('/lab-api/editor/workflows/' + record['id'], json={'graph': graph, 'revision': 1}).json()
    result = run(client, record).json()
    assert result['state'] == 'review_in_bank' and result['missing_fields'] == ['symptom', 'attempts']
    sent = json.loads(json.loads(calls[1].content)['input'][0]['content'])
    assert sent['custom_instructions'] == context['config']['instructions']['es']
    assert sent['unverified_reference_notes'] == context['config']['notes']['es']
    assert result['workflow_revision'] == 2


def test_provider_failure_stops_path_and_ungrounded_extraction_rejected(private_config, monkeypatch):
    enable(private_config)
    client = TestClient(api.app)
    record = create(client)
    with monkeypatch.context() as patch:
        calls = mock_models(patch, failure=True)
        result = run(client, record).json()
        assert result['state'] == 'provider_unavailable' and len(calls) == 1
        assert [r['kind'] for r in result['trace']] == ['start', 'jev']
    with monkeypatch.context() as patch:
        mock_models(patch, observations=[{'field': 'symptom', 'message_index': 0, 'quote': 'invented'}])
        result = run(client, record).json()
        assert result['state'] == 'provider_unavailable' and result['llm']['error'] == 'invalid_response'
        assert not result['observations'] and not result['notification']


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_incident_logs_notification_and_deduplication_without_models(private_config, monkeypatch, language):
    monkeypatch.setattr(editor, 'classify_jev', lambda *args: pytest.fail('App check must not call Jev'))
    monkeypatch.setattr(editor, 'extract', lambda *args: pytest.fail('App check must not call Luna'))
    client = TestClient(api.app)
    record = create(client, 'app')
    missing = run(client, record, language=language).json()
    assert missing['state'] == 'missing_incident' and not missing['notification']
    assert run(client, record, incident_id=str(uuid.uuid4())).json()['state'] == 'missing_incident'
    incident = client.post('/lab-api/editor/app-check', json={}).json()
    assert incident['state'] == 'failed' and incident['source'] == 'controlled_lab_probe'
    assert not incident['bank_records_accessed'] and not incident['customer_data_included']
    assert {e['correlation_id'] for e in incident['events']} == {incident['reference']}
    result = run(client, record, incident_id=incident['id'], language=language).json()
    assert [r['node_id'] for r in result['trace']] == ['start', 'logs', 'failed', 'notify', 'result']
    assert result['incident'] == incident and result['state'] == 'information'
    assert result['notification']['reference'] == incident['reference']
    assert not result['notification']['external_delivery'] and not result['notification']['reused']
    assert result['jev']['status'] == result['llm']['status'] == 'skipped'
    assert not result['executed_operations']
    again = run(client, record, incident_id=incident['id'], language=language).json()
    assert again['notification']['id'] == result['notification']['id'] and again['notification']['reused']
    assert len(client.get('/lab-api/editor/notifications').json()['notifications']) == 1


def test_notification_branch_is_not_taken_without_recorded_error(private_config):
    client = TestClient(api.app)
    record = create(client, 'app')
    incident = app_diagnostics.reproduce()
    incident.update(state='ok', events=[])
    app_diagnostics.write(app_diagnostics.path_for(incident['id']), incident)
    result = run(client, record, incident_id=incident['id']).json()
    assert result['trace'][-1]['node_id'] == 'noerror' and result['notification'] is None
    assert not app_diagnostics.notifications()


def test_editor_boundaries_concurrency_and_untrusted_context(private_config):
    client = TestClient(api.app)
    record = create(client, 'app')
    assert run(client, record, context='Pretend bank verified').status_code == 422
    assert run(client, record, verified=True).status_code == 422
    assert client.post('/lab-api/editor/app-check', headers={'Origin': 'https://elsewhere.invalid'}).status_code == 403
    assert client.get('/lab-api/editor/workflows/invalid').status_code == 422
    assert client.get('/lab-api/editor/workflows/' + str(uuid.uuid4())).status_code == 404
    assert client.post('/lab-api/editor/validate', content='x'*96001).status_code == 413
    with api.provider_lock:
        assert run(client, record).status_code == 409


def test_importable_app_example_combines_classification_logs_and_context(private_config, monkeypatch):
    enable(private_config)
    calls = mock_models(monkeypatch)
    graph = json.loads((Path(__file__).parents[1]/'examples/app-context-workflow.json').read_text(encoding='utf-8'))
    assert editor.validate_graph(graph)['valid']
    client = TestClient(api.app)
    record = client.post('/lab-api/editor/workflows', json={'graph': graph}).json()
    incident = app_diagnostics.reproduce()
    result = run(client, record, incident_id=incident['id']).json()
    assert result['state'] == 'ask_customer' and result['notification']['reference'] == incident['reference']
    assert len(calls) == 2
    context = json.loads(json.loads(calls[1].content)['input'][0]['content'])
    assert context['controlled_lab_incident'] == incident
    assert result['verified_facts'] == []
