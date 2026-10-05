from datetime import date
import copy
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import ServiceAgreement, Transaction, PhoneBill, BillPayment
from backend.service_agreements import agreement_context
from backend.spending_scenarios import ensure_spending_cases
from backend.ux_fixtures import ensure_pack, manifest_plan, other_records_hash
from backend.tests.test_ux_fixtures import manifest
from backend.tests.test_api import setup, login, ORIGIN
from backend.tests.test_workflow_chat import models, message
from backend.provider_updates import ProviderUpdates


def prepared(engine):
    pack=manifest();person=manifest_plan(pack)[0]
    with make_sessions(engine)() as db:
        ensure_pack(db,pack);scenario=ensure_spending_cases(db,person);db.commit()
    return pack,person,scenario


def test_owner_reference_plan_period_currency_and_overlaps_are_required(setup):
    _,engine=setup;pack,person,scenario=prepared(engine)
    with make_sessions(engine)() as db:
        tx=db.get(Transaction,scenario['transactionIds'][1])
        terms=db.scalar(select(ServiceAgreement).where(ServiceAgreement.user_id==person['userId']))
        payment=db.scalar(select(BillPayment).where(BillPayment.transaction_id==tx.id))
        bill=db.get(PhoneBill,payment.bill_id)
        value=agreement_context(db,tx)
        assert value['status']=='above-base' and value['differenceMinor']==16000
        assert value['monthlyMinor']==29900 and value['paymentStatus']=='pending'
        for field,changed in [('user_id','mateo'),('reference','another-line'),('provider_id','another-provider'),('plan_id','another-plan'),('currency','USD')]:
            old=getattr(terms,field);setattr(terms,field,changed);db.flush()
            assert agreement_context(db,tx)['status']=='needs-review'
            setattr(terms,field,old);db.flush()
        old=terms.valid_from;year,month=map(int,bill.period.split('-'))
        terms.valid_from=date(year,month,2);db.flush()
        assert agreement_context(db,tx)['reason']=='partial-period'
        terms.valid_from=old;db.flush()
        duplicate=ServiceAgreement(**{c.name:getattr(terms,c.name) for c in ServiceAgreement.__table__.columns})
        duplicate.id='overlap';duplicate.version=2;db.add(duplicate);db.flush()
        assert agreement_context(db,tx)['reason']=='overlapping-conditions'
        db.delete(duplicate);db.flush()
        bill.period='2026-99';db.flush()
        assert agreement_context(db,tx)['reason']=='invalid-period'
        db.rollback()


def test_fixture_repeat_is_idempotent_and_conflicting_conditions_are_not_overwritten(setup):
    _,engine=setup;pack,person,scenario=prepared(engine)
    with make_sessions(engine)() as db:
        baseline=other_records_hash(db,[])
        ensure_spending_cases(db,person);db.commit()
        assert other_records_hash(db,[])==baseline
        assert len(db.scalars(select(ServiceAgreement)).all())==1
        terms=db.scalar(select(ServiceAgreement));terms.monthly_minor=39900;db.commit()
        with pytest.raises(ValueError,match='do not overwrite'):ensure_spending_cases(db,person)
        db.rollback();assert terms.monthly_minor==39900


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_conditions_reach_review_and_registered_claim_without_model_or_financial_effects(setup,models,locale,monkeypatch):
    app,engine=setup;pack,person,scenario=prepared(engine)
    reader=ProviderUpdates(enabled=True);reader.publish('increase')
    app.state.provider_updates=reader;app.state.sessions.configure(info={'provider_updates':reader})
    client=TestClient(app)
    logged=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']})
    assert logged.status_code==200
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':logged.json()['csrfToken']})
    txid=scenario['transactionIds'][1]
    before=client.get('/api/bootstrap').json()
    detail=client.get('/api/movements/'+txid+'/trend').json()['comparison']
    assert detail['serviceAgreement']['monthlyMinor']==29900
    assert detail['providerNotice']['observation']['priceMinor']==45900
    assert detail['serviceAgreement']['publicationChangesAgreement'] is False
    calls,control=models;control['intent']='incorrect-charge'
    from backend import workflow_chat as chat
    def extract(messages,language,fields,*args,**kwargs):
        calls.append(('llm',copy.deepcopy(messages)))
        observations=[{'field':'difference','value':'299 MXN','quote':'299 MXN','message_index':len(messages)-1}] if '299 MXN' in messages[-1]['content'] else []
        return {'status':'ok','observations':observations,'assessment':'consistent','latency_ms':1}
    monkeypatch.setattr(chat.editor,'extract',extract)
    response=client.post('/api/assistant/flow',json=message(transactionId=txid,locale=locale,message={'es':'Me cobraron de más en el teléfono, revisen el importe','en':'I was overcharged for my phone, please review the amount','pt':'Cobraram a mais no telefone, revisem o valor'}[locale]))
    assert response.status_code==200,response.text
    value=response.json();cid=value['conversation']['id']
    assert value['flow']['canRegister']
    assert 'difference' not in value['flow']['missing_fields']
    for amount in ('299','459','160'):assert amount in value['text']
    clarified=client.post('/api/assistant/flow',json=message(conversationId=cid,locale=locale,message={'es':'Mi plan es de 299 MXN. No acepté cargos adicionales.','en':'My plan costs 299 MXN. I did not accept extra charges.','pt':'Meu plano custa 299 MXN. Não aceitei cobranças adicionais.'}[locale]))
    assert clarified.status_code==200,clarified.text
    value=clarified.json()
    assert value['flow']['canRegister']
    assert [c[0] for c in calls]==['triage','jev','llm','llm']
    for amount in ('299','459','160'):assert amount in value['text']
    preview=client.get('/api/conversations/'+cid+'/claim-preview').json()
    assert len(preview['summary'])<=1000
    assert '160' in preview['summary']
    registered=client.post('/api/conversations/'+cid+'/claim',json={'confirmed':True,'details':preview['summary'],'requestKey':str(uuid4())})
    assert registered.status_code==200,registered.text
    after=client.get('/api/bootstrap').json()
    assert after['products']==before['products'] and after['transactions']==before['transactions']
    assert '160' in registered.json()['summary']
    for private in ('29900','45900','16000','Teléfono Esencial',txid):assert private not in json.dumps(calls)
    other,_=login(app,'mateo')
    assert other.get('/api/movements/'+txid+'/trend').status_code==404
    assert other.get('/api/conversations/'+cid+'/claim-preview').status_code==404
