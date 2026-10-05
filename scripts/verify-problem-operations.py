"""Run inside local Compose API; creates marked persistent verification records.

Output contains a randomly generated verification login: redirect to a private
file under .local/verification, never to logs or Git. No existing balance changes.
"""
import hashlib
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from backend.db import make_engine, make_sessions
from backend.main import create_app
from backend.models import User, Product, CardProfile, Transaction, RequestCase, Refund, AuditEvent, now
from backend.security import hasher

if os.getenv("NEXQORI_LOCAL_VERIFY") != "1" or "@db:5432/nexqori" not in os.getenv("DATABASE_URL", ""):
    raise RuntimeError("Requires explicit local Compose verification environment")

engine = make_engine()
sessions = make_sessions(engine)
suffix = uuid4().hex[:12]
uid, account, card = (f"verify-{name}-{suffix}" for name in ("user", "account", "card"))
email = f"verify-{suffix}@nexqori.com"
password = secrets.token_urlsafe(28)


def untouched(db):
    records = db.execute(select(Product.id, Product.balance_minor).where(Product.user_id != uid).order_by(Product.id)).all()
    return hashlib.sha256(json.dumps([list(r) for r in records]).encode()).hexdigest()


with sessions() as db:
    before = untouched(db)
    db.add(User(id=uid, email=email, identity_number="V"+suffix, name="Verificación · operaciones "+suffix,
                password_hash=hasher.hash(password), role="customer", locale="es"))
    db.flush()
    db.add_all([Product(id=account, user_id=uid, type="account", last4="9012", balance_minor=10000),
                Product(id=card, user_id=uid, type="card", last4="9013", balance_minor=None)])
    db.flush()
    db.add(CardProfile(product_id=card, user_id=uid, provider_ref="verify-card-"+suffix,
                       expiry_month=12, expiry_year=2029, settlement_product_id=account))
    for index in range(1, 5):
        txid=f"verify-tx-{suffix}-{index}"
        db.add(Transaction(id=txid, user_id=uid, product_id=card, merchant=f"Verificación · comercio {index}",
                           category="shopping", amount_minor=-1001*index, currency="MXN", occurred_at=now(), status="completed"))
        db.flush()
        db.add(RequestCase(id=f"NQ-VERIFY-{suffix}-{index}", user_id=uid, transaction_id=txid,
                           request_key=str(uuid4()), service="cards", catalog_service_id="unrecognized-charge",
                           reason="unknown", details="Verificación persistente de revisión de cargo, sin datos reales.", status="in_review"))
    db.commit()

origin="http://testserver"
app=create_app(engine, [origin], False, login_limit=100)


def login(identifier, secret):
    client=TestClient(app)
    result=client.post('/api/auth/login', json={'identifier':identifier,'password':secret}, headers={'Origin':origin})
    assert result.status_code==200
    client.headers.update({'Origin':origin,'X-CSRF-Token':result.json()['csrfToken']})
    return client


client=login(email,password)
refunds=[]
for index in range(1,4):
    result=client.post(f'/api/requests/NQ-VERIFY-{suffix}-{index}/refund',json={'confirmed':True,'requestKey':str(uuid4())})
    assert result.status_code==200,result.text
    refunds.append(result.json()['id'])

admins=[login('00000002',os.environ['ADMIN_PASSWORD']) for _ in range(2)]
for index in range(1,4):
    # Fixtures are already in review; approval still must be explicit before credit.
    result=admins[0].post(f'/api/admin/requests/NQ-VERIFY-{suffix}-{index}/stage',json={
        'confirmed':True,'stage':'approved','note':'Verificación: evidencia ficticia revisada antes del abono.'})
    assert result.status_code==200,result.text


def race(ids, keys):
    barrier=Barrier(2)
    def perform(index):
        barrier.wait(timeout=15)
        result=admins[index].post('/api/admin/refunds/'+ids[index]+'/decision',json={
            'confirmed':True,'requestKey':keys[index],'decision':'approve',
            'password':os.environ['ADMIN_PASSWORD'],'note':'Verificación concurrente: evidencia ficticia revisada.'})
        assert result.status_code==200,result.text
        return result.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(perform,range(2)))


key=str(uuid4())
same=race([refunds[0],refunds[0]],[key,key])
assert same[0]['creditTransactionId']==same[1]['creditTransactionId']
race(refunds[1:3],[str(uuid4()),str(uuid4())])
with sessions() as db:
    assert db.get(Product,account).balance_minor==16006
    assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id==uid,Transaction.category=='refund'))==3
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.user_id==uid,AuditEvent.action=='refund_approved'))==3
    assert db.scalar(select(func.count()).select_from(Refund).where(Refund.user_id==uid,Refund.status=='approved'))==3
    assert untouched(db)==before

client.close()
for operator in admins: operator.close()
engine.dispose()
print(json.dumps({'email':email,'password':password,'userId':uid,'cardId':card,'accountId':account,
                  'uiCaseId':f'NQ-VERIFY-{suffix}-4','balanceBeforeUi':16006,'uiRefundAmount':4004,
                  'verification':{'same_refund_concurrent_once':True,'different_refunds_no_lost_balance':True,
                                  'three_credits_and_audit_events':True,'other_balances_unchanged':True}}))
