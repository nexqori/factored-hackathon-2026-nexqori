"""Explicit transaction replacement preserves the case but recomputes evidence."""
import copy
import hashlib
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend import workflow_chat as chat
from backend.db import make_sessions
from backend.models import AssistantTurn, AuditEvent, Conversation, ConversationFlow, Message, RequestCase
from backend.tests.test_api import ORIGIN, login, setup
from backend.tests.test_workflow_chat import message, models


def start(client, control, **kwargs):
    control['intent'] = 'unrecognized-charge'
    result = client.post('/api/assistant/flow', json=message(
        message='No reconozco este cobro y necesito revisarlo.', transactionId='TX-1002', **kwargs))
    assert result.status_code == 200, result.text
    assert result.json()['flow']['canRegister']
    return result.json()


def replace_body(conversation, **kwargs):
    return message(message='Quiero revisar este movimiento.', conversationId=conversation,
                   transactionId='TX-1001', replaceTransaction=True, **kwargs)


def claim_body(preview=None, **kwargs):
    return {'confirmed': True, 'details': (preview or {}).get('summary', 'No reconozco este movimiento y solicito revisión.'),
            'requestKey': str(uuid4()), **({'previewToken': preview['previewToken']} if preview else {}), **kwargs}


def stored(engine, cid):
    with make_sessions(engine)() as db:
        return {'transaction': db.get(Conversation, cid).transaction_id,
                'state': copy.deepcopy(db.get(ConversationFlow, cid).state),
                'messages': db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == cid)),
                'turns': db.scalar(select(func.count()).select_from(AssistantTurn)),
                'audits': db.scalar(select(func.count()).select_from(AuditEvent)),
                'requests': db.scalar(select(func.count()).select_from(RequestCase))}


def selected_evidence(result):
    return next(read['data']['transaction'] for read in result['flow']['bank_evidence']['reads']
                if read['tool'] == 'read-transaction-evidence')


@pytest.mark.parametrize('locale', ['es', 'en', 'pt'])
def test_explicit_replacement_keeps_contract_and_story_but_refreshes_evidence_once(setup, models, locale):
    app, engine = setup; client, _ = login(app); calls, control = models
    first = start(client, control, locale=locale); cid = first['conversation']['id']
    old_preview = client.get(f'/api/conversations/{cid}/claim-preview', params={'locale': locale}).json()
    before = client.get('/api/bootstrap').json()
    body = replace_body(cid, locale=locale)
    changed = client.post('/api/assistant/flow', json=body)
    assert changed.status_code == 200, changed.text
    value = changed.json()
    assert value['conversation']['transactionId'] == 'TX-1001'
    assert value['flow']['canRegister'] and value['flow']['contract'] == first['flow']['contract']
    assert value['flow']['jev'] == first['flow']['jev']
    assert selected_evidence(value)['id'] == 'TX-1001' and selected_evidence(value)['amountMinor'] == -28650
    assert [call[0] for call in calls] == ['triage', 'jev', 'llm', 'llm']
    assert calls[-1][1][0]['content'] == 'No reconozco este cobro y necesito revisarlo.'
    assert calls[-1][1][-1]['content'] == body['message']
    for private in ['Stream Plus', 'Mercado Central', 'TX-1002', 'TX-1001', '2026-09-27', '2026-09-28']:
        assert private not in json.dumps(calls, ensure_ascii=False)
    assert client.post('/api/assistant/flow', json=body).json() == value
    assert len(calls) == 4
    assert client.get(f'/api/conversations/{cid}/flow').json()['flow'] == value['flow']
    after = client.get('/api/bootstrap').json()
    assert all(before[key] == after[key] for key in ('products', 'transactions', 'requests'))
    with make_sessions(engine)() as db:
        row = db.get(ConversationFlow, cid)
        assert row.state['bank_binding']['transaction_id'] == 'TX-1001'
        assert row.state['claim_preview_required'] is True
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'chat_transaction_changed')).all()
        assert len(events) == 1 and events[0].transaction_id == 'TX-1001' and events[0].actor_id == 'andrea'
    # A dialog opened for the old movement cannot register the new one silently.
    for body in [claim_body(old_preview, locale=locale), claim_body(locale=locale)]:
        rejected = client.post(f'/api/conversations/{cid}/claim', json=body)
        assert rejected.status_code == 409 and rejected.json()['error'] == 'claim_preview_outdated'
    preview = client.get(f'/api/conversations/{cid}/claim-preview', params={'locale': locale}).json()
    assert preview['transactionId'] == 'TX-1001' and 'TX-1001' in preview['summary']
    assert 'TX-1002' not in preview['summary'] and preview['previewToken'] != old_preview['previewToken']
    registered = client.post(f'/api/conversations/{cid}/claim', json=claim_body(preview, locale=locale))
    assert registered.status_code == 200, registered.text
    with make_sessions(engine)() as db:
        claim = db.get(RequestCase, registered.json()['id'])
        assert claim.transaction_id == 'TX-1001' and claim.catalog_service_id == 'unrecognized-charge'


def test_without_explicit_flag_change_remains_conflict_and_registered_case_is_fixed(setup, models):
    app, engine = setup; client, _ = login(app); calls, control = models
    first = start(client, control); cid = first['conversation']['id']; before = stored(engine, cid)
    unconfirmed = replace_body(cid); unconfirmed.pop('replaceTransaction')
    result = client.post('/api/assistant/flow', json=unconfirmed)
    assert result.status_code == 409 and result.json()['error'] == 'conversation_context_conflict'
    assert stored(engine, cid) == before and len(calls) == 3
    preview = client.get(f'/api/conversations/{cid}/claim-preview').json()
    assert client.post(f'/api/conversations/{cid}/claim', json=claim_body(preview)).status_code == 200
    registered = stored(engine, cid)
    rejected = client.post('/api/assistant/flow', json=replace_body(cid))
    assert rejected.status_code == 409 and rejected.json()['error'] == 'conversation_context_conflict'
    assert stored(engine, cid) == registered and len(calls) == 3


def test_replace_validates_user_and_transaction_before_running_models(setup, models):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo'); admin, _ = login(app, 'nora')
    calls, control = models; first = start(client, control); cid = first['conversation']['id']; before = stored(engine, cid)
    for target in ['TX-2001', 'missing']:
        result = client.post('/api/assistant/flow', json={**replace_body(cid), 'transactionId': target})
        assert result.status_code == 404
    for actor, body, status in [
        (other, {**replace_body(cid), 'transactionId': 'TX-2001'}, 404),
        (admin, replace_body(cid), 403),
        (TestClient(app, headers={'Origin': ORIGIN}), replace_body(cid), 401),
    ]:
        assert actor.post('/api/assistant/flow', json=body).status_code == status
    assert client.post('/api/assistant/flow', json=replace_body(cid), headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    for missing in ['transactionId', 'conversationId']:
        body = replace_body(cid); body.pop(missing)
        assert client.post('/api/assistant/flow', json=body).status_code == 422
    assert stored(engine, cid) == before and len(calls) == 3


def test_replacement_clears_old_declared_fields_and_cannot_register_until_new_context_is_ready(setup, models):
    app, engine = setup; client, _ = login(app); calls, control = models
    first = client.post('/api/assistant/flow', json=message(transactionId='TX-1002', message='Esperaba 100 MXN')).json()
    assert first['flow']['canRegister']; cid = first['conversation']['id']
    replaced = client.post('/api/assistant/flow', json=replace_body(cid))
    assert replaced.status_code == 200, replaced.text
    value = replaced.json()
    assert value['flow']['missing_fields'] == ['difference'] and not value['flow']['canRegister']
    assert value['flow']['execution']['phase'] == 'waiting_reply'
    with make_sessions(engine)() as db:
        ctx = db.get(ConversationFlow, cid).state['context']
        assert ctx['observations'] == [] and ctx['bank_evidence']['verified_facts']
    assert client.get(f'/api/conversations/{cid}/claim-preview').status_code == 409
    assert client.post(f'/api/conversations/{cid}/claim', json=claim_body()).status_code == 409
    continued = client.post('/api/assistant/flow', json=message(conversationId=cid, message='Esperaba 100 MXN')).json()
    assert continued['flow']['canRegister'] and selected_evidence(continued)['id'] == 'TX-1001'
    assert [call[0] for call in calls] == ['triage', 'jev', 'llm', 'llm', 'llm']


def test_context_provider_failure_after_selection_never_reuses_previous_ready_state(setup, models, monkeypatch):
    app, engine = setup; client, _ = login(app); calls, control = models
    first = start(client, control); cid = first['conversation']['id']
    monkeypatch.setattr(chat.editor, 'extract', lambda *args, **kwargs: {'status': 'error', 'error': 'timeout'})
    result = client.post('/api/assistant/flow', json=replace_body(cid))
    assert result.status_code == 200, result.text
    value = result.json()
    assert value['conversation']['transactionId'] == 'TX-1001'
    assert value['flow']['state'] == 'provider_unavailable' and not value['flow']['canRegister']
    assert selected_evidence(value)['id'] == 'TX-1001'
    assert client.post(f'/api/conversations/{cid}/claim', json=claim_body()).status_code == 409
    with make_sessions(engine)() as db:
        state = db.get(ConversationFlow, cid).state
        assert state['context']['observations'] == [] and state['claim_preview_required'] is True


def test_unexpected_failure_rolls_back_selection_history_audit_and_retry(setup, models, monkeypatch):
    app, engine = setup; client, _ = login(app); calls, control = models
    first = start(client, control); cid = first['conversation']['id']; before = stored(engine, cid)
    original = chat.SessionReader.collect
    def unavailable(*args, **kwargs):
        raise RuntimeError('Controlled interruption before the turn is committed')
    monkeypatch.setattr(chat.SessionReader, 'collect', unavailable)
    body = replace_body(cid)
    with TestClient(app, raise_server_exceptions=False) as failing:
        failing.cookies.update(client.cookies); failing.headers.update(client.headers)
        result = failing.post('/api/assistant/flow', json=body)
    assert result.status_code == 500 and stored(engine, cid) == before
    monkeypatch.setattr(chat.SessionReader, 'collect', original)
    result = client.post('/api/assistant/flow', json=body)
    assert result.status_code == 200, result.text
    after = stored(engine, cid)
    assert after['transaction'] == 'TX-1001' and after['messages'] == before['messages'] + 2
    assert client.post('/api/assistant/flow', json=body).json() == result.json()
    assert stored(engine, cid) == after


def test_original_turn_retries_keep_fingerprint_after_optional_flag_added(setup, models):
    app, engine = setup; client, _ = login(app); calls, control = models
    body = message(transactionId='TX-1002'); first = client.post('/api/assistant/flow', json=body)
    assert first.status_code == 200
    historical = chat.FlowMessage.model_validate(body).model_dump(exclude={'requestKey', 'replaceTransaction', 'updateSelection'})
    expected = hashlib.sha256(json.dumps(historical, sort_keys=True).encode()).hexdigest()
    with make_sessions(engine)() as db:
        assert db.get(AssistantTurn, ('andrea', body['requestKey'])).fingerprint == expected
    assert client.post('/api/assistant/flow', json={**body, 'replaceTransaction': False}).json() == first.json()
    assert len(calls) == 3
