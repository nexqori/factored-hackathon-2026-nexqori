"""Local Compose fixtures and independent post-UI database verification.

Called by nexqori-cases.mjs via stdin. Preparation stdout contains generated
passwords and must only be captured in ignored .local files. Never resets data.
"""
import base64
import hashlib
import json
import os
import secrets
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url

from backend.db import make_engine, make_sessions
from backend.models import (AuditEvent, CardProfile, Conversation, Message,
                            Product, Refund, RequestCase, Transaction, User, now)
from backend.security import hasher
from backend.models import PhoneBill, BillPayment
from backend.catalog import SERVICES

url = make_url(os.environ["DATABASE_URL"])
if (os.getenv("NEXQORI_LOCAL_VERIFY") != "1" or url.host != "db"
        or url.database != "nexqori" or url.get_backend_name() != "postgresql"):
    raise RuntimeError("Only the explicit local Nexqori Compose environment is supported")
payload = json.loads(base64.b64decode(os.environ["NEXQORI_CASES_INPUT"]))
engine = make_engine()
sessions = make_sessions(engine)


def untouched(db, exclude):
    """Exclude only this run's owners; financial and case rows must stay intact."""
    digest = hashlib.sha256()
    for model in (Product, CardProfile, Transaction, RequestCase, Refund, PhoneBill, BillPayment):
        table = model.__table__
        digest.update(table.name.encode())
        query = select(table).where(table.c.user_id.not_in(exclude)).order_by(*table.primary_key.columns)
        for row in db.execute(query).yield_per(1000):
            digest.update(json.dumps(list(row), default=str, sort_keys=True, ensure_ascii=True).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def prepare():
    languages = payload["languages"]
    assert languages and len(languages) == len(set(languages)) and set(languages) <= {"es", "en", "pt"}
    definitions = payload["definitions"]
    assert [d["id"] for d in definitions] == ["bloqueo", "devolucion", "derivacion"]
    run_id = uuid4().hex[:12]
    admin = {"userId": f"verify-admin-{run_id}", "email": f"verify-admin-{run_id}@nexqori.com",
             "password": secrets.token_urlsafe(24), "name": f"Verificación · admin {run_id}"}
    cases = []
    for locale in languages:
        for index, definition in enumerate(definitions, 1):
            suffix = f"{run_id}-{locale}-{index}"
            cases.append({**definition, "locale": locale,
                          "userId": f"verify-user-{suffix}", "email": f"verify-{suffix}@nexqori.com",
                          "password": secrets.token_urlsafe(24),
                          "name": f"Verificación · {definition['id']} {locale} {run_id}",
                          "accountId": f"verify-account-{suffix}", "cardId": f"verify-card-{suffix}",
                          "transactionId": f"verify-tx-{suffix}", "last4": f"910{index}"})
    owners = [admin["userId"], *(c["userId"] for c in cases)]
    with sessions() as db:
        before = untouched(db, owners)
        db.add(User(id=admin["userId"], email=admin["email"], name=admin["name"],
                    password_hash=hasher.hash(admin["password"]), role="admin", locale="es"))
        for index, case in enumerate(cases):
            db.add(User(id=case["userId"], email=case["email"], identity_number=f"V{run_id}{index:02d}",
                        name=case["name"], password_hash=hasher.hash(case["password"]),
                        role="customer", locale=case["locale"]))
            db.flush()
            if payload.get('phoneBills'):
                case['billId'] = 'verify-bill-' + case['userId'].removeprefix('verify-user-')
                db.add(PhoneBill(id=case['billId'], user_id=case['userId'], reference='550000000' + str(index + 1),
                                 period='2026-10', due_date='2026-10-15', amount_minor=29900, currency='MXN'))
            db.add_all([
                Product(id=case["accountId"], user_id=case["userId"], type="account", last4="9001",
                        balance_minor=case["initialBalanceMinor"], currency="MXN"),
                Product(id=case["cardId"], user_id=case["userId"], type="card", last4=case["last4"], balance_minor=None),
            ])
            db.flush()
            db.add(CardProfile(product_id=case["cardId"], user_id=case["userId"], provider_ref=case["cardId"],
                               expiry_month=12, expiry_year=now().year + 3, settlement_product_id=case["accountId"]))
            db.add(Transaction(id=case["transactionId"], user_id=case["userId"], product_id=case["cardId"],
                               merchant=SERVICES['phone-bill']['provider'] if payload.get('phoneCharge') and case['id']=='bloqueo' else "Verificación · " + case["id"], category="shopping", currency="MXN",
                               amount_minor=-case["amountMinor"], status=case["transactionStatus"], occurred_at=now()))
        db.commit()
        assert untouched(db, owners) == before, "Existing financial or case records changed during preparation"
    return {"schemaVersion": 1, "runId": run_id, "createdAt": now().isoformat(),
            "admin": admin, "cases": cases, "untouchedHash": before}


def verify():
    pack = payload["pack"]  # Passwords are deliberately omitted by the runner.
    owners = [pack["adminId"], *(c["userId"] for c in pack["cases"])]
    assert all(owner.startswith("verify-") for owner in owners)
    results = []
    with sessions() as db:
        assert untouched(db, owners) == pack["untouchedHash"], "Other financial or case records changed"
        for case in pack["cases"]:
            uid = case["userId"]
            account = db.get(Product, case["accountId"])
            card = db.get(CardProfile, case["cardId"])
            tx = db.get(Transaction, case["transactionId"])
            claims = db.scalars(select(RequestCase).where(RequestCase.user_id == uid)).all()
            refunds = db.scalars(select(Refund).where(Refund.user_id == uid)).all()
            credits = db.scalars(select(Transaction).where(Transaction.user_id == uid, Transaction.category == "refund")).all()
            events = db.scalars(select(AuditEvent).where(AuditEvent.user_id == uid)).all()
            conversations = db.scalars(select(Conversation).where(Conversation.user_id == uid)).all()
            messages = db.scalars(select(Message).where(Message.user_id == uid)).all()
            assert account.user_id == card.user_id == tx.user_id == uid
            assert tx.status == case["transactionStatus"] and tx.amount_minor == -case["amountMinor"]
            assert len(claims) == 1 and claims[0].transaction_id == tx.id and claims[0].catalog_service_id == case["intent"]
            claim = claims[0]

            def event(action, actor=uid):
                found = [e for e in events if e.action == action]
                assert len(found) == 1 and found[0].actor_id == actor, f"Invalid {action} audit for {case['id']}"
                return found[0]

            assert event("created").request_id == claim.id
            assert any(e.action == "login" and e.actor_id == uid for e in events)
            assert len(conversations) >= 2 and all(c.transaction_id == tx.id for c in conversations)
            assert len(messages) >= 4 and {m.role for m in messages} == {"user", "assistant"}
            assert all(m.locale == case["locale"] for m in messages)
            assert sum(e.action == "transaction_context_viewed" and e.transaction_id == tx.id for e in events) >= 2
            assert any(e.action == "conversation_viewed" and e.actor_id == pack["adminId"] for e in events)
            expected_balance = case["initialBalanceMinor"]
            if case["id"] == "bloqueo":
                assert card.status == "blocked" and card.blocked_at is not None
                assert event("card_blocked").product_id == card.product_id
                assert not refunds and not credits and claim.status == "received"
            elif case["id"] == "devolucion":
                assert card.status == "active" and claim.status == "in_review"
                assert len(refunds) == len(credits) == 1
                refund, credit = refunds[0], credits[0]
                assert refund.status == "approved" and refund.decided_by == pack["adminId"]
                assert refund.destination_product_id == account.id and refund.credit_transaction_id == credit.id
                assert refund.amount_minor == credit.amount_minor == case["amountMinor"]
                assert credit.product_id == account.id and credit.status == "completed"
                for action, actor in (("refund_requested", uid), ("reviewed", pack["adminId"]), ("refund_approved", pack["adminId"])):
                    assert event(action, actor).request_id == claim.id
                expected_balance += case["amountMinor"]
            else:
                assert card.status == "active" and claim.status == "handed_off"
                assert not refunds and not credits
                assert event("handed_off").request_id == claim.id
            assert account.balance_minor == expected_balance
            results.append({"case": case["id"], "locale": case["locale"], "requestId": claim.id,
                            "balanceMinor": expected_balance, "cardStatus": card.status,
                            "requestStatus": claim.status, "refundCount": len(refunds), "creditCount": len(credits),
                            "conversationCount": len(conversations), "messageCount": len(messages),
                            "auditEventIds": [e.id for e in events]})
    return {"otherFinancialAndCaseRecordsUnchanged": True, "cases": results}


try:
    if payload["mode"] == "prepare":
        result = prepare()
    elif payload["mode"] == "verify":
        result = verify()
    else:
        raise ValueError("Unknown mode")
    print(json.dumps(result, ensure_ascii=False))
finally:
    engine.dispose()
