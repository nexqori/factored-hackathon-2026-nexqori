"""Receipt lookup and confirmed local ledger payments against isolated SQLite."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.db import make_sessions
from backend.models import AuditEvent, BillPayment, PhoneBill, Product, RequestCase, Transaction
from backend.tests.test_api import ORIGIN, login, setup


def pay_payload(**overrides):
    return {'confirmed': True, 'accountId': 'account-01', 'requestKey': str(uuid4()),
            'mode': 'total', 'expectedOutstandingMinor': 45900, **overrides}


def lookup(client, service='internet-bill', reference='INT-4821001'):
    response = client.post('/api/service-bills/lookup', json={'serviceId': service, 'reference': reference})
    assert response.status_code == 200, response.text
    return response.json()['bills']


def snapshot(engine):
    with make_sessions(engine)() as db:
        return {
            'balances': list(db.execute(select(Product.id, Product.balance_minor).order_by(Product.id))),
            'transactions': list(db.execute(select(Transaction.id, Transaction.amount_minor).order_by(Transaction.id))),
            'payments': db.scalar(select(func.count()).select_from(BillPayment)),
            'requests': db.scalar(select(func.count()).select_from(RequestCase)),
            'audits': list(db.execute(select(AuditEvent.action, AuditEvent.transaction_id).where(
                AuditEvent.action.in_(('phone_bill_paid', 'service_bill_paid'))).order_by(AuditEvent.id))),
        }


def test_lookup_normalizes_exact_reference_scopes_owner_and_lists_multiple_periods(setup):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo')
    with make_sessions(engine)() as db:
        db.add(PhoneBill(id='internet-next', user_id='andrea', service_id='internet-bill', reference='INT-4821001',
                         period='2026-11', due_date='2026-11-20', amount_minor=46900, allow_partial=True))
        db.add(PhoneBill(id='foreign-reference', user_id='mateo', service_id='internet-bill', reference='INT-4821001',
                         period='2026-12', due_date='2026-12-20', amount_minor=10000))
        db.commit()
    before = snapshot(engine)
    bills = lookup(client, reference='  int-4821001  ')
    assert [b['period'] for b in bills] == ['2026-10', '2026-11']
    assert bills[0]['amountMinor'] == bills[0]['outstandingMinor'] == 45900
    assert bills[0]['paidMinor'] == 0 and bills[0]['allowPartial'] is True
    assert [b['id'] for b in lookup(other)] == ['foreign-reference']
    assert lookup(client, reference='INT-NOT-FOUND') == []
    assert lookup(client, service='tv-bill') == []
    assert lookup(client, service='phone-bill', reference='55 (0000) 0001')[0]['reference'] == '5500000001'
    assert snapshot(engine) == before
    references = client.get('/api/service-bills/references').json()['references']
    assert {'serviceId': 'internet-bill', 'reference': 'INT-4821001'} in references
    assert len(references) == len({(r['serviceId'], r['reference']) for r in references})
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'service_bills_consulted')) == 5


def test_partial_then_total_uses_remaining_due_and_preserves_receipts(setup):
    app, engine = setup; client, _ = login(app)
    bill = lookup(client)[0]; before = snapshot(engine)
    partial_body = pay_payload(mode='partial', amountMinor=10000)
    first = client.post(f"/api/service-bills/{bill['id']}/pay", json=partial_body)
    assert first.status_code == 200, first.text
    partial = first.json()
    assert partial['amountMinor'] == 10000 and partial['remainingMinor'] == 35900
    assert partial['billAmountMinor'] == 45900 and partial['reference'] == bill['reference']
    current = lookup(client)[0]
    assert (current['paidMinor'], current['outstandingMinor'], current['paymentId']) == (10000, 35900, None)
    stale = client.post(f"/api/service-bills/{bill['id']}/pay", json=pay_payload())
    assert stale.status_code == 409 and stale.json()['error'] == 'bill_changed'
    total_body = pay_payload(expectedOutstandingMinor=35900)
    second = client.post(f"/api/service-bills/{bill['id']}/pay", json=total_body)
    assert second.status_code == 200, second.text
    total = second.json()
    assert total['amountMinor'] == 35900 and total['remainingMinor'] == 0
    assert partial['id'] != total['id']
    assert client.get('/api/payments/' + partial['id']).json() == partial
    assert client.get('/api/payments/' + total['id']).json() == total
    assert client.post(f"/api/service-bills/{bill['id']}/pay", json=partial_body).json() == partial
    assert client.post(f"/api/service-bills/{bill['id']}/pay", json=total_body).json() == total
    duplicate = client.post(f"/api/service-bills/{bill['id']}/pay", json=pay_payload())
    assert duplicate.status_code == 409 and duplicate.json()['error'] == 'bill_already_paid'
    current = lookup(client)[0]
    assert (current['paidMinor'], current['outstandingMinor'], current['paymentId']) == (45900, 0, total['id'])
    after = snapshot(engine)
    assert dict(after['balances'])['account-01'] == dict(before['balances'])['account-01'] - 45900
    assert after['payments'] == before['payments'] + 2 and after['requests'] == before['requests']
    assert len(after['transactions']) == len(before['transactions']) + 2 and len(after['audits']) == 2
    movements = client.get('/api/bootstrap').json()['transactions']
    for receipt in [partial, total]:
        movement = next(t for t in movements if t['id'] == receipt['transactionId'])
        assert movement['amountMinor'] == -receipt['amountMinor'] and movement['paymentId'] == receipt['id']


def test_different_phone_lines_and_services_can_be_paid_after_first_receipt(setup):
    app, engine = setup; client, _ = login(app)
    before = snapshot(engine)
    receipts = []
    for service, reference in [('phone-bill', '5500000001'), ('phone-bill', '5500000002'),
                               ('tv-bill', 'TV-4821001'), ('utilities-bill', 'LUZ-4821001')]:
        bill = lookup(client, service, reference)[0]
        result = client.post(f"/api/service-bills/{bill['id']}/pay", json=pay_payload(expectedOutstandingMinor=bill['amountMinor']))
        assert result.status_code == 200, result.text
        receipts.append(result.json())
    after = snapshot(engine)
    assert len({r['id'] for r in receipts}) == 4
    assert dict(after['balances'])['account-01'] == dict(before['balances'])['account-01'] - sum(r['amountMinor'] for r in receipts)
    assert after['requests'] == before['requests']
    assert after['payments'] == before['payments'] + 4


@pytest.mark.parametrize('override', [
    {'confirmed': False}, {'amountMinor': 1}, {'mode': 'partial'},
    {'mode': 'partial', 'amountMinor': 0}, {'mode': 'partial', 'amountMinor': -1},
    {'mode': 'partial', 'amountMinor': 1.5}, {'mode': 'partial', 'amountMinor': True},
    {'mode': 'partial', 'amountMinor': '100'}, {'mode': 'partial', 'amountMinor': 100000001},
    {'expectedOutstandingMinor': True}, {'expectedOutstandingMinor': 0},
    {'provider': 'Another provider'}, {'userId': 'mateo'},
])
def test_payment_rejects_invalid_amounts_confirmation_and_untrusted_fields(setup, override):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    response = client.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload(**override))
    assert response.status_code == 422, response.text
    assert snapshot(engine) == before


@pytest.mark.parametrize('bill,override,error,status', [
    ('tv-andrea-2026-10', {'expectedOutstandingMinor': 24900, 'mode': 'partial', 'amountMinor': 100}, 'partial_not_allowed', 422),
    ('internet-andrea-2026-10', {'mode': 'partial', 'amountMinor': 45901}, 'payment_exceeds_bill', 422),
    ('internet-andrea-2026-10', {'expectedOutstandingMinor': 40000}, 'bill_changed', 409),
    ('internet-andrea-2026-10', {'accountId': 'account-02'}, 'not_found', 404),
    ('internet-andrea-2026-10', {'accountId': 'card-01'}, 'not_found', 404),
    ('missing', {}, 'not_found', 404),
])
def test_rejected_payments_are_atomic(setup, bill, override, error, status):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    response = client.post(f'/api/service-bills/{bill}/pay', json=pay_payload(**override))
    assert response.status_code == status and response.json()['error'] == error
    assert snapshot(engine) == before


def test_insufficient_funds_idempotency_conflict_and_foreign_receipt(setup):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo')
    with make_sessions(engine)() as db:
        db.get(Product, 'account-01').balance_minor = 20000; db.commit()
    before = snapshot(engine)
    failed = client.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload())
    assert failed.status_code == 409 and failed.json()['error'] == 'insufficient_funds'
    assert snapshot(engine) == before
    body = pay_payload(mode='partial', amountMinor=5000)
    receipt = client.post('/api/service-bills/internet-andrea-2026-10/pay', json=body).json()
    after = snapshot(engine)
    for changed in [{'amountMinor': 6000}, {'accountId': 'savings-01'}, {'expectedOutstandingMinor': 40900}]:
        assert client.post('/api/service-bills/internet-andrea-2026-10/pay', json={**body, **changed}).status_code == 409
    assert client.post('/api/service-bills/phone-family-2026-10/pay', json=body).status_code == 409
    assert other.get('/api/payments/' + receipt['id']).status_code == 404
    assert other.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload(accountId='account-02')).status_code == 404
    assert snapshot(engine) == after


def test_lookup_and_payment_enforce_authentication_role_and_csrf(setup):
    app, _ = setup; client, _ = login(app); admin, _ = login(app, 'nora')
    anonymous = TestClient(app, headers={'Origin': ORIGIN})
    for route, body in [('/api/service-bills/lookup', {'serviceId': 'internet-bill', 'reference': 'INT-4821001'}),
                        ('/api/service-bills/internet-andrea-2026-10/pay', pay_payload())]:
        assert anonymous.post(route, json=body).status_code == 401
        assert admin.post(route, json=body).status_code == 403
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/service-bills/lookup', json={'serviceId': 'internet-bill', 'reference': 'INT-4821001'}).status_code == 403
    assert client.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload()).status_code == 403
    assert anonymous.get('/api/service-bills/references').status_code == 401
    assert admin.get('/api/service-bills/references').status_code == 403


def test_legacy_phone_route_cannot_pay_another_service(setup):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    body = {'confirmed': True, 'accountId': 'account-01', 'requestKey': str(uuid4())}
    assert client.post('/api/phone-bills/internet-andrea-2026-10/pay', json=body).status_code == 404
    assert snapshot(engine) == before


def test_failed_audit_insert_rolls_back_debit_movement_and_receipt(setup):
    app, engine = setup; client, _ = login(app)
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER reject_payment_audit BEFORE INSERT ON audit_events "
                          "WHEN NEW.action = 'service_bill_paid' BEGIN SELECT RAISE(ABORT, 'verification rollback'); END"))
    before = snapshot(engine)
    # Suppress only the intentional server exception so the persisted DB can be inspected.
    with TestClient(app, raise_server_exceptions=False) as failing:
        failing.cookies.update(client.cookies); failing.headers.update(client.headers)
        response = failing.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload())
    assert response.status_code == 500
    assert snapshot(engine) == before


def test_emptying_exact_balance_and_currency_rejection(setup):
    app, engine = setup; client, _ = login(app)
    with make_sessions(engine)() as db:
        db.get(Product, 'savings-01').currency = 'USD'
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.get(Product, 'account-01').balance_minor = 45900
        db.commit()
    result = client.post('/api/service-bills/internet-andrea-2026-10/pay', json=pay_payload())
    assert result.status_code == 200
    assert dict(snapshot(engine)['balances'])['account-01'] == 0
