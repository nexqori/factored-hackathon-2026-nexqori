from uuid import uuid4
import pytest
from sqlalchemy import select, func
from backend.tests.test_api import setup, login
from backend.db import make_sessions
from backend.models import Product, PhoneBill, BillPayment, AuditEvent


def payload(**kw):
    return {'accountId':'account-01','requestKey':str(uuid4()),'confirmed':True,**kw}


def test_phone_payment_debits_once_receipt_survives_and_never_creates_request(setup):
    app,engine=setup; client,_=login(app)
    bill=client.get('/api/phone-bills').json()['bills'][0]
    legacy=client.post('/api/services/phone-bill/requests',json={'confirmed':True,'locale':'es','requestKey':str(uuid4()),'accountId':'account-01','reference':'5500000001','amountMinor':29900})
    assert legacy.status_code==409 and legacy.json()['error']=='use_bill_payment'
    assert bill['amountMinor']==29900 and not bill['paymentId']
    before=client.get('/api/bootstrap').json(); body=payload()
    result=client.post(f"/api/phone-bills/{bill['id']}/pay",json=body)
    assert result.status_code==200,result.text
    receipt=result.json()
    assert receipt['status']=='completed' and receipt['amountMinor']==29900
    assert client.post(f"/api/phone-bills/{bill['id']}/pay",json=body).json()==receipt
    assert client.post(f"/api/phone-bills/{bill['id']}/pay",json=payload()).json()==receipt
    after=client.get('/api/bootstrap').json()
    assert after['requests']==before['requests']
    assert len(after['transactions'])==len(before['transactions'])+1
    tx=next(t for t in after['transactions'] if t['id']==receipt['transactionId'])
    assert tx['amountMinor']==-29900 and tx['paymentId']==receipt['id']
    old=next(p['balanceMinor'] for p in before['products'] if p['id']=='account-01')
    assert next(p['balanceMinor'] for p in after['products'] if p['id']=='account-01')==old-29900
    assert client.get('/api/payments/'+receipt['id']).json()==receipt
    assert client.get('/api/phone-bills').json()['bills'][0]['paymentId']==receipt['id']
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='phone_bill_paid'))==1


@pytest.mark.parametrize('override,status',[({'confirmed':False},422),({'amountMinor':1},422),({'accountId':'account-02'},404),({'accountId':'card-01'},404)])
def test_payment_cannot_override_amount_confirmation_or_owner(setup,override,status):
    app,_=setup; client,_=login(app); before=client.get('/api/bootstrap').json()
    assert client.post('/api/phone-bills/phone-andrea-2026-10/pay',json=payload(**override)).status_code==status
    after=client.get('/api/bootstrap').json()
    assert after['products']==before['products'] and after['transactions']==before['transactions']


def test_insufficient_balance_no_partial_effects_and_scoped_reads(setup):
    app,engine=setup; client,_=login(app); other,_=login(app,'mateo'); admin,_=login(app,'nora')
    with make_sessions(engine)() as db:
        db.get(Product,'account-01').balance_minor=1;db.commit()
    assert client.post('/api/phone-bills/phone-andrea-2026-10/pay',json=payload()).json()=={'error':'insufficient_funds'}
    assert other.get('/api/phone-bills').json()=={'bills':[]}
    assert other.post('/api/phone-bills/phone-andrea-2026-10/pay',json=payload(accountId='account-02')).status_code==404
    assert admin.get('/api/phone-bills').status_code==403
    assert other.get('/api/payments/unknown').status_code==404
    with make_sessions(engine)() as db: assert db.scalar(select(func.count()).select_from(BillPayment))==0
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/phone-bills/phone-andrea-2026-10/pay',json=payload()).status_code==403


def test_key_cannot_pay_another_bill_and_receipt_is_private(setup):
    app,engine=setup; client,_=login(app); other,_=login(app,'mateo')
    with make_sessions(engine)() as db:
        db.add(PhoneBill(id='other-bill',user_id='andrea',reference='5500000001',period='2026-11',due_date='2026-11-15',amount_minor=29900));db.commit()
    body=payload(); receipt=client.post('/api/phone-bills/phone-andrea-2026-10/pay',json=body).json()
    assert client.post('/api/phone-bills/other-bill/pay',json=body).status_code==409
    assert client.post('/api/phone-bills/phone-andrea-2026-10/pay',json=payload(accountId='savings-01')).status_code==409
    assert other.get('/api/payments/'+receipt['id']).status_code==404
