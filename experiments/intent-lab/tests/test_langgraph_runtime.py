"""Compatibility at the persisted execution boundary, with no real providers."""
import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from intent_lab import storage, workflow_editor as editor, workflow_execution as execution
from intent_lab import langgraph_runtime as runtime


@pytest.fixture
def record(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA_DIR', tmp_path)
    return editor.master_workflow()


@pytest.fixture
def providers(monkeypatch):
    calls = []
    control = {'family': 'problem', 'intent': 'app-support', 'observations': []}

    def triage(messages, language, *args, **kwargs):
        calls.append(('triage', copy.deepcopy(messages)))
        return {'status': 'ok', 'family': control['family']}, {}

    def classify(messages, language, *args, **kwargs):
        calls.append(('jev', copy.deepcopy(messages)))
        return {'status': 'ok', 'intent': control['intent']}, {}

    def extract(messages, language, fields, *args, **kwargs):
        calls.append(('context', copy.deepcopy(messages)))
        rows = control['observations'](messages) if callable(control['observations']) else control['observations']
        return {'status': 'ok', 'assessment': 'continue', 'observations': copy.deepcopy(rows), 'latency_ms': 1}

    monkeypatch.setattr(editor, 'classify_triage', triage)
    monkeypatch.setattr(editor, 'classify_jev', classify)
    monkeypatch.setattr(editor, 'extract', extract)
    return calls, control


def new_state(record, message='La app se cierra al pagar', **kwargs):
    return execution.create(record, [{'role': 'user', 'content': message}], 'es',
                            persist=lambda _: None, **kwargs)


def advance(state, mode='full', **kwargs):
    return execution.advance(state, mode, record_run=False, persist=lambda _: None, **kwargs)


def test_question_waits_for_real_reply_and_resumes_only_context(record, providers):
    calls, control = providers

    def observations(messages):
        rows = [{'field': 'symptom', 'message_index': 0, 'quote': 'La app se cierra al pagar'}]
        if len(messages) > 2:
            rows.append({'field': 'attempts', 'message_index': 2, 'quote': 'Ya reinicié y sigue igual'})
        return rows

    control['observations'] = observations
    state = new_state(record)
    first = advance(state)
    assert first['execution']['phase'] == 'waiting_reply'
    assert first['execution']['next_node_id'] == 'context'
    assert first['missing_fields'] == ['attempts']
    assert [item[0] for item in calls] == ['triage', 'jev', 'context']
    saved = copy.deepcopy(state)
    with pytest.raises(ValueError, match='reply_required'):
        advance(state)
    assert state == saved and len(calls) == 3
    second = advance(state, reply='Ya reinicié y sigue igual')
    assert second['execution']['phase'] == 'completed'
    assert second['state'] == 'review_in_bank'
    assert second['execution']['turn'] == 1
    assert [item[0] for item in calls] == ['triage', 'jev', 'context', 'context']
    assert [item['content'] for item in calls[-1][1] if item['role'] == 'user'] == [
        'La app se cierra al pagar', 'Ya reinicié y sigue igual']
    assert [item['node_id'] for item in second['trace']].count('context') == 2


def test_historical_json_resumes_after_cache_and_process_identity_change(record, providers, monkeypatch):
    calls, _ = providers
    state = new_state(record)
    while state['next_node_id'] != 'jev':
        advance(state, 'step')
    assert [item[0] for item in calls] == ['triage']
    original_version = state['version']
    original_trace = copy.deepcopy(state['trace'])
    # A persisted pre-LangGraph checkpoint has no runtime metadata or saver ID.
    state.pop('runtime', None)
    execution.write(json.loads(json.dumps(state)))
    runtime.compile_graph.cache_clear()
    monkeypatch.setattr(execution, 'BOOT_ID', 'fresh-process-after-upgrade')
    restored = execution.read(state['id'])
    assert restored['phase'] == 'paused' and restored['version'] == original_version
    result = advance(restored, 'step')
    assert [item[0] for item in calls] == ['triage', 'jev']
    assert restored['trace'][:-1] == original_trace
    assert result['execution']['version'] == original_version + 1
    assert result['execution']['next_node_id'] == 'case_route'
    final = advance(restored)
    assert final['execution']['phase'] == 'waiting_reply'
    assert [item[0] for item in calls] == ['triage', 'jev', 'context']
    assert restored['runtime']['name'] == 'langgraph'
    assert restored['runtime']['checkpoint_schema'] == 1


@pytest.mark.parametrize('family,intent', [
    *[('problem', intent) for intent in editor.PROBLEM_PORTS],
    ('query', 'account-balance'), ('query', 'phone-bill'), ('query', 'documents'),
])
def test_full_and_one_block_steps_choose_same_branch_and_result(record, providers, family, intent):
    calls, control = providers
    control.update(family=family, intent=intent)
    full = new_state(record)
    result_full = advance(full)
    calls_full = [item[0] for item in calls]
    calls.clear()
    stepped = new_state(record)
    while stepped['phase'] == 'paused':
        previous_length, previous_version = len(stepped['trace']), stepped['version']
        result_step = advance(stepped, 'step')
        assert len(stepped['trace']) == previous_length + 1
        assert stepped['version'] == previous_version + 1
    assert [item[0] for item in calls] == calls_full
    assert [item['node_id'] for item in full['trace']] == [item['node_id'] for item in stepped['trace']]
    assert full['visited_edges'] == stepped['visited_edges']
    for key in ('state', 'reply', 'contract', 'missing_fields', 'questions', 'observations',
                'executed_operations', 'authorizes_execution'):
        assert result_step[key] == result_full[key], key
    assert stepped['phase'] == full['phase']
    assert not result_full['executed_operations'] and result_full['authorizes_execution'] is False


def test_cached_topology_does_not_capture_owner_config_reader_or_persist(record, providers, monkeypatch):
    calls, control = providers
    control['intent'] = 'payment-status'
    runtime.compile_graph.cache_clear()
    # Warm once so both simultaneous calls intentionally share one compiled
    # instance; lru_cache may otherwise compile twice for concurrent misses.
    runtime.compile_graph(runtime.topology(record['graph']))
    barrier = threading.Barrier(2)
    snapshots = {'A': [], 'B': []}
    seen = []

    class Reader:
        def __init__(self, owner): self.user = {'id': owner}

        def collect(self, intent, binding, language, fields):
            assert binding['owner_id'] == self.user['id']
            barrier.wait(timeout=10)
            owner = self.user['id']
            return {'status': 'read', 'reads': [], 'missing_references': [],
                    'verified_facts': [{'field': field, 'value': 'PRIVATE-BANK-' + owner,
                        'source': 'nexqori_records', 'status': 'verified', 'reference_id': 'tx-' + owner,
                        'audit_event_id': 'audit-' + owner} for field in fields]}

    def extract(messages, language, fields, instructions, notes, intent, incident=None):
        owner = messages[0]['content'][-1]
        assert notes.endswith('policy-' + owner)
        assert 'PRIVATE-BANK-' not in json.dumps([messages, instructions, notes])
        seen.append(owner)
        return {'status': 'ok', 'assessment': 'continue', 'observations': [], 'latency_ms': 1}

    monkeypatch.setattr(editor, 'extract', extract)

    def run(owner):
        own_record = copy.deepcopy(record)
        next(node for node in own_record['graph']['nodes'] if node['kind'] == 'context')['config']['notes']['es'] = 'policy-' + owner
        state = new_state(own_record, 'Caso ' + owner, bank_binding={'owner_id': owner, 'transaction_id': 'tx-' + owner})
        return execution.advance(state, 'full', bank_reader=Reader(owner), record_run=False,
                                 persist=lambda value: snapshots[owner].append(copy.deepcopy(value)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {owner: pool.submit(run, owner) for owner in ('A', 'B')}
        results = {owner: future.result(timeout=20) for owner, future in futures.items()}
    assert sorted(seen) == ['A', 'B']
    assert runtime.compile_graph.cache_info().hits >= 1
    for owner, result in results.items():
        assert result['bank_context']['owner_id'] == owner
        assert {item['value'] for item in result['verified_facts']} == {'PRIVATE-BANK-' + owner}
        assert snapshots[owner]
        assert all(item['bank_binding']['owner_id'] == owner for item in snapshots[owner])
        assert 'PRIVATE-BANK-' + ('B' if owner == 'A' else 'A') not in json.dumps(snapshots[owner])
    assert 'PRIVATE-BANK-' not in json.dumps(calls)


def test_persist_failure_stops_without_repeating_completed_provider(record, providers):
    calls, _ = providers
    state = new_state(record)
    failures = []
    snapshots = []

    def persist(value):
        if value['trace'] and value['trace'][-1]['kind'] == 'jev' and not failures:
            failures.append('unavailable')
            raise OSError('test checkpoint unavailable')
        snapshots.append(copy.deepcopy(value))

    with pytest.raises(OSError, match='test checkpoint unavailable'):
        execution.advance(state, 'full', persist=persist, record_run=False)
    assert [item[0] for item in calls] == ['triage', 'jev']
    assert failures == ['unavailable']
    assert state['phase'] == 'interrupted' and state['next_node_id'] is None
    assert snapshots[-1]['phase'] == 'interrupted'


def test_running_checkpoint_from_previous_process_remains_interrupted_without_providers(record, providers, monkeypatch):
    calls, _ = providers
    state = new_state(record)
    state.update(phase='running', worker='previous-process')
    state.pop('runtime', None)
    execution.write(state)
    runtime.compile_graph.cache_clear()
    monkeypatch.setattr(execution, 'BOOT_ID', 'current-process')
    restored = execution.read(state['id'])
    assert restored['phase'] == 'interrupted' and restored['next_node_id'] is None
    assert calls == []


def test_parent_tracing_is_disabled_inside_provider_blocks(record, providers, monkeypatch):
    from langsmith.run_helpers import get_tracing_context, tracing_context
    from langsmith import Client

    observed = []

    def no_trace(*args, **kwargs):
        pytest.fail('Bank execution attempted hosted tracing')

    def extract(*args, **kwargs):
        observed.append(get_tracing_context()['enabled'])
        return {'status': 'ok', 'assessment': 'continue', 'observations': [], 'latency_ms': 1}

    monkeypatch.setattr(Client, 'create_run', no_trace)
    monkeypatch.setattr(Client, 'update_run', no_trace)
    monkeypatch.setattr(editor, 'extract', extract)
    with tracing_context(enabled=True):
        advance(new_state(record))
        assert get_tracing_context()['enabled'] is True
    assert observed == [False]
