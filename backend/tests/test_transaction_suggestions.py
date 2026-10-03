import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.db import make_sessions
from backend.models import Transaction, Conversation, AuditEvent
from backend.transaction_suggestions import choose, confirmation, local_date


@pytest.fixture
def phone(setup):
    app, engine = setup
    with make_sessions(engine)() as db:
        for id, owner, product, day, amount in [
            ('TX-PHONE-OLD', 'andrea', 'account-01', 29, -19900),
            ('TX-PHONE-NEW', 'andrea', 'account-01', 30, -29900),
            ('TX-OTHER-OWNER', 'mateo', 'account-02', 30, -49900),
            ('TX-CREDIT', 'andrea', 'account-01', 30, 9900),
        ]:
            db.add(Transaction(id=id,user_id=owner,product_id=product,merchant='Empresa Telefónica',
                category='utilities',amount_minor=amount,currency='MXN',
                occurred_at=datetime(2026,9,day,18,tzinfo=timezone.utc),status='completed'))
        db.commit()
    return app, engine


@pytest.mark.parametrize('locale,text,yes',[
    ('es','no reconozco e lcobro del celualar','Sí, es este'),
    ('en','I do not recognize my phone charge','Yes, this one'),
    ('pt','Não reconheço a cobrança do celular','Sim, é esse'),
])
def test_suggestion_is_owned_audited_unbound_until_confirmed_and_never_sent_to_models(phone,models,locale,text,yes):
    app,engine=phone; client,_=login(app); calls,control=models; control['intent']='unrecognized-charge'
    before=client.get('/api/bootstrap').json()
    body=message(message=text,locale=locale)
    value=client.post('/api/assistant/flow',json=body).json(); cid=value['conversation']['id']
    assert value['flow']['suggestedTransaction']['id']=='TX-PHONE-NEW'
    assert '299.00' in value['text'] or '299,00' in value['text']
    assert ('09/30/2026' if locale=='en' else '30/09/2026') in value['text']
    assert 'TX-PHONE-NEW' in value['text'] and 'TX-OTHER-OWNER' not in json.dumps(value)
    assert value['conversation']['transactionId'] is None and not value['flow']['canRegister']
    assert value['flow']['verified_facts']==[]
    assert client.get('/api/conversations/'+cid+'/flow').json()['flow']==value['flow']
    assert client.post('/api/assistant/flow',json=body).json()==value
    assert len(calls)==3
    with make_sessions(engine)() as db:
        assert db.get(Conversation,cid).transaction_id is None
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.conversation_id==cid,AuditEvent.action=='tool_transactions'))==1
    result=client.post('/api/assistant/flow',json=message(message=yes,locale=locale,conversationId=cid)).json()
    assert result['conversation']['transactionId']=='TX-PHONE-NEW'
    assert result['flow']['suggestedTransaction'] is None and result['flow']['canRegister']
    assert len(calls)==4  # Same contract; confirmation resumes context only.
    assert 'Empresa Telefónica' not in json.dumps(calls,ensure_ascii=False)
    assert 'TX-PHONE-NEW' not in json.dumps(calls) and '299.00' not in json.dumps(calls)
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'): assert after[key]==before[key]
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.conversation_id==cid,AuditEvent.action=='chat_transaction_selected'))==1


def test_rejection_and_explicit_other_selection_preserve_ownership(phone,models):
    app,engine=phone; client,_=login(app); other,_=login(app,'mateo'); calls,control=models;control['intent']='unrecognized-charge'
    value=client.post('/api/assistant/flow',json=message(message='No reconozco el cobro del celular')).json();cid=value['conversation']['id']
    assert other.get('/api/conversations/'+cid+'/flow').status_code==404
    assert client.post('/api/assistant/flow',json=message(message='Sí',conversationId=cid,transactionId='TX-OTHER-OWNER')).status_code==404
    result=client.post('/api/assistant/flow',json=message(message='No, es otro',conversationId=cid)).json()
    assert result['conversation']['transactionId'] is None
    assert result['flow']['suggestedTransaction']['id']=='TX-PHONE-OLD'
    selected=client.post('/api/assistant/flow',json=message(message='Revisa el movimiento seleccionado',conversationId=cid,transactionId='TX-1002')).json()
    assert selected['conversation']['transactionId']=='TX-1002'
    assert client.post('/api/assistant/flow',json=message(message='Otro',conversationId=cid,transactionId='TX-PHONE-NEW')).status_code==409


def test_no_phone_match_or_failed_provider_does_not_invent_one(setup,models):
    app,_=setup;client,_=login(app);calls,control=models;control['intent']='unrecognized-charge'
    value=client.post('/api/assistant/flow',json=message(message='No reconozco el cargo del celular')).json()
    assert value['flow']['suggestedTransaction'] is None
    assert not value['flow']['canRegister'] and value['conversation']['transactionId'] is None
    control['fail']=True
    result=client.post('/api/assistant/flow',json=message(message='No reconozco un cargo')).json()
    assert result['flow']['suggestedTransaction'] is None and result['flow']['state']=='provider_unavailable'


@pytest.mark.parametrize('text',['sí pero no es ese','no es ese','yes but another one','sim mas outro','si quiero bloquear mi tarjeta'])
def test_story_or_negation_is_not_affirmative_consent(text):
    assert confirmation(text)!='yes'


def test_reference_and_date_must_match_without_unrelated_fallback():
    rows=[{'id':'TX-1','merchant':'Empresa Telefónica','amountMinor':-29900,'date':'2026-09-30T18:00:00'},
          {'id':'TX-2','merchant':'Empresa Telefónica','amountMinor':-19900,'date':'2026-09-29T18:00:00'}]
    def pick(text,locale='es'): return choose(rows,[{'role':'user','content':text}],[],locale)
    assert pick('Fue el 29/09/2026')['id']=='TX-2'
    assert pick('On 09/29/2026','en')['id']=='TX-2'
    assert pick('El 2026-09-29')['id']=='TX-2'
    assert pick('Revisa TX-2')['id']=='TX-2'
    assert pick('Revisa TX-222') is None
    assert pick('Fue el 15/09/2026') is None
    assert choose(rows,[{'role':'user','content':'un cargo'}],['TX-1','TX-2']) is None


def test_date_uses_the_same_bank_timezone_as_the_transactions_screen():
    assert local_date('2026-10-03T02:54:00+00:00')=='2026-10-02'
    assert local_date('2026-10-03T02:54:00')=='2026-10-02'
