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
from backend.models import PhoneBill, BillPayment, BankTransfer
from backend.catalog import SERVICES

url = make_url(os.environ["DATABASE_URL"])
if (os.getenv("NEXQORI_LOCAL_VERIFY") != "1" or url.host != "db"
        or url.database != "nexqori" or url.get_backend_name() != "postgresql"):
    raise RuntimeError("Only the explicit local Nexqori Compose environment is supported")
payload = json.loads(base64.b64decode(os.environ["NEXQORI_CASES_INPUT"]))
engine = make_engine()
sessions = make_sessions(engine)


def untouched(db, exclude, *, integrated=False):
    """Exclude only this run's owners; financial and case rows must stay intact."""
    digest = hashlib.sha256()
    models = (Product, CardProfile, Transaction, RequestCase, Refund, PhoneBill, BillPayment)
    for model in models + ((BankTransfer,) if integrated else ()):
        table = model.__table__
        digest.update(table.name.encode())
        query = select(table).where(table.c.user_id.not_in(exclude)).order_by(*table.primary_key.columns)
        for row in db.execute(query).yield_per(1000):
            digest.update(json.dumps(list(row), default=str, sort_keys=True, ensure_ascii=True).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def prepare_banking(db, case):
    """Opt-in receipts and a query checkpoint; never calls an external model."""
    from backend.workflow_chat import execution, editor
    from backend.models import ConversationFlow

    suffix = case['userId'].removeprefix('verify-user-')
    case['accountReference'] = '7' + str(secrets.randbelow(10**17)).zfill(17)
    phone = '55' + str(secrets.randbelow(10**8)).zfill(8)
    alternate = '55' + str((int(phone[2:]) + 1) % 10**8).zfill(8)
    definitions = [('phone', 'phone-bill', phone, 29900, False),
                   ('phone-family', 'phone-bill', alternate, 19900, True),
                   ('internet', 'internet-bill', f'INT-{suffix}', 45900, True),
                   ('tv', 'tv-bill', f'TV-{suffix}', 24900, False),
                   ('utilities', 'utilities-bill', f'LUZ-{suffix}', 52000, True)]
    case['bills'] = []
    for key, service, reference, amount, partial in definitions:
        bill = {'id': f'verify-{key}-{suffix}', 'serviceId': service,
                'reference': reference.upper(), 'amountMinor': amount,
                'allowPartial': partial, 'period': '2026-10'}
        case['bills'].append(bill)
        db.add(PhoneBill(id=bill['id'], user_id=case['userId'], service_id=service,
                         reference=bill['reference'], period=bill['period'], due_date='2026-10-20',
                         amount_minor=amount, allow_partial=partial, currency='MXN'))
    case['billId'] = case['bills'][0]['id']
    case['conversationId'] = str(uuid4())
    locale = case['locale']
    words = {'es': ('Verificación · documentos', 'Quiero un documento PDF.', 'Puedes preparar tu documento.'),
             'en': ('Verification · documents', 'I want a PDF document.', 'You can prepare your document.'),
             'pt': ('Verificação · documentos', 'Quero um documento PDF.', 'Você pode preparar seu documento.')}
    title, question, reply = words[locale]
    conversation = Conversation(id=case['conversationId'], user_id=case['userId'], title=title, locale=locale)
    db.add(conversation); db.flush()
    state = execution.create({'id': 'verification-query', 'revision': 1, 'graph': editor.template()},
                             [{'role': 'user', 'content': question}], locale, thread_id=conversation.id,
                             bank_binding={'owner_id': case['userId'], 'transaction_id': None, 'request_id': None},
                             persist=lambda _: None)
    state.update(phase='completed', next_node_id=None)
    state['context'].update(triage={'status': 'ok', 'family': 'query'},
                            jev={'status': 'ok', 'intent': 'documents'}, intent='documents',
                            state='information', reply=reply)
    db.add(ConversationFlow(conversation_id=conversation.id, user_id=case['userId'], state=state))
    for role, content in [('user', question), ('assistant', reply)]:
        db.add(Message(id=str(uuid4()), user_id=case['userId'], conversation_id=conversation.id,
                       role=role, content=content, locale=locale))


def prepare():
    integrated = payload.get('integratedBanking') is True
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
    beneficiary = None
    if integrated:
        beneficiary = {'userId': f'verify-beneficiary-{run_id}',
                       'email': f'verify-beneficiary-{run_id}@nexqori.com',
                       'password': secrets.token_urlsafe(24), 'name': f'Verificación · beneficiario {run_id}',
                       'accountId': f'verify-recipient-account-{run_id}',
                       'reference': '7' + str(secrets.randbelow(10**17)).zfill(17),
                       'initialBalanceMinor': 10000}
    owners = [admin["userId"], *(c["userId"] for c in cases), *([beneficiary['userId']] if beneficiary else [])]
    with sessions() as db:
        before = untouched(db, owners, integrated=integrated)
        db.add(User(id=admin["userId"], email=admin["email"], name=admin["name"],
                    password_hash=hasher.hash(admin["password"]), role="admin", locale="es"))
        for index, case in enumerate(cases):
            db.add(User(id=case["userId"], email=case["email"], identity_number=f"V{run_id}{index:02d}",
                        name=case["name"], password_hash=hasher.hash(case["password"]),
                        role="customer", locale=case["locale"]))
            db.flush()
            if integrated:
                prepare_banking(db, case)
            elif payload.get('phoneBills'):
                case['billId'] = 'verify-bill-' + case['userId'].removeprefix('verify-user-')
                db.add(PhoneBill(id=case['billId'], user_id=case['userId'], reference='550000000' + str(index + 1),
                                 period='2026-10', due_date='2026-10-15', amount_minor=29900, currency='MXN'))
            db.add_all([
                Product(id=case["accountId"], user_id=case["userId"], type="account", last4="9001",
                        balance_minor=case["initialBalanceMinor"], currency="MXN",
                        transfer_reference=case.get('accountReference')),
                Product(id=case["cardId"], user_id=case["userId"], type="card", last4=case["last4"], balance_minor=None),
            ])
            db.flush()
            db.add(CardProfile(product_id=case["cardId"], user_id=case["userId"], provider_ref=case["cardId"],
                               expiry_month=12, expiry_year=now().year + 3, settlement_product_id=case["accountId"]))
            db.add(Transaction(id=case["transactionId"], user_id=case["userId"], product_id=case["cardId"],
                               merchant=SERVICES['phone-bill']['provider'] if payload.get('phoneCharge') and case['id']=='bloqueo' else "Verificación · " + case["id"], category="shopping", currency="MXN",
                               amount_minor=-case["amountMinor"], status=case["transactionStatus"], occurred_at=now()))
        if beneficiary:
            db.add(User(id=beneficiary['userId'], email=beneficiary['email'], name=beneficiary['name'],
                        password_hash=hasher.hash(beneficiary['password']), role='customer', locale='es'))
            db.flush()
            db.add(Product(id=beneficiary['accountId'], user_id=beneficiary['userId'], type='account', last4='9002',
                           balance_minor=beneficiary['initialBalanceMinor'], currency='MXN',
                           transfer_reference=beneficiary['reference']))
        db.commit()
        assert untouched(db, owners, integrated=integrated) == before, "Existing financial or case records changed during preparation"
    return {"schemaVersion": 1, "runId": run_id, "createdAt": now().isoformat(),
            "admin": admin, "cases": cases, "untouchedHash": before,
            **({'integratedBanking': True, 'beneficiary': beneficiary} if beneficiary else {})}


def verify():
    pack = payload["pack"]  # Passwords are deliberately omitted by the runner.
    owners = [pack["adminId"], *(c["userId"] for c in pack["cases"]),
              *([pack['beneficiary']['userId']] if pack.get('integratedBanking') else [])]
    assert all(owner.startswith("verify-") for owner in owners)
    results = []
    with sessions() as db:
        assert untouched(db, owners, integrated=pack.get('integratedBanking', False)) == pack["untouchedHash"], "Other financial or case records changed"
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


def verify_banking():
    """Independent post-UI ledger and owner checks for the opt-in banking pack."""
    from backend.models import ChatDocument
    pack = payload['pack']
    assert pack.get('integratedBanking') is True
    beneficiary = pack['beneficiary']
    owners = [pack['adminId'], beneficiary['userId'], *(c['userId'] for c in pack['cases'])]
    assert all(owner.startswith('verify-') for owner in owners)
    result = []; transferred = 0
    with sessions() as db:
        assert untouched(db, owners, integrated=True) == pack['untouchedHash'], 'Other financial or case records changed'
        for case in pack['cases']:
            owner = case['userId']; amount = case['transferAmountMinor']; transferred += amount
            bills = db.scalars(select(PhoneBill).where(PhoneBill.user_id == owner)).all()
            payments = db.scalars(select(BillPayment).where(BillPayment.user_id == owner)).all()
            transfers = db.scalars(select(BankTransfer).where(BankTransfer.user_id == owner)).all()
            transactions = db.scalars(select(Transaction).where(Transaction.user_id == owner)).all()
            requests = db.scalars(select(RequestCase).where(RequestCase.user_id == owner)).all()
            docs = db.scalars(select(ChatDocument).where(ChatDocument.user_id == owner)).all()
            events = db.scalars(select(AuditEvent).where(AuditEvent.user_id == owner)).all()
            assert len(bills) == 5 and len(payments) == 6 and len(transfers) == 1
            assert not requests, 'Payments or transfers created an unrelated request'
            for bill in bills:
                records = [p for p in payments if p.bill_id == bill.id]
                assert sum(p.receipt['amountMinor'] for p in records) == bill.amount_minor
                assert len(records) == (2 if bill.service_id == 'internet-bill' else 1)
                for payment in records:
                    tx = next(t for t in transactions if t.id == payment.transaction_id)
                    assert tx.product_id == case['accountId'] and tx.amount_minor == -payment.receipt['amountMinor']
                    assert tx.status == 'completed' and payment.receipt['reference'] == bill.reference
                    assert payment.account_id == case['accountId']
            transfer = transfers[0]
            assert transfer.recipient_user_id == beneficiary['userId'] and transfer.recipient_product_id == beneficiary['accountId']
            assert transfer.source_product_id == case['accountId'] and transfer.amount_minor == amount
            debit, credit = db.get(Transaction, transfer.debit_transaction_id), db.get(Transaction, transfer.credit_transaction_id)
            assert debit.user_id == owner and credit.user_id == beneficiary['userId']
            assert debit.amount_minor == -amount and credit.amount_minor == amount
            assert debit.product_id == case['accountId'] and credit.product_id == beneficiary['accountId']
            assert len(transactions) == 8, 'Unexpected transaction or retry duplication'
            expected_balance = case['initialBalanceMinor'] - sum(b.amount_minor for b in bills) - amount
            assert db.get(Product, case['accountId']).balance_minor == expected_balance
            assert len(docs) == case['documentCount'] == 3
            assert {d.kind for d in docs} == {'statement', 'products_summary', 'requests_summary'}
            assert all(d.conversation_id == case['conversationId'] and d.content.startswith(b'%PDF-') for d in docs)
            assert all(db.get(Message, d.message_id).user_id == owner for d in docs)
            expected_actions = {'phone_bill_paid': 2, 'service_bill_paid': 4, 'transfer_sent': 1, 'document_generated': 3}
            for action, count in expected_actions.items():
                selected = [e for e in events if e.action == action]
                assert len(selected) == count and all(e.actor_id == owner for e in selected), action
            result.append({'userId': owner, 'balanceMinor': expected_balance, 'paymentCount': len(payments),
                           'transferId': transfer.id, 'documentCount': len(docs), 'requestCount': len(requests)})
        recipient = db.get(Product, beneficiary['accountId'])
        assert recipient.user_id == beneficiary['userId']
        assert recipient.balance_minor == beneficiary['initialBalanceMinor'] + transferred
        credits = db.scalars(select(Transaction).where(Transaction.user_id == beneficiary['userId'])).all()
        assert len(credits) == len(pack['cases']) and sum(t.amount_minor for t in credits) == transferred
    return {'otherFinancialAndCaseRecordsUnchanged': True, 'cases': result,
            'recipientCreditMinor': transferred, 'recipientBalanceMinor': beneficiary['initialBalanceMinor'] + transferred}


try:
    if payload["mode"] == "prepare":
        result = prepare()
    elif payload["mode"] == "verify":
        result = verify()
    elif payload['mode'] == 'verify_banking':
        result = verify_banking()
    else:
        raise ValueError("Unknown mode")
    print(json.dumps(result, ensure_ascii=False))
finally:
    engine.dispose()
