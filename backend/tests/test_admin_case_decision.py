"""The admin decision and the customer's outcome share the same stored evidence."""
from datetime import timedelta

import pytest
from sqlalchemy import select, func

from backend.db import make_sessions
from backend.models import AuditEvent, Product, Transaction
from backend.tests.test_api import setup, login, payload
from backend.tests.test_operations import make_refund, approve_payload


def test_review_summary_uses_only_owner_history_and_does_not_authorize_money(setup):
    app, engine = setup
    customer, _ = login(app)
    other, _ = login(app, 'mateo')
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload(transactionId='TX-1001')).json()['id']
    with make_sessions(engine)() as db:
        source = db.get(Transaction, 'TX-1001')
        for index in range(1, 4):
            for owner, product, amount in [('andrea', source.product_id, -10000), ('mateo', 'account-02', -999900)]:
                db.add(Transaction(id=f'history-{owner}-{index}', user_id=owner, product_id=product,
                    merchant=source.merchant, category=source.category, amount_minor=amount,
                    currency=source.currency, occurred_at=source.occurred_at-timedelta(days=30*index), status='completed'))
        db.commit()
    before = customer.get('/api/bootstrap').json()
    url = f'/api/admin/users/andrea/requests/{case}/trace'
    assert customer.get(url).status_code == 403
    assert other.get(f'/api/requests/{case}/trace').status_code == 404
    detail = admin.get(url).json()['reviewContext']
    assert detail['canStartReview'] and not detail['canDecideRefund']
    assert detail['financialEffect'] == 'none'
    assert '100.00' in detail['summary']['es'] and '9999' not in str(detail)
    assert 'comparable_history' not in detail['missingEvidence']
    own = customer.get(f'/api/requests/{case}/trace').json()['reviewContext']
    assert not own['canStartReview'] and not own['canDecideRefund']
    after = customer.get('/api/bootstrap').json()
    assert all(before[key] == after[key] for key in ('products', 'transactions', 'requests'))


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_admin_decision_is_visible_to_customer_and_retry_has_one_effect(setup, decision):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case, _, refund = make_refund(customer)
    before = customer.get('/api/bootstrap').json()
    review_url = f'/api/admin/requests/{case}/review'
    assert customer.post(review_url, json={'confirmed': True}).status_code == 403
    assert admin.post(review_url, json={'confirmed': False}).status_code == 422
    assert admin.post(review_url, json={'confirmed': True}).status_code == 200
    assert admin.post(review_url, json={'confirmed': True}).status_code == 200
    body = {**approve_payload(), 'decision': decision, 'note': 'Revisamos el registro y confirmamos el resultado para el cliente.'}
    url = f"/api/admin/refunds/{refund['id']}/decision"
    assert customer.post(url, json=body).status_code == 403
    assert admin.post(url, json=body).status_code == 200
    assert admin.post(url, json=body).status_code == 200
    detail = customer.get(f'/api/requests/{case}/trace').json()
    assert detail['request']['status'] == 'in_review'
    assert detail['refund']['decisionNote'] == body['note']
    assert detail['refund']['decidedBy']['name']
    assert detail['reviewContext']['financialEffect'] == ('credited' if decision == 'approve' else 'none')
    assert detail['transaction']['id'] == 'TX-1001' and detail['transaction']['status'] == 'completed'
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category == 'refund')) == int(decision == 'approve')
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'reviewed', AuditEvent.request_id == case)) == 1
    if decision == 'reject':
        after = customer.get('/api/bootstrap').json()
        assert after['products'] == before['products'] and after['transactions'] == before['transactions']


def test_pending_payment_remains_unresolved_and_without_refund_decision(setup):
    app, _ = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload(transactionId='TX-1005', reason='payment')).json()['id']
    detail = admin.get(f'/api/admin/users/andrea/requests/{case}/trace').json()['reviewContext']
    assert 'payment_confirmation' in detail['missingEvidence']
    assert not detail['canDecideRefund'] and detail['financialEffect'] == 'none'
    closed = admin.post(f'/api/admin/attention/requests/{case}/resolve', json={
        'confirmed': True, 'noPending': True, 'summary': 'No debe cerrarse mientras el pago permanece pendiente.'})
    assert closed.status_code == 409


def test_nonfinancial_problem_does_not_require_contract_or_movement(setup):
    app, _ = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload(transactionId=None, reason='other',
        details='La aplicación se cierra al intentar cambiar el idioma.')).json()['id']
    context = admin.get(f'/api/admin/users/andrea/requests/{case}/trace').json()['reviewContext']
    assert context['missingEvidence'] == []
    assert all(value == '' for value in context['summary'].values())
    assert not context['canDecideRefund']
