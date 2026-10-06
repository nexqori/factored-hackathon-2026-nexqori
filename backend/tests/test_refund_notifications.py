from fastapi import HTTPException
import pytest
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import AuditEvent, NotificationPreference, Refund, Transaction, User
from backend.tests.test_api import setup, login
from backend.tests.test_operations import make_refund, approve_case, approve_payload
from backend.email_templates import refund_message


@pytest.mark.parametrize('failure', [False, True])
def test_mail_after_committed_credit_once_and_only_to_owner(setup, monkeypatch, failure):
    app, engine = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    sent = []
    with make_sessions(engine)() as db:
        db.add(NotificationPreference(user_id='andrea', email='owner-notifications@example.com'))
        db.commit()
    def deliver(recipient, subject, plain, html):
        with make_sessions(engine)() as db:
            credit = db.scalar(select(Transaction).where(Transaction.category == 'refund'))
            assert credit is not None and credit.status == 'completed'
            assert credit.id in plain and credit.id in html
        sent.append((recipient, subject, plain))
        if failure:
            raise HTTPException(503, 'mail_unavailable')
    monkeypatch.setattr('backend.notifications.send_email', deliver)
    case, _, refund = make_refund(customer)
    approve_case(admin, case)
    assert not sent
    body = approve_payload()
    url = f"/api/admin/refunds/{refund['id']}/decision"
    response = admin.post(url, json=body)
    assert response.status_code == 200 and response.json()['creditTransactionId']
    assert admin.post(url, json=body).json() == response.json()
    assert len(sent) == 1 and sent[0][0] == 'owner-notifications@example.com'
    assert case in sent[0][2] and 'MXN 286.50' in sent[0][2]
    with make_sessions(engine)() as db:
        assert db.get(Refund, refund['id']).status == 'approved'
        expected = 'notification_refund_failed' if failure else 'notification_refund_accepted'
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == expected)).all()
        assert len(events) == 1 and events[0].user_id == 'andrea'


def test_rejection_does_not_send_credit_receipt(setup, monkeypatch):
    app, _ = setup
    customer, _ = login(app)
    admin, _ = login(app, 'nora')
    monkeypatch.setattr('backend.notifications.send_email', lambda *args: pytest.fail('No credit to notify'))
    _, _, refund = make_refund(customer)
    body = {**approve_payload(), 'decision': 'reject'}
    assert admin.post(f"/api/admin/refunds/{refund['id']}/decision", json=body).status_code == 200


@pytest.mark.parametrize('locale', ['es', 'en', 'pt'])
def test_branded_refund_receipt_escapes_values(locale):
    subject, plain, html = refund_message(locale, 45900, 'MXN', '<case>', '<credit>', '9700')
    assert 'Nexqori' in subject and 'MXN 459.00' in plain
    assert '<case>' not in html and '&lt;case&gt;' in html
    assert '<credit>' not in html and '&lt;credit&gt;' in html
    assert '#9A4B32' in html and f'lang="{locale}"' in html
