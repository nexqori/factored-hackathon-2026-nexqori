from uuid import uuid4

import pytest
from sqlalchemy import func, select
from backend.attention import process_due
from backend.db import make_sessions
from backend.models import AttentionReview, AuditEvent, ChatFeedback, Conversation, ConversationFlow, Message, RequestCase, Transaction, now
from backend.tests.test_api import setup, login, payload


def case_clients(setup):
    app, engine = setup
    client, _ = login(app)
    admin, _ = login(app, 'nora')
    result = client.post('/api/requests', json=payload())
    assert result.status_code == 201, result.text
    identity = result.json()['id']
    return client, admin, engine, '/api/attention/requests/' + identity


def resolve(admin, path):
    result = admin.post(path.replace('/api/', '/api/admin/') + '/resolve', json={
        'confirmed': True, 'noPending': True, 'summary': 'Se revisó el cobro y se explicó su origen al cliente.'})
    assert result.status_code == 200, result.text
    return result.json()['review']


def scores(**changes):
    return {'revision': 0, 'locale': 'es', 'nps': 9, 'csat': None, 'ces': None,
            'comment': 'La explicación fue útil.', 'submit': False, **changes}


def test_partial_deadline_late_response_and_no_financial_effect(setup):
    client, admin, engine, path = case_clients(setup)
    before = client.get('/api/bootstrap').json()
    review = resolve(admin, path)
    assert review['dueAt'] - review['confirmedAt'] == 900
    assert resolve(admin, path)['dueAt'] == review['dueAt']
    assert client.put(path + '/feedback', json=scores()).status_code == 200
    sessions = make_sessions(engine)
    assert process_due(sessions, review['dueAt'] - 1) == 0
    assert process_due(sessions, review['dueAt']) == 1
    assert process_due(sessions, review['dueAt'] + 10) == 0
    final = client.get(path).json()['review']
    assert final['status'] == 'closed'
    assert final['snapshots'][0]['received']['nps'] == 9
    assert final['snapshots'][0]['missing'] == ['csat']
    assert final['snapshots'][0]['feedback'] == 'partial'
    submission = scores(revision=1, csat=4, submit=True)
    sent = client.put(path + '/feedback', json=submission)
    assert sent.status_code == 200, sent.text
    assert client.put(path + '/feedback', json=submission).status_code == 200
    assert sent.json()['review']['snapshots'] == final['snapshots']
    aggregate = admin.get('/api/admin/overview').json()['chatFeedback']
    assert aggregate['nps']['responses'] == 1 and aggregate['nps']['npsScore'] == 100
    assert aggregate['csat']['responses'] == 1 and aggregate['csat']['csatPercent'] == 100
    assert aggregate['ces']['responses'] == 0
    assert aggregate['nps']['averageConversationDurationMs'] is None
    after = client.get('/api/bootstrap').json()
    for field in ('products', 'transactions', 'requests'):
        assert before[field] == after[field]
    with sessions() as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == 'attention_closed_by_timer')) == 1
        assert db.scalar(select(func.count(ChatFeedback.id))) == 2


def test_empty_feedback_is_not_a_zero_score(setup):
    client, admin, engine, path = case_clients(setup)
    row = resolve(admin, path)
    assert process_due(make_sessions(engine), row['dueAt']) == 1
    result = client.get(path).json()['review']
    assert result['snapshots'][0]['feedback'] == 'unanswered'
    assert result['snapshots'][0]['missing'] == ['nps', 'csat']
    assert admin.get('/api/admin/overview').json()['chatFeedback']['nps']['responses'] == 0


def test_case_conversation_new_message_stops_closure(setup):
    client, admin, engine, path = case_clients(setup)
    sessions = make_sessions(engine)
    with sessions() as db:
        db.add(Conversation(id='case-followup', user_id='andrea', locale='es', title='Seguimiento', transaction_id='TX-1002'))
        db.commit()
    row = resolve(admin, path)
    with sessions() as db:
        db.add(Message(id=str(uuid4()), user_id='andrea', conversation_id='case-followup', role='user', content='Sigo teniendo el problema.', locale='es'))
        db.commit()
    assert process_due(sessions, row['dueAt']) == 0
    assert client.get(path).json()['review']['status'] == 'reopened'


def test_ownership_csrf_roles_and_score_validation(setup):
    client, admin, engine, path = case_clients(setup)
    other, _ = login(setup[0], 'mateo')
    assert other.get(path).status_code == 404
    assert client.post(path + '/resolve', json={'confirmed': True, 'noPending': True, 'summary': 'No pueden cerrar mi reclamo.'}).status_code == 403
    resolve(admin, path)
    assert other.put(path + '/feedback', json=scores()).status_code == 404
    assert client.put(path + '/feedback', json=scores(), headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.put(path + '/feedback', json=scores(nps=11)).status_code == 422
    assert client.put(path + '/feedback', json=scores(nps=True)).status_code == 422
    assert client.put(path + '/feedback', json=scores(submit=True)).status_code == 422
    assert client.put(path + '/feedback', json=scores(revision=3)).status_code == 409
    assert client.put(path + '/feedback', json=scores(nps=0)).status_code == 200
    assert client.get(path).json()['review']['answers']['nps'] == 0


def test_pending_refund_prevents_resolution_and_reopening_stops_timer(setup):
    client, admin, engine, path = case_clients(setup)
    row = resolve(admin, path)
    assert client.post(path + '/reopen', json={'confirmed': True}).status_code == 200
    assert process_due(make_sessions(engine), row['dueAt']) == 0
    assert client.get(path).json()['review']['status'] == 'reopened'
    refund = client.post(path.replace('/attention', '') + '/refund', json={'confirmed': True, 'requestKey': str(uuid4())})
    assert refund.status_code == 200, refund.text
    assert admin.post(path.replace('/api/', '/api/admin/') + '/resolve', json={
        'confirmed': True, 'noPending': True, 'summary': 'No puede cerrar una devolución pendiente.'}).status_code == 409


def test_new_pending_operation_stops_scheduled_closure(setup):
    client, admin, engine, path = case_clients(setup)
    row = resolve(admin, path)
    refund = client.post(path.replace('/attention', '') + '/refund', json={'confirmed': True, 'requestKey': str(uuid4())})
    assert refund.status_code == 200
    assert process_due(make_sessions(engine), row['dueAt']) == 0
    assert client.get(path).json()['review']['status'] == 'reopened'


def test_payment_pending_and_changed_case_prevent_closure(setup):
    client, admin, engine, path = case_clients(setup)
    sessions = make_sessions(engine)
    with sessions() as db:
        db.get(Transaction, 'TX-1002').status = 'pending'; db.commit()
    assert admin.get(path.replace('/api/', '/api/admin/')).json()['pending']
    with sessions() as db:
        db.get(Transaction, 'TX-1002').status = 'completed'; db.commit()
    row = resolve(admin, path)
    assert admin.post(path.replace('/attention/', '/admin/') + '/review', json={'confirmed': True}).status_code == 200
    assert process_due(sessions, row['dueAt']) == 0
    assert client.get(path).json()['review']['status'] == 'reopened'


def test_customer_query_requires_completed_flow_and_new_message_stops_timer(setup):
    app, engine = setup
    client, _ = login(app)
    sessions = make_sessions(engine)
    with sessions() as db:
        db.add(Conversation(id='query-feedback', user_id='andrea', locale='es', title='Consulta resuelta'))
        db.flush()
        db.add(ConversationFlow(conversation_id='query-feedback', user_id='andrea', state={
            'phase': 'completed', 'context': {'triage': {'family': 'problem'}}}))
        db.commit()
    path = '/api/attention/conversations/query-feedback'
    body = {'confirmed': True, 'noPending': True, 'summary': 'Mi consulta de saldo fue resuelta.'}
    assert client.post(path + '/resolve', json=body).status_code == 409
    with sessions() as db:
        db.get(ConversationFlow, 'query-feedback').state = {'phase': 'completed', 'context': {'triage': {'family': 'query'}}}; db.commit()
    row = client.post(path + '/resolve', json=body).json()['review']
    with sessions() as db:
        db.add(Message(id=str(uuid4()), user_id='andrea', conversation_id='query-feedback', role='user', content='Tengo otra duda', locale='es')); db.commit()
    assert process_due(sessions, row['dueAt']) == 0
    assert client.get(path).json()['review']['status'] == 'reopened'


def test_late_save_snapshots_information_before_new_answers(setup, monkeypatch):
    client, admin, engine, path = case_clients(setup)
    row = resolve(admin, path)
    monkeypatch.setattr('backend.attention.time.time', lambda: row['dueAt'] + 1)
    # Cookies/session remain valid; the due review has not been scanned yet.
    result = client.put(path + '/feedback', json=scores())
    assert result.status_code == 200, result.text
    assert result.json()['review']['snapshots'][0]['feedback'] == 'unanswered'
    assert result.json()['review']['answers']['nps'] == 9


def test_form_survives_new_app_and_server_clock_not_client(setup):
    client, admin, engine, path = case_clients(setup)
    row = resolve(admin, path)
    from backend.main import create_app
    app = create_app(engine, ['http://testserver'], False)
    fresh, _ = login(app)
    assert fresh.get(path).json()['review']['dueAt'] == row['dueAt']
    assert fresh.put(path + '/feedback', json={**scores(), 'dueAt': 1}).status_code == 422
    assert process_due(app.state.sessions, row['dueAt']) == 1
    assert fresh.get(path).json()['review']['status'] == 'closed'
