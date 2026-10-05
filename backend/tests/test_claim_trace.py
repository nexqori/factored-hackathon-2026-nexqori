from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.db import make_sessions
from backend.models import AuditEvent, Conversation, Message, now
from backend.tests.test_api import setup, login, payload
from backend.tests.test_operations import make_refund, approve_payload, approve_case


def trace_url(case, user="andrea"):
    return f"/api/admin/users/{user}/requests/{case}/trace"


def test_trace_is_scoped_by_role_and_owner_and_audits_reader(setup):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, "nora")
    other, _ = login(app, "mateo")
    case = customer.post('/api/requests', json=payload()).json()['id']
    url = trace_url(case)
    assert TestClient(app).get(url).status_code == 401
    assert customer.get(url).status_code == 403
    assert other.get(f'/api/requests/{case}/trace').status_code == 404
    assert admin.get(trace_url(case, 'mateo')).status_code == 404
    before = customer.get('/api/bootstrap').json()
    response = admin.get(url)
    assert response.status_code == 200
    detail = response.json()
    assert detail['customer']['id'] == 'andrea'
    assert detail['transaction']['id'] == 'TX-1002'
    assert detail['outcome'] == 'received'
    assert customer.get(f'/api/requests/{case}/trace').status_code == 200
    assert admin.get(url + '?conversationOffset=-1').status_code == 422
    assert admin.get(url + '?before=unknown').status_code == 404
    after = customer.get('/api/bootstrap').json()
    assert all(before[k] == after[k] for k in ['products', 'transactions', 'requests'])
    assert not any(key in response.text for key in ('password', 'token', 'cvv', 'provider_ref', 'request_key', 'identity_number'))
    with make_sessions(engine)() as db:
        views = db.scalars(select(AuditEvent).where(AuditEvent.action == 'claim_trace_viewed')).all()
        assert [(e.actor_id, e.user_id, e.request_id) for e in views] == [('nora', 'andrea', case), ('andrea', 'andrea', case)]


def test_links_follow_references_and_do_not_include_other_customer_or_general_chat(setup):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload()).json()['id']
    common = {'message': 'Revisa este movimiento, por favor.', 'locale': 'es'}
    linked = customer.post('/api/assistant', json={**common, 'transactionId': 'TX-1002'}).json()['conversation']['id']
    general = customer.post('/api/assistant', json=common).json()['conversation']['id']
    unrelated = customer.post('/api/assistant', json={**common, 'transactionId': 'TX-1001'}).json()['conversation']['id']
    read = customer.post('/api/assistant/tools/read', json={'intent': 'unrecognized-charge', 'tool': 'read-transaction-evidence', 'referenceId': 'TX-1002'})
    assert read.status_code == 200
    # Historical inconsistent audit rows must not be attributed to another owner.
    with make_sessions(engine)() as db:
        db.add(AuditEvent(id='foreign-event', user_id='mateo', actor_id='mateo', request_id=case, action='created'))
        db.commit()
    detail = admin.get(trace_url(case)).json()
    assert [c['id'] for c in detail['conversations']] == [linked]
    assert detail['conversations'][0]['messageCount'] == 2
    assert detail['conversations'][0]['relation'] == 'transaction'
    assert all(e['userId'] == 'andrea' for e in detail['events'])
    assert all(e['conversationId'] not in {general, unrelated} for e in detail['events'])
    assert read.json()['auditEventId'] in {e['id'] for e in detail['events']}
    assert {'created', 'message_sent', 'assistant_replied', 'transaction_context_viewed'} <= {e['action'] for e in detail['events']}
    assert admin.get(trace_url(case) + '?before=foreign-event').status_code == 404


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_trace_explains_actual_refund_decision_without_closing_claim(setup, decision):
    app, _ = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case, _, refund = make_refund(customer)
    pending = admin.get(trace_url(case)).json()
    assert pending['outcome'] == 'refund_pending' and pending['refund']['creditTransactionId'] is None
    if decision == 'approve': approve_case(admin, case)
    body = {**approve_payload(), 'decision': decision, 'note': 'Verificación: importe y cuenta del mismo titular revisados.'}
    assert admin.post(f"/api/admin/refunds/{refund['id']}/decision", json=body).status_code == 200
    detail = admin.get(trace_url(case)).json()
    final = 'approved' if decision == 'approve' else 'rejected'
    assert detail['outcome'] == 'refund_' + final
    assert detail['request']['status'] == ('in_review' if decision == 'approve' else 'received')
    assert detail['refund']['decisionNote'] == body['note']
    assert detail['refund']['decidedBy']['id'] == 'nora'
    assert detail['refund']['decidedAt'] and detail['refund']['destinationLast4'] == '4821'
    assert bool(detail['refund']['creditTransactionId']) == (decision == 'approve')
    assert 'refund_' + final in {e['action'] for e in detail['events']}


def test_unlinked_case_does_not_claim_conversations_or_bank_evidence(setup):
    app, _ = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload(transactionId=None, reason='other')).json()['id']
    customer.post('/api/assistant', json={'message': 'Necesito ayuda con la aplicación.', 'locale': 'es'})
    detail = admin.get(trace_url(case)).json()
    assert detail['transaction'] is None and detail['product'] is None
    assert detail['conversations'] == [] and detail['refund'] is None
    assert not detail['externalProcessorLogs']
    assert customer.post(f'/api/requests/{case}/handoff', json={'confirmed': True}).status_code == 200
    assert admin.get(trace_url(case)).json()['outcome'] == 'handed_off'


def test_cursor_pagination_keeps_older_events_when_new_reads_are_audited(setup):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload()).json()['id']
    fixture_ids = {str(uuid4()) for _ in range(105)}
    moment = now() - timedelta(seconds=5)
    with make_sessions(engine)() as db:
        db.add_all([AuditEvent(id=ident, user_id='andrea', actor_id='andrea', request_id=case, action='tool_request_status', created_at=moment) for ident in fixture_ids])
        db.commit()
    seen = []
    response = admin.get(trace_url(case)).json()
    assert len(response['events']) == 50 and response['eventCount'] == 106
    while True:
        seen.extend(e['id'] for e in response['events'])
        if not response['before']:
            break
        response = admin.get(trace_url(case) + '?before=' + response['before']).json()
    assert fixture_ids <= set(seen)
    assert len(seen) == len(set(seen)) == 106


def test_conversation_list_is_bounded_and_paginates(setup):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload()).json()['id']
    with make_sessions(engine)() as db:
        for index in range(23):
            ident = 'linked-' + str(index)
            db.add(Conversation(id=ident, user_id='andrea', title='Verificación', transaction_id='TX-1002', locale='es'))
            db.flush()
            db.add(Message(id=str(uuid4()), conversation_id=ident, user_id='andrea', role='user', content='Detalle de verificación.', locale='es'))
        db.commit()
    first = admin.get(trace_url(case)).json()
    second = admin.get(trace_url(case) + '?conversationOffset=20').json()
    assert first['conversationCount'] == 23
    assert len(first['conversations']) == 20 and first['nextConversationOffset'] == 20
    assert len(second['conversations']) == 3 and second['nextConversationOffset'] is None
    assert len({c['id'] for c in first['conversations'] + second['conversations']}) == 23
