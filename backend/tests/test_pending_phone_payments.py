"""Explicit local pending-payment fixture; never a scheduled external payment."""
import hashlib
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.db import make_sessions
from backend.models import AuditEvent, BillPayment, Transaction
from backend.payments import ServicePayment
from backend.tests.test_api import ORIGIN, login, setup
from backend.tests.test_service_payments import lookup, pay_payload, snapshot


BILL = 'phone-andrea-2026-10'
URL = f'/api/service-bills/{BILL}/pay'


def pending_body(**kwargs):
    return pay_payload(expectedOutstandingMinor=29900, processingMode='pending', **kwargs)


def test_pending_phone_payment_debits_once_and_exposes_truthful_receipt_and_evidence(setup):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo')
    before = snapshot(engine)
    body = pending_body()
    response = client.post(URL, json=body)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt['status'] == 'pending' and receipt['amountMinor'] == 29900 and receipt['remainingMinor'] == 0
    assert client.get('/api/payments/' + receipt['id']).json() == receipt
    assert client.post(URL, json=body).json() == receipt
    bill = lookup(client, 'phone-bill', '5500000001')[0]
    assert bill['paidMinor'] == 0 and bill['pendingMinor'] == 29900 and bill['outstandingMinor'] == 0
    assert bill['paymentStatus'] == 'pending'
    assert bill['pendingPaymentId'] == bill['paymentId'] == receipt['id']
    assert bill['processingOptions'] == ['immediate', 'pending']
    for mode in ['immediate', 'pending']:
        duplicate = client.post(URL, json=pay_payload(expectedOutstandingMinor=29900, processingMode=mode))
        assert duplicate.status_code == 409 and duplicate.json()['error'] == 'bill_in_processing'
    after = snapshot(engine)
    assert dict(after['balances'])['account-01'] == dict(before['balances'])['account-01'] - 29900
    assert after['payments'] == before['payments'] + 1 and after['requests'] == before['requests']
    assert len(after['transactions']) == len(before['transactions']) + 1
    evidence_body = {'intent': 'payment-status', 'tool': 'read-transaction-evidence', 'referenceId': receipt['transactionId'], 'locale': 'es'}
    evidence = client.post('/api/assistant/tools/read', json=evidence_body)
    assert evidence.status_code == 200, evidence.text
    result = evidence.json()
    assert result['data']['transaction']['status'] == 'pending'
    assert result['data']['transaction']['amountMinor'] == -29900
    assert result['data']['externalProcessorLogs'] is False and result['executed_operations'] == []
    assert other.post('/api/assistant/tools/read', json=evidence_body).status_code == 404
    assert other.get('/api/payments/' + receipt['id']).status_code == 404
    movements = client.get('/api/bootstrap').json()['transactions']
    movement = next(tx for tx in movements if tx['id'] == receipt['transactionId'])
    assert movement['status'] == 'pending' and movement['paymentId'] == receipt['id']
    assert snapshot(engine) == after
    with make_sessions(engine)() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.transaction_id == receipt['transactionId'])).all()
        pending = [e for e in events if e.action == 'phone_bill_pending']
        assert len(pending) == 1 and pending[0].actor_id == pending[0].user_id == 'andrea'
        assert not any(e.action == 'phone_bill_paid' for e in events)
        assert db.get(Transaction, receipt['transactionId']).status == 'pending'


@pytest.mark.parametrize('final_mode', ['pending', 'immediate'])
def test_pending_and_immediate_partial_payments_share_one_outstanding_amount(setup, final_mode):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    url = '/api/service-bills/phone-family-2026-10/pay'
    first_body = pay_payload(mode='partial', amountMinor=5000, expectedOutstandingMinor=19900, processingMode='pending')
    first = client.post(url, json=first_body)
    assert first.status_code == 200, first.text
    second_body = pay_payload(mode='partial', amountMinor=5000, expectedOutstandingMinor=14900)
    second = client.post(url, json=second_body)
    assert second.status_code == 200, second.text
    bill = lookup(client, 'phone-bill', '5500000002')[0]
    assert (bill['paidMinor'], bill['pendingMinor'], bill['outstandingMinor']) == (5000, 5000, 9900)
    assert bill['paymentStatus'] == 'pending' and bill['paymentId'] is None
    assert bill['pendingPaymentId'] == first.json()['id']
    too_much = client.post(url, json=pay_payload(mode='partial', amountMinor=9901, expectedOutstandingMinor=9900, processingMode='pending'))
    assert too_much.status_code == 422 and too_much.json()['error'] == 'payment_exceeds_bill'
    final_body = pay_payload(expectedOutstandingMinor=9900, processingMode=final_mode)
    final = client.post(url, json=final_body)
    assert final.status_code == 200, final.text
    assert final.json()['amountMinor'] == 9900 and final.json()['remainingMinor'] == 0
    bill = lookup(client, 'phone-bill', '5500000002')[0]
    expected_paid, expected_pending = (5000, 14900) if final_mode == 'pending' else (14900, 5000)
    assert (bill['paidMinor'], bill['pendingMinor'], bill['outstandingMinor']) == (expected_paid, expected_pending, 0)
    assert bill['paymentStatus'] == 'pending'
    assert bill['pendingPaymentId'] == (final.json()['id'] if final_mode == 'pending' else first.json()['id'])
    assert bill['paymentId'] == final.json()['id']
    assert final.json()['status'] == ('pending' if final_mode == 'pending' else 'completed')
    for body, receipt in [(first_body, first.json()), (second_body, second.json()), (final_body, final.json())]:
        assert client.post(url, json=body).json() == receipt
    after = snapshot(engine)
    assert dict(after['balances'])['account-01'] == dict(before['balances'])['account-01'] - 19900
    assert after['payments'] == before['payments'] + 3
    assert len(after['transactions']) == len(before['transactions']) + 3
    assert after['requests'] == before['requests']


def test_immediate_default_preserves_historical_fingerprint_and_cannot_be_changed_to_pending(setup):
    app, engine = setup; client, _ = login(app)
    body = pay_payload(expectedOutstandingMinor=29900)
    response = client.post(URL, json=body)
    assert response.status_code == 200 and response.json()['status'] == 'completed'
    receipt = response.json()
    historical = ServicePayment.model_validate(body).model_dump(exclude={'requestKey', 'processingMode'})
    old_hash = hashlib.sha256(json.dumps(historical, sort_keys=True).encode()).hexdigest()
    with make_sessions(engine)() as db:
        stored = db.get(BillPayment, receipt['id'])
        assert stored.fingerprint == old_hash
        # Model the retry of a receipt persisted before processingMode existed.
        stored.fingerprint = old_hash; db.commit()
    after = snapshot(engine)
    assert client.post(URL, json={**body, 'processingMode': 'immediate'}).json() == receipt
    changed = client.post(URL, json={**body, 'processingMode': 'pending'})
    assert changed.status_code == 409 and changed.json()['error'] == 'conflict'
    assert snapshot(engine) == after
    bill = lookup(client, 'phone-bill', '5500000001')[0]
    assert bill['paidMinor'] == 29900 and bill['pendingMinor'] == 0 and bill['paymentStatus'] == 'completed'


@pytest.mark.parametrize('override', [
    {'confirmed': False}, {'status': 'completed'}, {'processingMode': 'completed'},
    {'processingMode': 'failed'}, {'processingMode': None}, {'userId': 'mateo'},
])
def test_pending_requires_confirmation_and_does_not_accept_arbitrary_status(setup, override):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    response = client.post(URL, json={**pending_body(), **override})
    assert response.status_code == 422
    assert snapshot(engine) == before


def test_pending_is_phone_only_and_legacy_endpoint_keeps_its_existing_contract(setup):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    bill = lookup(client)[0]
    assert bill['processingOptions'] == ['immediate']
    rejected = client.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload(processingMode='pending'))
    assert rejected.status_code == 422 and rejected.json()['error'] == 'processing_not_available'
    legacy_body = {'confirmed': True, 'accountId': 'account-01', 'requestKey': str(uuid4())}
    assert client.post(f'/api/phone-bills/{BILL}/pay', json={**legacy_body, 'processingMode': 'pending'}).status_code == 422
    assert snapshot(engine) == before
    receipt = client.post(URL, json=pending_body()).json()
    after = snapshot(engine)
    # A legacy client can recover the existing pending receipt, never charge it again.
    assert client.post(f'/api/phone-bills/{BILL}/pay', json=legacy_body).json() == receipt
    assert snapshot(engine) == after


def test_pending_authentication_owner_role_and_csrf(setup):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo'); admin, _ = login(app, 'nora')
    anonymous = TestClient(app, headers={'Origin': ORIGIN}); before = snapshot(engine)
    assert anonymous.post(URL, json=pending_body()).status_code == 401
    assert admin.post(URL, json=pending_body()).status_code == 403
    assert other.post(URL, json=pending_body(accountId='account-02')).status_code == 404
    assert client.post(URL, json=pending_body(accountId='account-02')).status_code == 404
    client.headers.pop('X-CSRF-Token')
    assert client.post(URL, json=pending_body()).status_code == 403
    assert snapshot(engine) == before


def test_pending_audit_failure_rolls_back_and_same_key_retry_then_succeeds_once(setup):
    app, engine = setup; client, _ = login(app); body = pending_body()
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER reject_pending_audit BEFORE INSERT ON audit_events "
                          "WHEN NEW.action = 'phone_bill_pending' BEGIN SELECT RAISE(ABORT, 'verification rollback'); END"))
    before = snapshot(engine)
    with TestClient(app, raise_server_exceptions=False) as failing:
        failing.cookies.update(client.cookies); failing.headers.update(client.headers)
        response = failing.post(URL, json=body)
    assert response.status_code == 500 and snapshot(engine) == before
    with engine.begin() as conn:
        conn.execute(text('DROP TRIGGER reject_pending_audit'))
    result = client.post(URL, json=body)
    assert result.status_code == 200, result.text
    after = snapshot(engine)
    assert client.post(URL, json=body).json() == result.json()
    assert snapshot(engine) == after
    assert after['payments'] == before['payments'] + 1
    assert dict(after['balances'])['account-01'] == dict(before['balances'])['account-01'] - 29900


@pytest.mark.parametrize('locale,pending_word', [('es', 'pendiente'), ('en', 'pending'), ('pt', 'pendente')])
def test_pending_record_can_be_queried_and_reported_without_resolving_payment(setup, locale, pending_word):
    app, engine = setup; client, _ = login(app)
    receipt = client.post(URL, json=pending_body()).json(); before = snapshot(engine)
    conversation = client.post('/api/assistant', json={
        'message': {'es':'Verificación del movimiento de teléfono.','en':'Review the phone transaction.','pt':'Verificar a movimentação de telefone.'}[locale], 'locale': locale,
        'currentPage': 'movements', 'transactionId': receipt['transactionId']})
    assert conversation.status_code == 200, conversation.text
    assert conversation.json()['evidence']['transaction']['status'] == 'pending'
    assert pending_word in conversation.json()['text'].lower()
    assert snapshot(engine) == before
    claim = client.post('/api/services/payment-status/requests', json={
        'confirmed': True, 'locale': locale, 'requestKey': str(uuid4()), 'transactionId': receipt['transactionId'],
        'notes': 'El pago de teléfono sigue pendiente después del débito.'})
    assert claim.status_code == 201, claim.text
    after = snapshot(engine)
    assert after['balances'] == before['balances'] and after['transactions'] == before['transactions']
    assert after['requests'] == before['requests'] + 1 and after['payments'] == before['payments']
    assert client.get('/api/payments/' + receipt['id']).json()['status'] == 'pending'
