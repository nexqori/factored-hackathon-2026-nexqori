"""Own-account debits, recipient credits and retries through the real API."""
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.db import make_sessions
from backend.models import AuditEvent, BankTransfer, Product, RequestCase, Transaction, TransferQuote, User
from backend.tests.test_api import ORIGIN, login, setup


def lookup(client, reference='700000000000001103'):
    result = client.post('/api/transfers/recipient', json={'reference': reference})
    assert result.status_code == 200, result.text
    return result.json()


def transfer_body(quote, **overrides):
    return {'quoteId': quote['quoteId'], 'confirmed': True, 'accountId': 'account-01',
            'amountMinor': 12500, 'note': 'Pago compartido', 'requestKey': str(uuid4()), **overrides}


def snapshot(engine):
    with make_sessions(engine)() as db:
        return {'balances': list(db.execute(select(Product.id, Product.balance_minor).order_by(Product.id))),
                'transactions': list(db.execute(select(Transaction.id, Transaction.amount_minor).order_by(Transaction.id))),
                'transfers': db.scalar(select(func.count()).select_from(BankTransfer)),
                'requests': db.scalar(select(func.count()).select_from(RequestCase)),
                'audits': list(db.execute(select(AuditEvent.action, AuditEvent.transaction_id).where(
                    AuditEvent.action.in_(('transfer_sent', 'transfer_received'))).order_by(AuditEvent.id)))}


def test_confirmed_transfer_conserves_money_and_creates_owned_movement_for_each_person(setup):
    app, engine = setup; client, _ = login(app); recipient, _ = login(app, 'mateo')
    before = snapshot(engine)
    quote = lookup(client)
    assert quote['name'] == 'Mateo Silva' and quote['last4'] == '1103' and quote['currency'] == 'MXN'
    assert 590 <= quote['expiresAt'] - int(time.time()) <= 600
    assert snapshot(engine) == before
    body = transfer_body(quote)
    result = client.post('/api/transfers', json=body)
    assert result.status_code == 200, result.text
    receipt = result.json()
    assert receipt['amountMinor'] == 12500 and receipt['status'] == 'completed'
    assert receipt['senderName'] == 'Andrea Rivera' and receipt['recipientName'] == 'Mateo Silva'
    assert receipt['note'] == body['note']
    after = snapshot(engine)
    old, current = dict(before['balances']), dict(after['balances'])
    assert current['account-01'] == old['account-01'] - 12500
    assert current['account-02'] == old['account-02'] + 12500
    assert sum(v or 0 for v in current.values()) == sum(v or 0 for v in old.values())
    assert after['transfers'] == before['transfers'] + 1 and after['requests'] == before['requests']
    assert len(after['transactions']) == len(before['transactions']) + 2 and len(after['audits']) == 2
    assert client.post('/api/transfers', json=body).json() == receipt
    assert snapshot(engine) == after
    sent = client.get('/api/transfers/' + receipt['id']).json()
    received = recipient.get('/api/transfers/' + receipt['id']).json()
    assert sent['direction'] == 'sent' and received['direction'] == 'received'
    assert sent['transactionId'] != received['transactionId']
    for owner, view, amount in [(client, sent, -12500), (recipient, received, 12500)]:
        movements = owner.get('/api/bootstrap').json()['transactions']
        transaction = next(t for t in movements if t['id'] == view['transactionId'])
        assert transaction['amountMinor'] == amount and transaction['transferId'] == receipt['id']
        assert not any(t['id'] == (received if owner is client else sent)['transactionId'] for t in movements)
    with make_sessions(engine)() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action.in_(('transfer_sent', 'transfer_received')))).all()
        assert {(e.user_id, e.actor_id, e.action) for e in events} == {
            ('andrea', 'andrea', 'transfer_sent'), ('mateo', 'andrea', 'transfer_received')}


def test_recipient_lookup_is_exact_rejects_self_and_reveals_no_balance(setup):
    app, engine = setup; client, _ = login(app); before = snapshot(engine)
    for reference in ['700000000000004821', '700000000000007206', '799999999999999999']:
        response = client.post('/api/transfers/recipient', json={'reference': reference})
        assert response.status_code == 404 and response.json()['error'] == 'recipient_not_found'
    for reference in ['1103', '70000000000000110*', ' 700000000000001103', 'Mateo Silva']:
        assert client.post('/api/transfers/recipient', json={'reference': reference}).status_code == 422
    quote = lookup(client)
    assert set(quote) == {'quoteId', 'name', 'reference', 'last4', 'currency', 'expiresAt'}
    assert snapshot(engine) == before


@pytest.mark.parametrize('override', [
    {'confirmed': False}, {'amountMinor': 0}, {'amountMinor': -1}, {'amountMinor': 1.2},
    {'amountMinor': True}, {'amountMinor': '100'}, {'amountMinor': 100000001},
    {'note': 'x' * 141}, {'recipientId': 'andrea'}, {'userId': 'mateo'}, {'currency': 'USD'},
])
def test_transfer_rejects_untrusted_values_without_financial_effect(setup, override):
    app, engine = setup; client, _ = login(app); quote = lookup(client); before = snapshot(engine)
    response = client.post('/api/transfers', json=transfer_body(quote, **override))
    assert response.status_code == 422, response.text
    assert snapshot(engine) == before


def test_other_user_cannot_spend_quote_or_account_and_unrelated_user_cannot_read_receipt(setup):
    app, engine = setup; client, _ = login(app); other, _ = login(app, 'mateo')
    quote = lookup(client); before = snapshot(engine)
    assert other.post('/api/transfers', json=transfer_body(quote, accountId='account-02')).status_code == 404
    for account in ['account-02', 'card-01', 'missing']:
        result = client.post('/api/transfers', json=transfer_body(quote, accountId=account))
        assert result.status_code in (404, 422), result.text
    assert snapshot(engine) == before
    with make_sessions(engine)() as db:
        # A third customer uses the normal seeded customer's password only in this isolated database.
        db.add(User(id='third', email='third@nexqori.com', name='Third customer', role='customer',
                    password_hash=db.get(User, 'mateo').password_hash, locale='es'))
        db.commit()
    third = TestClient(app)
    from backend.tests.test_api import PASSWORDS
    result = third.post('/api/auth/login', json={'email': 'third@nexqori.com', 'password': PASSWORDS[2]}, headers={'Origin': ORIGIN})
    assert result.status_code == 200
    third.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': result.json()['csrfToken']})
    receipt = client.post('/api/transfers', json=transfer_body(quote)).json()
    assert third.get('/api/transfers/' + receipt['id']).status_code == 404
    assert third.post('/api/transfers', json=transfer_body(quote)).status_code == 404


def test_expired_quote_blocks_new_transfer_but_keeps_completed_retry(setup):
    app, engine = setup; client, _ = login(app); quote = lookup(client)
    with make_sessions(engine)() as db:
        db.get(TransferQuote, quote['quoteId']).expires_at = int(time.time()) - 1; db.commit()
    before = snapshot(engine)
    result = client.post('/api/transfers', json=transfer_body(quote))
    assert result.status_code == 409 and result.json()['error'] == 'recipient_expired'
    assert snapshot(engine) == before
    fresh = lookup(client); body = transfer_body(fresh)
    receipt = client.post('/api/transfers', json=body).json()
    with make_sessions(engine)() as db:
        db.get(TransferQuote, fresh['quoteId']).expires_at = int(time.time()) - 1; db.commit()
    completed = snapshot(engine)
    assert client.post('/api/transfers', json=body).json() == receipt
    assert snapshot(engine) == completed


def test_transfer_retry_with_changed_parameters_conflicts(setup):
    app, engine = setup; client, _ = login(app); quote = lookup(client); body = transfer_body(quote)
    assert client.post('/api/transfers', json=body).status_code == 200
    before = snapshot(engine)
    another_quote = lookup(client)
    for override in [{'amountMinor': 12501}, {'note': 'Different note'}, {'accountId': 'savings-01'}, {'quoteId': another_quote['quoteId']}]:
        result = client.post('/api/transfers', json={**body, **override})
        assert result.status_code == 409 and result.json()['error'] == 'conflict'
    assert snapshot(engine) == before


def test_insufficient_funds_and_changed_recipient_role_are_rechecked(setup):
    app, engine = setup; client, _ = login(app); quote = lookup(client)
    with make_sessions(engine)() as db:
        db.get(Product, 'account-01').balance_minor = 10; db.commit()
    before = snapshot(engine)
    result = client.post('/api/transfers', json=transfer_body(quote))
    assert result.status_code == 409 and result.json()['error'] == 'insufficient_funds'
    assert snapshot(engine) == before
    with make_sessions(engine)() as db:
        db.get(User, 'mateo').role = 'admin'; db.commit()
    result = client.post('/api/transfers', json=transfer_body(quote, amountMinor=1))
    assert result.status_code == 404
    assert snapshot(engine) == before


def test_transfer_and_recipient_require_customer_authentication_and_csrf(setup):
    app, _ = setup; client, _ = login(app); quote = lookup(client); admin, _ = login(app, 'nora')
    anonymous = TestClient(app, headers={'Origin': ORIGIN})
    for route, body in [('/api/transfers/recipient', {'reference': '700000000000001103'}),
                        ('/api/transfers', transfer_body(quote))]:
        assert anonymous.post(route, json=body).status_code == 401
        assert admin.post(route, json=body).status_code == 403
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/transfers/recipient', json={'reference': '700000000000001103'}).status_code == 403
    assert client.post('/api/transfers', json=transfer_body(quote)).status_code == 403
    assert anonymous.get('/api/transfers/unknown').status_code == 401
    assert admin.get('/api/transfers/unknown').status_code == 403


def test_failed_receiver_audit_rolls_back_both_balances_and_movements(setup):
    app, engine = setup; client, _ = login(app); quote = lookup(client)
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER reject_transfer_audit BEFORE INSERT ON audit_events "
                          "WHEN NEW.action = 'transfer_received' BEGIN SELECT RAISE(ABORT, 'verification rollback'); END"))
    before = snapshot(engine)
    with TestClient(app, raise_server_exceptions=False) as failing:
        failing.cookies.update(client.cookies); failing.headers.update(client.headers)
        response = failing.post('/api/transfers', json=transfer_body(quote))
    assert response.status_code == 500
    assert snapshot(engine) == before


def test_transfer_checks_recipient_account_type_again_and_can_send_exact_balance(setup):
    app, engine = setup; client, _ = login(app); quote = lookup(client)
    with make_sessions(engine)() as db:
        db.get(Product, 'account-02').type = 'card'
        db.commit()
    before = snapshot(engine)
    failed = client.post('/api/transfers', json=transfer_body(quote))
    assert failed.status_code == 422 and failed.json()['error'] == 'transfer_account'
    assert snapshot(engine) == before
    with make_sessions(engine)() as db:
        db.get(Product, 'account-02').type = 'account'
        db.get(Product, 'account-01').balance_minor = 12500
        db.commit()
    response = client.post('/api/transfers', json=transfer_body(quote))
    assert response.status_code == 200
    assert dict(snapshot(engine)['balances'])['account-01'] == 0
