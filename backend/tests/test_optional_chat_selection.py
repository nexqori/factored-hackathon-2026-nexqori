"""The unified details form applies optional references as one owned selection."""
import json

import pytest
from sqlalchemy import select, func
from backend.db import make_sessions
from backend.models import ConversationFlow, AuditEvent
from backend.tests.test_api import setup, login, payload
from backend.tests.test_workflow_chat import models, message
from backend.tests.test_conversation_selection import start, claim_body, stored


def create_case(client, transaction_id='TX-1002'):
    response = client.post('/api/requests', json=payload(transactionId=transaction_id))
    assert response.status_code == 201, response.text
    return response.json()['id']


@pytest.mark.parametrize('movement,case', [(False,False),(True,False),(False,True),(True,True)])
def test_optional_selection_at_start_and_after_clearing_is_persisted_and_idempotent(setup, models, movement, case):
    app, engine = setup; client, _ = login(app); calls, control = models
    rid = create_case(client); control.update(family='query', intent='request-status')
    before = client.get('/api/bootstrap').json()
    first = client.post('/api/assistant/flow', json=message(message='Quiero consultar este caso.',
        transactionId='TX-1002', requestId=rid)).json()
    cid = first['conversation']['id']
    body = message(conversationId=cid, message='Quiero revisar los registros seleccionados.', updateSelection=True,
                   transactionId='TX-1002' if movement else None, requestId=rid if case else None)
    response = client.post('/api/assistant/flow', json=body)
    assert response.status_code == 200, response.text
    value = response.json(); before_retry = stored(engine, cid); call_count = len(calls)
    assert value['conversation']['transactionId'] == ('TX-1002' if movement else None)
    assert value['flow']['selectedRequestId'] == (rid if case else None)
    assert client.get(f'/api/conversations/{cid}/flow').json()['flow'] == value['flow']
    with make_sessions(engine)() as db:
        binding = db.get(ConversationFlow, cid).state['bank_binding']
        assert binding['transaction_id'] == ('TX-1002' if movement else None)
        assert binding['request_id'] == (rid if case else None)
    assert client.post('/api/assistant/flow', json=body).json() == value
    assert stored(engine, cid) == before_retry and len(calls) == call_count
    # A new conversation also accepts any of the four combinations.
    initial = client.post('/api/assistant/flow', json=message(message='Quiero consultar este caso.',
        transactionId='TX-1002' if movement else None, requestId=rid if case else None))
    assert initial.status_code == 200, initial.text
    assert initial.json()['flow']['selectedRequestId'] == (rid if case else None)
    after = client.get('/api/bootstrap').json()
    assert all(after[key] == before[key] for key in ('products','transactions','requests'))
    assert rid not in json.dumps(calls) and 'TX-1002' not in json.dumps(calls)


def test_changing_movement_and_case_keeps_both_and_invalidates_old_claim_preview(setup, models):
    app, engine = setup; client, _ = login(app); calls, control = models
    rid = create_case(client, 'TX-1001'); first = start(client, control); cid = first['conversation']['id']
    old_preview = client.get(f'/api/conversations/{cid}/claim-preview').json()
    response = client.post('/api/assistant/flow', json=message(conversationId=cid,
        message='Quiero revisar este movimiento y este caso.', updateSelection=True, transactionId='TX-1001', requestId=rid))
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['flow']['selectedRequestId'] == rid and value['conversation']['transactionId'] == 'TX-1001'
    assert value['flow']['contract'] == first['flow']['contract']
    assert [call[0] for call in calls] == ['triage','jev','llm','llm']
    assert client.post(f'/api/conversations/{cid}/claim', json=claim_body(old_preview)).status_code == 409
    with make_sessions(engine)() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'chat_context_changed')).all()
        assert len(events) == 1 and events[0].request_id == rid and events[0].transaction_id == 'TX-1001'


def test_invalid_case_cannot_partially_change_movement_and_registered_case_cannot_be_cleared(setup, models):
    app, engine = setup; client, _ = login(app); calls, control = models
    other, _ = login(app, 'mateo')
    foreign = other.post('/api/requests', json=payload(transactionId='TX-2001')).json()['id']
    first = start(client, control); cid = first['conversation']['id']; before = stored(engine, cid); count = len(calls)
    for rid, tx in [(foreign, 'TX-1001'), ('not-found', 'TX-1001'), (None,'TX-2001')]:
        result = client.post('/api/assistant/flow', json=message(conversationId=cid,updateSelection=True,
            transactionId=tx,requestId=rid))
        assert result.status_code == 404 and stored(engine,cid) == before and len(calls) == count
    preview = client.get(f'/api/conversations/{cid}/claim-preview').json()
    assert client.post(f'/api/conversations/{cid}/claim', json=claim_body(preview)).status_code == 200
    registered = stored(engine,cid)
    result = client.post('/api/assistant/flow', json=message(conversationId=cid,updateSelection=True,
        transactionId=None,requestId=None))
    assert result.status_code == 409 and stored(engine,cid) == registered
