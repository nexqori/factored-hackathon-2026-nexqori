import json
from uuid import uuid4
import pytest
from sqlalchemy import select
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.tests.test_operations import approve_case, approve_payload
from backend.db import make_sessions
from backend.models import AuditEvent, ConversationFlow, Transaction
from backend.voice_summary import registered_summary


@pytest.mark.parametrize('locale', ['es', 'en', 'pt'])
@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_registered_chat_reads_fresh_decision_and_credit_without_models(setup, models, locale, decision):
    app, engine = setup; customer, _ = login(app); admin, _ = login(app, 'nora'); other, _ = login(app, 'mateo')
    calls, control = models; control['intent'] = 'unrecognized-charge'
    first = customer.post('/api/assistant/flow', json=message(locale=locale, transactionId='TX-1002')).json()
    cid = first['conversation']['id']
    claim = customer.post('/api/conversations/'+cid+'/claim', json={'confirmed':True, 'details':'Cargo no reconocido para revisar.', 'requestKey':str(uuid4())}).json()
    rid = claim['id']; before = customer.get('/api/bootstrap').json(); model_count = len(calls)
    def follow():
        body = message(locale=locale, conversationId=cid, message={'es':'¿Cómo va mi caso? ¿Ya se realizó el reembolso?', 'en':'What is the status of my case? Has the refund been completed?', 'pt':'Como vai minha reclamação? O reembolso foi realizado?'}[locale])
        response = customer.post('/api/assistant/flow', json=body)
        assert response.status_code == 200, response.text
        assert customer.post('/api/assistant/flow', json=body).json() == response.json()
        assert len(calls) == model_count
        return response.json()
    pending = follow(); assert rid in pending['text']
    approve_case(admin, rid)
    approved = follow()
    assert any(word in approved['text'] for word in ('todavía', 'no completed refund', 'ainda'))
    assert customer.get('/api/bootstrap').json()['products'] == before['products']
    refund = admin.get('/api/admin/requests/'+rid+'/refund').json()['refund']
    result = admin.post('/api/admin/refunds/'+refund['id']+'/decision', json={**approve_payload(), 'decision':decision}).json()
    fresh = follow()
    reads = fresh['flow']['bank_evidence']['reads']; data = next(r['data'] for r in reads if r['tool']=='read-request-status')
    assert data['request']['handling']['stage'] == 'approved'
    assert data['refund']['status'] == ('approved' if decision=='approve' else 'rejected')
    with make_sessions(engine)() as db:
        voice = registered_summary(db, 'andrea', rid, locale)
        assert registered_summary(db, 'mateo', rid, locale) is None
        assert db.scalar(select(AuditEvent).where(AuditEvent.action=='tool_request_status', AuditEvent.request_id==rid, AuditEvent.conversation_id==cid))
        state = db.get(ConversationFlow, cid).state
        assert rid not in json.dumps(state['messages'])
    if decision == 'approve':
        reference = result['creditTransactionId']; assert reference in fresh['text']
        assert any(word in voice for word in ('reembolso realizado', 'has been refunded', 'já foi reembolsada'))
        assert reference not in voice
    else:
        assert data['refund']['creditTransactionId'] is None
        assert any(word in fresh['text'] for word in ('rechazada', 'declined', 'rejeitada'))
        assert customer.get('/api/bootstrap').json()['products'] == before['products']
    assert other.post('/api/assistant/flow', json=message(conversationId=cid)).status_code == 404
    control.update(intent='request-status', family='query')
    selected = customer.post('/api/assistant/flow', json=message(locale=locale, requestId=rid, message={'es':'Estado del caso', 'en':'What is my case status?', 'pt':'Qual é o estado da minha reclamação?'}[locale])).json()
    assert rid in selected['text']
    if decision=='approve': assert reference in selected['text']


def test_approval_without_valid_completed_credit_is_not_a_refund(setup, models):
    from backend.tests.test_operations import make_refund
    from backend.case_followup import read_case_status, case_status_reply
    app, engine = setup; customer, _ = login(app); admin, _ = login(app, 'nora')
    rid, _, refund = make_refund(customer); approve_case(admin, rid)
    credit = admin.post('/api/admin/refunds/'+refund['id']+'/decision', json=approve_payload()).json()['creditTransactionId']
    with make_sessions(engine)() as db:
        db.get(Transaction, credit).status='pending'; db.flush()
        data=read_case_status(db,'andrea',rid)
        assert data['refund']['creditTransactionId'] is None
        assert 'todavía no consta' in case_status_reply(data,'es')
        db.rollback()
