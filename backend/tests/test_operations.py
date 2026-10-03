from uuid import uuid4

import pytest
from sqlalchemy import select, func, event
from sqlalchemy.exc import IntegrityError

from backend.db import make_sessions
from backend.models import AuditEvent, CardProfile, Product, Refund, RequestCase, Transaction
from backend.tests.test_api import setup, login, payload, PASSWORDS


def operation(**extra):
    return {"confirmed": True, "requestKey": str(uuid4()), **extra}


def make_refund(client, transaction="TX-1001"):
    case = client.post("/api/requests", json=payload(transactionId=transaction)).json()["id"]
    request = operation()
    response = client.post(f"/api/requests/{case}/refund", json=request)
    assert response.status_code == 200, response.text
    return case, request, response.json()


def approve_payload(**extra):
    return operation(password=PASSWORDS[1], decision="approve", note="Verificación de evidencia y titularidad.", **extra)


def test_block_ownership_confirmation_password_and_retry(setup, monkeypatch):
    app, engine = setup
    monkeypatch.setenv("CARD_PROVIDER", "local_fixture")
    customer, _ = login(app)
    other, _ = login(app, "mateo")
    admin, _ = login(app, "nora")
    body = operation(password=PASSWORDS[0])
    url = "/api/cards/card-01/block"
    assert other.post(url, json=body).status_code == 404
    assert admin.post(url, json=body).status_code == 403
    assert customer.post(url, json={**body, "confirmed": False}).status_code == 422
    assert customer.post(url, json={**body, "userId": "mateo"}).status_code == 422
    assert customer.post(url, json=body, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert customer.post(url, json={**body, "password": "wrong"}).status_code == 403
    assert customer.post(url, json=body).json()["status"] == "blocked"
    assert customer.post(url, json=body).status_code == 200
    card = customer.get("/api/cards").json()["cards"][0]
    assert card["status"] == "blocked" and not card["canReveal"] and not card["canBlock"]
    assert customer.post("/api/cards/card-01/reveal", json={"password": PASSWORDS[0]}).json()["error"] == "card_blocked"
    with make_sessions(engine)() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == "card_blocked")).all()
        assert len(events) == 1 and events[0].product_id == "card-01" and events[0].actor_id == "andrea"


def test_refund_requires_admin_and_credits_exact_owner_once(setup):
    app, engine = setup
    client, _ = login(app)
    other, _ = login(app, "mateo")
    admin, _ = login(app, "nora")
    before = client.get("/api/bootstrap").json()
    case, request, refund = make_refund(client)
    url = f"/api/requests/{case}/refund"
    assert refund["status"] == "pending" and refund["destinationLast4"] == "4821"
    assert client.get("/api/bootstrap").json()["products"] == before["products"]
    assert other.get(url).status_code == 404
    assert other.post(url, json=request).status_code == 404
    assert admin.post(url, json=request).status_code == 403
    assert client.get(f"/api/admin/requests/{case}/refund").status_code == 403
    assert client.post(url, json={**request, "amountMinor": 1}).status_code == 422
    assert client.post(url, json={**request, "accountId": "account-02"}).status_code == 422
    assert client.post(url, json=request).json()["id"] == refund["id"]
    decision_url = f"/api/admin/refunds/{refund['id']}/decision"
    decision = approve_payload()
    assert client.post(decision_url, json=decision).status_code == 403
    assert admin.post(decision_url, json=decision, headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert admin.post(decision_url, json={**decision, "confirmed": False}).status_code == 422
    assert admin.post(decision_url, json={**decision, "password": "bad"}).status_code == 403
    assert admin.post(decision_url, json={**decision, "destination": "account-02"}).status_code == 422
    response = admin.post(decision_url, json=decision)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert admin.post(decision_url, json=decision).json() == response.json()
    assert admin.post(decision_url, json={**decision, "decision": "reject"}).status_code == 409
    with make_sessions(engine)() as db:
        assert db.get(Product, "account-01").balance_minor == 1845000 + 28650
        assert db.get(Product, "account-02").balance_minor == 520000
        credits = db.scalars(select(Transaction).where(Transaction.category == "refund")).all()
        assert len(credits) == 1 and credits[0].user_id == "andrea" and credits[0].amount_minor == 28650
        assert credits[0].id == response.json()["creditTransactionId"]
        audits = db.scalars(select(AuditEvent).where(AuditEvent.action.like("refund_%"))).all()
        assert [(a.action, a.actor_id, a.user_id) for a in audits] == [("refund_requested", "andrea", "andrea"), ("refund_approved", "nora", "andrea")]


def test_rejected_refund_never_changes_money_or_can_be_approved_later(setup):
    app, engine = setup
    client, _ = login(app)
    admin, _ = login(app, "nora")
    _, _, refund = make_refund(client)
    decision = {**approve_payload(), "decision": "reject"}
    url = f"/api/admin/refunds/{refund['id']}/decision"
    assert admin.post(url, json=decision).json()["status"] == "rejected"
    assert admin.post(url, json=decision).status_code == 200
    assert admin.post(url, json=approve_payload()).status_code == 409
    with make_sessions(engine)() as db:
        assert db.get(Product, "account-01").balance_minor == 1845000
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category == "refund")) == 0


@pytest.mark.parametrize("transaction", ["TX-1004", "TX-1005", "TX-1006"])
def test_positive_pending_and_declined_transactions_cannot_be_refunded(setup, transaction):
    client, _ = login(setup[0])
    case = client.post("/api/requests", json=payload(transactionId=transaction)).json()["id"]
    url = f"/api/requests/{case}/refund"
    assert client.get(url).json()["eligible"] is False
    assert client.post(url, json=operation()).status_code == 409


def test_destination_and_original_revalidated_at_approval(setup):
    app, engine = setup
    client, _ = login(app)
    admin, _ = login(app, "nora")
    _, _, refund = make_refund(client)
    with make_sessions(engine)() as db:
        db.get(Transaction, "TX-1001").amount_minor = -100
        db.commit()
    response = admin.post(f"/api/admin/refunds/{refund['id']}/decision", json=approve_payload())
    assert response.status_code == 409 and response.json()["error"] == "refund_changed"
    with make_sessions(engine)() as db:
        assert db.get(Refund, refund["id"]).status == "pending"
        assert db.get(Product, "account-01").balance_minor == 1845000


def test_no_inferred_destination_and_foreign_owner_database_constraints(setup):
    app, engine = setup
    client, _ = login(app)
    with make_sessions(engine)() as db:
        card = db.get(CardProfile, "card-01")
        card.settlement_product_id = "account-02"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.get(CardProfile, "card-01").settlement_product_id = None
        db.commit()
    case = client.post("/api/requests", json=payload(transactionId="TX-1001")).json()["id"]
    assert client.post(f"/api/requests/{case}/refund", json=operation()).json()["error"] == "refund_destination_unavailable"


def test_refund_idempotency_keys_cannot_be_rebound(setup):
    app, engine = setup
    client, _ = login(app)
    admin, _ = login(app, "nora")
    _, first_key, first = make_refund(client)
    second_case, _, second = make_refund(client, "TX-1002")
    assert client.post(f"/api/requests/{second_case}/refund", json=first_key).status_code == 409
    decision = approve_payload()
    assert admin.post(f"/api/admin/refunds/{first['id']}/decision", json=decision).status_code == 200
    assert admin.post(f"/api/admin/refunds/{second['id']}/decision", json=decision).status_code == 409
    with make_sessions(engine)() as db:
        assert db.get(Refund, second["id"]).status == "pending"
        assert db.get(Product, "account-01").balance_minor == 1845000 + 28650


def test_query_case_cannot_activate_refund(setup):
    app, engine = setup
    client, _ = login(app)
    case = client.post("/api/requests", json=payload(transactionId="TX-1001")).json()["id"]
    with make_sessions(engine)() as db:
        db.get(RequestCase, case).catalog_service_id = "account-balance"
        db.commit()
    assert client.post(f"/api/requests/{case}/refund", json=operation()).json()["error"] == "refund_not_eligible"


def test_failed_audit_rolls_back_credit_balance_and_decision(setup):
    app, engine = setup
    client, _ = login(app)
    admin, _ = login(app, "nora")
    _, _, refund = make_refund(client)
    def fail_audit(_mapper, _connection, record):
        if record.action == "refund_approved":
            raise IntegrityError("verification audit failure", {}, Exception("verification"))
    event.listen(AuditEvent, "before_insert", fail_audit)
    try:
        assert admin.post(f"/api/admin/refunds/{refund['id']}/decision", json=approve_payload()).status_code == 409
    finally:
        event.remove(AuditEvent, "before_insert", fail_audit)
    with make_sessions(engine)() as db:
        assert db.get(Product, "account-01").balance_minor == 1845000
        assert db.get(Refund, refund["id"]).status == "pending"
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category == "refund")) == 0
