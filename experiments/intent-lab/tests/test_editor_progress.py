"""The visual workspace uses actual interpreter events and evidence-backed case metadata."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from intent_lab import api, workflow_editor as editor, workflow_execution as execution
from test_providers import private_config
from test_luna_dialogue import enable
from test_workflow_editor import create, mock_models


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_case_catalog_and_templates(private_config, monkeypatch, language):
    monkeypatch.setattr(editor, 'classify_jev', lambda *a: pytest.fail('Read must not call a model'))
    client = TestClient(api.app)
    response = client.get('/lab-api/editor/cases', params={'language': language})
    assert response.status_code == 200
    rows = response.json()['cases']
    assert len(rows) == 25 and len({r['intent'] for r in rows}) == 25
    problems = [r for r in rows if r['family'] == 'problem']
    assert len(problems) == 6 and all(r['contract']['steps'] for r in problems)
    sourced = {r['intent']: r['evidence']['records'] for r in problems if r['evidence']}
    assert sourced == {'unrecognized-charge': 12297, 'incorrect-charge': 12194,
                      'app-support': 12128, 'branch-support': 11892, 'service-feedback': 11886}
    assert all(r['title'] and r['example'] and r['example_source'] == 'authored_category_example' for r in rows)
    for row in rows:
        graph = client.get('/lab-api/editor/case-template/' + row['intent']).json()
        assert graph == editor.template()  # Cases never change the graph or preset its classification.
        assert editor.validate_graph(graph)['valid']
    assert client.get('/lab-api/editor/case-template/invented').status_code == 404


def streamed(client, record, **extra):
    response = client.post('/lab-api/editor/workflows/' + record['id'] + '/run-stream', json={
        'revision': record['revision'], 'messages': [{'role': 'user', 'content': 'Error X, reinicié'}], **extra})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/x-ndjson')
    return [json.loads(line) for line in response.text.splitlines() if json.loads(line)['event'] != 'heartbeat']


@pytest.mark.parametrize('assessment,observations,terminal,port', [
    ('continue', [], 'ask', 'yes'),
    ('continue', [{'field': 'symptom', 'message_index': 0, 'quote': 'Error X'},
                  {'field': 'attempts', 'message_index': 0, 'quote': 'reinicié'}], 'review', 'no'),
    ('human_review', [], 'escalate', 'yes'),
])
def test_progress_matches_executed_path_and_saved_snapshot(private_config, monkeypatch, assessment, observations, terminal, port):
    enable(private_config)
    calls = mock_models(monkeypatch, assessment, observations)
    client = TestClient(api.app)
    record = create(client)
    events = streamed(client, record)
    result = events[-1]['result']
    assert events[-1]['event'] == 'complete' and len(calls) == 2
    finished = [e['trace'] for e in events if e['event'] == 'node_finished']
    assert finished == result['trace'] and finished[-1]['node_id'] == terminal
    assert [e['node_id'] for e in events if e['event'] == 'node_started'] == [r['node_id'] for r in finished]
    assert [e['edge_id'] for e in events if e['event'] == 'edge_taken'] == result['visited_edges']
    assert [r for r in finished if r['kind'] == 'condition'][-1]['output']['port'] == port
    # Each node starts before it finishes; an edge appears only after its source has completed.
    for i, event in enumerate(events[:-1]):
        if event['event'] == 'node_started':
            assert events[i+1]['event'] == 'node_finished'
            assert events[i+1]['trace']['node_id'] == event['node_id']
        elif event['event'] == 'edge_taken':
            assert events[i-1]['event'] == 'node_finished' and events[i+1]['event'] == 'node_started'
    saved = client.get('/lab-api/runs/' + result['id']).json()['result']
    assert saved == result and not saved['executed_operations'] and not saved['authorizes_execution']


def test_started_event_emitted_before_model_returns(private_config, monkeypatch):
    client = TestClient(api.app)
    record = create(client)
    seen = []
    def classifier(*args):
        assert seen[-1] == {'event': 'node_started', 'node_id': 'jev', 'kind': 'jev'}
        assert not any(e['event'] == 'node_finished' and e['trace']['node_id'] == 'jev' for e in seen)
        return {'status': 'unavailable'}, None
    monkeypatch.setattr(editor, 'classify_jev', classifier)
    result = editor.run_workflow(record, [{'role': 'user', 'content': 'Pregunta'}], 'es', on_event=seen.append)
    assert result['state'] == 'provider_unavailable'
    assert [t['kind'] for t in result['trace']] == ['start', 'jev']


def test_stream_preconditions_and_error_release_lock(private_config, monkeypatch):
    client = TestClient(api.app)
    record = create(client, 'app')
    url = '/lab-api/editor/workflows/' + record['id'] + '/run-stream'
    body = {'revision': 1, 'messages': [{'role': 'user', 'content': 'No puedo entrar'}]}
    assert client.post(url, json={**body, 'revision': 2}).status_code == 409
    with api.provider_lock:
        assert client.post(url, json=body).status_code == 409
    assert client.post(url, content='x'*24001).status_code == 413
    with monkeypatch.context() as patch:
        def broken(*args): raise RuntimeError('private-provider-detail')
        patch.setattr(execution, '_one', broken)
        events = streamed(client, record)
        assert events[-1] == {'event': 'error', 'code': 'execution_failed'}
        assert events[0]['event'] == 'execution_created'
        state = client.get('/lab-api/editor/executions/' + events[0]['result']['execution']['id']).json()
        assert state['execution']['phase'] == 'interrupted'
        assert not api.provider_lock.locked()
    events = streamed(client, record)
    assert events[-1]['result']['state'] == 'missing_incident'
    graph = copy.deepcopy(record['graph'])
    graph['edges'].pop()
    record = client.put('/lab-api/editor/workflows/' + record['id'], json={'graph': graph, 'revision': 1}).json()
    assert client.post(url, json={**body, 'revision': record['revision']}).status_code == 422
