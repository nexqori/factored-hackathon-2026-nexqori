from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import Product, Transaction, AuditEvent
from backend.spending_scenarios import ensure_spending_cases
from backend.ux_fixtures import ensure_pack, manifest_plan, other_records_hash
from backend.tests.test_ux_fixtures import manifest
from backend.tests.test_api import setup, login, ORIGIN
from backend.tests.test_workflow_chat import models, message
from backend.provider_updates import ProviderUpdates
from uuid import uuid4
import pytest
import json


def test_comparisons_are_scoped_read_only_and_require_customer(setup):
    app,engine=setup;pack=manifest()
    with make_sessions(engine)() as db:
        ensure_pack(db,pack);person=manifest_plan(pack)[0]
        before=other_records_hash(db,[person['userId']])
        first=ensure_spending_cases(db,person);db.commit()
        assert other_records_hash(db,[person['userId']])==before
        complete=other_records_hash(db,[])
        assert not ensure_spending_cases(db,person)['created'];db.commit()
        assert other_records_hash(db,[])==complete
        account=db.get(Product,person['accountId'])
        assert account.balance_minor==person['balanceMinor']+700000-570000-149500-45900
    client=TestClient(app)
    logged=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']})
    assert logged.status_code==200
    initial=client.get('/api/bootstrap').json()
    result=client.get('/api/movements/trends');assert result.status_code==200
    assert result.json()['nextOffset'] is None
    outliers=[r for r in result.json()['items'] if r['classification']=='unusual']
    assert {r['transactionId'] for r in outliers}==set(first['transactionIds'])
    expected=[(60000,'350.0','merchant-product'),(29900,'53.5','bill-reference')]
    for txid,(average,percent,basis) in zip(first['transactionIds'],expected):
        evidence=client.get('/api/movements/'+txid+'/trend').json()['comparison']
        assert evidence['count']==5 and evidence['averageMinor']==average
        assert evidence['differencePercent']==percent and evidence['basis']==basis
        assert evidence['unusualIncrease']
    assert client.get('/api/bootstrap').json()==initial
    other,_=login(app,'mateo')
    for txid in first['transactionIds']: assert other.get('/api/movements/'+txid+'/trend').status_code==404
    assert not any(r['transactionId'] in first['transactionIds'] for r in other.get('/api/movements/trends').json()['items'])
    admin,_=login(app,'nora');assert admin.get('/api/movements/trends').status_code==403
    assert TestClient(app).get('/api/movements/trends').status_code==401


def test_pagination_does_not_skip_equal_dates_or_analyze_future_pages(setup):
    app,engine=setup
    with make_sessions(engine)() as db:
        tx=db.get(Transaction,'TX-1002')
        for i in range(85):
            db.add(Transaction(id=f'PAGE-{i:03}',user_id=tx.user_id,product_id=tx.product_id,
                merchant='Distinct merchant '+str(i),category=tx.category,amount_minor=-100,currency='MXN',
                occurred_at=tx.occurred_at,status='completed'))
        db.commit();expected=set(db.scalars(select(Transaction.id).where(Transaction.user_id==tx.user_id,Transaction.amount_minor<0)))
    client,_=login(app);seen=[];offset=0
    while offset is not None:
        page=client.get('/api/movements/trends',params={'offset':offset}).json()
        assert len(page['items'])<=40
        seen.extend(row['transactionId'] for row in page['items']);offset=page['nextOffset']
    assert len(seen)==len(set(seen)) and set(seen)==expected


def test_fixture_refuses_existing_foreign_owner_and_partial_failure_is_atomic(setup):
    _,engine=setup;pack=manifest()
    with make_sessions(engine)() as db:
        ensure_pack(db,pack);db.commit();person=manifest_plan(pack)[0]
        original=other_records_hash(db,[])
        person['accountId']='account-foreign'
        import pytest
        with pytest.raises(ValueError): ensure_spending_cases(db,person)
        db.rollback();assert other_records_hash(db,[])==original


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_published_rate_is_context_not_a_decision_or_model_payload(setup,models,locale):
    app,engine=setup;pack=manifest();person=manifest_plan(pack)[0]
    reader=ProviderUpdates(enabled=True);reader.publish('increase')
    app.state.provider_updates=reader;app.state.sessions.configure(info={'provider_updates':reader})
    with make_sessions(engine)() as db:
        ensure_pack(db,pack);scenario=ensure_spending_cases(db,person);db.commit()
    client=TestClient(app);logged=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']})
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':logged.json()['csrfToken']})
    txid=scenario['transactionIds'][1]
    detail=client.get('/api/movements/'+txid+'/trend').json()['comparison']
    assert detail['providerNotice']['customerContractVerified'] is False
    assert detail['providerNotice']['observation']['priceMinor']==45900
    before=client.get('/api/bootstrap').json();calls,control=models;control['intent']='payment-status'
    response=client.post('/api/assistant/flow',json=message(transactionId=txid,locale=locale,message={'es':'Pagué mi teléfono y sigue pendiente','en':'I paid my phone bill and it is still pending','pt':'Paguei meu telefone e continua pendente'}[locale]))
    assert response.status_code==200,response.text
    value=response.json();assert value['flow']['canRegister']
    assert 'Teléfono Esencial' in value['text'] and '2026-10-01' in value['text']
    cid=value['conversation']['id']
    preview=client.get('/api/conversations/'+cid+'/claim-preview').json()
    assert len(preview['summary'])<=1000
    assert client.post('/api/conversations/'+cid+'/claim',json={'confirmed':True,'details':preview['summary'],'requestKey':str(uuid4())}).status_code==200
    after=client.get('/api/bootstrap').json()
    assert after['products']==before['products'] and after['transactions']==before['transactions']
    assert 'Teléfono Esencial' not in json.dumps(calls) and '45900' not in json.dumps(calls)


def test_exception_excludes_future_baseline_is_owned_confirmed_and_idempotent(setup):
    from datetime import timedelta
    from backend.models import SpendingException
    from backend.payment_history import compare_payments, comparison_text
    app,engine=setup;pack=manifest();person=manifest_plan(pack)[0]
    with make_sessions(engine)() as db:
        ensure_pack(db,pack);scenario=ensure_spending_cases(db,person);db.commit()
        target=db.get(Transaction,scenario['transactionIds'][0])
        later=Transaction(id='LATER-REGULAR',user_id=target.user_id,product_id=target.product_id,
            merchant=target.merchant,category=target.category,amount_minor=-60000,currency='MXN',
            occurred_at=target.occurred_at+timedelta(minutes=5),status='completed')
        db.add(later);db.commit()
        assert compare_payments(db,later)['averageMinor']==95000
    client=TestClient(app)
    auth=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']}).json()
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':auth['csrfToken']})
    txid=scenario['transactionIds'][0];path='/api/movements/'+txid+'/recognize-exception'
    initial=client.get('/api/bootstrap').json()
    assert client.post(path,json={'confirmed':False}).status_code==400
    assert client.post(path,json={'confirmed':'true'}).status_code==422
    other,_=login(app,'mateo');assert other.post(path,json={'confirmed':True}).status_code==404
    admin,_=login(app,'nora');assert admin.post(path,json={'confirmed':True}).status_code==403
    assert TestClient(app).post(path,json={'confirmed':True},headers={'Origin':ORIGIN}).status_code in (401,403)
    assert client.post('/api/movements/'+scenario['transactionIds'][1]+'/recognize-exception',json={'confirmed':True}).status_code==409
    result=client.post(path,json={'confirmed':True});assert result.status_code==200,result.text
    assert result.json()['classification']=='exceptional'
    assert result.json()['comparison']['recognizedException']
    assert not result.json()['comparison']['unusualIncrease']
    assert client.post(path,json={'confirmed':True}).json()==result.json()
    assert client.get('/api/movements/'+txid+'/trend').json()==result.json()
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'):assert after[key]==initial[key]
    with make_sessions(engine)() as db:
        following=compare_payments(db,db.get(Transaction,'LATER-REGULAR'))
        assert following['count']==5 and following['averageMinor']==60000
        assert following['minMinor']==58000 and following['maxMinor']==62000
        assert txid not in [r['transactionId'] for r in following['samples']]
        assert len(db.scalars(select(SpendingException).where(SpendingException.transaction_id==txid)).all())==1
        assert len(db.scalars(select(AuditEvent).where(AuditEvent.transaction_id==txid,AuditEvent.action=='spending_exception_confirmed')).all())==1
        for locale in ('es','en','pt'):
            assert comparison_text(result.json()['comparison'],locale)
