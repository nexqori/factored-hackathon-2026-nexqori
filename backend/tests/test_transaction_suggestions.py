import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.db import make_sessions
from backend.models import Transaction, Conversation, ConversationFlow, AuditEvent
from backend.transaction_suggestions import choose, confirmation, local_date, search_clues


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


def test_combines_partial_clues_and_does_not_use_plan_price_or_unrelated_completed_charge():
    rows=[{'id':'TX-INTERNET','merchant':'Internet Plus','amountMinor':-45900,'date':'2026-10-03T18:00:00','status':'completed'},
          {'id':'TX-PHONE','merchant':'Empresa Telefónica','amountMinor':-45900,'date':'2026-10-02T18:00:00','status':'declined'},
          {'id':'TX-OLD','merchant':'Empresa Telefónica','amountMinor':-29900,'date':'2026-10-01T18:00:00','status':'completed'}]
    history=[{'role':'user','content':'Quiero revisar una transacción fallida'},
             {'role':'user','content':'Es la última del teléfono, me cobraron 459 MXN y mi plan es 299 MXN'}]
    assert choose(rows,history,[])['id']=='TX-PHONE'
    assert choose(rows[:1],history,[]) is None
    assert search_clues([{'role':'user','content':'Me cobraron 2,700 MXN'}])['amountMinor']==270000
    assert search_clues([{'role':'user','content':'Me cobraron 2.700,50 MXN'}])['amountMinor']==270050
    assert search_clues([{'role':'user','content':'Esperaba 299 MXN'}]).get('amountMinor') is None
    assert choose(rows,history+[{'role':'user','content':'Es TX-OLD'}],[])['id']=='TX-OLD'


@pytest.mark.parametrize('locale,browse',[
    ('es','Puedes mostrarme las últimas transacciones para mostrarte cuál es'),
    ('en','Show my latest transactions so I can identify it'),
    ('pt','Pode mostrar minhas últimas movimentações para identificar qual é'),
])
def test_real_call_sequence_opens_movements_without_restarting_contract_or_using_a_question(phone,models,locale,browse):
    app,engine=phone;client,_=login(app);calls,control=models;control['intent']='payment-status'
    initial=client.post('/api/assistant/flow',json=message(message={'es':'Quiero revisar una transacción fallida','en':'I want to review a failed transaction','pt':'Quero revisar uma transação falha'}[locale],locale=locale)).json()
    cid=initial['conversation']['id']
    corrected=client.post('/api/assistant/flow',json=message(conversationId=cid,message={'es':'Es la última del cobro de teléfono','en':'It is my latest phone payment','pt':'É meu último pagamento de telefone'}[locale],locale=locale)).json()
    assert corrected['flow']['suggestedTransaction'] is None  # Fixture phone payments are completed.
    assert corrected['flow']['transactionSearch']['kind']=='no_match'
    assert corrected['navigation']['filters']['status']=='declined'
    with make_sessions(engine)() as db: old=db.get(ConversationFlow,cid).state
    count=len(calls);body=message(conversationId=cid,message=browse,locale=locale)
    shown=client.post('/api/assistant/flow',json=body).json()
    assert shown['navigation']['route']=='/movements' and shown['flow']['transactionSearch']['kind']=='browse'
    assert len(calls)==count
    assert shown['flow']['contract']==corrected['flow']['contract']
    assert shown['conversation']['transactionId'] is None
    assert client.post('/api/assistant/flow',json=body).json()==shown
    with make_sessions(engine)() as db:
        current=db.get(ConversationFlow,cid).state
        assert current['turn']==old['turn'] and current['next_node_id']==old['next_node_id']
        assert current['messages']==old['messages']
    # A reference read aloud after opening the list proposes a record; it does
    # not silently select it or authorize any banking action.
    proposed=client.post('/api/assistant/flow',json=message(conversationId=cid,message={'es':'Es TX-PHONE-NEW','en':'It is TX-PHONE-NEW','pt':'É TX-PHONE-NEW'}[locale],locale=locale)).json()
    assert proposed['flow']['suggestedTransaction']['id']=='TX-PHONE-NEW'
    assert proposed['navigation']['route']=='/movements?transaction=TX-PHONE-NEW'
    assert proposed['conversation']['transactionId'] is None


def test_repeated_browsing_preserves_evidence_indices_and_can_filter_without_spending_questions(phone,models):
    app,engine=phone;client,_=login(app);calls,control=models;control['intent']='payment-status'
    initial=client.post('/api/assistant/flow',json=message(message='Quiero revisar una transacción fallida')).json()
    cid=initial['conversation']['id']
    with make_sessions(engine)() as db: old=db.get(ConversationFlow,cid).state
    count=len(calls)
    for _ in range(16):
        result=client.post('/api/assistant/flow',json=message(conversationId=cid,message='Muéstrame los pagos de teléfono')).json()
        assert result['navigation']['filters']=={'q':'Empresa Telefónica'}
        assert result['flow']['transactionSearch']['count']==2
    assert len(calls)==count
    with make_sessions(engine)() as db:
        current=db.get(ConversationFlow,cid).state
        assert current['messages']==old['messages']
        assert current['context']['observations']==old['context']['observations']
        assert current['turn']==old['turn']
    resumed=client.post('/api/assistant/flow',json=message(conversationId=cid,message='Es TX-PHONE-NEW')).json()
    assert resumed['flow']['suggestedTransaction']['id']=='TX-PHONE-NEW'


def test_search_filters_before_limit_and_keeps_owner_and_audit(phone,models):
    app,engine=phone;client,_=login(app);_,control=models;control['intent']='unrecognized-charge'
    with make_sessions(engine)() as db:
        for i in range(25):
            db.add(Transaction(id=f'TX-NOISE-{i}',user_id='andrea',product_id='account-01',merchant='Comercio reciente',category='shopping',amount_minor=-99900,currency='MXN',occurred_at=datetime(2026,10,3,18,tzinfo=timezone.utc),status='completed'))
        db.commit()
    result=client.post('/api/assistant/flow',json=message(message='No reconozco el cobro de teléfono de 299 MXN')).json()
    assert result['flow']['suggestedTransaction']['id']=='TX-PHONE-NEW'
    assert 'TX-OTHER-OWNER' not in json.dumps(result)
    for extra in ({'owner':'mateo'},{'q':'Empresa','amountMinor':-1}):
        assert client.post('/api/assistant/tools/read',json={'intent':'account-activity','tool':'read-transactions','transactionSearch':extra}).status_code==422
    value=client.post('/api/assistant/tools/read',json={'intent':'account-activity','tool':'read-transactions','transactionSearch':{'q':'TX-OTHER-OWNER'}}).json()
    assert value['data']['transactions']==[] and value['executed_operations']==[]
    assert client.post('/api/assistant/tools/read',json={'intent':'account-activity','tool':'read-transactions','transactionSearch':{'q':'%'}}).json()['data']['transactions']==[]


@pytest.mark.parametrize('text', [
    'Sí, no reconozco ese cobro. ¿Puedes hacerme un reclamo?',
    'pasar Sí, no reconozco ese cobro. ¿Puedes hacerme un reclamo',
    'Sí es ese, prepara mi reclamo',
    'Yes, I do not recognize that charge. Please prepare a complaint.',
    'Sim, não reconheço essa cobrança. Pode preparar uma reclamação?',
])
def test_compound_selection_prepares_review_without_registering(phone, models, text):
    app, engine = phone; client, _ = login(app); calls, control = models
    control['intent'] = 'unrecognized-charge'
    locale = 'en' if text.startswith('Yes') else 'pt' if text.startswith('Sim') else 'es'
    first = client.post('/api/assistant/flow', json=message(locale=locale, message={'es':'No reconozco el cobro del celular','en':'I do not recognize my phone charge','pt':'Não reconheço a cobrança do celular'}[locale])).json()
    cid = first['conversation']['id']; before = client.get('/api/bootstrap').json()
    body = message(message=text, conversationId=cid, locale=locale)
    response = client.post('/api/assistant/flow', json=body)
    assert response.status_code == 200, response.text
    reply = response.json()
    assert reply['conversation']['transactionId'] == 'TX-PHONE-NEW'
    assert reply['flow']['suggestedTransaction'] is None
    assert reply['flow']['canRegister']
    assert reply['flow']['reviewRequestKey'] == body['requestKey']
    assert client.post('/api/assistant/flow', json=body).json() == reply
    preview = client.get('/api/conversations/'+cid+'/claim-preview').json()
    assert 'TX-PHONE-NEW' in preview['summary']
    assert client.get('/api/bootstrap').json()['requests'] == before['requests']
    assert 'TX-PHONE-NEW' not in json.dumps(calls)


@pytest.mark.parametrize('text', [
    'Sí, no reconozco ese cobro pero es otro movimiento',
    'Dije sí, no reconozco ese cobro, como ejemplo',
    'Sí, pero no estoy seguro; puedes hacerme un reclamo',
    'Yes but another one, prepare a complaint',
    'Sim, não é esse, prepare uma reclamação',
    'Quiero hacer un reclamo',
])
def test_ambiguous_compound_does_not_select(text):
    assert confirmation(text) != 'yes'
